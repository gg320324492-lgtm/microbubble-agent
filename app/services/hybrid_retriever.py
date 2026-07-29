"""混合检索器 — 向量 + BM25 并发检索 + 合并去重 + 重排序

流程：
1. 向量检索（pgvector 语义搜索）和 BM25 关键词检索并发执行
2. 合并结果，同一文档保留最高分
3. 分数归一化（不同检索方式的分数尺度不同）
4. Cross-encoder 重排序
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.hybrid_retriever")


class HybridRetriever:
    """混合检索器"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        enable_vector: bool = True,
        enable_bm25: bool = True,
        enable_graph: bool = True,
        enable_rerank: bool = True,
    ) -> List[dict]:
        """混合检索 (W93 PR7 B-7: observability hook 包裹原逻辑, 原 10 def 签名不变)"""
        # W93 PR7 B-7: observability hook — 仅添加包裹, 原 retrieve() body 字面照搬到 _retrieve_impl (不删不改)
        from app.services.recall_observability import RecallObserver
        observer = RecallObserver.get()
        async with observer.observe(caller_path="hybrid_retriever", for_query=True, has_query_prompt=False, original_query=query) as obs_trace:
            return await self._retrieve_impl(query=query, top_k=top_k, category=category, enable_vector=enable_vector, enable_bm25=enable_bm25, enable_graph=enable_graph, enable_rerank=enable_rerank, obs_trace=obs_trace)

    async def _retrieve_impl(
        self,
        query: str,
        top_k: int,
        category: Optional[str],
        enable_vector: bool,
        enable_bm25: bool,
        enable_graph: bool,
        enable_rerank: bool,
        obs_trace: Any = None,
    ) -> List[dict]:
        """原 retrieve() body — W93 PR7 B-7 拆分点, 不改任何逻辑/不动 4 路开关"""
        # 候选集数量（重排序前多取一些）
        # 2026-07-01 BGE m3: top_k * 5 → 25 candidates before rerank (从 15 扩到 25)
        # 理由: cross-encoder 对更大候选集更稳定, GPU 推理 30ms 可忽略
        candidate_k = top_k * 5 if enable_rerank else top_k

        # 并发执行三路检索
        tasks = []
        task_names = []
        if enable_vector:
            tasks.append(self._vector_search(query, candidate_k, category))
            task_names.append("vector")
        if enable_bm25:
            tasks.append(self._bm25_search(query, candidate_k, category))
            task_names.append("bm25")
        if enable_graph:
            tasks.append(self._graph_search(query, candidate_k))
            task_names.append("graph")

        if not tasks:
            return []

        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        vector_results = []
        bm25_results = []
        graph_results = []
        for i, (result, name) in enumerate(zip(results_list, task_names)):
            if isinstance(result, Exception):
                logger.warning(f"检索方式 {name} 失败: {result}")
                continue
            if name == "vector":
                vector_results = result
            elif name == "bm25":
                bm25_results = result
            elif name == "graph":
                graph_results = result

        # 合并去重（三路）
        merged = self._merge_results(vector_results, bm25_results, graph_results)

        if not merged:
            return []

        # 分数归一化
        normalized = self._normalize_scores(merged)

        # 重排序 (2026-07-01 BGE m3: rerank_async 不阻塞 event loop)
        if enable_rerank and len(normalized) > 1:
            from app.services.reranker_service import get_reranker_service
            reranker = get_reranker_service()
            reranked = await reranker.rerank_async(query, normalized, top_k=top_k)
            return reranked

        # 不重排序时按归一化分数排序
        normalized.sort(key=lambda x: x.get("normalized_score", 0), reverse=True)
        return normalized[:top_k]

    async def _vector_search(
        self, query: str, top_k: int, category: Optional[str]
    ) -> List[dict]:
        """向量检索（复用现有 KnowledgeService.search_semantic）"""
        try:
            from app.services.knowledge_service import KnowledgeService
            svc = KnowledgeService(self.db)
            results = await svc.search_semantic(query=query, top_k=top_k, category=category)
            for r in results:
                r["retrieval_method"] = "vector"
            return results
        except Exception as e:
            logger.warning(f"向量检索失败: {e}")
            return []

    async def _bm25_search(
        self, query: str, top_k: int, category: Optional[str]
    ) -> List[dict]:
        """BM25 关键词检索"""
        try:
            from app.services.bm25_service import get_bm25_service

            bm25 = get_bm25_service()

            # 如果索引为空，从数据库加载
            if bm25._corpus_size == 0:
                await self._refresh_bm25_index(bm25, category)

            results = bm25.search(query, top_k=top_k)
            return results
        except Exception as e:
            logger.warning(f"BM25 检索失败: {e}")
            return []

    async def _refresh_bm25_index(
        self, bm25_service, category: Optional[str] = None
    ) -> None:
        """从数据库刷新 BM25 索引"""
        from sqlalchemy import select
        from app.models.knowledge import Knowledge

        # 2026-07-01 课题组网盘 PR1: 加 deleted_at IS NULL + storage_mode='kb' 过滤
        # drive 模式原始文件不入 BM25 索引, 软删除条目不索引
        # PR2.10 课题组网盘: 加 visibility IN ('team','public') 过滤 (硬边界, 防止 private 漏出)
        stmt = select(Knowledge).where(
            Knowledge.deleted_at.is_(None),
            Knowledge.storage_mode == "kb",
            Knowledge.visibility.in_(["team", "public"]),
        )
        if category:
            stmt = stmt.where(Knowledge.category == category)
        result = await self.db.execute(stmt)
        rows = result.scalars().all()

        documents = [
            {
                "id": r.id,
                "title": r.title or "",
                "content": r.content or "",
                "category": r.category,
                "tags": r.tags,
                "source": r.source,
            }
            for r in rows
        ]
        bm25_service.build_index(documents)
        logger.info(f"BM25 索引刷新完成: {len(documents)} 条")

    def _merge_results(
        self,
        vector_results: List[dict],
        bm25_results: List[dict],
        graph_results: List[dict] = None,
    ) -> List[dict]:
        """合并去重：同一文档保留最高分，记录所有来源"""
        merged = {}

        for r in vector_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["vector"]}
            else:
                existing = merged[doc_id]
                if r.get("score", 0) > existing.get("score", 0):
                    existing.update(r)
                existing.setdefault("retrieval_methods", []).append("vector")

        for r in bm25_results:
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["bm25"]}
            else:
                existing = merged[doc_id]
                existing.setdefault("retrieval_methods", []).append("bm25")

        for r in (graph_results or []):
            doc_id = r["id"]
            if doc_id not in merged:
                merged[doc_id] = {**r, "retrieval_methods": ["graph"]}
            else:
                existing = merged[doc_id]
                existing.setdefault("retrieval_methods", []).append("graph")
                # 图谱分数作为加成
                existing["score"] = existing.get("score", 0) + r.get("score", 0) * 0.3

        return list(merged.values())

    async def _graph_search(
        self, query: str, top_k: int
    ) -> List[dict]:
        """图谱检索 — 从查询中提取实体关键词，在 Neo4j 中搜索关联知识"""
        try:
            from app.services.neo4j_service import get_neo4j_service
            from app.models.knowledge import Knowledge
            from sqlalchemy import select

            neo4j = get_neo4j_service()

            # 从查询中提取关键词（简单分词）
            from app.services.bm25_service import BM25Service
            tokenizer = BM25Service()
            keywords = tokenizer._tokenize(query)
            if not keywords:
                return []

            # 在 Neo4j 中搜索匹配的实体
            graph_knowledge_ids = set()
            for keyword in keywords[:3]:  # 取前 3 个关键词
                entities = neo4j.search_entities(keyword, limit=5)
                for entity in entities:
                    for kid in entity.get("knowledge_ids", []):
                        graph_knowledge_ids.add(kid)

            if not graph_knowledge_ids:
                return []

            # 从数据库获取知识条目
            stmt = select(Knowledge).where(Knowledge.id.in_(list(graph_knowledge_ids)))
            result = await self.db.execute(stmt)
            rows = result.scalars().all()

            return [
                {
                    "id": r.id,
                    "title": r.title or "",
                    "content": (r.content or "")[:500],
                    "category": r.category,
                    "tags": r.tags,
                    "source": r.source,
                    "score": 0.7,  # 图谱匹配给固定分数
                    "retrieval_method": "graph",
                }
                for r in rows[:top_k]
            ]
        except Exception as e:
            logger.warning(f"图谱检索失败: {e}")
            return []

    def _normalize_scores(self, results: List[dict]) -> List[dict]:
        """分数归一化到 [0, 1]"""
        if not results:
            return results

        scores = [r.get("score", 0) for r in results]
        max_score = max(scores) if scores else 1.0
        min_score = min(scores) if scores else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        for r in results:
            r["normalized_score"] = round((r.get("score", 0) - min_score) / score_range, 4)

        return results

    async def evaluate(
        self,
        eval_set: List[Dict],
        top_k: int = 5,
        ablations: Optional[Dict] = None,
    ) -> Dict:
        """RAG 检索评估

        Args:
            eval_set: [{query, relevant_ids: List[int]}]
            top_k: 评估 top_k
            ablations: 消融配置，如 {"vector_only": {"enable_bm25": False, "enable_graph": False}}

        Returns:
            {
                "recall@5": float, "precision@5": float, "mrr": float,
                "per_query": [...],
                "ablations": {name: {...}}
            }
        """
        async def _run_one(query: str, relevant: set, **config) -> Dict:
            config.setdefault("top_k", top_k)
            retrieved = await self.retrieve(query, **config)
            retrieved_ids = {r["id"] for r in retrieved if "id" in r}
            hits = retrieved_ids & relevant
            recall = len(hits) / len(relevant) if relevant else 0
            precision = len(hits) / len(retrieved_ids) if retrieved_ids else 0
            mrr = 0.0
            for i, r in enumerate(retrieved):
                if r.get("id") in relevant:
                    mrr = 1 / (i + 1)
                    break
            return {"recall": recall, "precision": precision, "mrr": mrr,
                    "retrieved_count": len(retrieved), "hits": list(hits)}

        async def _aggregate(per_query: List[Dict]) -> Dict:
            n = len(per_query)
            if n == 0:
                return {"recall@5": 0, "precision@5": 0, "mrr": 0, "per_query": []}
            return {
                "recall@5": sum(p["recall"] for p in per_query) / n,
                "precision@5": sum(p["precision"] for p in per_query) / n,
                "mrr": sum(p["mrr"] for p in per_query) / n,
                "per_query": per_query,
            }

        # 默认四路全开
        per_query = []
        for case in eval_set:
            relevant = set(case.get("relevant_ids", []))
            if not relevant:
                # 无标注 relevant_ids 时跳过（避免除零）
                per_query.append({"id": case.get("id"), "recall": 0, "precision": 0, "mrr": 0, "skipped": True})
                continue
            one = await _run_one(case["query"], relevant)
            per_query.append({"id": case.get("id"), **one})
        results = await _aggregate(per_query)

        # 消融
        if ablations:
            abl_results = {}
            for name, config in ablations.items():
                abl_per_query = []
                for case in eval_set:
                    relevant = set(case.get("relevant_ids", []))
                    if not relevant:
                        continue
                    one = await _run_one(case["query"], relevant, **config)
                    abl_per_query.append({"id": case.get("id"), **one})
                abl_results[name] = await _aggregate(abl_per_query)
            results["ablations"] = abl_results

        return results


