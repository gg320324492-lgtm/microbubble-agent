"""Drive v2 PR9 — File Version Diff API Endpoints (2026-07-24)

2 个端点 (v2 PR9 文件版本对比):
- GET /api/v1/drive/versions/files/{file_id}/diff?from=N&to=M
    → 文本走 difflib.unified_diff, 二进制走 metadata-only diff
- GET /api/v1/drive/versions/files/{file_id}/versions/{version_id}/preview?head_lines=N
    → 取该版本前 N 行 (用于对比 UI 左侧窗)

设计:
- 独立 router (FastAPI APIRouter), 在 main.py 注册到 /api/v1
- rate limit: 自动走 drive_read (GET) tier (CLAUDE.md v31.2.6)
- 错误处理: 业务错误转 HTTPException + 状态码

注意: 路径前缀由 main.py 设置 (/api/v1), 这里只填后段.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.schemas.drive_version_diff import (
    VersionDiffResponse,
    VersionPreviewResponse,
    VersionMeta,
)
from app.services.drive_version_diff_service import (
    DriveVersionDiffService,
    DriveVersionDiffServiceError,
)

router = APIRouter(tags=["网盘文件版本对比"])


# ============================================================
# 1. 版本对比 (diff)
# ============================================================


@router.get(
    "/versions/files/{file_id}/diff",
    response_model=VersionDiffResponse,
)
async def diff_versions(
    file_id: int,
    from_version: int = Query(
        ..., alias="from", ge=1,
        description="起始版本号 (1-indexed version_number, 必须 >= 1)",
    ),
    to_version: int = Query(
        ..., alias="to", ge=1,
        description="目标版本号 (1-indexed version_number, 必须 >= 1)",
    ),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """对比文件的两个版本

    文本文件 (ext 白名单: txt/md/py/js/ts/json/yaml/csv/html/css/sql/sh 等):
    返回 unified_diff + 变更行号 + 增删行数

    二进制文件 (pdf/zip/image 等): 返回 metadata diff (size_delta + uploader_delta)
    单版本相同时: 空 diff (unified_diff=None, size_delta=0, uploader_delta=False)
    """
    svc = DriveVersionDiffService(db)
    try:
        result = await svc.compare_versions(
            file_id=file_id,
            from_version_number=from_version,
            to_version_number=to_version,
            current_user_id=user.id,
        )
    except DriveVersionDiffServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    return VersionDiffResponse(
        file_id=result.file_id,
        file_name=result.file_name,
        from_version_number=result.from_version_number,
        from_version_id=result.from_version_id,
        to_version_number=result.to_version_number,
        to_version_id=result.to_version_id,
        is_text=result.is_text,
        unified_diff=result.unified_diff,
        changed_lines=result.changed_lines,
        additions=result.additions,
        deletions=result.deletions,
        size_delta=result.size_delta,
        uploader_delta=result.uploader_delta,
        from_meta=VersionMeta(**result.from_meta),
        to_meta=VersionMeta(**result.to_meta),
    )


# ============================================================
# 2. 版本预览 (preview, 取前 N 行)
# ============================================================


@router.get(
    "/versions/files/{file_id}/versions/{version_id}/preview",
    response_model=VersionPreviewResponse,
)
async def preview_file_version(
    file_id: int,
    version_id: int,
    head_lines: int = Query(
        200, ge=1, le=2000,
        description="最多返回前 N 行 (默认 200, max 2000, 防爆内存)",
    ),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """预览某版本前 N 行 (用于对比 UI 左侧窗)

    - 文本文件: 返回 preview_lines (truncated 提示是否完整)
    - 二进制文件: 返回空 preview_lines + note 说明
    """
    svc = DriveVersionDiffService(db)
    try:
        result = await svc.preview_version(
            version_id=version_id,
            current_user_id=user.id,
            head_lines=head_lines,
        )
    except DriveVersionDiffServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 二次校验: 该 version 必须属于 file_id (防御 URL 串联)
    if result["file_id"] != file_id:
        raise HTTPException(
            status_code=400,
            detail=f"版本 id={version_id} 不属于文件 id={file_id}",
        )

    return VersionPreviewResponse(**result)
