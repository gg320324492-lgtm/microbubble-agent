"""W2 T3 P2-A — Celery beat 主动清理过期 chat_share

设计要点（与 chat_history_tasks.cleanup_soft_deleted_sessions_task 一致）：
- 独立 create_celery_engine_and_session() + NullPool：避免全局 async_session 绑定主进程
  事件循环，与 asyncio.run() 新循环冲突 (CLAUDE.md 2026-06-30 #043 铁律)
- 始终 logger.warning（即便清理 0 个）→ 健康监控可见
- execute_backup_then_delete：先备份后 DELETE，PR6-P10 事故防复发 (误删可 JSON 恢复)

chat_share 业务语义：
- expires_at = NULL → 永不过期 (用户创建时可选)
- expires_at < NOW() → 过期即失效，必须清理
- 无 deleted_at 软删除字段 (与 chat_sessions 不同)，直接物理删除
- session_id FK ON DELETE CASCADE：会话被删时 share 自动清 (PR6-P10 兜底)
- 但 24h Redis TTL 不清理 PG 行的 bug：share 永久存在 + 仍能被外部 /chat/shares/{token} 查到
  → P2-A 主动清理填补此空缺

# W2 T3 决策依据：docs/session-polling-audit-2026-07-20.md
"""
import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import and_

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.chat_history import ChatShare
from app.services.cleanup_backup import execute_backup_then_delete

logger = logging.getLogger("microbubble.chat_share_cleanup")


@celery_app.task(name="app.services.chat_share_tasks.cleanup_expired_chat_shares_task")
def cleanup_expired_chat_shares_task():
    """Celery beat 任务：物理清除所有 expires_at < NOW() 的 chat_share。

    返回:
        dict: {"status": "ok"|"error", "deleted_count": int, "cutoff": iso, "error": str?}

    关键铁律 (W2 T3 P2-A)：
    1. expires_at IS NOT NULL 守卫：NULL = 永不过期 (业务语义)，绝不删
    2. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    3. deleted_count = 0 也要 logger.info 输出（健康监控 + 审计追溯）
    4. PR6-P10 备份：先 SELECT 全字段 → JSON 备份 → 再 DELETE (事故防复发)
    5. NullPool + engine.dispose() 避免连接池跨事件循环 (CLAUDE.md 2026-06-30 #043 复用)
    6. cutoff 用 timezone.utc → service 内部 _to_naive_datetime 转换 (CLAUDE.md 2026-06-05 教训)
    """
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                cutoff = datetime.now(timezone.utc)
                async with session_factory() as db:
                    deleted_count, _backup_path = await execute_backup_then_delete(
                        db,
                        model=ChatShare,
                        where_clause=and_(
                            ChatShare.expires_at.isnot(None),
                            ChatShare.expires_at < cutoff,
                        ),
                        table_name="chat_shares",
                        extra_metadata={
                            "cutoff_date": cutoff.isoformat(),
                            "strategy": "expires_at IS NOT NULL AND expires_at < NOW() (主动清理 24h Redis TTL 失效的 PG 行)",
                        },
                    )
                    if deleted_count > 0:
                        logger.warning(
                            f"🗑️ [chat_share] 自动清理: 物理删除 {deleted_count} 个过期 share "
                            f"(cutoff={cutoff.isoformat()})"
                        )
                    else:
                        logger.info(
                            f"✅ [chat_share] 健康: 当前无过期 share (cutoff={cutoff.isoformat()})"
                        )
                    return {"status": "ok", "deleted_count": deleted_count, "cutoff": cutoff.isoformat()}
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [chat_share] 自动清理失败: {e}", exc_info=True)
        return {"status": "error", "error": str(e), "deleted_count": 0}