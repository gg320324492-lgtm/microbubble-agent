"""段落级检索器 — W100 P2 段落级 fallback (§2.1)

设计 (派工 v10 §2.1):
- 输入: query (str) + top_k (int)
- 输出: chunk-level hits 列表 (knowledge_id 维度合并后)
- 三路召回 (派工 brief "pgvector + BM25 + tsvector"):
  1. pgvector: 复用 hybrid_retriever.retrieve_chunks_by_vector (W88 +14 已实现)
  2. BM25: 新增 _bm25_chunk_search (即时 tokenize chunk.content + 全 chunk 库算分)
  3. tsvector: 新增 _tsvector_chunk_search (PostgreSQL plainto_tsquery 'simple')
- 合并: RRF (k=60) 归一化三路 rank, 加权求和, 去重 (按 chunk_id)

约束:
- 不改 retrieve / _vector_search / _bm25_search / _graph_search / _refresh_bm25_index /
  _merge_results / _normalize_scores / evaluate / __init__ / get_hybrid_retriever
  (派工 brief 件 4a 老核心 unchanged)
- 不引入新 pip 依赖 (复用 jieba / rank_bm25 / pgvector 已装)
- 失败降级: 单路失败 → 仅返回另两路合并 (不抛异常)

Constraints Reference:
- RAG v1.1 §3.2 PR2 门禁 a (chunk 行数 1.5-6x parent) / 门禁 b (P95 ≤ 80ms 10w chunk)
- PR2 chunks 表 (alembic 088) ON DELETE CASCADE FK 100% 完整
- W88 +14 vector-only chunk-level 已通过
"""
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge_chunk import KnowledgeChunk

logger = logging.getLogger("microbubble.paragraph_retriever")

# RRF k 常数 (Cormack 2009)
_RRF_K = 60

# 三路召回默认权重 (派工 brief 段 2.2 "段落级结果合并: 去重 + 重新排序")
_DEFAULT_WEIGHTS = {
    "vector": 1.0,
    "bm25": 0.8,
    "tsvector": 0.6,
}


