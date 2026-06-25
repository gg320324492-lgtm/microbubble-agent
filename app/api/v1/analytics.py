"""检索质量监控埋点 API (v31)

3 个 endpoint:
  - POST /analytics/search-event  记录搜索事件 (query + top_ids), 返回 search_event_id
  - PATCH /analytics/search-event/{id}/click  记录点击 (clicked_id + click_position)
  - GET /analytics/stats?days=7  返回核心指标 (CTR / 零点击率 / 平均位置 / 按 model 分组)
  - GET /analytics/logs          返回最近 N 条搜索日志 (详细列表)

设计决策:
  - v31.2: POST/PATCH 加 Optional auth (登录用户绑 user_id, 匿名 NULL)
  - GET stats/logs 仍无需 auth (聚合数据 + 列表不含 PII)
  - embedding_model 从环境变量读 (EMBEDDING_MODEL_NAME), 零前端复杂度, 一致性最高
  - top_ids 用 PG ARRAY(Integer) 存 (pgvector 原生支持)

参考:
  - app/models/search_log.py (SearchLog model + user_id 列 v31.2)
  - app/core/security.py (get_current_user_optional v31.2)
  - app/api/v1/dashboard.py (stats endpoint 风格)
  - plan: .claude/plans/breezy-discovering-ripple.md (v31 + v31.2)
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user_optional
from app.models.member import Member
from app.models.search_log import SearchLog

logger = logging.getLogger("microbubble.analytics")

router = APIRouter(tags=["检索质量"])


# ==================== Pydantic Schemas ====================


class SearchEventRequest(BaseModel):
    """POST /analytics/search-event 请求体"""

    query: str = Field(..., min_length=1, max_length=500)
    top_ids: List[int] = Field(..., min_items=1, max_items=20)
    session_id: Optional[str] = Field(None, max_length=100)
    source: Optional[str] = Field(None, max_length=50)  # 'knowledge_search' / 'agent_chat'


class SearchEventResponse(BaseModel):
    """POST /analytics/search-event 响应"""

    search_event_id: int


class ClickRequest(BaseModel):
    """PATCH /analytics/search-event/{id}/click 请求体"""

    clicked_id: int = Field(..., ge=1)
    click_position: int = Field(..., ge=1, le=20)  # 1-based, top_ids 数组中的位置


class ClickResponse(BaseModel):
    """PATCH 响应"""

    ok: bool


# ==================== Endpoints ====================


@router.post(
    "/analytics/search-event",
    response_model=SearchEventResponse,
    summary="记录一次搜索事件 (query + top-K 检索结果 IDs)",
)
async def record_search_event(
    payload: SearchEventRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Member] = Depends(get_current_user_optional),
):
    """用户发起搜索时调用. 返回 search_event_id, 后续 click 用 PATCH 更新.

    embedding_model 从环境变量 EMBEDDING_MODEL_NAME 读 (后端单一来源, 零前端复杂度).

    v31.2: 登录用户绑 user_id, 匿名写 NULL (便于 per-user 聚合).
    """
    embedding_model = os.getenv(
        "EMBEDDING_MODEL_NAME", "Qwen/Qwen3-Embedding-0.6B"
    )

    log = SearchLog(
        query=payload.query,
        top_ids=payload.top_ids,
        embedding_model=embedding_model,
        session_id=payload.session_id,
        source=payload.source or "knowledge_search",
        user_id=current_user.id if current_user else None,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    logger.debug(
        f"search-event id={log.id} query='{payload.query[:30]}' "
        f"model={embedding_model} top_n={len(payload.top_ids)} "
        f"user_id={log.user_id}"
    )
    return SearchEventResponse(search_event_id=log.id)


@router.patch(
    "/analytics/search-event/{event_id}/click",
    response_model=ClickResponse,
    summary="记录点击 (更新 clicked_id + click_position)",
)
async def record_click(
    event_id: int,
    payload: ClickRequest,
    db: AsyncSession = Depends(get_db),
    current_user: Optional[Member] = Depends(get_current_user_optional),
):
    """用户点击某条搜索结果时调用. 更新 SearchLog 的点击位置.

    v31.2: PATCH 时如果用户已登录, 覆盖 user_id (POST 匿名 → PATCH 已登录的场景,
    写入真实归属; 便于 per-user 分析 "哪些用户常点哪些位置").
    """
    log = await db.get(SearchLog, event_id)
    if not log:
        raise HTTPException(status_code=404, detail=f"search_event {event_id} not found")

    log.clicked_id = payload.clicked_id
    log.click_position = payload.click_position
    # v31.2: PATCH 时如果有 user, 覆盖 (POST 匿名 → PATCH 登录补归属)
    if current_user:
        log.user_id = current_user.id
    await db.commit()
    logger.debug(
        f"click event={event_id} clicked_id={payload.clicked_id} "
        f"position={payload.click_position} "
        f"user_id={current_user.id if current_user else None}"
    )
    return ClickResponse(ok=True)


@router.get(
    "/analytics/stats",
    summary="返回核心指标 (按天/按 embedding_model 分组)",
)
async def get_stats(
    days: int = Query(7, ge=1, le=90, description="统计天数"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """核心指标:
      - total_searches  总搜索次数
      - total_clicks    总点击次数
      - any_click_rate  任何点击率 = clicks / searches
      - zero_click_rate 零点击率 = (searches - clicks) / searches (top-10 召回失败率)
      - avg_click_position  平均点击位置 (1-based; MRR proxy)
      - by_model        按 embedding_model 分组对比
      - by_source       按数据源分组对比 (knowledge_search / agent_chat)
      - trend           最近 days 天的搜索量趋势 (date -> count)

    用单条 SQL 聚合 + GROUP BY 一次性查完 (避免 N+1).
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)

    # 主聚合 (单条 SQL)
    result = await db.execute(
        text("""
            SELECT
                COUNT(*) AS total_searches,
                COUNT(clicked_id) AS total_clicks,
                AVG(click_position) FILTER (WHERE clicked_id IS NOT NULL) AS avg_click_pos,
                COUNT(*) FILTER (WHERE clicked_id IS NULL) AS zero_click_count
            FROM search_logs
            WHERE created_at >= :cutoff
        """),
        {"cutoff": cutoff},
    )
    row = result.fetchone()
    total_searches = int(row[0] or 0)
    total_clicks = int(row[1] or 0)
    avg_click_pos = float(row[2]) if row[2] is not None else None
    zero_click_count = int(row[3] or 0)

    # 按 embedding_model 分组
    by_model_result = await db.execute(
        text("""
            SELECT
                embedding_model,
                COUNT(*) AS total,
                COUNT(clicked_id) AS clicks
            FROM search_logs
            WHERE created_at >= :cutoff AND embedding_model IS NOT NULL
            GROUP BY embedding_model
            ORDER BY total DESC
        """),
        {"cutoff": cutoff},
    )
    by_model = {
        r[0]: {
            "searches": int(r[1]),
            "clicks": int(r[2]),
            "any_click_rate": round(int(r[2]) / int(r[1]), 4) if int(r[1]) > 0 else 0,
        }
        for r in by_model_result
    }

    # 按 source 分组
    by_source_result = await db.execute(
        text("""
            SELECT
                source,
                COUNT(*) AS total,
                COUNT(clicked_id) AS clicks
            FROM search_logs
            WHERE created_at >= :cutoff AND source IS NOT NULL
            GROUP BY source
            ORDER BY total DESC
        """),
        {"cutoff": cutoff},
    )
    by_source = {
        r[0] or "unknown": {
            "searches": int(r[1]),
            "clicks": int(r[2]),
            "any_click_rate": round(int(r[2]) / int(r[1]), 4) if int(r[1]) > 0 else 0,
        }
        for r in by_source_result
    }

    # v31.2.4: 按 user_id 分组 (per-user dashboard)
    # JOIN members 取真实名字, NULL user_id = 匿名用户
    # 仅显示有搜索量的用户 (searches > 0), top 20 by 搜索量
    by_user_result = await db.execute(
        text("""
            SELECT
                COALESCE(m.id::text, 'anonymous') AS user_key,
                COALESCE(m.name, '匿名用户') AS user_name,
                COALESCE(m.username, '') AS username,
                COUNT(*) AS searches,
                COUNT(sl.clicked_id) AS clicks,
                AVG(sl.click_position) FILTER (WHERE sl.clicked_id IS NOT NULL) AS avg_pos
            FROM search_logs sl
            LEFT JOIN members m ON sl.user_id = m.id
            WHERE sl.created_at >= :cutoff
            GROUP BY COALESCE(m.id::text, 'anonymous'), COALESCE(m.name, '匿名用户'), COALESCE(m.username, '')
            HAVING COUNT(*) > 0
            ORDER BY searches DESC
            LIMIT 20
        """),
        {"cutoff": cutoff},
    )
    by_user = [
        {
            "user_id": r[0] if r[0] != "anonymous" else None,
            "name": r[1],
            "username": r[2],
            "searches": int(r[3]),
            "clicks": int(r[4]),
            "any_click_rate": round(int(r[4]) / int(r[3]), 4) if int(r[3]) > 0 else 0,
            "avg_click_position": round(float(r[5]), 2) if r[5] is not None else None,
        }
        for r in by_user_result
    ]

    # 趋势: 最近 days 天的每日搜索量
    trend_result = await db.execute(
        text("""
            SELECT
                DATE(created_at) AS day,
                COUNT(*) AS searches,
                COUNT(clicked_id) AS clicks
            FROM search_logs
            WHERE created_at >= :cutoff
            GROUP BY DATE(created_at)
            ORDER BY day
        """),
        {"cutoff": cutoff},
    )
    trend = [
        {
            "date": r[0].isoformat() if r[0] else None,
            "searches": int(r[1]),
            "clicks": int(r[2]),
        }
        for r in trend_result
    ]

    # 计算比率
    any_click_rate = round(total_clicks / total_searches, 4) if total_searches > 0 else 0
    zero_click_rate = round(zero_click_count / total_searches, 4) if total_searches > 0 else 0

    return {
        "days": days,
        "total_searches": total_searches,
        "total_clicks": total_clicks,
        "any_click_rate": any_click_rate,
        "zero_click_rate": zero_click_rate,
        "avg_click_position": round(avg_click_pos, 2) if avg_click_pos is not None else None,
        "by_model": by_model,
        "by_user": by_user,  # v31.2.4: per-user dashboard 维度
        "by_source": by_source,
        "trend": trend,
    }


@router.get("/analytics/logs")
async def list_recent_logs(
    limit: int = Query(50, ge=1, le=200),
    source: Optional[str] = Query(None, max_length=50),
    db: AsyncSession = Depends(get_db),
):
    """
    返回最近 N 条搜索日志（详细列表）.

    用于前端 AnalyticsView 表格 + 移动端 sheet.
    按 created_at DESC 排序, 可选 source 过滤.
    """
    stmt = select(SearchLog).order_by(SearchLog.created_at.desc()).limit(limit)
    if source:
        stmt = stmt.where(SearchLog.source == source)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [
        {
            "id": r.id,
            "query": r.query,
            "embedding_model": r.embedding_model,
            "top_ids": list(r.top_ids or []),
            "clicked_id": r.clicked_id,
            "click_position": r.click_position,
            "session_id": r.session_id,
            "source": r.source,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}
