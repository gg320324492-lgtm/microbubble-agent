"""Drive v2 PR10 — 协同编辑 Celery 任务 (2026-07-24, W68 第 7 批 B-1)

2 个 Celery task:
1. flush_ydoc_state_task(file_id=None)
   - 每 30s 周期把 Y.Doc snapshot 从 op log 重放刷盘到 drive_documents.ydoc_state
   - file_id=None (beat 周期调用): 刷所有近 30s 有新 op 的活跃文档
   - file_id=int (显式调用): 只刷该文档
2. compress_op_logs_task()
   - 每天凌晨 3:00 合并 7 天前 op → 已在 ydoc_state (apply_remote_op 已同步落 snapshot)
     → 删 7 天前 op log (审计窗口外, 减小表体积)

设计要点 (CLAUDE.md 铁律, 与 chat_share_tasks / drive_cleanup_tasks 一致):
- 独立 create_celery_engine_and_session() + NullPool: 避免全局 async_session 绑主进程
  事件循环, 与 asyncio.run() 新循环冲突 (方案 C 铁律 1 + chat-history 铁律 7)
- failure best-effort: try/except + logger.error, 不抛 (让 Celery 不重试链)
- deleted_count/flushed_count = 0 也 logger.info (健康监控可见)
- cutoff 用 datetime.now(timezone.utc) → tz-aware, DB 存 naive → replace(tzinfo=None)
  (CLAUDE.md 2026-06-05 教训: tz-aware vs naive 严格隔离)

参考:
- app/services/chat_share_tasks.py (Celery task 模式)
- app/services/drive_cleanup_tasks.py (drive 清理模式)
- app/services/drive_collab_service.py (flush_ydoc_state_to_db + recover_from_crash)
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, select

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.drive_document import DriveDocOpLog, DriveDocument
from app.services.drive_collab_service import DriveCollabService

logger = logging.getLogger("microbubble.drive_collab_tasks")

#: op log 保留天数 (审计窗口, 7 天后 op 已合并进 snapshot → 删)
OP_LOG_RETENTION_DAYS = 7
#: flush 周期检测的 "近期活跃" 窗口 (秒)
FLUSH_ACTIVE_WINDOW_SEC = 120


@celery_app.task(name="app.services.drive_collab_tasks.flush_ydoc_state_task")
def flush_ydoc_state_task(file_id: int = None):
    """Celery beat 任务: 把活跃文档的 Y.Doc snapshot 刷盘

    调用:
    - beat 每 30s: file_id=None → 刷所有近 FLUSH_ACTIVE_WINDOW_SEC 内有新 op 的文档
    - 显式 flush_ydoc_state_task.delay(file_id): 只刷该文档

    返回:
        dict: {"status": "ok"|"error", "flushed_count": int, "error": str?}

    铁律 (W68 第 7 批 B-1):
    1. 从 op log 重放兜底 (无内存 state 时, service.flush_ydoc_state_to_db(state=None))
    2. 任务失败不抛 → return {status: error}
    3. flushed_count = 0 也 logger.info (健康监控)
    4. NullPool + engine.dispose() 避免跨事件循环 (chat-history 铁律 7 复用)
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            flushed = 0
            try:
                async with session_factory() as db:
                    if file_id is not None:
                        target_ids = [file_id]
                    else:
                        # 近期有新 op 的文档 (naive cutoff, DB 存 naive)
                        cutoff = (
                            datetime.now(timezone.utc) - timedelta(seconds=FLUSH_ACTIVE_WINDOW_SEC)
                        ).replace(tzinfo=None)
                        result = await db.execute(
                            select(distinct(DriveDocOpLog.file_id))
                            .where(DriveDocOpLog.applied_at >= cutoff)
                        )
                        target_ids = [row[0] for row in result.all()]

                    for fid in target_ids:
                        # state=None → service 从 op log 重放重建后刷盘
                        ok = await DriveCollabService.flush_ydoc_state_to_db(db, fid, state=None)
                        if ok:
                            flushed += 1

                if flushed > 0:
                    logger.info(
                        "💾 [collab-flush] 刷盘 %d 个活跃文档 Y.Doc snapshot", flushed
                    )
                else:
                    logger.info("✅ [collab-flush] 健康: 当前无活跃文档需刷盘")
                return {"status": "ok", "flushed_count": flushed}
            finally:
                await engine.dispose()

        return asyncio.run(_run())
    except Exception as e:
        logger.error("❌ [collab-flush] 刷盘失败: %s", e, exc_info=True)
        return {"status": "error", "error": str(e), "flushed_count": 0}


@celery_app.task(name="app.services.drive_collab_tasks.compress_op_logs_task")
def compress_op_logs_task():
    """Celery beat 任务: 删 OP_LOG_RETENTION_DAYS 天前的 op log

    apply_remote_op 已在每次应用后同步落 snapshot (ydoc_state 始终最新),
    因此 7 天前的 op log 已被合并进 snapshot, 删除不丢内容 (仅丢审计明细).

    返回:
        dict: {"status": "ok"|"error", "deleted_count": int, "cutoff": iso, "error": str?}

    铁律 (W68 第 7 批 B-1):
    1. 删前先确保对应文档 snapshot 已重放最新 (recover_from_crash 幂等重建)
    2. cutoff naive (DB 存 naive)
    3. 任务失败不抛 → return {status: error}
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                cutoff = (
                    datetime.now(timezone.utc) - timedelta(days=OP_LOG_RETENTION_DAYS)
                ).replace(tzinfo=None)
                async with session_factory() as db:
                    # 1) 找出所有有 7 天前 op 的文档, 先重放确保 snapshot 完整
                    fid_result = await db.execute(
                        select(distinct(DriveDocOpLog.file_id))
                        .where(DriveDocOpLog.applied_at < cutoff)
                    )
                    affected_ids = [row[0] for row in fid_result.all()]
                    for fid in affected_ids:
                        # 幂等重建 snapshot (含全部 op), 保证删 op 前内容已在 ydoc_state
                        await DriveCollabService.recover_from_crash(db, fid)

                    # 2) 删 7 天前 op log
                    from sqlalchemy import delete as sql_delete

                    del_result = await db.execute(
                        sql_delete(DriveDocOpLog).where(DriveDocOpLog.applied_at < cutoff)
                    )
                    await db.commit()
                    deleted_count = del_result.rowcount or 0

                    if deleted_count > 0:
                        logger.warning(
                            "🗑️ [collab-compress] 删除 %d 条 7 天前 op log "
                            "(affected %d docs, cutoff=%s)",
                            deleted_count, len(affected_ids), cutoff.isoformat(),
                        )
                    else:
                        logger.info(
                            "✅ [collab-compress] 健康: 无 7 天前 op log (cutoff=%s)",
                            cutoff.isoformat(),
                        )
                    return {
                        "status": "ok",
                        "deleted_count": deleted_count,
                        "cutoff": cutoff.isoformat(),
                    }
            finally:
                await engine.dispose()

        return asyncio.run(_run())
    except Exception as e:
        logger.error("❌ [collab-compress] 压缩失败: %s", e, exc_info=True)
        return {"status": "error", "error": str(e), "deleted_count": 0}
