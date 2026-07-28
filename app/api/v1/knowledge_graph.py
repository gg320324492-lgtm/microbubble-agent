"""知识图谱查询 API (Phase 9 batch 1, W85 B-1)

3 个端点:
- GET /api/v1/knowledge-graph/paths?start=&end=&max_depth=
- GET /api/v1/knowledge-graph/neighbors?node=&limit=
- GET /api/v1/knowledge-graph/subgraph?concepts=&depth=

派工前提铁律 12 第 9 条: 0 production code 例外 1 已批 (Phase 9 启动 batch 1).
W82 B-1 P0 实战: 所有端点 ``Depends(get_current_user)`` 鉴权 + read tier 限流.
W83 B-1 fail-degraded-allow: rate_limit 故障不阻塞, 由中间件保障.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.kg_query_service import KGQueryService

logger = logging.getLogger("microbubble.kg_query_api")

router = APIRouter()


@router.get("/knowledge-graph/paths")
async def get_knowledge_graph_paths(
    start: int = Query(..., description="起始节点 id"),
    end: int = Query(..., description="终止节点 id"),
    max_depth: int = Query(3, description="最大路径深度 (1..5)"),
    limit: int = Query(10, description="最大返回路径数 (1..20)"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """路径查询: 返回 start→end 的所有简单路径（最多 max_depth 跳）"""
    svc = KGQueryService(db)
    try:
        paths = await svc.query_paths(start_id=start, end_id=end,
                                       max_depth=max_depth, limit=limit)
    except ValueError as e:
        return {"error": {"code": "INVALID_INPUT", "message": str(e)}, "paths": []}
    except Exception as e:
        logger.exception("路径查询异常: %s", e)
        return {"error": {"code": "QUERY_FAILED", "message": "路径查询失败"}, "paths": []}
    return {"paths": paths, "total": len(paths), "start": start, "end": end}


@router.get("/knowledge-graph/neighbors")
async def get_knowledge_graph_neighbors(
    node: int = Query(..., description="中心节点 id"),
    limit: int = Query(20, description="最大返回邻居数 (1..100)"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """邻居查询: 返回中心节点 1 跳邻居 + 关系元数据"""
    svc = KGQueryService(db)
    try:
        result = await svc.query_neighbors(node_id=node, limit=limit)
    except ValueError as e:
        return {"error": {"code": "INVALID_INPUT", "message": str(e)},
                "center": None, "neighbors": [], "edges": []}
    except Exception as e:
        logger.exception("邻居查询异常: %s", e)
        return {"error": {"code": "QUERY_FAILED", "message": "邻居查询失败"},
                "center": None, "neighbors": [], "edges": []}
    return result


@router.get("/knowledge-graph/subgraph")
async def get_knowledge_graph_subgraph(
    concepts: str = Query(..., description="概念节点 id 列表 (逗号分隔)"),
    depth: int = Query(2, description="钻取深度 (1..5)"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """子图钻取: 从一组概念节点出发，BFS 展开 depth 层"""
    try:
        concept_ids = [int(x.strip()) for x in concepts.split(",") if x.strip()]
    except ValueError:
        return {"error": {"code": "INVALID_INPUT", "message": "concepts 必须为逗号分隔的整数"},
                "nodes": [], "edges": []}

    svc = KGQueryService(db)
    try:
        result = await svc.query_subgraph(concept_ids=concept_ids, depth=depth)
    except ValueError as e:
        return {"error": {"code": "INVALID_INPUT", "message": str(e)},
                "nodes": [], "edges": []}
    except Exception as e:
        logger.exception("子图查询异常: %s", e)
        return {"error": {"code": "QUERY_FAILED", "message": "子图查询失败"},
                "nodes": [], "edges": []}
    return result