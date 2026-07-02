"""课题组网盘 (Lab Group Drive) — Celery beat 软删除清理任务
2026-07-01

设计要点（与 chat_history_tasks.py / task_service.auto_purge_trash_task 一致）：
- 独立 create_async_engine(NullPool) + async_sessionmaker：避免全局
  async_session 绑定主进程事件循环，与 asyncio.run() 新循环冲突
- NullPool：禁用连接池，每任务创建新连接避免跨 loop 复用
- engine.dispose() finally：清理连接
- 始终 logger.warning (即便删除 0 个) → 健康监控可见

清理范围：
- Knowledge 表: storage_mode='drive' AND deleted_at < cutoff 的记录
- Folder 表: deleted_at < cutoff 的记录 (级联检查: 不能有未清理的子文件)

清理顺序:
1. 先清理 Knowledge 文件 (含 drive_extracted 升级后的 kb 文件也清, 用户可能想撤销升级)
2. 再清理 Folder (无子节点的孤儿 folder)
3. 最后调用 file_service.delete_file() 物理删除 MinIO 对象

调度频率: 1h (与 task/chat 清理对齐)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, delete, and_, func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.celery import celery_app
from app.config import settings
from app.models.knowledge import Knowledge
from app.models.folder import Folder
from app.services.cleanup_backup import backup_rows_to_json
from app.services.cleanup_safety import confirm_retention_param

logger = logging.getLogger("microbubble.drive_cleanup")


@celery_app.task(name="app.services.drive_cleanup_tasks.cleanup_expired_drive_files_task")
def cleanup_expired_drive_files_task(retention_days: Optional[int] = None):
    """Celery beat 任务：物理清除 retention_days 天前软删除的 drive 文件 + 孤儿 folder。

    Args:
        retention_days: 保留天数 (None 时使用 settings.DRIVE_RETENTION_DAYS, 默认 3)

    Returns:
        dict: {"status": "ok"|"error", "deleted_files": int, "deleted_folders": int, "minio_orphans": int, "cutoff": iso, "error": str?}

    关键铁律：
    1. 任务失败不抛 → return {status: error} 让 Celery 不重试链
    2. deleted_count = 0 也要 logger.info 输出 (健康监控 + 审计追溯)
    3. NullPool 避免连接池跨事件循环 (CLAUDE.md 2026-06-03 垃圾桶清理铁律复用)
    4. cutoff 计算后转 tz-naive (CLAUDE.md 2026-06-05 tz-aware vs naive 教训)
       — Knowledge.deleted_at 是 TIMESTAMP WITHOUT TIME ZONE, asyncpg 不能直接比较
    5. 必须清 MinIO 对象 (否则 bucket 无限增长) — file_service.delete_file()
    """
    days = retention_days if retention_days is not None else getattr(
        settings, "DRIVE_RETENTION_DAYS", 3
    )

    # PR6-P11 二次确认守卫: retention_days != settings 默认值时延迟 + warn
    # 事故防复发: PR6-P9 误传 retention_days=0 删 31 条 (drive_cleanup 同模式风险)
    guard = confirm_retention_param(
        retention_days=retention_days,
        default=getattr(settings, "DRIVE_RETENTION_DAYS", 3),
        task_name="cleanup_expired_drive_files_task",
    )
    if not guard["proceed"]:
        return {
            "status": "skipped",
            "reason": guard["reason"],
            "retention_days": guard["effective_days"],
            "deleted_files": 0,
            "deleted_folders": 0,
        }
    try:
        async def _run():
            engine = create_async_engine(
                settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
                poolclass=NullPool,
            )
            session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            try:
                # 计算 cutoff: UTC-aware → 立即转 tz-naive (PostgreSQL TIMESTAMP 列要求)
                cutoff_aware = datetime.now(timezone.utc) - timedelta(days=days)
                cutoff = cutoff_aware.replace(tzinfo=None)

                async with session_factory() as db:
                    # ========== 1. 软删除的 drive 文件 ==========
                    # 范围: storage_mode='drive' AND deleted_at < cutoff
                    # 注: drive_extracted 升级后的 kb 文件也清, 因为用户主动软删表示想撤销
                    drive_files_where = and_(
                        Knowledge.storage_mode == "drive",
                        Knowledge.deleted_at.isnot(None),
                        Knowledge.deleted_at < cutoff,
                    )
                    # PR6-P10: 先备份后 DELETE (事故防复发, PR6-P9 误删 31 条教训)
                    file_count, _file_backup_path = await backup_rows_to_json(
                        db,
                        model=Knowledge,
                        where_clause=drive_files_where,
                        table_name="drive_files",
                        extra_metadata={
                            "cutoff_date": cutoff.isoformat(),
                            "strategy": "storage_mode='drive' AND deleted_at IS NOT NULL AND deleted_at < cutoff",
                        },
                    )
                    stmt_files = select(Knowledge).where(drive_files_where)
                    result_files = await db.execute(stmt_files)
                    expired_files = result_files.scalars().all()

                    # 物理删除 MinIO 对象 + 硬删 DB 行
                    deleted_file_count = 0
                    minio_cleanup_failures = []
                    for f in expired_files:
                        try:
                            if f.file_path:
                                from app.services.file_service import file_service
                                file_service.delete_file(f.file_path)
                        except Exception as e:
                            minio_cleanup_failures.append({
                                "knowledge_id": f.id,
                                "file_path": f.file_path,
                                "error": str(e),
                            })
                            logger.warning(
                                f"⚠️ [drive_cleanup] MinIO 删除失败 id={f.id} "
                                f"path={f.file_path}: {e}"
                            )

                    # 硬删 DB 行 (无论 MinIO 是否删成功, DB 行必须清)
                    if expired_files:
                        delete_files_stmt = delete(Knowledge).where(
                            and_(
                                Knowledge.storage_mode == "drive",
                                Knowledge.deleted_at.isnot(None),
                                Knowledge.deleted_at < cutoff,
                            )
                        )
                        await db.execute(delete_files_stmt)
                        deleted_file_count = len(expired_files)

                    # ========== 2. 孤儿 Folder (无子文件 + 无子 folder) ==========
                    # 找出过期 folder
                    folders_where = and_(
                        Folder.deleted_at.isnot(None),
                        Folder.deleted_at < cutoff,
                    )
                    # PR6-P10: 先备份后 DELETE (事故防复发)
                    _folder_count, _folder_backup_path = await backup_rows_to_json(
                        db,
                        model=Folder,
                        where_clause=folders_where,
                        table_name="folders",
                        extra_metadata={
                            "cutoff_date": cutoff.isoformat(),
                            "strategy": "deleted_at IS NOT NULL AND deleted_at < cutoff (孤儿 folder, 无子文件/folder)",
                        },
                    )
                    stmt_folders = select(Folder).where(folders_where)
                    result_folders = await db.execute(stmt_folders)
                    expired_folders = result_folders.scalars().all()

                    # 防御性: 跳过有未清理子文件的 folder (避免误删)
                    safe_to_delete = []
                    for folder in expired_folders:
                        # 查子 folder
                        child_folder_count = await db.scalar(
                            select(func.count(Folder.id)).where(
                                and_(
                                    Folder.parent_id == folder.id,
                                    Folder.deleted_at.is_(None),
                                )
                            )
                        )
                        # 查子文件
                        child_file_count = await db.scalar(
                            select(func.count(Knowledge.id)).where(
                                and_(
                                    Knowledge.folder_id == folder.id,
                                    Knowledge.deleted_at.is_(None),
                                )
                            )
                        )
                        if child_folder_count == 0 and child_file_count == 0:
                            safe_to_delete.append(folder)

                    if safe_to_delete:
                        delete_folders_stmt = delete(Folder).where(
                            Folder.id.in_([f.id for f in safe_to_delete])
                        )
                        await db.execute(delete_folders_stmt)

                    await db.commit()

                    # ========== 3. 日志输出 ==========
                    deleted_folder_count = len(safe_to_delete)
                    skipped_folders = len(expired_folders) - len(safe_to_delete)

                    if deleted_file_count > 0 or deleted_folder_count > 0:
                        logger.warning(
                            f"🗑️ [drive_cleanup] 自动清理: 删除 {deleted_file_count} 个 drive 文件, "
                            f"{deleted_folder_count} 个孤儿 folder (跳过 {skipped_folders} 个非空 folder) "
                            f"(cutoff={cutoff.isoformat()}, retention={days}天)"
                        )
                    else:
                        logger.info(
                            f"✅ [drive_cleanup] 健康: 当前无超过 {days} 天的过期 drive 文件/folder "
                            f"(cutoff={cutoff.isoformat()})"
                        )

                    return {
                        "status": "ok",
                        "deleted_files": deleted_file_count,
                        "deleted_folders": deleted_folder_count,
                        "skipped_folders": skipped_folders,
                        "minio_cleanup_failures": len(minio_cleanup_failures),
                        "cutoff": cutoff.isoformat(),
                    }
            finally:
                await engine.dispose()

        result = asyncio.run(_run())
        return result
    except Exception as e:
        logger.error(f"❌ [drive_cleanup] 自动清理失败: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "deleted_files": 0,
            "deleted_folders": 0,
        }