"""Drive v2 PR16 — workspace 回收站 file_versions 保留期 service (2026-07-24, W68 第 13 批 C-3)

设计要点:
- 不依赖 Celery: service 函数可被 Celery task / 普通 async context / 测试 mock 调用
- 2 步策略 (与 chat_history 30 天保留对齐):
  * Step 1 (软删): 找 Knowledge.deleted_at < cutoff-30d 关联的 file_versions
    → set v.purged_at = now (软删, audit window 内可恢复)
  * Step 2 (物理删): 找 v.purged_at < cutoff-30d 的 file_versions
    → 删 MinIO 对象 + hard DELETE
- DRY: 用 backup_before_delete 复用 (PR6-P10) — JSON 备份到 /tmp
- 早返回兼容: 0 行时仍 commit 走完流程
- cutoff 接受 tz-aware / naive (内部统一 to_naive_datetime)

与 drive_cleanup_service.clean_old_drive_files 关键差异:
- 触发源不同:
  * clean_old_drive_files: 删 Knowledge 行本身 (storage_mode='drive')
  * 本 service: 删 Knowledge 行**关联**的 file_versions 行 (Knowledge.deleted_at 软删后)
- 软删 vs 硬删不同:
  * clean_old_drive_files: 直接 hard DELETE (Knowledge 行本身)
  * 本 service: 2 步 (软删 + 硬删, 留 audit window)
- 不删 Knowledge 行 (CASCADE 也不触发, 因是软删), 只清理 file_versions 派生数据

铁律:
1. cutoff_date 接受 tz-aware / naive (内部统一 to_naive_datetime)
2. MinIO 删除失败 → logger.warning + minio_cleanup_failures += 1, 但 DB 行仍硬删
3. backup_before_delete 失败抛异常 → caller 决定是否中止清理
4. return dict 字段命名与 chat_history_service.cleanup_soft_deleted_sessions 一致
5. Step 1 (软删) 用 system member.id (Celery auto-purge), Step 2 不写 purged_by
6. Step 1 不物理删 MinIO (audit window 内可能 restore), Step 2 才物理删
"""
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion
from app.models.knowledge import Knowledge
from app.services.cleanup_backup import backup_rows_to_json
from app.utils.datetime_utils import to_naive_datetime

logger = logging.getLogger("microbubble.drive_version_retention_service")


