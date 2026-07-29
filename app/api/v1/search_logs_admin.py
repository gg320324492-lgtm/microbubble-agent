"""SearchLog admin API (PR6 / W92) -- SearchLog frontend enablement.

Background (plan `rag-quirky-otter.md` PR6 + 11.2):
  Backend instrumentation has been complete since v30/v31
  (`app/models/search_log.py:50-101` + `app/api/v1/analytics.py`),
  but the frontend never consumed the raw per-row log. Gap 7 of the RAG plan.

This module is ADDITIVE ONLY:
  - `app/models/search_log.py` is NOT touched (0 diff, verified by 5-piece check 4)
  - `app/api/v1/analytics.py` legacy routes are NOT touched
  - no alembic migration (PR6 is explicitly a non-exception PR)

7 dimensions exposed per row (plan gate a: `>= 7` dims):
  1. time          -> created_at
  2. query         -> query
  3. candidates    -> candidate_count = len(top_ids)
  4. hit           -> hit = clicked_id IS NOT NULL
  5. click         -> clicked_id + click_position
  6. latency       -> latency_ms (see LATENCY SEMANTICS below)
  7. user          -> user_id + user_name (LEFT JOIN members)

LATENCY SEMANTICS (honest reporting, no schema change):
  `search_logs` has NO query-latency column and PR6 must not add one.
  `latency_ms` here is a DERIVED proxy: (updated_at - created_at) in ms,
  i.e. the interval between the search event being written and the click PATCH
  landing. It measures user dwell/decision time, NOT retrieval latency.
  Rows without a click have latency_ms = None.
  A true retrieval-latency column is deferred to PR7 (observability), which
  owns the schema change.

Endpoints:
  GET /admin/search-logs          paginated 7-dim rows + filters
  GET /admin/search-logs/summary  aggregate gates (recall rate / slow-query pct)

Auth: `get_current_admin_user` (admin | leader), mirroring
`app/api/v1/admin_kb_monitor.py`. The legacy `/analytics/logs` route stays
unauthenticated for backwards compatibility -- this new route is the hardened one.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.member import Member

logger = logging.getLogger("microbubble.search_logs_admin")

router = APIRouter(tags=["检索日志管理"])

# Heartbeat rows written by app/services/analytics_tasks.py are synthetic and
# must never pollute retrieval-quality metrics (same rule as analytics.py).
SYNTHETIC_SOURCE = "system_metrics"

# Plan gate (c): slow query share <= 5%. A "slow" row is one whose derived
# latency exceeds this threshold.
SLOW_QUERY_THRESHOLD_MS = 500


class SearchLogRow(BaseModel):
    """One search log row, 7 dimensions."""

    id: int
    created_at: Optional[str] = None      # dim 1 time
    query: str                            # dim 2 query
    candidate_count: int                  # dim 3 candidates
    hit: bool                             # dim 4 hit
    clicked_id: Optional[int] = None      # dim 5 click
    click_position: Optional[int] = None  # dim 5 click
    latency_ms: Optional[int] = None      # dim 6 latency (derived proxy)
    user_id: Optional[int] = None         # dim 7 user
    user_name: Optional[str] = None       # dim 7 user
    # context, not counted toward the 7 gate dims
    embedding_model: Optional[str] = None
    source: Optional[str] = None
    session_id: Optional[str] = None
    top_ids: List[int] = []


class SearchLogPage(BaseModel):
    items: List[SearchLogRow]
    total: int
    limit: int
    offset: int
    dimensions: List[str]


class SearchLogSummary(BaseModel):
    days: int
    total_searches: int
    total_clicks: int
    recall_rate: float          # gate (b): clicks / impressions >= 0.30
    recall_rate_gate_pass: bool
    slow_query_count: int
    slow_query_rate: float      # gate (c): slow / total <= 0.05
    slow_query_gate_pass: bool
    slow_query_gate_evaluable: bool  # False while latency is a dwell-time proxy
    slow_query_threshold_ms: int
    avg_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[int] = None
    avg_click_position: Optional[float] = None
    distinct_users: int
    latency_semantics: str


# The 7 gate dimensions, exported so the frontend and tests assert one source of truth.
GATE_DIMENSIONS = [
    "created_at",
    "query",
    "candidate_count",
    "hit",
    "click_position",
    "latency_ms",
    "user_id",
]


def _cutoff(days: int) -> datetime:
    """Naive UTC cutoff -- search_logs.created_at is TIMESTAMP WITHOUT TIME ZONE."""
    return (datetime.now(timezone.utc) - timedelta(days=days)).replace(tzinfo=None)


@router.get(
    "/admin/search-logs",
    response_model=SearchLogPage,
    summary="分页检索日志 (7 维: 时间/查询/候选数/命中/点击/耗时/user)",
)
async def list_search_logs(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: Optional[str] = Query(None, max_length=200, description="query 子串过滤"),
    source: Optional[str] = Query(None, max_length=50),
    user_id: Optional[int] = Query(None, ge=1),
    hit_only: bool = Query(False, description="仅返回有点击的行"),
    slow_only: bool = Query(False, description="仅返回 latency > 阈值的行"),
    db: AsyncSession = Depends(get_db),
    _admin: Member = Depends(get_current_admin_user),
) -> SearchLogPage:
    """Return paginated 7-dimension search log rows.

    Single JOIN, no N+1: member name resolved in the same statement.
    Synthetic heartbeat rows are excluded unconditionally.
    """
    where = [
        "sl.created_at >= :cutoff",
        "sl.source IS DISTINCT FROM :synthetic",
    ]
    params: dict = {"cutoff": _cutoff(days), "synthetic": SYNTHETIC_SOURCE}

    if q:
        where.append("sl.query ILIKE :q")
        params["q"] = f"%{q}%"
    if source:
        where.append("sl.source = :source")
        params["source"] = source
    if user_id is not None:
        where.append("sl.user_id = :user_id")
        params["user_id"] = user_id
    if hit_only:
        where.append("sl.clicked_id IS NOT NULL")
    if slow_only:
        where.append(
            "sl.clicked_id IS NOT NULL AND "
            "EXTRACT(EPOCH FROM (sl.updated_at - sl.created_at)) * 1000 > :slow_ms"
        )
        params["slow_ms"] = SLOW_QUERY_THRESHOLD_MS

    where_sql = " AND ".join(where)

    total_row = await db.execute(
        text(f"SELECT COUNT(*) FROM search_logs sl WHERE {where_sql}"), params
    )
    total = int(total_row.scalar() or 0)

    rows = await db.execute(
        text(
            f"""
            SELECT
                sl.id,
                sl.created_at,
                sl.query,
                COALESCE(array_length(sl.top_ids, 1), 0) AS candidate_count,
                sl.clicked_id,
                sl.click_position,
                CASE
                    WHEN sl.clicked_id IS NULL THEN NULL
                    ELSE ROUND(
                        EXTRACT(EPOCH FROM (sl.updated_at - sl.created_at)) * 1000
                    )::bigint
                END AS latency_ms,
                sl.user_id,
                m.name AS user_name,
                sl.embedding_model,
                sl.source,
                sl.session_id,
                sl.top_ids
            FROM search_logs sl
            LEFT JOIN members m ON sl.user_id = m.id
            WHERE {where_sql}
            ORDER BY sl.created_at DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {**params, "limit": limit, "offset": offset},
    )

    items = [
        SearchLogRow(
            id=int(r[0]),
            created_at=r[1].isoformat() if r[1] else None,
            query=r[2] or "",
            candidate_count=int(r[3] or 0),
            hit=r[4] is not None,
            clicked_id=r[4],
            click_position=r[5],
            latency_ms=int(r[6]) if r[6] is not None else None,
            user_id=r[7],
            user_name=r[8],
            embedding_model=r[9],
            source=r[10],
            session_id=r[11],
            top_ids=list(r[12] or []),
        )
        for r in rows
    ]

    return SearchLogPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        dimensions=GATE_DIMENSIONS,
    )


