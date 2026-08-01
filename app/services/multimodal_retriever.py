"""OCR-backed multimodal retrieval for the fifth hybrid RAG path.

W100-RAG-5 uses a text-to-text dual tower because ``knowledge_images`` has
no persisted image embedding column.  The query tower reuses the existing
Redis-backed query embedding cache; the candidate tower batches the OCR text
through the same embedding model.  OCR execution itself remains in the
multimodal extraction pipeline -- this retriever only consumes completed rows.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_multimodal import KnowledgeImage

logger = logging.getLogger("microbubble.multimodal_retriever")


class MultimodalRetriever:
    """Retrieve document images by semantic similarity to their OCR text."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_images(
        self,
        query: str,
        top_k: int = 5,
        ocr_status: str = "done",
    ) -> List[dict]:
        """Return the images whose completed OCR text best matches ``query``.

        Candidate embeddings are intentionally computed at query time because
        the Phase 7 image table has no embedding column.  Batch generation
        avoids one model invocation per image.  Invalid inputs or embedding
        failures degrade to an empty fifth path without affecting text RAG.
        """
        normalized_query = (query or "").strip()
        if not normalized_query or top_k <= 0:
            return []

        candidates = await self._load_candidates(ocr_status)
        if not candidates:
            return []

        from app.services.embedding_service import (
            generate_embeddings,
            get_or_compute_query_embedding,
        )

        query_embedding = await get_or_compute_query_embedding(normalized_query)
        if not query_embedding:
            return []

        texts = [str(row["ocr_text"]) for row in candidates]
        candidate_embeddings = await generate_embeddings(
            texts,
            for_query=False,
        )
        if not candidate_embeddings or len(candidate_embeddings) != len(candidates):
            return []

        ranked: List[dict] = []
        for row, candidate_embedding in zip(candidates, candidate_embeddings):
            similarity = self._cosine_similarity(query_embedding, candidate_embedding)
            if similarity is None:
                continue
            ranked.append(
                {
                    "id": row["knowledge_id"],
                    "image_id": row["image_id"],
                    "knowledge_id": row["knowledge_id"],
                    "image_url": row["image_url"],
                    "similarity": similarity,
                    "score": similarity,
                    "ocr_text": row["ocr_text"],
                    "page_number": row["page_number"],
                    "retrieval_method": "image",
                }
            )

        ranked.sort(key=lambda item: item["similarity"], reverse=True)
        return ranked[:top_k]

    async def _load_candidates(self, ocr_status: str) -> List[Dict[str, Any]]:
        stmt = (
            select(
                KnowledgeImage.id.label("image_id"),
                KnowledgeImage.knowledge_id,
                KnowledgeImage.image_url,
                KnowledgeImage.ocr_text,
                KnowledgeImage.page_number,
            )
            .where(
                KnowledgeImage.ocr_status == ocr_status,
                KnowledgeImage.ocr_text.is_not(None),
                KnowledgeImage.ocr_text != "",
            )
            .order_by(KnowledgeImage.id)
        )
        try:
            result = await self.db.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.warning("多模态候选查询失败: %s", exc)
            return []

        return [
            {
                "image_id": row.image_id,
                "knowledge_id": row.knowledge_id,
                "image_url": row.image_url,
                "ocr_text": row.ocr_text,
                "page_number": row.page_number,
            }
            for row in rows
        ]

    @staticmethod
    def _cosine_similarity(
        left: Sequence[float],
        right: Sequence[float],
    ) -> Optional[float]:
        if not left or not right or len(left) != len(right):
            return None
        dot = sum(float(a) * float(b) for a, b in zip(left, right))
        left_norm = math.sqrt(sum(float(value) ** 2 for value in left))
        right_norm = math.sqrt(sum(float(value) ** 2 for value in right))
        if left_norm == 0.0 or right_norm == 0.0:
            return None
        return round(dot / (left_norm * right_norm), 6)


__all__ = ["MultimodalRetriever"]