async def soft_delete_expired_versions(
    db: AsyncSession,
    cutoff_date: datetime,
    system_user_id: Optional[int] = None,
) -> dict:
    """Step 1: 软删 file_versions (关联 Knowledge.deleted_at < cutoff)

    策略:
    - 找 Knowledge.deleted_at IS NOT NULL AND Knowledge.deleted_at < cutoff
    - JOIN 拿这些 file 关联的 file_versions (purged_at IS NULL)
    - set v.purged_at = now, v.purged_by = system_user_id (Celery auto-purge = 系统用户)

    Args:
        db: AsyncSession (由 caller 提供, 通常是 Celery task 创建的 NullPool session)
        cutoff_date: 截止时间 (driver task 用 datetime.now(timezone.utc) - timedelta),
                     接受 tz-aware (UTC) 或 naive (本地)
        system_user_id: 写 v.purged_by 的 member.id (None 时跳过 FK 写入)

    Returns:
        dict: {
            "soft_deleted_count": int,         # Step 1 软删的 file_versions 行数
            "candidates_with_deleted_file": int,  # Knowledge.deleted_at < cutoff 的文件数
        }

    设计要点:
    1. JOIN Knowledge: drive_file_versions.file_id = Knowledge.id
       (FK ON DELETE CASCADE, 但 Knowledge 是软删所以不触发, 必须显式 JOIN)
    2. backup_before_delete: 不走 backup (软删不删行, 数据保留)
    3. 不删 MinIO 对象 (audit window 内可能 restore 关联 Knowledge)
    4. 早返回兼容: 0 行时仍 commit 走完流程
    """
    cutoff_naive = to_naive_datetime(cutoff_date)
    if cutoff_naive is None:
        raise ValueError("cutoff_date 不能为 None (caller 应传 datetime.now(timezone.utc) - timedelta)")

    # 1. 找 Knowledge.deleted_at < cutoff 的 file_id 列表
    expired_files_stmt = (
        select(Knowledge.id)
        .where(
            and_(
                Knowledge.deleted_at.isnot(None),
                Knowledge.deleted_at < cutoff_naive,
            )
        )
    )
    expired_file_ids = (await db.execute(expired_files_stmt)).scalars().all()

    if not expired_file_ids:
        return {
            "soft_deleted_count": 0,
            "candidates_with_deleted_file": 0,
        }

    # 2. 找这些 file 关联的 file_versions (purged_at IS NULL, 即未软删)
    versions_to_soft_delete_stmt = select(DriveFileVersion).where(
        and_(
            DriveFileVersion.file_id.in_(expired_file_ids),
            DriveFileVersion.purged_at.is_(None),
        )
    )
    result = await db.execute(versions_to_soft_delete_stmt)
    versions_to_soft_delete = result.scalars().all()

    soft_deleted_count = 0
    now = datetime.utcnow()
    for v in versions_to_soft_delete:
        v.purged_at = now
        if system_user_id is not None:
            v.purged_by = system_user_id
        soft_deleted_count += 1

    # 3. commit (single commit for batch)
    await db.commit()

    if soft_deleted_count > 0:
        logger.warning(
            f"🗂️ [drive_version_retention] 软删 {soft_deleted_count} 个 file_versions "
            f"(关联 {len(expired_file_ids)} 个已删 file, cutoff={cutoff_naive.isoformat()})"
        )
    else:
        logger.info(
            f"✅ [drive_version_retention] 健康: 无需软删 file_versions "
            f"(cutoff={cutoff_naive.isoformat()})"
        )

    return {
        "soft_deleted_count": soft_deleted_count,
        "candidates_with_deleted_file": len(expired_file_ids),
    }


async def hard_delete_expired_versions(
    db: AsyncSession,
    cutoff_date: datetime,
) -> dict:
    """Step 2: 物理删 file_versions (v.purged_at < cutoff)

    策略:
    - 找 v.purged_at IS NOT NULL AND v.purged_at < cutoff 的 file_versions
    - 物理删 MinIO 对象 (best effort, 失败不阻塞 DB 删)
    - hard DELETE DB 行
    - backup_before_delete (PR6-P10): 备份 JSON 到 /tmp (回滚兜底)

    Args:
        db: AsyncSession (由 caller 提供)
        cutoff_date: 截止时间 (driver task 用 datetime.now(timezone.utc) - timedelta)

    Returns:
        dict: {
            "hard_deleted_count": int,         # Step 2 物理删的 file_versions 行数
            "minio_cleanup_failures": int,     # MinIO 对象删除失败数 (DB 行仍硬删)
        }

    设计要点:
    1. PR6-P10 backup_before_delete: backup_rows_to_json 备份 → caller DELETE
    2. MinIO 物理删除: 用 file_service.delete_file() 逐个, 失败不阻塞 DB 硬删
    3. 早 commit (防止 long-running task 锁太久)
    """
    cutoff_naive = to_naive_datetime(cutoff_date)
    if cutoff_naive is None:
        raise ValueError("cutoff_date 不能为 None (caller 应传 datetime.now(timezone.utc) - timedelta)")

    # 1. 找候选: v.purged_at < cutoff AND v.purged_at IS NOT NULL
    versions_where = and_(
        DriveFileVersion.purged_at.isnot(None),
        DriveFileVersion.purged_at < cutoff_naive,
    )

    # 2. PR6-P10 backup_before_delete: 先 SELECT → JSON 备份 → caller DELETE
    deleted_count, _backup_path = await backup_rows_to_json(
        db,
        model=DriveFileVersion,
        where_clause=versions_where,
        table_name="drive_file_versions",
        extra_metadata={
            "cutoff_date": cutoff_naive.isoformat(),
            "strategy": "purged_at IS NOT NULL AND purged_at < cutoff (Step 2 物理删)",
        },
    )

    # 3. SELECT 拿 MinIO object keys (backup_rows_to_json 只返 count, 不返 rows)
    stmt_versions = select(DriveFileVersion).where(versions_where)
    result = await db.execute(stmt_versions)
    expired_versions = result.scalars().all()

    # 4. 物理删 MinIO 对象 (best effort)
    minio_cleanup_failures = 0
    for v in expired_versions:
        if not v.minio_object_key:
            continue
        try:
            from app.services.file_service import file_service
            file_service.delete_file(v.minio_object_key)
        except Exception as e:
            minio_cleanup_failures += 1
            logger.warning(
                f"⚠️ [drive_version_retention] MinIO 删除失败 id={v.id} "
                f"key={v.minio_object_key}: {e}"
            )

    # 5. 物理删 DB 行
    if deleted_count > 0:
        delete_versions_stmt = delete(DriveFileVersion).where(versions_where)
        await db.execute(delete_versions_stmt)

    # 6. 早 commit
    await db.commit()

    if deleted_count > 0:
        logger.warning(
            f"🗑️ [drive_version_retention] 物理删 {deleted_count} 个 file_versions "
            f"(MinIO 失败 {minio_cleanup_failures} 个, cutoff={cutoff_naive.isoformat()})"
        )
    else:
        logger.info(
            f"✅ [drive_version_retention] 健康: 无需物理删 file_versions "
            f"(cutoff={cutoff_naive.isoformat()})"
        )

    return {
        "hard_deleted_count": deleted_count,
        "minio_cleanup_failures": minio_cleanup_failures,
    }


