"""#043 Phase 7 — Celery 30 天清理 chat_history 软删除会话

设计要点（与 task_service.auto_purge_trash_task 一致）：
- 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
  async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
- NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
- engine.dispose() finally：清理连接
- 始终 logger.warning（即便删除 0 个）→ 健康监控可见

CASCADE 自动清除：
- chat_messages（session_id FK ON DELETE CASCADE）
- chat_shares（session_id FK ON DELETE CASCADE）

#043 完整铁律沉淀：CLAUDE.md 2026-06-30 #043 章节（待 commit 时回填）
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.celery import celery_app
from app.config import settings
from app.services.chat_history_service import cleanup_soft_deleted_sessions
from app.services.cleanup_safety import confirm_retention_param

logger = logging.getLogger("microbubble.chat_history_cleanup")


@celery_app.task(name="app.services.chat_history_tasks.cleanup_soft_deleted_sessions_task")
def cleanup_soft_deleted_sessions_task(retention_days: Optional[int] = None):
    """Celery beat 任务：物理清除 `retention_days` 天前软删除的会话。

    Args:
        retention_days: 保留天数（None 时使用 settings.CHAT_HISTORY_RETENTION_DAYS，默认 30）

    Returns:
        dict: {"status": "ok"|"error", "deleted_count": int, "cutoff": iso, "error": str?}

    #043 Phase 7 关键铁律：
    1. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    2. deleted_count = 0 也要 logger.info 输出（健康监控 + 审计追溯）
    3. NullPool 避免连接池跨事件循环（CLAUDE.md 2026-06-03 垃圾桶清理铁律复用）
    4. cutoff 用 timezone.utc（CLAUDE.md 2026-06-05 tz-aware 教训）
    """
    days = retention_days if retention_days is not None else getattr(
        settings, "CHAT_HISTORY_RETENTION_DAYS", 30
    )

    # PR6-P11 二次确认守卫: retention_days != settings 默认值时延迟 + warn
    # 事故防复发: PR6-P9 误传 retention_days=0 删 31 条 (chat_history 同模式风险)
    guard = confirm_retention_param(
        retention_days=retention_days,
        default=getattr(settings, "CHAT_HISTORY_RETENTION_DAYS", 30),
        task_name="cleanup_soft_deleted_sessions_task",
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
            engine = create_async_engine(
                settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                poolclass=NullPool,
            )
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                # chat_history_service.cleanup_soft_deleted_sessions 内部会 commit
                # cutoff 传 tz-aware（service 内部 _to_naive_datetime 不再需要，但保持一致）
                async with session_factory() as db:
                    deleted_count = await cleanup_soft_deleted_sessions(db, cutoff)
                    if deleted_count > 0:
                        logger.warning(
                            f"🗑️ [chat_history] 自动清理: 永久删除 {deleted_count} 个超过 {days} 天的软删除会话 "
                            f"(cutoff={cutoff.isoformat()})"
                        )
                    else:
                        logger.info(
                            f"✅ [chat_history] 健康: 当前无超过 {days} 天的过期会话 "
                            f"(cutoff={cutoff.isoformat()})"
                        )
                    return {"status": "ok", "deleted_count": deleted_count, "cutoff": cutoff.isoformat()}
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [chat_history] 自动清理失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "deleted_count": 0}
