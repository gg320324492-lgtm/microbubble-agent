"""整页视觉转写召回 — PPT/文档「一页一图」的视觉转写文本进检索池 (2026-10-10 agent44)

## 定位

与 :mod:`app.services.multimodal_retriever`（第 5 路，``knowledge_images``
的 OCR 文本）同构的**文本双塔召回**，但候选来自迁移 144 新建的
``knowledge_page_transcripts``：一篇文档一页一条**整页**视觉转写。

两者刻意分开：``knowledge_images`` 的语义是「文档里抽出的某张图」，
``knowledge_page_transcripts`` 的语义是「整页幻灯片的视觉转写」。
混表会污染既有 5446 行的 figure 语义（见迁移 144 docstring）。

## 可见性边界（与第 5 路逐字同款，类 20.215「逐字段圈界」）

``deleted_at IS NULL`` + ``visibility IN ('team','public')`` + ``storage_mode
= 'kb'`` 三道一道不少。``storage_mode`` 这道**不需要放开** ——
本表的 ``knowledge_id`` 指向的是 ``drive_to_kb_service`` 建的 **kb 孪生行**，
孪生行本来就是 ``storage_mode='kb'``。这正是把落点选在孪生行而非 drive 行的
原因：既有第 5 路一行不改，既有 5446 行候选池零影响。

## blocked 行

``blocked = TRUE`` 的行只有 metadata、``content IS NULL``，由数据库 CHECK
约束保证，检索侧无需（也无法）把它们召回。

## 召回失败降级

与第 5 路一致：任何异常/空结果都降级为空结果，不影响文本四路。
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Knowledge
from app.models.knowledge_page_transcript import KnowledgePageTranscript
from app.services.multimodal_retriever import MultimodalRetriever

logger = logging.getLogger("microbubble.page_transcript_retriever")

#: 相似度下限 —— 低于此值的结果**丢弃**, 不进 top_k。
#:
#: 为什么需要 (agent44 实测): 整页转写是纯余弦扫描, 没有任何下限的话
#: ``zzqx_nonexistent_probe_8891`` 这种库里根本不存在的串也能拿到
#: **sim=0.517**, 比多数真探针还高 —— 即「任何 query 都会返回 top_k 条」。
#: 那样的 top_k 是噪声, 汇进 hybrid_retriever 会给随机文档加 image 式加权。
#:
#: 标定依据 (本页真探针 vs 反例探针实测, 见 scripts/a44_verify_probe_rank.py):
#:   真命中 (语义探针 top1/top2) 0.628 ~ 0.815
#:   库内不存在的反例          0.488 ~ 0.517
#: 取 0.55 落在两者之间, 留 ~0.08 余量防标定漂移。
MIN_SIMILARITY = float(os.getenv("PAGE_TRANSCRIPT_MIN_SIMILARITY", "0.55"))


class PageTranscriptRetriever:
    """按整页视觉转写文本做语义召回。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_pages(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[dict]:
        """返回转写文本与 ``query`` 最相似的整页。

        与 ``MultimodalRetriever.search_images`` 同款：embedding 已持久化，
        NULL 的（入库时 embedding 失败的少数页）实时算并回填，仍取不到就丢弃。
        """
        normalized_query = (query or "").strip()
        if not normalized_query or top_k <= 0:
            return []

        candidates = await self._load_candidates()
        if not candidates:
            return []

        from app.services.embedding_service import (
            generate_embeddings,
            get_or_compute_query_embedding,
        )

        query_embedding = await get_or_compute_query_embedding(normalized_query)
        if not query_embedding:
            return []

        missing_idx = [
            i for i, row in enumerate(candidates) if not row.get("embedding")
        ]
        if missing_idx:
            texts = [str(candidates[i]["content"]) for i in missing_idx]
            computed = await generate_embeddings(texts, for_query=False)
            if computed and len(computed) == len(missing_idx):
                for i, emb in zip(missing_idx, computed):
                    if emb is not None:
                        candidates[i]["embedding"] = emb
                await self._persist_embeddings(
                    [
                        (candidates[i]["id"], candidates[i]["embedding"])
                        for i in missing_idx
                        if candidates[i].get("embedding")
                    ]
                )
            candidates = [row for row in candidates if row.get("embedding")]
            if not candidates:
                return []

        ranked: List[dict] = []
        below_floor = 0
        for row in candidates:
            similarity = MultimodalRetriever._cosine_similarity(
                query_embedding, row["embedding"]
            )
            if similarity is None:
                continue
            if similarity < MIN_SIMILARITY:
                below_floor += 1
                continue
            ranked.append(
                {
                    # 与第 5 路一致: id 用 knowledge_id, 让 hybrid_retriever 的
                    # 按 knowledge 合并逻辑把页面命中折算到同一篇文档上
                    "id": row["knowledge_id"],
                    "knowledge_id": row["knowledge_id"],
                    "page_transcript_id": row["id"],
                    "page_number": row["page_number"],
                    "file_name": row["file_name"],
                    "content": row["content"],
                    "similarity": similarity,
                    "score": similarity,
                    "retrieval_method": "page_transcript",
                }
            )

        ranked.sort(key=lambda item: item["similarity"], reverse=True)
        if below_floor:
            logger.debug(
                "整页转写召回: %d 条低于下限 %.2f 已丢弃",
                below_floor, MIN_SIMILARITY,
            )
        return ranked[:top_k]

    async def _load_candidates(self) -> List[Dict[str, Any]]:
        stmt = (
            select(
                KnowledgePageTranscript.id,
                KnowledgePageTranscript.knowledge_id,
                KnowledgePageTranscript.page_number,
                KnowledgePageTranscript.content,
                KnowledgePageTranscript.file_name,
                KnowledgePageTranscript.embedding,
            )
            .join(Knowledge, Knowledge.id == KnowledgePageTranscript.knowledge_id)
            .where(
                # blocked 行 content IS NULL (CK 约束保证), 这里显式再挡一层
                KnowledgePageTranscript.blocked.is_(False),
                KnowledgePageTranscript.content.is_not(None),
                # ── 可见性硬边界 (与 multimodal_retriever 逐字同款) ──
                Knowledge.deleted_at.is_(None),
                Knowledge.storage_mode == "kb",
                Knowledge.visibility.in_(["team", "public"]),
            )
            .order_by(KnowledgePageTranscript.id)
        )
        try:
            result = await self.db.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.warning("整页转写候选查询失败: %s", exc)
            return []

        return [
            {
                "id": row.id,
                "knowledge_id": row.knowledge_id,
                "page_number": row.page_number,
                "content": row.content,
                "file_name": row.file_name,
                "embedding": row.embedding,
            }
            for row in rows
        ]

    async def _persist_embeddings(self, pairs: Sequence[tuple]) -> None:
        """回填 embedding (best-effort, 失败不阻塞检索)。"""
        if not pairs:
            return
        try:
            from sqlalchemy import update

            for row_id, emb in pairs:
                await self.db.execute(
                    update(KnowledgePageTranscript)
                    .where(KnowledgePageTranscript.id == row_id)
                    .values(embedding=emb)
                )
            await self.db.commit()
            logger.debug("整页转写 embedding 回填: %d rows", len(pairs))
        except Exception as exc:
            logger.warning("整页转写 embedding 回填失败 (best-effort): %s", exc)
            try:
                await self.db.rollback()
            except Exception:
                pass


__all__ = ["PageTranscriptRetriever"]
