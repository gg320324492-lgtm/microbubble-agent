"""auto_intake_rollback_tasks — W68 第 10 批 B-3 Celery tasks (2026-07-24)

3 个 Celery task:
1. retry_rejected_kb_intake_task(rejected_id)
   - 触发 24h 后重试 (apply_async(countdown=86400))
   - 实际重试逻辑: 调 save_to_kb_service 重跑入库 (5 道防线重审)
2. permanent_suspend_rejected_kb_intake_task(rejected_id)
   - 3 次失败后永久挂起, 写 knowledge_pending_review
3. daily_kb_intake_health_check_task()
   - 每日 03:00 跑, 统计近 7d 失败率
   - 失败率 > 20% 触发 KbIntakeAlertService.send_alert_if_high_failure_rate

设计要点 (CLAUDE.md 铁律, 与 chat_history_tasks / drive_collab_tasks 一致):
- 独立 create_celery_engine_and_session() + NullPool: 避免全局 async_session 绑主进程
  事件循环, 与 asyncio.run() 新循环冲突 (方案 C 铁律 1 + chat-history 铁律 7)
- failure best-effort: try/except + logger.error, 不抛 (让 Celery 不重试链)
- 处理 0 行也 logger.info (健康监控可见)
- cutoff 用 datetime.now(timezone.utc) → tz-aware, DB 存 naive → replace(tzinfo=None)
  (CLAUDE.md 2026-06-05 教训: tz-aware vs naive 严格隔离)

参考:
- app/services/chat_history_tasks.py (Celery task 模式)
- app/services/drive_collab_tasks.py (drive 清理模式)
- app/services/auto_intake_rollback_service.py (业务核心)
- app/services/save_to_kb_service.py (5 道防线重审)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.services.auto_intake_rollback_service import (
    AutoIntakeRollbackService,
    MAX_RETRY_COUNT,
    RETRY_INTERVAL_SECONDS,
)
from app.services.kb_intake_alert_service import KbIntakeAlertService

logger = logging.getLogger("microbubble.auto_intake_rollback_tasks")


# =============================================================================
# Task 1: 单条 retry (24h 间隔, 由 apply_async(countdown=86400) 触发)
# =============================================================================
@celery_app.task(name="app.services.auto_intake_rollback_tasks.retry_rejected_kb_intake_task")
def retry_rejected_kb_intake_task(rejected_id: int) -> dict:
    """Celery task: 重试 1 条 rejected 入库

    调用:
    - apply_async(args=[rejected_id], countdown=86400) - 24h 延迟触发
    - retry_rejected_kb_intake_task.delay(rejected_id) - 立即触发

    流程:
    1. should_retry 检查 (24h 到 / retry_count < 3 / 未挂起)
    2. 调 save_to_kb_service 重跑 5 道防线 + 入库
    3. 成功: 删 rejected 行 (本 task 仅 log, 实际删除由调用方或 retry_count 超次时统一处理)
       失败: schedule_retry 排下次 + retry_count++
    4. retry_count 达到 MAX_RETRY_COUNT → mark_permanent_suspend

    返回:
        dict: {"status": "ok"|"skipped"|"error", "rejected_id": int, "action": str, ...}

    铁律 (W68 第 10 批 B-3):
    1. should_retry 4 条件全部满足才执行重试 (24h + retry_count<3 + 未挂起 + next_retry_at 不为 NULL)
    2. 重试成功 → 删 rejected 行 (知识已入库, 失败记录无意义)
    3. 重试失败 → schedule_retry 重排下次 (24h 后) + retry_count++
    4. 永久挂起 → mark_permanent_suspend 写 knowledge_pending_review + permanent_suspended=True
    5. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                async with session_factory() as db:
                    svc = AutoIntakeRollbackService(db)

                    # 1) should_retry 检查
                    if not await svc.should_retry(rejected_id):
                        logger.info(
                            f"⏭️ [retry] skip rejected_id={rejected_id}: should_retry=False"
                        )
                        return {
                            "status": "skipped",
                            "rejected_id": rejected_id,
                            "reason": "should_retry returned False",
                        }

                    # 2) 调 save_to_kb_service 重跑入库
                    #    注: 业务实际重试 = 重跑 5 道防线 + 入库
                    #    save_to_kb_service 是 B-2 已建服务 (本批同 agent 实施)
                    try:
                        from app.services.save_to_kb_service import SaveToKbService
                        from app.models.knowledge_rejected import KnowledgeRejected
                        from sqlalchemy import select

                        # 拿 rejected 详情供重试用
                        rej_result = await db.execute(
                            select(KnowledgeRejected).where(KnowledgeRejected.id == rejected_id)
                        )
                        rejected = rej_result.scalar_one_or_none()
                        if not rejected:
                            return {
                                "status": "error",
                                "rejected_id": rejected_id,
                                "error": "rejected row not found",
                            }

                        save_svc = SaveToKbService(db)
                        retry_result = await save_svc.retry_from_rejected(rejected)
                    except Exception as retry_exc:
                        # 重试本身失败 → schedule_retry 排下次
                        logger.warning(
                            f"⚠️ [retry] retry_from_rejected failed rejected_id={rejected_id}: "
                            f"{retry_exc}"
                        )
                        await svc.schedule_retry(rejected_id)
                        return {
                            "status": "retried_failed",
                            "rejected_id": rejected_id,
                            "error": str(retry_exc)[:200],
                        }

                    # 3) 重试结果分流
                    if retry_result and retry_result.get("status") == "ok":
                        # 成功: 删 rejected 行 (级联触发: knowledge_pending_review.rejected_id SET NULL)
                        from app.models.knowledge_rejected import KnowledgeRejected as KR
                        from sqlalchemy import delete as sa_delete

                        await db.execute(sa_delete(KR).where(KR.id == rejected_id))
                        await db.commit()
                        logger.warning(
                            f"✅ [retry] SUCCESS rejected_id={rejected_id} qa_id={rejected.qa_id!r} "
                            f"→ deleted rejected row"
                        )
                        return {
                            "status": "ok",
                            "rejected_id": rejected_id,
                            "action": "deleted",
                            "knowledge_id": retry_result.get("knowledge_id"),
                        }
                    else:
                        # save_to_kb_service 报告"未通过"或"部分通过" → schedule_retry
                        await svc.schedule_retry(rejected_id)
                        logger.info(
                            f"🔄 [retry] rejected_id={rejected_id} retry_count++, "
                            f"next_retry scheduled"
                        )
                        return {
                            "status": "retried_pending",
                            "rejected_id": rejected_id,
                            "retry_result": retry_result,
                        }
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [retry] task failed rejected_id={rejected_id}: {e}", exc_info=True)
        return {"status": "error", "rejected_id": rejected_id, "error": str(e)[:200]}