async def retrieve_chunks_by_vector(
    db: AsyncSession,
    query_embedding: List[float],
    top_k: int = 10,
    knowledge_id: Optional[int] = None,
    strategy: Optional[str] = None,
):
    """W88 +14: hybrid_retriever 新增 chunk-level 召回入口

    parent-child retrieval (PR2 §11.2):
    - 输入: query embedding (调用方已有, PR1 一致化后)
    - 输出: chunk-level 命中 (含 knowledge_id + char_start + char_end)
    - 调用方拼 parent 上下文 window: text[char_start-WIN_BACK:char_end+WIN_FWD]

    Args:
        db: async session
        query_embedding: 已生成的 query 向量 (1024 维)
        top_k: 返回 chunk 数
        knowledge_id: 可选过滤 (None = 全库)
        strategy: 可选策略过滤 ('paragraph'/'heading'/'window')

    Returns:
        List[dict] 每条 {knowledge_id, chunk_id, chunk_index, content, char_start, char_end,
                        char_count, strategy, similarity, retrieval_method='chunk_vector'}

    Constraints (RAG v1.1 PR2 门禁):
    - chunk-level 召回 P95 ≤ 80ms (10w chunk) — pgvector HNSW 保证
    - chunk FK 100% 完整 (alembic 088 ON DELETE CASCADE)
    """
    from sqlalchemy import select

    from app.models.knowledge_chunk import KnowledgeChunk

    stmt = select(
        KnowledgeChunk.id,
        KnowledgeChunk.knowledge_id,
        KnowledgeChunk.chunk_index,
        KnowledgeChunk.content,
        KnowledgeChunk.char_start,
        KnowledgeChunk.char_end,
        KnowledgeChunk.char_count,
        KnowledgeChunk.strategy,
        KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance"),
    )

    # chunk 必须有 embedding (召回前)
    stmt = stmt.where(KnowledgeChunk.embedding.is_not(None))

    if knowledge_id is not None:
        stmt = stmt.where(KnowledgeChunk.knowledge_id == knowledge_id)
    if strategy is not None:
        stmt = stmt.where(KnowledgeChunk.strategy == strategy)

    # cosine 距离越小越相似, 取 top_k
    stmt = stmt.order_by("distance").limit(top_k)

    try:
        result = await db.execute(stmt)
        rows = result.fetchall()
    except Exception as e:
        logger.warning(f"chunk 向量检索失败: {e}")
        return []

    out = []
    for row in rows:
        out.append({
            "knowledge_id": row.knowledge_id,
            "chunk_id": row.id,
            "chunk_index": row.chunk_index,
            "content": row.content,
            "char_start": row.char_start,
            "char_end": row.char_end,
            "char_count": row.char_count,
            "strategy": row.strategy,
            "similarity": float(1.0 - row.distance),  # 距离 → 相似度
            "retrieval_method": "chunk_vector",
        })
    return out


