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

  - 2026-10-09 类 20.219 同源第 5 例修复: 全部 6 处查询补 storage_mode='kb' 过滤
    (详见模块下方 INGESTABLE_STORAGE_MODE 注释块)

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
from app.services.rag_auto_ingest_service import INGESTABLE_STORAGE_MODE

logger = logging.getLogger("microbubble.admin_kb_monitor")

router = APIRouter(tags=["KB 监控"])


# 2026-10-09 类 20.219 同源第 5 例修复: 本模块全部 analysis_status 查询补 storage_mode 过滤
#
# 背景: Knowledge.content 对 storage_mode='drive' 的行并非真实正文 —— drive_service.py
# 写入的是占位串 ``[drive upload] <file_name>`` (约 30 字符)。app/models/knowledge.py:26
# 的 analysis_status 默认值是 "pending", 且 drive_service 的 6 条建行路径 (普通上传 /
# 秒传 / 新版本 / 上传会话完成) **都不显式设置 analysis_status** → 每个网盘文件入库都
# 落在 pending。而 knowledge_polling_service (第 4 例修复后) 与 rag_auto_ingest_service
# (第 3 例) 已按 storage_mode=='kb' 硬过滤, drive 行**永远不会被 claim**。
#
# 后果: 修复前本模块算出的队列深度 / 重试中 / 失败列表把 drive 行算进去, 数字虚高
# **且永远不会下降** (每传一个网盘文件 +1, 且永远 drain 不掉) —— 正是类 20.219
# 「占位垃圾掩盖漏注册」的第五种形态: 漏的这次不是注册, 是**监控口径**。
#
# 口径说明 (为什么 ingested 也一并过滤, 而不是当"全量入库数"保留):
#   前端 KbMonitorView.vue 把 ingested 当**比率的分母**用 ——
#     失败率 = trend.failed / trend.ingested (L171)
#     抽检率 = done / ingested (L335)
#     success_rate = done / ingested (后端 L148)
#   分母若不与分子同口径, drive 行会把失败率/抽检率系统性稀释。且"新文件入库总数"
#   在本 dashboard 并未丢失: 「本周新增入库」卡片走的是另一个 endpoint
#   (useKbMonitor summary, 7 天入库/回滚), 仍是全量口径。
#
# 与其余读路径一致 (app/api/v1/knowledge.py、chat_attachments.py、
# micro_bubble_agent.py、knowledge_polling_service.py、rag_auto_ingest_service.py) ——
# 全部按 storage_mode=='kb' 硬过滤。
#
# 常量 import 复用而非复制第二份 (两份必然漂移 = 同类事故的第五种形态)。
# 已实测双向 import 无循环依赖: rag_auto_ingest_service 只 import
# celery/celery_db/模型层, 从不 import app.api.* —— API 层 → service 层是单向的。
#
# 为什么本地再造一个 _ingestable_kb_clause() 而不是直接调 service 层的
# _ingestable_rows_clause(): 后者返回 (analysis_status=='pending',
# storage_mode==...) 的二元组, 其中 "状态=pending" 那一半在本模块**不成立**
# (queue_depth 要 pending OR analyzing, failures 要 failed OR 滞留 pending),
# 取其 [1] 元素既私有又易碎。单例真相是那个**公开常量** INGESTABLE_STORAGE_MODE,
# 本地只负责把它包成针对 Knowledge 的 clause。
def _ingestable_kb_clause():
    """``storage_mode='kb'`` clause —— 本模块所有 ORM 查询的公共过滤条件。"""
    return Knowledge.storage_mode == INGESTABLE_STORAGE_MODE


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
    """核心指标 (**全部只统计 storage_mode='kb'**, 类 20.219 第 5 例):
      - ingested   窗口内新入库总数 (created_at >= cutoff, storage_mode='kb')
      - done       窗口内已成功分析 (analysis_status='done')
      - failed     窗口内标记失败 (analysis_status='failed')
      - retrying   仍 pending 且已超过 MAX_ATTEMPTS 轮 (估算重试中/需介入)
      - queue_depth 全局待处理队列深度 (analysis_status in pending/analyzing)
      - success_rate  done / ingested
      - trend      逐小时 bucket: {hour, ingested, done, failed}
      - polling_interval_sec  后台轮询间隔 (供前端计算"预计清空时间")

    单条 SQL GROUP BY 聚合, 避免 N+1.

    ⚠️ drive 行 (网盘文件, 正文是 "[drive upload] <file_name>" 占位串) 全部排除:
    它们不会被 claim, 计入会让 queue_depth/retrying 虚高且永远不下降。需要"新文件
    入库总数"请看 `useKbMonitor` 的 7 天 intake summary (另一个 endpoint, 全量口径)。
    """
    cutoff = _naive_cutoff(hours)

    # 窗口内按 analysis_status 分组计数 (类 20.219 第 5 例: 限 storage_mode='kb')
    status_result = await db.execute(
        text(
            """
            SELECT analysis_status, COUNT(*) AS c
            FROM knowledge
            WHERE created_at >= :cutoff
              AND storage_mode = :ingestable_storage_mode
            GROUP BY analysis_status
            """
        ),
        {"cutoff": cutoff, "ingestable_storage_mode": INGESTABLE_STORAGE_MODE},
    )
    status_counts = {(r[0] or "unknown"): int(r[1]) for r in status_result}
    ingested = sum(status_counts.values())
    done = status_counts.get("done", 0)
    failed = status_counts.get("failed", 0)

    # 全局队列深度 (不限窗口: pending + analyzing 都算堆积)
    queue_result = await db.execute(
        select(func.count(Knowledge.id)).where(
            Knowledge.analysis_status.in_(["pending", "analyzing"]),
            _ingestable_kb_clause(),
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
            _ingestable_kb_clause(),
        )
    )
    retrying = int(retrying_result.scalar_one() or 0)

    # 逐小时趋势 (窗口内) — 类 20.219 第 5 例: 与 ingested 同口径限 kb
    # (前端 KbMonitorView.vue L171 用 trend.failed / trend.ingested 算失败率)
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
              AND storage_mode = :ingestable_storage_mode
            GROUP BY date_trunc('hour', created_at)
            ORDER BY h
            """
        ),
        {"cutoff": cutoff, "ingestable_storage_mode": INGESTABLE_STORAGE_MODE},
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
    """队列深度快照 (轻量, 供前端高频轮询, **只计 storage_mode='kb'**):
      - pending    等待分析
      - analyzing  正在分析 (理论上短暂, 长期滞留说明 worker 卡)
      - queue_depth = pending + analyzing
      - polling_interval_sec  轮询间隔
      - eta_minutes  估算清空时间 = ceil(queue_depth / batch) * interval / 60

    以 DB 计数为准, 不依赖 Celery inspect (worker 未连时也能返回).

    ⚠️ drive 行排除 (类 20.219 第 5 例): 网盘文件行默认落 pending 但永不被 claim,
    计入会让 queue_depth 与 eta_minutes 虚高且 eta 永远归不了零。
    """
    result = await db.execute(
        text(
            """
            SELECT analysis_status, COUNT(*) AS c
            FROM knowledge
            WHERE analysis_status IN ('pending', 'analyzing')
              AND storage_mode = :ingestable_storage_mode
            GROUP BY analysis_status
            """
        ),
        {"ingestable_storage_mode": INGESTABLE_STORAGE_MODE},
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
    """失败列表 (供 admin 手动重提 / 排查, **只列 storage_mode='kb'**):
      - analysis_status='failed' 一定纳入
      - include_stuck=True 时, 额外纳入超 MAX_ATTEMPTS 轮仍 pending 的滞留项

    按 created_at DESC 排序. 每条含 id/title/status/created_at/quality_score.

    ⚠️ drive 行排除 (类 20.219 第 5 例): drive 行不会被处理, 出现在这里只会诱导 admin
    对着一批永远不会被 claim 的行反复人工重提 (假告警)。手动重提后仍是 pending,
    下一轮又被过滤掉 —— 症状看起来像"重提无效", 根因在口径不在重提动作。
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
    # 类 20.219 第 5 例: drive 行永不被处理, 不该出现在失败/滞留列表里 (admin 会照着
    # 这份列表去人工重提 —— 重提了也永远不会被 claim, 是纯粹的假告警)
    stmt = stmt.where(_ingestable_kb_clause())
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