# =============================================================================
# Task 2: 永久挂起 (3 次失败后由 retry task 内部触发)
# =============================================================================
@celery_app.task(name="app.services.auto_intake_rollback_tasks.permanent_suspend_rejected_kb_intake_task")
def permanent_suspend_rejected_kb_intake_task(rejected_id: int) -> dict:
    """Celery task: 永久挂起 1 条 rejected, 转 knowledge_pending_review

    调用:
    - retry_rejected_kb_intake_task 内部 retry_count 达到上限时触发
    - 手动: permanent_suspend_rejected_kb_intake_task.delay(rejected_id)

    流程:
    1. 调 AutoIntakeRollbackService.mark_permanent_suspend
    2. 写 knowledge_pending_review (人工审阅)
    3. 标记 rejected.permanent_suspended=True (Celery 不再扫)

    返回:
        dict: {"status": "ok"|"error", "rejected_id": int, "pending_review_id": int?}

    铁律 (W68 第 10 批 B-3):
    1. mark_permanent_suspend 已做幂等 (qa_id UNIQUE), 重复调不重复写
    2. 不删 rejected 行 (保留 7 天审计追溯, daily 任务统一清理)
    3. 任务失败不抛 → return {status: error}
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                async with session_factory() as db:
                    svc = AutoIntakeRollbackService(db)
                    pending = await svc.mark_permanent_suspend(rejected_id)
                    if pending is None:
                        return {
                            "status": "error",
                            "rejected_id": rejected_id,
                            "error": "rejected row not found",
                        }
                    logger.warning(
                        f"🚫 [permanent_suspend] rejected_id={rejected_id} "
                        f"→ pending_review_id={pending.id} review_status={pending.review_status}"
                    )
                    return {
                        "status": "ok",
                        "rejected_id": rejected_id,
                        "pending_review_id": pending.id,
                        "qa_id": pending.qa_id,
                    }
            finally:
                await engine.dispose()

        return asyncio.run(_run())
    except Exception as e:
        logger.error(
            f"❌ [permanent_suspend] task failed rejected_id={rejected_id}: {e}", exc_info=True
        )
        return {"status": "error", "rejected_id": rejected_id, "error": str(e)[:200]}


# =============================================================================
# Task 3: Daily health check (失败率统计 + 告警 + 清理)
# =============================================================================
@celery_app.task(name="app.services.auto_intake_rollback_tasks.daily_kb_intake_health_check_task")
def daily_kb_intake_health_check_task(days: int = 7) -> dict:
    """Celery beat 任务: 每日 03:00 跑, 统计近 7d 失败率 + 告警 + 清理

    流程:
    1. AutoIntakeRollbackService.get_failure_rate(days) → 失败率
    2. failure_rate > 0.20 → KbIntakeAlertService.send_alert_if_high_failure_rate
    3. delete_permanent_suspended_old(retention_days=7) → 物理清理

    返回:
        dict: {
            "status": "ok"|"error",
            "failure_rate_data": dict,
            "alert_sent": bool,
            "deleted_count": int,
            "error": str?,
        }

    铁律 (W68 第 10 批 B-3):
    1. daily 03:00 beat schedule (与其他 daily 任务错峰)
    2. 失败率 < 20% 不发告警 (防抖节省资源)
    3. 告警失败不阻塞 (best-effort)
    4. 清理 0 行也 logger.info (健康监控)
    5. 任务失败不抛 → return {status: error}
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                async with session_factory() as db:
                    svc = AutoIntakeRollbackService(db)
                    alert_svc = KbIntakeAlertService()

                    # 1) 失败率统计
                    failure_rate_data = await svc.get_failure_rate(days=days)

                    # 2) 告警 (失败率 > 20%)
                    alert_sent = False
                    if failure_rate_data.get("should_alert"):
                        alert_sent = await alert_svc.send_alert_if_high_failure_rate(
                            failure_rate_data=failure_rate_data
                        )

                    # 3) 物理清理 (7 天前永久挂起的 rejected 行)
                    deleted_count = await svc.delete_permanent_suspended_old(retention_days=7)

                    # 健康监控日志 (即使 0 行也输出, 便于审计追溯)
                    logger.warning(
                        f"📊 [daily_health_check] window={days}d "
                        f"rejected={failure_rate_data['rejected_count']} "
                        f"success={failure_rate_data['success_count']} "
                        f"pending={failure_rate_data['pending_review_count']} "
                        f"failure_rate={failure_rate_data['failure_rate']:.2%} "
                        f"alert_sent={alert_sent} "
                        f"cleaned_old={deleted_count}"
                    )

                    return {
                        "status": "ok",
                        "failure_rate_data": failure_rate_data,
                        "alert_sent": alert_sent,
                        "deleted_count": deleted_count,
                    }
            finally:
                await engine.dispose()

        return asyncio.run(_run())
    except Exception as e:
        logger.error(f"❌ [daily_health_check] task failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)[:200]}


# =============================================================================
# Helper: 24h 延迟入队 (Celery apply_async countdown=86400)
# =============================================================================
def schedule_retry_in_24h(rejected_id: int) -> str:
    """24h 延迟触发 retry_rejected_kb_intake_task

    Args:
        rejected_id: knowledge_rejected.id

    Returns:
        Celery task ID (str)

    用法:
        from app.services.auto_intake_rollback_tasks import schedule_retry_in_24h
        schedule_retry_in_24h(rejected_id=42)

    设计要点:
    - apply_async(countdown=86400) 而非 delay(): delay 是立即, countdown 是延迟
    - 失败时 logger.error 不抛 (调用方应 best-effort)
    """
    try:
        result = retry_rejected_kb_intake_task.apply_async(
            args=[rejected_id],
            countdown=RETRY_INTERVAL_SECONDS,
        )
        logger.info(
            f"⏰ [schedule_retry_in_24h] rejected_id={rejected_id} task_id={result.id}"
        )
        return result.id
    except Exception as e:
        logger.error(
            f"❌ [schedule_retry_in_24h] rejected_id={rejected_id}: {e}", exc_info=True
        )
        return ""