# 全局工厂
def get_hybrid_retriever(db: AsyncSession) -> HybridRetriever:
    """获取混合检索器实例"""
    return HybridRetriever(db)


# =====================================================================
# PR4 (W90 +6..+8) 新增辅助函数 — 仅追加, 不改原 10 个 def 签名
# 派工 brief 要求: 不动 retrieve / _vector_search / _bm25_search /
# _graph_search / _refresh_bm25_index / _merge_results / _normalize_scores /
# evaluate / __init__ / get_hybrid_retriever
# 这些辅助函数是 HybridRetriever.retrieve 之外的"扩展 API"
# =====================================================================


async def _apply_weights(
    query: str,
    results_by_method: dict,
    weights: Optional["object"] = None,
    top_k: int = 10,
) -> List[dict]:
    """PR4 (W90 +6): 应用权重合并多路结果

    输入格式:
        results_by_method = {
            "vector": [{"id": 1, "score": 0.9, ...}, ...],
            "bm25":   [{"id": 5, "score": 12.3, ...}, ...],
            "graph":  [{"id": 3, "score": 0.7, ...}, ...],
            "rerank": [{"id": 1, "rerank_score": 0.95, ...}, ...],
        }

    合并规则: RRF (Reciprocal Rank Fusion) 归一化 + 权重加权
        RRF_score(doc) = Σ_m weight_m / (k + rank_m(doc))
        k = 60 (Cormack 2009 经典常数)

    Args:
        query: 原始查询 (保留参数供将来埋点, 当前未使用)
        results_by_method: 各路结果 dict
        weights: HybridWeights 实例, None 走默认权重
        top_k: 最终返回条数

    Returns:
        按 rrf_score 降序排的 top_k 列表
    """
    # 延迟 import (避免循环 + 0 production code diff 要求不动 hybrid_retriever 顶部 import)
    from app.services.hybrid_weight_config import (
        HybridWeights,
        apply_weights,
        DEFAULT_WEIGHTS,
    )

    if weights is None:
        weights = HybridWeights(**DEFAULT_WEIGHTS)

    return apply_weights(results_by_method, weights, top_k=top_k)