@router.get(
    "/admin/search-logs/summary",
    response_model=SearchLogSummary,
    summary="检索日志聚合门禁 (回收率 >= 30% / 慢查询 <= 5%)",
)
async def search_logs_summary(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _admin: Member = Depends(get_current_admin_user),
) -> SearchLogSummary:
    """Aggregate the two numeric gates the PR6 plan asks for.

    recall_rate    = clicks / impressions   (plan gate b, target >= 0.30)
    slow_query_rate = slow / total          (plan gate c, target <= 0.05)

    Both are reported as measured. A failing gate is a DATA finding
    (users are not clicking / the proxy latency is high), not a code defect --
    the caller must report the real number rather than tune the threshold.

    `slow_query_gate_evaluable` is False by construction: gate (c) is defined
    over *retrieval* latency, and this endpoint can only expose the dwell-time
    proxy (see module docstring). The rate is still computed and returned so
    the number is visible, but it must not be read as gate (c) passing.
    PR7 owns the real latency column and can flip this to True.
    """
    row = (
        await db.execute(
            text(
                """
                WITH base AS (
                    SELECT
                        clicked_id,
                        click_position,
                        user_id,
                        CASE
                            WHEN clicked_id IS NULL THEN NULL
                            ELSE EXTRACT(EPOCH FROM (updated_at - created_at)) * 1000
                        END AS latency_ms
                    FROM search_logs
                    WHERE created_at >= :cutoff
                      AND source IS DISTINCT FROM :synthetic
                )
                SELECT
                    COUNT(*)                                              AS total,
                    COUNT(clicked_id)                                     AS clicks,
                    COUNT(*) FILTER (WHERE latency_ms > :slow_ms)         AS slow_count,
                    AVG(latency_ms)                                       AS avg_latency,
                    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms)
                                                                          AS p95_latency,
                    AVG(click_position) FILTER (WHERE clicked_id IS NOT NULL)
                                                                          AS avg_pos,
                    COUNT(DISTINCT user_id)                               AS distinct_users
                FROM base
                """
            ),
            {
                "cutoff": _cutoff(days),
                "synthetic": SYNTHETIC_SOURCE,
                "slow_ms": SLOW_QUERY_THRESHOLD_MS,
            },
        )
    ).fetchone()

    total = int(row[0] or 0)
    clicks = int(row[1] or 0)
    slow_count = int(row[2] or 0)

    recall_rate = round(clicks / total, 4) if total > 0 else 0.0
    slow_rate = round(slow_count / total, 4) if total > 0 else 0.0

    return SearchLogSummary(
        days=days,
        total_searches=total,
        total_clicks=clicks,
        recall_rate=recall_rate,
        recall_rate_gate_pass=recall_rate >= 0.30,
        slow_query_count=slow_count,
        slow_query_rate=slow_rate,
        slow_query_gate_pass=slow_rate <= 0.05,
        slow_query_gate_evaluable=False,
        slow_query_threshold_ms=SLOW_QUERY_THRESHOLD_MS,
        avg_latency_ms=round(float(row[3]), 2) if row[3] is not None else None,
        p95_latency_ms=int(row[4]) if row[4] is not None else None,
        avg_click_position=round(float(row[5]), 2) if row[5] is not None else None,
        distinct_users=int(row[6] or 0),
        latency_semantics=(
            "derived proxy: updated_at - created_at (click dwell time), "
            "NOT retrieval latency; true latency column deferred to PR7"
        ),
    )
