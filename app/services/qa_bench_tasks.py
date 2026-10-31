"""qa_bench_tasks.py — Celery beat tasks for qa-bench 7-day auto-intake rollback (W71 B-3)

派工依据:
- docs/chatgpt-structured-floyd-w69-plan.md §2.5: 要求 app/services/qa_bench_tasks.py:auto_intake_rollback_task
- docs/qa-bench-d8-comprehensive-survey-2026-07-24.md §3.3: 真验证发现仅 scripts/auto_intake_rollback.py CLI,
  无 Celery task. 派生新任务: 必须新建本模块 + Celery beat 注册 + 4/4 e2e PASS

铁律 (W68 第 11 批 + 派工 v6 第 5 条):
1. 独立 create_celery_engine_and_session (NullPool) — 跨 event loop 安全
2. engine.dispose() finally — 避免 asyncpg 连接泄漏
3. cutoff 用 **naive UTC** — `knowledge.created_at` 是 `TIMESTAMP WITHOUT TIME ZONE`,
   传 tz-aware datetime 给 asyncpg 会报 DataError("can't subtract offset-naive and
   offset-aware datetimes") ⇒ 必须 `.replace(tzinfo=None)` (CLAUDE.md 类 20.221:
   DB 存 UTC; 本仓标准写法见 app/models/base.py)
4. 任务失败不抛 → return {status: error} 让 Celery 不重试链
5. 始终 logger.warning / info (即便回滚 0 条) → 健康监控可见
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.knowledge import Knowledge
from app.services.cleanup_safety import confirm_retention_param_auto

logger = logging.getLogger("microbubble.qa_bench_rollback")

DEFAULT_RETENTION_DAYS = 7


def utc_cutoff_naive(retention_days: int) -> datetime:
    """返回 N 天前的 **naive UTC** datetime（可直接与 TIMESTAMP WITHOUT TIME ZONE 列比较）

    ⚠️ 不要改成 `datetime.now(timezone.utc)` — 那个是 tz-aware, asyncpg 会直接报
    `DataError: can't subtract offset-naive and offset-aware datetimes`。
    这正是本任务 2026-10-30 之前每天静默失败的根因。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)


@celery_app.task(name="app.services.qa_bench_tasks.auto_intake_rollback_task")
def auto_intake_rollback_task(retention_days: Optional[int] = None):
    """Celery beat daily 任务: 自动回滚 N 天前入库的 auto_expansion 低质量条目

    设计要点 (与 file_mention_tasks / drive_cleanup_tasks 一致):
    1. 查 knowledge 表 source_type='auto_expansion' AND created_at < NOW() - retention_days
    2. **软删除** (`deleted_at` 置值 ⇒ 从所有知识库查询/RAG 召回中消失, 行保留供审计)
       —— ⚠️ 不是 `is_active`: Knowledge 模型**没有** is_active 列, 写它会直接编译失败。
    3. 写 data/auto_intake_rollback_YYYYMMDD_HHMMSS.json 报告 (与 API 端点对齐)
    4. 0 条也要 logger.info 输出 (健康监控)

    Args:
        retention_days: 保留天数 (None = 用默认 7)。非默认值会触发仓库统一的
            保留期守卫 (`confirm_retention_param_auto`, 同 drive_cleanup_tasks)。
    """

    guard = confirm_retention_param_auto(
        retention_days=retention_days,
        default=DEFAULT_RETENTION_DAYS,
        task_name="app.services.qa_bench_tasks.auto_intake_rollback_task",
    )
    if not guard["proceed"]:
        logger.warning("[qa-bench] auto_intake_rollback 被守卫拦下: %s", guard.get("reason"))
        return {"status": "skipped", "reason": guard.get("reason"),
                "rolled_back": 0, "retention_days": guard["effective_days"]}
    effective_days = guard["effective_days"]

    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                cutoff = utc_cutoff_naive(effective_days)
                deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
                async with session_factory() as db:
                    # 1. 查候选 (auto_expansion + created_at < cutoff)
                    candidates_result = await db.execute(
                        select(Knowledge.id, Knowledge.title, Knowledge.created_at)
                        .where(Knowledge.source_type == "auto_expansion")
                        .where(Knowledge.created_at < cutoff)
                        .where(Knowledge.deleted_at.is_(None))
                    )
                    candidates = candidates_result.fetchall()
                    candidate_ids = [c[0] for c in candidates]

                    # 2. 软删除 (置 deleted_at ⇒ 从检索/列表消失, 行保留可审计)
                    if candidate_ids:
                        await db.execute(
                            update(Knowledge)
                            .where(Knowledge.id.in_(candidate_ids))
                            .values(deleted_at=deleted_at)
                        )
                        await db.commit()
                    return candidates
            finally:
                await engine.dispose()

        candidates = asyncio.run(_run())
        rolled_back = len(candidates)

        # 3. 写 rollback 报告 JSON (与 knowledge API §rollback_count 聚合对齐)
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "retention_days": effective_days,
            "deleted_count": rolled_back,
            "entries": [{"id": c[0], "title": c[1], "created_at": str(c[2])}
                        for c in candidates],
        }
        report_path = Path(f"data/auto_intake_rollback_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        if rolled_back > 0:
            logger.warning(f"[qa-bench] auto_intake_rollback: 回滚 {rolled_back} 条 (retention_days={effective_days})")
        else:
            logger.info(f"[qa-bench] auto_intake_rollback: 健康, 无候选 (retention_days={effective_days})")

        return {"status": "ok", "rolled_back": rolled_back, "retention_days": effective_days}

    except Exception as e:
        logger.error(f"[qa-bench] auto_intake_rollback 失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "rolled_back": 0, "retention_days": effective_days}