async def get_retention_stats(db: AsyncSession) -> dict:
    """拿 file_versions 保留期统计 (admin endpoint 展示用)

    Returns:
        dict: {
            "total_versions": int,              # file_versions 总行数
            "active_versions": int,             # purged_at IS NULL (活跃)
            "soft_deleted_versions": int,       # purged_at IS NOT NULL (软删)
            "expired_versions": int,            # purged_at < (now - 30d) 待物理删
            "files_with_deleted_versions": int, # 关联 file 已软删的 versions 数
        }

    设计要点:
    1. 单 query 多聚合 (func.count + filter) — 避免 N+1
    2. expired 用 settings.DRIVE_VERSION_RETENTION_DAYS 默认值
    3. files_with_deleted_versions: JOIN Knowledge WHERE deleted_at IS NOT NULL
    """
    from app.config import settings
    from datetime import timedelta

    retention_days = getattr(settings, "DRIVE_VERSION_RETENTION_DAYS", 30)
    expired_cutoff = datetime.utcnow() - timedelta(days=retention_days)

    # 1. total / active / soft_deleted (单 query 多聚合)
    stmt_stats = select(
        func.count(DriveFileVersion.id).label("total"),
        func.count(DriveFileVersion.id).filter(
            DriveFileVersion.purged_at.is_(None)
        ).label("active"),
        func.count(DriveFileVersion.id).filter(
            DriveFileVersion.purged_at.isnot(None)
        ).label("soft_deleted"),
        func.count(DriveFileVersion.id).filter(
            and_(
                DriveFileVersion.purged_at.isnot(None),
                DriveFileVersion.purged_at < expired_cutoff,
            )
        ).label("expired"),
    )
    row = (await db.execute(stmt_stats)).one()
    total = row.total or 0
    active = row.active or 0
    soft_deleted = row.soft_deleted or 0
    expired = row.expired or 0

    # 2. files_with_deleted_versions: JOIN Knowledge WHERE Knowledge.deleted_at IS NOT NULL
    files_with_deleted_stmt = (
        select(func.count(DriveFileVersion.id))
        .join(Knowledge, DriveFileVersion.file_id == Knowledge.id)
        .where(Knowledge.deleted_at.isnot(None))
    )
    files_with_deleted = (await db.execute(files_with_deleted_stmt)).scalar() or 0

    return {
        "total_versions": total,
        "active_versions": active,
        "soft_deleted_versions": soft_deleted,
        "expired_versions": expired,
        "files_with_deleted_versions": files_with_deleted,
        "retention_days": retention_days,
    }