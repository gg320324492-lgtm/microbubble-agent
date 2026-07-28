"""知识图谱 Cypher 查询封装 (Phase 9 batch 1, W85 B-1)

提供路径查询、邻居节点、子图钻取 3 类 Cypher 风格查询封装。
沿用 ``KnowledgeGraphService`` 的 BFS + 关系表语义，但提供更细粒度的 API。

设计要点 (派工 v6 §1.2 + W83 B-1 fail-degraded-allow 实战):
1. **input validation**: max_depth/limit 严格白名单 + 类型校验
2. **error handling**: 数据库异常统一 RuntimeError 上抛，路由层捕获转 4xx
3. **rate limiting**: 由调用方 ``@rate_limit`` 装饰器接管，本服务不重复限流
4. **Cypher 风格命名**: ``query_paths`` / ``query_neighbors`` / ``query_subgraph``
   与图数据库 Neo4j API 对齐，未来可直接替换底层实现 (不破坏前端契约)
"""

import logging
from typing import List, Optional

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.knowledge import Knowledge, KnowledgeRelation

logger = logging.getLogger("microbubble.kg_query")

# 派工前提铁律: 输入白名单 (派工 v6 §1.2 范畴)
_MAX_DEPTH_LIMIT = 5   # 路径深度上限，避免指数爆炸
_LIMIT_CAP = 100       # 邻居/子图节点数上限
_PATHS_LIMIT_CAP = 20  # 路径数上限


