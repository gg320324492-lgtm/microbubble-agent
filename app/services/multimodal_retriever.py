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

from app.models.knowledge import Knowledge
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

        2026-09-01 WP5 重构:
        1. embedding 持久化 — knowledge_images.embedding (迁移 129) 有值直接用,
           NULL 才实时算并回填 (此前每次 query 全量重算, 图多了拖垮检索)
        2. 可见性硬边界 — join knowledge 加 kb + deleted_at IS NULL +
           team/public 过滤 (此前 private drive 文档 OCR 会漏出)

        Invalid inputs or embedding failures degrade to an empty fifth path
        without affecting text RAG.
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

        # embedding 分派: 已持久化的直接用, 缺失的批量算 + 回填
        missing_idx = [i for i, row in enumerate(candidates) if not row.get("embedding")]
        if missing_idx:
            texts = [str(candidates[i]["ocr_text"]) for i in missing_idx]
            computed = await generate_embeddings(texts, for_query=False)
            if computed and len(computed) == len(missing_idx):
                for i, emb in zip(missing_idx, computed):
                    if emb is not None:
                        candidates[i]["embedding"] = emb
                await self._persist_embeddings(
                    [(candidates[i]["image_id"], candidates[i]["embedding"]) for i in missing_idx if candidates[i].get("embedding")]
                )
            # 丢弃仍未取到 embedding 的候选
            candidates = [row for row in candidates if row.get("embedding")]
            if not candidates:
                return []

        ranked: List[dict] = []
        for row in candidates:
            similarity = self._cosine_similarity(query_embedding, row["embedding"])
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

    async def _persist_embeddings(self, pairs) -> None:
        """回填 knowledge_images.embedding (best-effort, 失败不阻塞检索)"""
        if not pairs:
            return
        try:
            from sqlalchemy import update

            from app.models.knowledge_multimodal import KnowledgeImage

            for image_id, emb in pairs:
                await self.db.execute(
                    update(KnowledgeImage)
                    .where(KnowledgeImage.id == image_id)
                    .values(embedding=emb)
                )
            await self.db.commit()
            logger.debug("多模态 embedding 回填: %d rows", len(pairs))
        except Exception as exc:
            logger.warning("多模态 embedding 回填失败 (best-effort): %s", exc)
            try:
                await self.db.rollback()
            except Exception:
                pass

    async def _load_candidates(self, ocr_status: str) -> List[Dict[str, Any]]:
        stmt = (
            select(
                KnowledgeImage.id.label("image_id"),
                KnowledgeImage.knowledge_id,
                KnowledgeImage.image_url,
                KnowledgeImage.ocr_text,
                KnowledgeImage.page_number,
                KnowledgeImage.embedding,
            )
            .join(Knowledge, Knowledge.id == KnowledgeImage.knowledge_id)
            .where(
                KnowledgeImage.ocr_status == ocr_status,
                KnowledgeImage.ocr_text.is_not(None),
                KnowledgeImage.ocr_text != "",
                # 可见性硬边界 (与 search_semantic 同款)
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
                Knowledge.visibility.in_(["team", "public"]),
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
                "embedding": row.embedding,
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