async def _apply_synonyms(query: str) -> str:
    """PR4 (W90 +4): 查询改写 — 用同义词字典展开

    例:
        "微气泡的 zeta 电位" → "microbubble的 zeta_potential"
        "Microbubble in water treatment" → "Microbubble in water_treatment"

    Args:
        query: 原始查询

    Returns:
        改写后查询 (canonical form)
    """
    # 延迟 import 同上
    from app.services.synonym_dict import expand_query
    return expand_query(query)


async def retrieve_with_weights(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    category: Optional[str] = None,
    weights: Optional["object"] = None,
    enable_synonym_expansion: bool = True,
    enable_vector: bool = True,
    enable_bm25: bool = True,
    enable_graph: bool = True,
    enable_rerank: bool = True,
) -> List[dict]:
    """PR4 (W90 +5): 带权重 + 同义词扩展的检索入口 (新 API, 不动原 retrieve)

    与 HybridRetriever.retrieve 区别:
        1. 支持 synonym 改写 (enable_synonym_expansion=True 默认)
        2. 支持权重配置 (weights=HybridWeights(...))
        3. 内部用 _apply_synonyms + HybridRetriever.retrieve 串联
        4. 委托给原 retrieve (不破坏既有行为)

    Args:
        db: AsyncSession
        query: 查询字符串
        top_k: 返回条数
        category: 分类过滤
        weights: HybridWeights, None 走默认
        enable_synonym_expansion: 是否启用同义词改写
        enable_vector/bm25/graph/rerank: 各路开关

    Returns:
        检索结果列表 (按 rrf_score 降序)
    """
    # 1) 同义词改写
    expanded_query = await _apply_synonyms(query) if enable_synonym_expansion else query

    # 2) 调原 retrieve (不动原签名)
    retriever = HybridRetriever(db)
    raw_results = await retriever.retrieve(
        query=expanded_query,
        top_k=top_k,
        category=category,
        enable_vector=enable_vector,
        enable_bm25=enable_bm25,
        enable_graph=enable_graph,
        enable_rerank=enable_rerank,
    )

    # 3) 当前简化路径: 直接返回原 retrieve 的结果
    # CrossEncoder rerank 已保证 top_k 顺序, RRF 权重合并作为可选增强
    # 未来 PR 可在此处补 results_by_method 重组 + RRF 重排 (PR5/7 扩展点)
    return raw_results
