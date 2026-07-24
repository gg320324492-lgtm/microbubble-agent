"""Drive v2 PR16 — workspace 回收站 admin endpoint (2026-07-24, W68 第 13 批 C-3)

背景 (W68 第 4 批 #2 agent 调研发现):
- workspace admin 删除文件后, 关联 file_versions 行成孤儿
- 当前无 admin endpoint 监控/手动触发清理
- 本文件补齐 2 endpoint: stats 查询 + 手动触发清理

2 个 endpoint (全部 admin/leader only):
  - GET  /api/v1/admin/drive/retention-stats  → 返 stats 字典
  - POST /api/v1/admin/drive/cleanup-now      → 手动触发 Celery task (sync 等待)

数据源:
  - drive_file_versions 表 (purged_at 列, 070_drive_version_retention migration 加)
  - app/services/drive_version_retention_service.py (3 service 函数)
  - app/services/drive_version_retention_tasks.py (Celery wrapper)

设计决策:
  - 复用 `app.api.v1.admin.get_current_admin` (与 admin_audit.py / admin_kb_monitor.py 同款)
  - cleanup-now endpoint: 直接调 service 函数 sync 执行 (不走 Celery .delay())
    * admin 手动触发要立即看到结果
    * Celery beat 调度走独立路径 (每日 04:00)
  - retention_days 参数: 与 Celery task 行为一致 (二次确认守卫复用)
  - 复用 confirm_retention_param_auto (PR6-P11+ 守卫模式)

参考:
  - app/api/v1/admin_kb_monitor.py (3 endpoint admin 鉴权范式)
  - app/api/v1/admin_audit.py (get_current_admin 复用)
  - app/services/drive_version_retention_service.py (service 函数)
  - app/services/drive_version_retention_tasks.py (Celery wrapper)
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin import get_current_admin
from app.config import settings
from app.core.database import get_db
from app.models.member import Member
from app.services.cleanup_safety import confirm_retention_param_auto
from app.services.drive_version_retention_service import (
    get_retention_stats,
    hard_delete_expired_versions,
    soft_delete_expired_versions,
)

logger = logging.getLogger("microbubble.drive_admin_retention")

router = APIRouter(prefix="/admin/drive", tags=["Drive 回收站管理 (admin)"])


# ============================================================================
# GET /admin/drive/retention-stats — 保留期统计
# ============================================================================


@router.get("/retention-stats")
async def get_drive_retention_stats(
    db: AsyncSession = Depends(get_db),
    current_admin: Member = Depends(get_current_admin),
):
    """拿 file_versions 保留期统计 (admin/leader only)

    Returns:
        dict: {
            "total_versions": int,                # file_versions 总行数
            "active_versions": int,               # purged_at IS NULL (活跃)
            "soft_deleted_versions": int,         # purged_at IS NOT NULL (软删)
            "expired_versions": int,              # 待物理删 (超 30 天)
            "files_with_deleted_versions": int,   # 关联 file 已删的 versions 数
            "retention_days": int,                # 当前 retention 配置
        }

    设计要点:
    - 单 query 多聚合 (get_retention_stats 内部), 避免 N+1
    - 不暴露 SQL 细节, admin 看数字即可
    """
    stats = await get_retention_stats(db)
    return stats


# ============================================================================
# POST /admin/drive/cleanup-now — 手动触发清理 (同步执行)
# ============================================================================


@router.post("/cleanup-now")
async def cleanup_drive_versions_now(
    retention_days: Optional[int] = Query(
        None,
        description="覆盖 settings.DRIVE_VERSION_RETENTION_DAYS (None = 用默认值)",
        ge=0,
        le=365,
    ),
    db: AsyncSession = Depends(get_db),
    current_admin: Member = Depends(get_current_admin),
):
    """手动触发 2 步 file_versions 清理 (admin/leader only, 同步执行)

    行为:
    1. 二次确认守卫: retention_days != 默认值时延迟 + warn (复用 PR6-P11+ 模式)
    2. Step 1 软删: 关联 Knowledge.deleted_at < cutoff 的 file_versions
    3. Step 2 物理删: v.purged_at < cutoff 的 file_versions
    4. 返详细计数给 admin 看

    Args:
        retention_days: 覆盖默认 retention 天数 (None 用 settings, 默认 30)
        db: AsyncSession (FastAPI Depends)
        current_admin: admin/leader user

    Returns:
        dict: {
            "status": "ok"|"skipped"|"error",
            "retention_days": int,
            "soft_deleted_count": int,
            "hard_deleted_count": int,
            "minio_cleanup_failures": int,
            "system_user_id": Optional[int],
            "cutoff": iso,
            "executed_by": int,  # admin user.id
            "error": str?,
        }

    设计要点:
    - 同步执行 (不走 Celery .delay()), admin 要立即看到结果
    - 用 request session (Depends(get_db)), 不是 Celery NullPool engine
    - 二次确认守卫: retention_days != settings 默认值时延迟 0.5s + warn
    - 系统用户 ID: 复用 task 文件同样的 _resolve_system_user_id 逻辑
    """
    default_days = getattr(settings, "DRIVE_VERSION_RETENTION_DAYS", 30)

    # 二次确认守卫 (PR6-P11+ 范式)
    guard = confirm_retention_param_auto(
        retention_days=retention_days,
        default=default_days,
        task_name="admin.cleanup_drive_versions_now",
    )
    if not guard["proceed"]:
        return {
            "status": "skipped",
            "reason": guard["reason"],
            "retention_days": guard["effective_days"],
            "soft_deleted_count": 0,
            "hard_deleted_count": 0,
            "minio_cleanup_failures": 0,
            "system_user_id": None,
            "cutoff": None,
            "executed_by": current_admin.id,
        }

    days = guard["effective_days"]

    try:
        # 拿系统用户 ID (复用 task 同款逻辑)
        from app.services.drive_version_retention_tasks import _resolve_system_user_id
        system_user_id = await _resolve_system_user_id(db)
        if system_user_id is None:
            from app.services.drive_version_retention_tasks import SYSTEM_USER_ID_FALLBACK
            system_user_id = SYSTEM_USER_ID_FALLBACK

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # Step 1: 软删
        step1_result = await soft_delete_expired_versions(
            db, cutoff, system_user_id=system_user_id
        )

        # Step 2: 物理删
        step2_result = await hard_delete_expired_versions(db, cutoff)

        soft = step1_result["soft_deleted_count"]
        hard = step2_result["hard_deleted_count"]
        minio_fails = step2_result["minio_cleanup_failures"]

        logger.warning(
            f"[admin_cleanup] admin={current_admin.id} ({current_admin.username}) "
            f"手动清理: 软删 {soft} + 物理删 {hard} 个 file_versions "
            f"(MinIO 失败 {minio_fails} 个, retention={days}天)"
        )

        return {
            "status": "ok",
            "retention_days": days,
            "soft_deleted_count": soft,
            "hard_deleted_count": hard,
            "minio_cleanup_failures": minio_fails,
            "system_user_id": system_user_id,
            "cutoff": cutoff.isoformat(),
            "executed_by": current_admin.id,
        }
    except Exception as e:
        logger.error(
            f"❌ [admin_cleanup] admin={current_admin.id} 手动清理失败: {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "error": str(e),
            "retention_days": days,
            "soft_deleted_count": 0,
            "hard_deleted_count": 0,
            "minio_cleanup_failures": 0,
            "system_user_id": None,
            "cutoff": None,
            "executed_by": current_admin.id,
        }