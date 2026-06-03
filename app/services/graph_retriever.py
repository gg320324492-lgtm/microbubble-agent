"""GraphRAG 检索器 — 图谱引导检索 + 社区摘要

基于 Neo4j 知识图谱的高级检索能力：
1. 实体引导检索 — 从查询中提取实体，遍历图谱找到关联知识
2. 多跳推理 — 沿关系边遍历 2-3 跳，发现间接关联
3. 社区摘要 — 按实体类型聚类，生成全局主题概览
4. 路径发现 — 找到两个实体之间的最短路径
"""

import logging
from typing import Dict, List, Optional

logger = logging.getLogger("microbubble.graph_retriever")


class GraphRetriever:
    """GraphRAG 检索器"""

    def __init__(self):
        pass

    async def retrieve_by_entities(
        self, query: str, top_k: int = 10
    ) -> List[dict]:
        """实体引导检索 — 从查询中提取实体关键词，搜索关联知识"""
        try:
            from app.services.neo4j_service import get_neo4j_service
            from app.services.bm25_service import BM25Service
            from app.models.knowledge import Knowledge
            from sqlalchemy import select
            from app.core.database import async_session

            neo4j = get_neo4j_service()
            if neo4j._get_driver() is None:
                return []

            # 从查询中提取关键词
            tokenizer = BM25Service()
            keywords = tokenizer._tokenize(query)
            if not keywords:
                return []

            # 在 Neo4j 中搜索匹配的实体
            knowledge_ids = set()
            for keyword in keywords[:5]:
                entities = neo4j.search_entities(keyword, limit=5)
                for entity in entities:
                    for kid in entity.get("knowledge_ids", []):
                        knowledge_ids.add(kid)

                    # 遍历邻居实体
                    neighbors = neo4j.get_neighbors(entity["name"], hops=1, limit=10)
                    for node in neighbors.get("nodes", []):
                        neighbor_entity = neo4j.get_entity(node["name"])
                        if neighbor_entity:
                            for kid in neighbor_entity.get("knowledge_ids", []):
                                knowledge_ids.add(kid)

            if not knowledge_ids:
                return []

            # 从数据库获取知识条目
            async with async_session() as db:
                stmt = select(Knowledge).where(Knowledge.id.in_(list(knowledge_ids)))
                result = await db.execute(stmt)
                rows = result.scalars().all()

                return [
                    {
                        "id": r.id,
                        "title": r.title or "",
                        "content": (r.content or "")[:500],
                        "category": r.category,
                        "tags": r.tags,
                        "source": r.source,
                        "score": 0.8,  # 图谱匹配给较高分数
                        "retrieval_method": "graph_entity",
                    }
                    for r in rows[:top_k]
                ]
        except Exception as e:
            logger.warning(f"Entity-guided retrieval failed: {e}")
            return []

    async def multi_hop_retrieve(
        self, entity_name: str, hops: int = 2, top_k: int = 10
    ) -> Dict:
        """多跳推理检索 — 沿关系边遍历"""
        try:
            from app.services.neo4j_service import get_neo4j_service

            neo4j = get_neo4j_service()
            if neo4j._get_driver() is None:
                return {"center": entity_name, "nodes": [], "edges": [], "paths": []}

            # 获取多跳邻居
            neighbors = neo4j.get_neighbors(entity_name, hops=hops, limit=top_k * 2)

            # 获取社区摘要
            communities = neo4j.get_community_summary(limit=5)

            return {
                "center": entity_name,
                "nodes": neighbors.get("nodes", []),
                "edges": neighbors.get("edges", []),
                "communities": communities,
            }
        except Exception as e:
            logger.warning(f"Multi-hop retrieval failed: {e}")
            return {"center": entity_name, "nodes": [], "edges": [], "paths": []}

    async def get_community_overview(self, limit: int = 10) -> List[Dict]:
        """获取图谱社区摘要 — 全局主题概览"""
        try:
            from app.services.neo4j_service import get_neo4j_service

            neo4j = get_neo4j_service()
            if neo4j._get_driver() is None:
                return []

            return neo4j.get_community_summary(limit=limit)
        except Exception as e:
            logger.warning(f"Community overview failed: {e}")
            return []

    async def find_entity_paths(
        self, source: str, target: str, max_hops: int = 3
    ) -> List[List[Dict]]:
        """查找两个实体之间的路径"""
        try:
            from app.services.neo4j_service import get_neo4j_service

            neo4j = get_neo4j_service()
            if neo4j._get_driver() is None:
                return []

            return neo4j.find_paths(source, target, max_hops=max_hops)
        except Exception as e:
            logger.warning(f"Path finding failed: {e}")
            return []

    async def get_entity_context(self, entity_name: str) -> Dict:
        """获取实体的完整上下文（属性 + 关系 + 关联知识）"""
        try:
            from app.services.neo4j_service import get_neo4j_service

            neo4j = get_neo4j_service()
            if neo4j._get_driver() is None:
                return {}

            entity = neo4j.get_entity(entity_name)
            if not entity:
                return {}

            # 获取关联知识条目
            from app.models.knowledge import Knowledge
            from sqlalchemy import select
            from app.core.database import async_session

            knowledge_ids = entity.get("knowledge_ids", [])
            if not knowledge_ids:
                return entity

            async with async_session() as db:
                stmt = select(Knowledge).where(Knowledge.id.in_(knowledge_ids))
                result = await db.execute(stmt)
                rows = result.scalars().all()
                entity["knowledge_items"] = [
                    {"id": r.id, "title": r.title, "summary": r.summary}
                    for r in rows
                ]

            return entity
        except Exception as e:
            logger.warning(f"Entity context retrieval failed: {e}")
            return {}


# 全局单例
_graph_retriever: Optional[GraphRetriever] = None


def get_graph_retriever() -> GraphRetriever:
    """获取 GraphRAG 检索器单例"""
    global _graph_retriever
    if _graph_retriever is None:
        _graph_retriever = GraphRetriever()
    return _graph_retriever