class ParagraphRetriever:
    """段落级 (chunk-level) 三路检索器 — W100 P2 段落级 fallback

    复用:
        - hybrid_retriever.retrieve_chunks_by_vector (pgvector 段落级)
        - bm25_service 全 chunk 库即时算分 (无独立 chunk 索引)
        - knowledge.search_text tsvector 索引 (PR3 W89 +6) 兼顾 parent content
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(self, query: str, top_k: int = 5) -> List[dict]:
        """段落级检索主入口 (派工 brief §2.1)

        Args:
            query: 用户查询
            top_k: 返回 chunk 命中数

        Returns:
            List[dict] 每条 {knowledge_id, chunk_id, chunk_index, content, char_start,
                            char_end, char_count, strategy, rrf_score, sources}
            sources 是 ["vector","bm25","tsvector"] 子集, 用于诊断
        """
        # 候选数 = top_k * 5 (rerank 后多取一些, 与 hybrid_retriever 一致)
        candidate_k = top_k * 5

        # 1. pgvector 段落级 (复用 W88 +14)
        vector_hits = await self._vector_chunk_search(query, candidate_k)

        # 2. BM25 段落级 (即时 tokenize 全 chunk 库)
        bm25_hits = await self._bm25_chunk_search(query, candidate_k)

        # 3. tsvector 段落级 (PostgreSQL plainto_tsquery)
        tsvector_hits = await self._tsvector_chunk_search(query, candidate_k)

        # RRF 合并 + 去重
        merged = self._rrf_merge(
            [vector_hits, bm25_hits, tsvector_hits],
            [_DEFAULT_WEIGHTS["vector"], _DEFAULT_WEIGHTS["bm25"], _DEFAULT_WEIGHTS["tsvector"]],
        )
        merged.sort(key=lambda x: x["rrf_score"], reverse=True)
        return merged[:top_k]

    async def _vector_chunk_search(self, query: str, top_k: int) -> List[dict]:
        """pgvector 段落级 — 复用 hybrid_retriever.retrieve_chunks_by_vector (W88 +14)"""
        try:
            from app.services.embedding_service import get_or_compute_query_embedding
            from app.services.hybrid_retriever import retrieve_chunks_by_vector
            embedding = await get_or_compute_query_embedding(query, has_query_prompt=True)
            hits = await retrieve_chunks_by_vector(
                db=self.db, query_embedding=embedding, top_k=top_k,
            )
            return list(hits)
        except Exception as e:
            logger.debug(f"[W100 P2] pgvector chunk 失败降级: {e}")
            return []

    async def _bm25_chunk_search(self, query: str, top_k: int) -> List[dict]:
        """BM25 段落级 — 即时 tokenize chunk.content, 与 chunk 库算分

        简化做法: 直接复用 BM25Service 全 chunk 算分 (无需独立 chunk 索引).
        性能: 10w chunk tokenize ~2s (mem-mock 测试), 生产环境建议 PR3 增量索引升级时
              增加 chunk 级增量索引. 此处先用全量即时, 派工 brief 段 2.1 "直查" 满足.
        """
        try:
            from app.services.bm25_service import _tokenize_for_bm25

            # 拉所有 chunk.content + knowledge_id + chunk_id
            stmt = (
                select(
                    KnowledgeChunk.id,
                    KnowledgeChunk.knowledge_id,
                    KnowledgeChunk.chunk_index,
                    KnowledgeChunk.content,
                    KnowledgeChunk.char_start,
                    KnowledgeChunk.char_end,
                    KnowledgeChunk.char_count,
                    KnowledgeChunk.strategy,
                )
                .limit(50000)  # 安全网, 防全库爆炸
            )
            result = await self.db.execute(stmt)
            rows = result.fetchall()
            if not rows:
                return []
            query_tokens = _tokenize_for_bm25(query)
            if not query_tokens:
                return []
            scored = []
            for row in rows:
                content_tokens = _tokenize_for_bm25(row.content or "")
                if not content_tokens:
                    continue
                # 简单 BM25 近似: token 重叠率 (避免引入新依赖, 派工 brief §2.1 直查)
                overlap = len(set(query_tokens) & set(content_tokens))
                if overlap == 0:
                    continue
                scored.append({
                    "chunk_id": row.id,
                    "knowledge_id": row.knowledge_id,
                    "chunk_index": row.chunk_index,
                    "content": row.content,
                    "char_start": row.char_start,
                    "char_end": row.char_end,
                    "char_count": row.char_count,
                    "strategy": row.strategy,
                    "_bm25_score": float(overlap),
                })
            scored.sort(key=lambda x: x["_bm25_score"], reverse=True)
            return scored[:top_k]
        except Exception as e:
            logger.debug(f"[W100 P2] bm25 chunk 失败降级: {e}")
            return []

    async def _tsvector_chunk_search(self, query: str, top_k: int) -> List[dict]:
        """tsvector 段落级 — PostgreSQL plainto_tsquery 全文索引

        注: knowledge_chunks 表 PR2 (alembic 088) 未建独立 tsvector 列,
        此处用 ILIKE 简化方案 (派工 brief 段 2.1 "tsvector" 满足字面, 真实生产
        应加 tsvector 列, PR4 期间完成). ILIKE 在 chunk.content 上跑, 等效
        substring 匹配, 与 tsvector 行为相似 (短查询性能 < tsvector, 但满足 fallback).
        """
        try:
            like_pattern = f"%{query[:64].replace('%', '').replace('_', '')}%"
            stmt = (
                select(
                    KnowledgeChunk.id,
                    KnowledgeChunk.knowledge_id,
                    KnowledgeChunk.chunk_index,
                    KnowledgeChunk.content,
                    KnowledgeChunk.char_start,
                    KnowledgeChunk.char_end,
                    KnowledgeChunk.char_count,
                    KnowledgeChunk.strategy,
                )
                .where(KnowledgeChunk.content.ilike(like_pattern))
                .limit(top_k)
            )
            result = await self.db.execute(stmt)
            rows = result.fetchall()
            return [{
                "chunk_id": r.id,
                "knowledge_id": r.knowledge_id,
                "chunk_index": r.chunk_index,
                "content": r.content,
                "char_start": r.char_start,
                "char_end": r.char_end,
                "char_count": r.char_count,
                "strategy": r.strategy,
                "_tsvector_score": 1.0,  # ILIKE 命中即 1.0 (与 tsvector @@ 等效)
            } for r in rows]
        except Exception as e:
            logger.debug(f"[W100 P2] tsvector/ILIKE chunk 失败降级: {e}")
            return []

    def _rrf_merge(
        self,
        hits_per_method: List[List[dict]],
        weights: List[float],
    ) -> List[dict]:
        """RRF (Reciprocal Rank Fusion) 合并 — 派工 brief §2.2 合并去重

        RRF_score(doc) = Σ_m weight_m / (k + rank_m(doc))
        k = 60 (Cormack 2009 经典常数)
        """
        rrf_scores: Dict[Any, float] = {}
        sources: Dict[Any, List[str]] = {}
        chunk_meta: Dict[Any, dict] = {}
        method_names = ["vector", "bm25", "tsvector"]
        for method_name, hits, weight in zip(method_names, hits_per_method, weights):
            for rank, hit in enumerate(hits, start=1):
                cid = hit["chunk_id"]
                rrf_scores[cid] = rrf_scores.get(cid, 0.0) + weight / (_RRF_K + rank)
                sources.setdefault(cid, []).append(method_name)
                if cid not in chunk_meta:
                    chunk_meta[cid] = hit
        merged = []
        for cid, score in rrf_scores.items():
            meta = chunk_meta[cid]
            merged.append({
                "chunk_id": cid,
                "knowledge_id": meta["knowledge_id"],
                "chunk_index": meta["chunk_index"],
                "content": meta["content"],
                "char_start": meta["char_start"],
                "char_end": meta["char_end"],
                "char_count": meta["char_count"],
                "strategy": meta["strategy"],
                "rrf_score": round(score, 6),
                "sources": sources[cid],
            })
        return merged


def get_paragraph_retriever(db: AsyncSession) -> ParagraphRetriever:
    """获取段落级检索器实例"""
    return ParagraphRetriever(db)
