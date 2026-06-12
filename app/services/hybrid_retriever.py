"""混合检索器 — 向量 + BM25 并发检索 + 合并去重 + 重排序

流程：
1. 向量检索（pgvector 语义搜索）和 BM25 关键词检索并发执行
2. 合并结果，同一文档保留最高分
3. 分数归一化（不同检索方式的分数尺度不同）
4. Cross-encoder 重排序
"""

import asyncio
import logging
from typing import Dict, List, Optional

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
        """混合检索

        Args:
            query: 查询文本
            top_k: 最终返回条数
            category: 可选分类过滤
            enable_vector: 是否启用向量检索
            enable_bm25: 是否启用 BM25 检索
            enable_graph: 是否启用图谱检索
            enable_rerank: 是否启用重排序

        Returns:
            检索结果列表
        """
        # 候选集数量（重排序前多取一些）
        candidate_k = top_k * 3 if enable_rerank else top_k

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

        # 重排序
        if enable_rerank and len(normalized) > 1:
            from app.services.reranker_service import get_reranker_service
            reranker = get_reranker_service()
            reranked = reranker.rerank(query, normalized, top_k=top_k)
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

        stmt = select(Knowledge)
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


# 全局工厂
def get_hybrid_retriever(db: AsyncSession) -> HybridRetriever:
    """获取混合检索器实例"""
    return HybridRetriever(db)
