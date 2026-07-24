"""Drive v2 PR16 — workspace 回收站 file_versions 保留期 Celery task (2026-07-24)

设计要点（与 chat_history_tasks.py / drive_cleanup_tasks.py 一致）：
- 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
  async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
- NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
- engine.dispose() finally：清理连接
- 始终 logger.warning (即便删除 0 个) → 健康监控可见
- 2 步策略 (软删 + 物理删):
  * Step 1: 软删关联 Knowledge.deleted_at < (now - 30d) 的 file_versions
  * Step 2: 物理删 v.purged_at < (now - 30d) 的 file_versions

**与 chat_history / drive_cleanup 关键差异:**
- chat_history / drive_cleanup: 单步直接 hard DELETE (无 audit window)
- 本 task: 2 步 (软删 + 物理删), 留 audit window 30 天可恢复
- 双步都依赖 settings.DRIVE_VERSION_RETENTION_DAYS (默认 30 天)
- Step 1 需要 system_user_id (Celery 自动跑无用户, 写系统用户 ID)

**职责拆分 (与 drive_cleanup 范式一致):**
- service 文件 (drive_version_retention_service.py): 物理清理逻辑 (3 函数)
  * soft_delete_expired_versions() — Step 1 软删
  * hard_delete_expired_versions() — Step 2 物理删
  * get_retention_stats() — admin stats
- 本 task 文件: thin Celery wrapper (~80 行)
  * NullPool engine + 二次确认守卫 + asyncio.run + logger.warning 输出

调度频率: 每日 04:00 (凌晨低峰, 与 task/chat/drive cleanup 1h 调度不同, 因 drive_versions 体量小)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.config import settings
from app.services.cleanup_safety import confirm_retention_param_auto
from app.services.drive_version_retention_service import (
    hard_delete_expired_versions,
    soft_delete_expired_versions,
)
from app.models.member import Member

logger = logging.getLogger("microbubble.drive_version_retention")


# 2026-07-24 W68 第 13 批 C-3: Celery auto-purge 用的系统用户 ID
# 设计: 用 member.id = 1 (第一个注册用户, 通常是 admin/leader), 找不到则 None
# 复用 chat_history / drive_cleanup 同模式 (NULL 表示系统匿名)
SYSTEM_USER_ID_FALLBACK = 1


async def _resolve_system_user_id(db) -> Optional[int]:
    """拿 Celery auto-purge 用的系统用户 ID (member 表第一行 admin)

    Returns:
        Optional[int]: system member.id, 找不到时返回 None (FK 写入跳过)
    """
    from sqlalchemy import select
    stmt = select(Member.id).where(Member.role.in_(["admin", "leader"])).order_by(Member.id).limit(1)
    row = (await db.execute(stmt)).first()
    if row is None:
        return None
    return row[0]


@celery_app.task(name="app.services.drive_version_retention_tasks.cleanup_expired_versions_task")
def cleanup_expired_versions_task(retention_days: Optional[int] = None):
    """Celery beat 任务: 2 步清理 file_versions (软删 + 物理删)

    Args:
        retention_days: 保留天数 (None 时使用 settings.DRIVE_VERSION_RETENTION_DAYS, 默认 30)

    Returns:
        dict: {
            "status": "ok"|"skipped"|"error",
            "soft_deleted_count": int,
            "hard_deleted_count": int,
            "minio_cleanup_failures": int,
            "system_user_id": Optional[int],
            "cutoff": iso,
            "error": str?,
        }

    关键铁律:
    1. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    2. 0 个也要 logger.info 输出 (健康监控 + 审计追溯)
    3. NullPool 避免连接池跨事件循环 (CLAUDE.md 2026-06-03 垃圾桶清理铁律复用)
    4. cutoff 计算后转 tz-naive (CLAUDE.md 2026-06-05 tz-aware vs naive 教训)
    5. PR6-P11+ 二次确认守卫: confirm_retention_param_auto 自动选严格/友好模式
    6. 2 步策略: 先软删 (Step 1) → 再物理删 (Step 2, 用同一切 cutoff - retention_days)
       — 单次 Celery run 完整跑完 2 步, 简化运维
    """
    days = retention_days if retention_days is not None else getattr(
        settings, "DRIVE_VERSION_RETENTION_DAYS", 30
    )

    # PR6-P11 + PR6-P12 二次确认守卫: retention_days != settings 默认值时延迟 + warn
    guard = confirm_retention_param_auto(
        retention_days=retention_days,
        default=getattr(settings, "DRIVE_VERSION_RETENTION_DAYS", 30),
        task_name="app.services.drive_version_retention_tasks.cleanup_expired_versions_task",
    )
    if not guard["proceed"]:
        return {
            "status": "skipped",
            "reason": guard["reason"],
            "retention_days": guard["effective_days"],
            "soft_deleted_count": 0,
            "hard_deleted_count": 0,
            "minio_cleanup_failures": 0,
        }
    try:
        async def _run():
            engine, session_factory = create_celery_engine_and_session()
            try:
                # cutoff: 同一时间点用于 Step 1 + Step 2
                # Step 1: Knowledge.deleted_at < cutoff (关联 file 软删超 N 天)
                # Step 2: v.purged_at < cutoff (file_versions 软删超 N 天)
                cutoff_aware = datetime.now(timezone.utc) - timedelta(days=days)

                async with session_factory() as db:
                    # 拿系统用户 ID (用于 Step 1 写 purged_by FK)
                    system_user_id = await _resolve_system_user_id(db)
                    if system_user_id is None:
                        system_user_id = SYSTEM_USER_ID_FALLBACK

                    # === Step 1: 软删 file_versions ===
                    step1_result = await soft_delete_expired_versions(
                        db, cutoff_aware, system_user_id=system_user_id
                    )

                    # === Step 2: 物理删 file_versions ===
                    step2_result = await hard_delete_expired_versions(
                        db, cutoff_aware
                    )

                    # 日志输出 (drive 多步统计)
                    soft = step1_result["soft_deleted_count"]
                    hard = step2_result["hard_deleted_count"]
                    minio_fails = step2_result["minio_cleanup_failures"]
                    if soft > 0 or hard > 0:
                        logger.warning(
                            f"🗂️ [drive_version_retention] 自动清理: 软删 {soft} 个 + 物理删 {hard} 个 "
                            f"file_versions (MinIO 失败 {minio_fails} 个, "
                            f"cutoff={cutoff_aware.isoformat()}, retention={days}天, "
                            f"system_user={system_user_id})"
                        )
                    else:
                        logger.info(
                            f"✅ [drive_version_retention] 健康: 当前无超过 {days} 天的过期 file_versions "
                            f"(cutoff={cutoff_aware.isoformat()})"
                        )

                    return {
                        "status": "ok",
                        "soft_deleted_count": soft,
                        "hard_deleted_count": hard,
                        "minio_cleanup_failures": minio_fails,
                        "system_user_id": system_user_id,
                        "cutoff": cutoff_aware.isoformat(),
                    }
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [drive_version_retention] 自动清理失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "soft_deleted_count": 0,
            "hard_deleted_count": 0,
            "minio_cleanup_failures": 0,
        }