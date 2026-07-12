"""2026-07-02 v2 PR6-P9 — Celery 30 天清理 file_mentions 通知

设计要点（与 chat_history_tasks 范式一致）：
- 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
  async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
- NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
- engine.dispose() finally：清理连接
- 始终 logger.warning / logger.info（即便删除 0 个）→ 健康监控可见

CASCADE 自动清除：无（file_mentions 无外键引用，物理删除安全）

铁律沉淀：CLAUDE.md 2026-07-02 v2 PR6-P9 章节
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app
from app.config import settings
from app.services.notification_service import cleanup_old_mentions
from app.services.cleanup_safety import confirm_retention_param_auto
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("microbubble.file_mention_cleanup")


@celery_app.task(name="app.services.file_mention_tasks.cleanup_old_mentions_task")
def cleanup_old_mentions_task(retention_days: Optional[int] = None):
    """Celery beat 任务：物理清除 `retention_days` 天前的 file_mentions 通知。

    一刀切 (is_read=true/false 都删)，简化逻辑 + 防止未读通知无限堆积。

    Args:
        retention_days: 保留天数（None 时使用 settings.MENTION_RETENTION_DAYS，默认 30）

    Returns:
        dict: {"status": "ok"|"error", "deleted_count": int, "cutoff": iso, "error": str?}

    PR6-P9 关键铁律（与 chat_history_tasks 范式一致）：
    1. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    2. deleted_count = 0 也要 logger.info 输出（健康监控 + 审计追溯）
    3. NullPool 避免连接池跨事件循环（CLAUDE.md 2026-06-03 垃圾桶清理铁律复用）
    4. cutoff 用 timezone.utc（CLAUDE.md 2026-06-05 tz-aware 教训）
    """
    days = retention_days if retention_days is not None else getattr(
        settings, "MENTION_RETENTION_DAYS", 30
    )

    # PR6-P11 + PR6-P12 二次确认守卫: retention_days != settings 默认值时延迟 + warn
    # 事故防复发: PR6-P9 误传 retention_days=0 删 31 条 production file_mentions
    # PR6-P12: 用统一入口 confirm_retention_param_auto, 根据 settings.CLEANUP_CRITICAL_GUARDED_TASKS
    #          自动选择友好模式 (延迟 + warn) 或严格模式 (or_skip 直接拒绝)
    guard = confirm_retention_param_auto(
        retention_days=retention_days,
        default=getattr(settings, "MENTION_RETENTION_DAYS", 30),
        task_name="app.services.file_mention_tasks.cleanup_old_mentions_task",
    )
    if not guard["proceed"]:
        return {
            "status": "skipped",
            "reason": guard["reason"],
            "retention_days": guard["effective_days"],
            "deleted_count": 0,
        }
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                # cleanup_old_mentions 内部会 commit
                async with session_factory() as db:
                    deleted_count = await cleanup_old_mentions(db, cutoff)
                    if deleted_count > 0:
                        logger.warning(
                            f"🗑️ [file_mention] 自动清理: 永久删除 {deleted_count} 条超过 {days} 天的通知 "
                            f"(cutoff={cutoff.isoformat()})"
                        )
                    else:
                        logger.info(
                            f"✅ [file_mention] 健康: 当前无超过 {days} 天的过期通知 "
                            f"(cutoff={cutoff.isoformat()})"
                        )
                    return {"status": "ok", "deleted_count": deleted_count, "cutoff": cutoff.isoformat()}
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [file_mention] 自动清理失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "deleted_count": 0}