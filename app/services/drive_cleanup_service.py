"""课题组网盘 (Lab Group Drive) — 物理清除 service 函数

2026-07-02 PR6-P12+ 增量 — 从 drive_cleanup_tasks.py 拆出独立 service 函数
(与 chat_history_service.cleanup_soft_deleted_sessions 范式一致: task 顶层
做 Celery beat + NullPool + 二次确认守卫, service 内部跑 SQL + 物理删除).

设计要点:
- 不依赖 Celery: service 函数可被 Celery task / 普通 async context / 测试 mock 调用
- PR6-P10 backup_before_delete 复用: 2 张表 (drive_files + folders) 都先备份
- MinIO 物理删除: file_service.delete_file() 失败不阻塞 DB 硬删 (防御性)
- 孤儿 folder 防御性: 跳过有未清理子文件 / 子 folder 的, 避免误删
- 早返回兼容: 0 行时仍 commit (避免 nullify error)

铁律:
1. cutoff_date 接受 tz-aware / naive (内部统一 to_naive_datetime)
2. MinIO 删除失败 → logger.warning + minio_cleanup_failures += 1, 但 DB 行仍硬删
3. backup_before_delete 失败抛异常 → caller 决定是否中止清理
4. return dict 字段命名与 chat_history_service.cleanup_soft_deleted_sessions 一致 (deleted_count 等)
   但 drive 多张表, 所以拆 deleted_files + deleted_folders + skipped_folders

与 chat_history_service.cleanup_soft_deleted_sessions 关键差异:
- drive 多张表 (Knowledge + Folder), chat_history 单表 (ChatSession)
- drive 拆成 2 步: backup_rows_to_json + 显式 DELETE WHERE safe_to_delete
  (因为 folder 表需要先 SELECT 检查"是否有子文件 / 子 folder", 不是全删)
- chat_history 用 execute_backup_then_delete (1 步, 全删, 无安全检查)
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.folder import Folder
from app.models.knowledge import Knowledge
from app.services.cleanup_backup import backup_rows_to_json
from app.utils.datetime_utils import to_naive_datetime

logger = logging.getLogger("microbubble.drive_cleanup_service")


# 2026-07-12 死代码清理: 复用 app.utils.datetime_utils.to_naive_datetime
# (原本独立 inline, 现统一到 chat_history_service 同样的严格 astimezone(UTC) 版本)


async def clean_old_drive_files(db: AsyncSession, cutoff_date: datetime) -> dict:
    """物理清除 cutoff_date 之前软删除的 drive 文件 + 孤儿 folder.

    Args:
        db: AsyncSession (由 caller 提供, 通常是 Celery task 创建的 NullPool session)
        cutoff_date: 截止时间 (driver task 用 datetime.now(timezone.utc) - timedelta),
                     接受 tz-aware (UTC) 或 naive (本地)

    Returns:
        dict: {
            "deleted_files": int,           # 物理删除的 drive 文件数 (Knowledge 行)
            "deleted_folders": int,         # 物理删除的孤儿 folder 数 (Folder 行)
            "skipped_folders": int,         # 跳过有未清理子文件 / 子 folder 的 folder 数
            "minio_cleanup_failures": int,  # MinIO 对象删除失败数 (DB 行仍硬删)
        }

    设计要点:
    1. cleanup 顺序: 先 drive 文件 (Knowledge 表) → 再孤儿 folder (Folder 表)
    2. PR6-P10 backup_before_delete: 2 张表都走 backup_rows_to_json (1 步 backup + caller DELETE)
    3. MinIO 物理删除: 用 file_service.delete_file() 逐个清理, 失败不阻塞 DB 硬删
    4. 孤儿 folder 防御性检查: 跳过 child_folder_count > 0 或 child_file_count > 0 的
    5. 早返回兼容: 0 行时仍 commit 走完流程 (返回 {deleted_files:0, deleted_folders:0, ...})

    与 drive_cleanup_tasks.py Celery wrapper 的关系:
    - task 调 service + 持有 NullPool engine + logger.warning 输出 + 二次确认守卫
    - service 只关心 DB + MinIO 物理删除 + 计数, 不关心 Celery / asyncio.run / 守卫
    """
    cutoff_naive = to_naive_datetime(cutoff_date)
    if cutoff_naive is None:
        raise ValueError("cutoff_date 不能为 None (caller 应传 datetime.now(timezone.utc) - timedelta)")

    # ========== 1. 软删除的 drive 文件 (Knowledge 表) ==========
    drive_files_where = and_(
        Knowledge.storage_mode == "drive",
        Knowledge.deleted_at.isnot(None),
        Knowledge.deleted_at < cutoff_naive,
    )
    # PR6-P10 backup_before_delete: 先 SELECT → JSON 备份 → caller 自己 DELETE
    # (drive 文件无"安全检查"逻辑, 直接 DELETE WHERE where_clause 全部)
    deleted_file_count, _file_backup_path = await backup_rows_to_json(
        db,
        model=Knowledge,
        where_clause=drive_files_where,
        table_name="drive_files",
        extra_metadata={
            "cutoff_date": cutoff_naive.isoformat(),
            "strategy": "storage_mode='drive' AND deleted_at IS NOT NULL AND deleted_at < cutoff",
        },
    )
    # 物理删 DB 行
    if deleted_file_count > 0:
        delete_files_stmt = delete(Knowledge).where(drive_files_where)
        await db.execute(delete_files_stmt)

    # ========== 2. MinIO 物理删除 (防御性: 失败不阻塞 DB 硬删) ==========
    # 单独 SELECT 拿 file_path (backup_rows_to_json 只返 count, 不返 rows)
    stmt_files = select(Knowledge).where(drive_files_where)
    result_files = await db.execute(stmt_files)
    expired_files = result_files.scalars().all()

    minio_cleanup_failures = 0
    for f in expired_files:
        if not f.file_path:
            continue
        try:
            from app.services.file_service import file_service
            file_service.delete_file(f.file_path)
        except Exception as e:
            minio_cleanup_failures += 1
            logger.warning(
                f"⚠️ [drive_cleanup_service] MinIO 删除失败 id={f.id} "
                f"path={f.file_path}: {e}"
            )

    # ========== 3. 孤儿 Folder (无子文件 + 无子 folder) ==========
    folders_where = and_(
        Folder.deleted_at.isnot(None),
        Folder.deleted_at < cutoff_naive,
    )
    # PR6-P10 backup_before_delete: folder 表先备份 (全 expired_folders, 包括有子的)
    _folder_count, _folder_backup_path = await backup_rows_to_json(
        db,
        model=Folder,
        where_clause=folders_where,
        table_name="folders",
        extra_metadata={
            "cutoff_date": cutoff_naive.isoformat(),
            "strategy": "deleted_at IS NOT NULL AND deleted_at < cutoff (孤儿 folder, 无子文件/folder)",
        },
    )

    # 防御性: 跳过有未清理子文件的 folder (避免误删父级)
    stmt_folders = select(Folder).where(folders_where)
    result_folders = await db.execute(stmt_folders)
    expired_folders = result_folders.scalars().all()

    safe_to_delete = []
    skipped_folders = 0
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
        else:
            skipped_folders += 1

    # 物理删 safe_to_delete (不删 skipped_folders, 保护父级)
    if safe_to_delete:
        delete_folders_stmt = delete(Folder).where(
            Folder.id.in_([f.id for f in safe_to_delete])
        )
        await db.execute(delete_folders_stmt)

    # 早 commit (防止 long-running task 锁太久, 单次 commit 0.5-2s 完成)
    await db.commit()

    return {
        "deleted_files": deleted_file_count,
        "deleted_folders": len(safe_to_delete),
        "skipped_folders": skipped_folders,
        "minio_cleanup_failures": minio_cleanup_failures,
    }