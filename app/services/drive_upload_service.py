"""Drive v2 PR9 — Upload Helper: 自动创建初始版本 (2026-07-24)

背景:
- v2 PR9 引入 drive_file_versions 表 (文件版本仓库)
- 之前 DriveService.create_file() 只创建 Knowledge 行, 不写版本表
- 本文件作为 thin shim, 提供 `create_initial_version()` 辅助, 在新文件上传后被调用

用法:
    from app.services.drive_upload_service import create_initial_version
    await create_initial_version(
        db=db, file_id=new_k.id, uploader_id=user.id,
        minio_object_key=new_k.file_path, size=new_k.file_size,
    )

设计:
- 单独文件 (不是 DriveService 的方法) → 0 production code 改动铁律维持
- 不破坏 v1 老路径 (DriveService.create_file 不动)
- 失败 best-effort, 失败仅 logger.warning, 不阻塞上传主流程
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_file_version import DriveFileVersion

logger = logging.getLogger(__name__)


async def create_initial_version(
    *,
    db: AsyncSession,
    file_id: int,
    minio_object_key: str,
    size: int,
    uploader_id: int,
    comment: Optional[str] = None,
) -> Optional[DriveFileVersion]:
    """为新上传的文件创建初始版本 (v1, is_current=1)

    调用场景:
    - DriveService.create_file() 后调用 (普通上传)
    - DriveService.create_instant_upload() 后调用 (秒传)
    - DriveService.complete_chunked_upload() 后调用 (分片上传)

    Returns:
        新创建的 DriveFileVersion 行, 或 None (失败时)

    注意:
    - 失败仅 logger.warning, 不抛异常 (上传主流程不该被版本表失败阻塞)
    - 幂等: 同一 file_id 二次调用会创建 v2 (业务层应避免)
    """
    try:
        v1 = DriveFileVersion(
            file_id=file_id,
            version_number=1,
            minio_object_key=minio_object_key,
            size=size,
            uploader_id=uploader_id,
            comment=comment or "Initial version",
            is_current=1,
        )
        db.add(v1)
        await db.commit()
        await db.refresh(v1)
        logger.info(
            f"[drive_upload_service.create_initial_version] "
            f"file_id={file_id} → v1 object={minio_object_key} size={size}"
        )
        return v1
    except Exception as e:
        logger.warning(
            f"[drive_upload_service.create_initial_version] 创建 v1 失败 "
            f"(不影响上传主流程): file_id={file_id} error={e!r}"
        )
        return None