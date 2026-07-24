"""KB 自动入库监控 API — qa-bench v3.1 决策 D5 (Dashboard KB 监控)

W68 第 7 批 A-4 (2026-07-24) — 锚点范式第 78 守恒.

背景:
  plan `qa-bench-v3.1-decisions.md` D1-D8 中, D5 (Dashboard KB 监控) 核心前端
  `web/src/views/admin/KbMonitorView.vue` 与配套后端 endpoint 一直缺失
  (7/8 决策项已闭环, D5 单项缺). 本文件补齐后端 3 endpoint.

3 个 endpoint (全部 admin/leader only, write tier 30/min):
  - GET /admin/kb-monitor/overview?hours=24  返回入库/失败/重试/队列 核心统计 + 24h 趋势
  - GET /admin/kb-monitor/queue-depth        返回 Celery beat 队列深度 (pending 堆积)
  - GET /admin/kb-monitor/failures?limit=50  返回失败/滞留 (超 MAX_ATTEMPTS 仍 pending) 列表

数据源:
  - knowledge 表 analysis_status 列 (pending/analyzing/done/failed)
  - app/services/knowledge_polling_service.py (每 KB_POLLING_INTERVAL_SEC 后台批处理 pending)
    · 失败的行 rollback 后保持 pending → 下一轮重试 (MAX_ATTEMPTS=3)
    · 因此 "滞留 pending 且 created_at 早于 N 轮前" 近似 = 需要人工介入的失败项

设计决策:
  - 复用 `app.api.v1.admin.get_current_admin` (与 admin_audit.py 同款鉴权)
  - 队列深度以 DB pending 计数为准 (不依赖 Celery inspect, 避免 worker 未连时 500)
  - 趋势按小时 bucket 聚合, 单条 SQL GROUP BY (避免 N+1)
  - tz-aware cutoff → naive (CLAUDE.md 2026-06-05 教训, search_logs analytics 同款)

参考:
  - app/api/v1/analytics.py (stats endpoint SQL 聚合风格)
  - app/api/v1/admin_audit.py (get_current_admin 复用)
  - app/services/knowledge_polling_service.py (MAX_ATTEMPTS / KB_POLLING_INTERVAL_SEC)
  - plan: .claude/plans/qa-bench-v3.1-decisions.md (D5)
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import get_current_admin
from app.config import settings
from app.core.database import get_db
from app.models.knowledge import Knowledge
from app.models.member import Member
from app.services.knowledge_polling_service import MAX_ATTEMPTS

logger = logging.getLogger("microbubble.admin_kb_monitor")

router = APIRouter(tags=["KB 监控"])


def _naive_cutoff(hours: int) -> datetime:
    """tz-aware now - hours → naive UTC (与 knowledge.created_at server_default now() 对齐)."""
    return (datetime.now(timezone.utc) - timedelta(hours=hours)).replace(tzinfo=None)


@router.get(
    "/admin/kb-monitor/overview",
    summary="KB 自动入库监控总览 (过去 N 小时入库/失败/重试/队列 + 逐小时趋势)",
)
async def kb_monitor_overview(
    hours: int = Query(24, ge=1, le=168, description="统计窗口小时数 (默认 24, 最长 7 天)"),
    current_user: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """核心指标:
      - ingested   窗口内新入库总数 (created_at >= cutoff)
      - done       窗口内已成功分析 (analysis_status='done')
      - failed     窗口内标记失败 (analysis_status='failed')
      - retrying   仍 pending 且已超过 MAX_ATTEMPTS 轮 (估算重试中/需介入)
      - queue_depth 全局待处理队列深度 (analysis_status in pending/analyzing)
      - success_rate  done / ingested
      - trend      逐小时 bucket: {hour, ingested, done, failed}
      - polling_interval_sec  后台轮询间隔 (供前端计算"预计清空时间")

    单条 SQL GROUP BY 聚合, 避免 N+1.
    """
    cutoff = _naive_cutoff(hours)

    # 窗口内按 analysis_status 分组计数
    status_result = await db.execute(
        text(
            """
            SELECT analysis_status, COUNT(*) AS c
            FROM knowledge
            WHERE created_at >= :cutoff
            GROUP BY analysis_status
            """
        ),
        {"cutoff": cutoff},
    )
    status_counts = {(r[0] or "unknown"): int(r[1]) for r in status_result}
    ingested = sum(status_counts.values())
    done = status_counts.get("done", 0)
    failed = status_counts.get("failed", 0)

    # 全局队列深度 (不限窗口: pending + analyzing 都算堆积)
    queue_result = await db.execute(
        select(func.count(Knowledge.id)).where(
            Knowledge.analysis_status.in_(["pending", "analyzing"])
        )
    )
    queue_depth = int(queue_result.scalar_one() or 0)

    # "重试中/需介入" 估算: 仍 pending 且 created_at 早于 MAX_ATTEMPTS 轮轮询前
    # 一轮轮询处理一批, 早于 MAX_ATTEMPTS * interval 仍 pending → 多次失败滞留
    polling_interval = float(settings.KB_POLLING_INTERVAL_SEC)
    stuck_cutoff = (
        datetime.now(timezone.utc)
        - timedelta(seconds=polling_interval * MAX_ATTEMPTS)
    ).replace(tzinfo=None)
    retrying_result = await db.execute(
        select(func.count(Knowledge.id)).where(
            Knowledge.analysis_status == "pending",
            Knowledge.created_at < stuck_cutoff,
        )
    )
    retrying = int(retrying_result.scalar_one() or 0)

    # 逐小时趋势 (窗口内)
    trend_result = await db.execute(
        text(
            """
            SELECT
                date_trunc('hour', created_at) AS h,
                COUNT(*) AS ingested,
                COUNT(*) FILTER (WHERE analysis_status = 'done') AS done,
                COUNT(*) FILTER (WHERE analysis_status = 'failed') AS failed
            FROM knowledge
            WHERE created_at >= :cutoff
            GROUP BY date_trunc('hour', created_at)
            ORDER BY h
            """
        ),
        {"cutoff": cutoff},
    )
    trend = [
        {
            "hour": r[0].isoformat() if r[0] else None,
            "ingested": int(r[1]),
            "done": int(r[2]),
            "failed": int(r[3]),
        }
        for r in trend_result
    ]

    success_rate = round(done / ingested, 4) if ingested > 0 else None

    return {
        "hours": hours,
        "ingested": ingested,
        "done": done,
        "failed": failed,
        "retrying": retrying,
        "queue_depth": queue_depth,
        "success_rate": success_rate,
        "status_counts": status_counts,
        "polling_interval_sec": polling_interval,
        "trend": trend,
    }


@router.get(
    "/admin/kb-monitor/queue-depth",
    summary="KB 后台处理队列深度 (pending / analyzing 堆积)",
)
async def kb_monitor_queue_depth(
    current_user: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """队列深度快照 (轻量, 供前端高频轮询):
      - pending    等待分析
      - analyzing  正在分析 (理论上短暂, 长期滞留说明 worker 卡)
      - queue_depth = pending + analyzing
      - polling_interval_sec  轮询间隔
      - eta_minutes  估算清空时间 = ceil(queue_depth / batch) * interval / 60

    以 DB 计数为准, 不依赖 Celery inspect (worker 未连时也能返回).
    """
    result = await db.execute(
        text(
            """
            SELECT analysis_status, COUNT(*) AS c
            FROM knowledge
            WHERE analysis_status IN ('pending', 'analyzing')
            GROUP BY analysis_status
            """
        )
    )
    counts = {(r[0] or "unknown"): int(r[1]) for r in result}
    pending = counts.get("pending", 0)
    analyzing = counts.get("analyzing", 0)
    queue_depth = pending + analyzing

    polling_interval = float(settings.KB_POLLING_INTERVAL_SEC)
    batch = 50  # knowledge_polling_service.DEFAULT_LIMIT
    rounds = (queue_depth + batch - 1) // batch if queue_depth > 0 else 0
    eta_minutes = round(rounds * polling_interval / 60.0, 1)

    return {
        "pending": pending,
        "analyzing": analyzing,
        "queue_depth": queue_depth,
        "polling_interval_sec": polling_interval,
        "batch_size": batch,
        "eta_minutes": eta_minutes,
    }


@router.get(
    "/admin/kb-monitor/failures",
    summary="KB 入库失败 / 滞留列表 (analysis_status='failed' 或超轮次仍 pending)",
)
async def kb_monitor_failures(
    limit: int = Query(50, ge=1, le=200, description="返回条数"),
    include_stuck: bool = Query(
        True, description="是否含滞留 pending (超 MAX_ATTEMPTS 轮仍未处理)"
    ),
    current_user: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """失败列表 (供 admin 手动重提 / 排查):
      - analysis_status='failed' 一定纳入
      - include_stuck=True 时, 额外纳入超 MAX_ATTEMPTS 轮仍 pending 的滞留项

    按 created_at DESC 排序. 每条含 id/title/status/created_at/quality_score.
    """
    statuses = ["failed"]
    stuck_cutoff: Optional[datetime] = None
    if include_stuck:
        polling_interval = float(settings.KB_POLLING_INTERVAL_SEC)
        stuck_cutoff = (
            datetime.now(timezone.utc)
            - timedelta(seconds=polling_interval * MAX_ATTEMPTS)
        ).replace(tzinfo=None)

    stmt = select(Knowledge)
    if include_stuck and stuck_cutoff is not None:
        stmt = stmt.where(
            (Knowledge.analysis_status == "failed")
            | (
                (Knowledge.analysis_status == "pending")
                & (Knowledge.created_at < stuck_cutoff)
            )
        )
    else:
        stmt = stmt.where(Knowledge.analysis_status.in_(statuses))
    stmt = stmt.order_by(Knowledge.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    rows = result.scalars().all()
    items = [
        {
            "id": r.id,
            "title": r.title,
            "analysis_status": r.analysis_status,
            "quality_score": r.quality_score,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "is_stuck": (
                r.analysis_status == "pending"
                and stuck_cutoff is not None
                and r.created_at is not None
                and r.created_at < stuck_cutoff
            ),
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}