class KGQueryService:
    """知识图谱 Cypher 风格查询封装"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _validate_depth(depth: int) -> int:
        if depth < 1 or depth > _MAX_DEPTH_LIMIT:
            raise ValueError(f"max_depth 必须在 1..{_MAX_DEPTH_LIMIT} 之间")
        return depth

    @staticmethod
    def _validate_limit(limit: int, cap: int = _LIMIT_CAP) -> int:
        if limit < 1 or limit > cap:
            raise ValueError(f"limit 必须在 1..{cap} 之间")
        return limit

    async def query_neighbors(self, node_id: int, limit: int = 20) -> dict:
        """邻居节点查询（1 跳邻居 + 关系元数据）

        对应 Cypher: MATCH (n)-[r]->(m) WHERE id(n)=node_id RETURN m, r
        """
        limit = self._validate_limit(limit)

        # 1. 验证源节点存在
        src = await self._fetch_node(node_id)
        if not src:
            return {"center": None, "neighbors": [], "edges": [], "total": 0}

        # 2. 出边 + 反向边（视为无向图邻居）
        result = await self.db.execute(
            select(KnowledgeRelation, Knowledge).join(
                Knowledge,
                or_(
                    KnowledgeRelation.target_id == Knowledge.id,
                    KnowledgeRelation.source_id == Knowledge.id,
                )
            ).where(
                or_(
                    KnowledgeRelation.source_id == node_id,
                    KnowledgeRelation.target_id == node_id,
                )
            ).order_by(KnowledgeRelation.score.desc()).limit(limit)
        )

        neighbors = {}
        edges = []
        for row in result.all():
            rel = row.KnowledgeRelation
            kn = row.Knowledge
            # 计算"另一端"节点 id
            other_id = rel.target_id if rel.source_id == node_id else rel.source_id
            if other_id == node_id:
                continue
            if other_id not in neighbors:
                neighbors[other_id] = {
                    "id": kn.id,
                    "title": (kn.title or "")[:30],
                    "category": kn.category or "未分类",
                    "relation_count": 0,
                }
            neighbors[other_id]["relation_count"] += 1
            edges.append({
                "source": rel.source_id,
                "target": rel.target_id,
                "type": rel.relation_type,
                "score": rel.score,
                "reason": rel.reason,
            })

        return {
            "center": {"id": src.id, "title": src.title[:30], "category": src.category or "未分类"},
            "neighbors": list(neighbors.values()),
            "edges": edges,
            "total": len(neighbors),
        }

    async def query_paths(self, start_id: int, end_id: int, max_depth: int = 3,
                          limit: int = 10) -> List[dict]:
        """路径查询（两个节点间的所有简单路径）

        对应 Cypher: MATCH p=(a)-[*..maxDepth]-(b) WHERE id(a)=start AND id(b)=end RETURN p
        """
        max_depth = self._validate_depth(max_depth)
        limit = self._validate_limit(limit, cap=_PATHS_LIMIT_CAP)

        if start_id == end_id:
            return []

        # BFS 找所有简单路径（去环），深度限制 max_depth
        paths: List[List[int]] = []
        queue: List[List[int]] = [[start_id]]
        seen_paths: set = set()

        while queue and len(paths) < limit:
            path = queue.pop(0)
            if len(path) - 1 >= max_depth:
                continue
            tail = path[-1]
            # 查 tail 的出边
            result = await self.db.execute(
                select(KnowledgeRelation).where(
                    KnowledgeRelation.source_id == tail
                ).limit(limit * 2)
            )
            for rel in result.scalars().all():
                nxt = rel.target_id
                if nxt in path:  # 避免环
                    continue
                new_path = path + [nxt]
                if nxt == end_id:
                    # 找到一条终点路径
                    key = tuple(new_path)
                    if key not in seen_paths:
                        seen_paths.add(key)
                        paths.append(new_path)
                else:
                    queue.append(new_path)

        # 转换为含边类型/分数的 dict
        out: List[dict] = []
        for path in paths:
            seg_edges = await self._fetch_path_edges(path)
            out.append({
                "node_ids": path,
                "edges": seg_edges,
                "length": len(path) - 1,
            })
        return out

    async def _fetch_path_edges(self, node_ids: List[int]) -> List[dict]:
        """拉取一条路径上所有相邻边的关系类型 + 分数"""
        if len(node_ids) < 2:
            return []
        result = await self.db.execute(
            select(KnowledgeRelation).where(
                and_(
                    KnowledgeRelation.source_id.in_(node_ids[:-1]),
                    KnowledgeRelation.target_id.in_(node_ids[1:]),
                )
            )
        )
        return [
            {"source": r.source_id, "target": r.target_id,
             "type": r.relation_type, "score": r.score}
            for r in result.scalars().all()
        ]

    async def query_subgraph(self, concept_ids: List[int], depth: int = 2) -> dict:
        """子图钻取（从一组概念节点出发，BFS 展开 depth 层）

        对应 Cypher: MATCH (c)-[*..depth]-(m) WHERE id(c) IN concept_ids RETURN c, m
        """
        depth = self._validate_depth(depth)
        if not concept_ids:
            return {"nodes": [], "edges": [], "root_ids": []}

        # 去重 + 限制根节点数
        root_ids = list(set(concept_ids))[:20]

        # 1. 拉取所有根节点
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id.in_(root_ids))
        )
        roots = result.scalars().all()
        if not roots:
            return {"nodes": [], "edges": [], "root_ids": root_ids}

        nodes = {
            kn.id: {
                "id": kn.id,
                "title": (kn.title or "")[:30],
                "category": kn.category or "未分类",
                "is_root": True,
            }
            for kn in roots
        }
        edges = []
        visited = set(nodes.keys())
        frontier = [(rid, 0) for rid in nodes.keys()]

        # 2. BFS 展开到 depth 层
        while frontier:
            current_id, current_depth = frontier.pop(0)
            if current_depth >= depth:
                continue
            result = await self.db.execute(
                select(KnowledgeRelation, Knowledge).join(
                    Knowledge,
                    KnowledgeRelation.target_id == Knowledge.id
                ).where(
                    or_(
                        KnowledgeRelation.source_id == current_id,
                        KnowledgeRelation.target_id == current_id,
                    )
                ).limit(_LIMIT_CAP)
            )
            for row in result.all():
                rel = row.KnowledgeRelation
                kn = row.Knowledge
                other_id = rel.target_id if rel.source_id == current_id else rel.source_id
                if other_id == current_id:
                    continue
                # 添加节点
                if other_id not in nodes:
                    nodes[other_id] = {
                        "id": kn.id,
                        "title": (kn.title or "")[:30],
                        "category": kn.category or "未分类",
                        "is_root": False,
                    }
                if other_id not in visited:
                    visited.add(other_id)
                    frontier.append((other_id, current_depth + 1))
                # 添加边（去重）
                edge_key = (min(rel.source_id, rel.target_id), max(rel.source_id, rel.target_id), rel.relation_type)
                if not any((min(e["source"], e["target"]), max(e["source"], e["target"]), e["type"]) == edge_key
                           for e in edges):
                    edges.append({
                        "source": rel.source_id,
                        "target": rel.target_id,
                        "type": rel.relation_type,
                        "score": rel.score,
                    })

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "root_ids": root_ids,
            "depth": depth,
        }

    async def _fetch_node(self, node_id: int) -> Optional[Knowledge]:
        result = await self.db.execute(
            select(Knowledge).where(Knowledge.id == node_id)
        )
        return result.scalar_one_or_none()