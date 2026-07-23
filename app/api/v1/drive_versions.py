"""Drive v2 PR9 — File Version API Endpoints (2026-07-24)

5 个端点 (v2 PR9 文件版本管理):
- GET  /api/v1/drive/versions/files/{file_id}/versions                  → 列表
- POST /api/v1/drive/versions/files/{file_id}/versions                  → 上传新版本 (multipart)
- GET  /api/v1/drive/versions/versions/{version_id}/download            → 下载指定版本
- POST /api/v1/drive/versions/files/{file_id}/versions/{version_id}/rollback → 回滚
- DELETE /api/v1/drive/versions/versions/{version_id}                   → 删除某版

设计:
- 独立 router (FastAPI APIRouter), 在 main.py 注册到 /api/v1
- rate limit: 自动走 drive_upload (POST/DELETE) / drive_list (GET) tier (CLAUDE.md v31.2.6)
- 错误处理: 业务错误转 HTTPException + 状态码
"""
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.schemas.drive_file_version import (
    DriveFileVersionDeleteResponse,
    DriveFileVersionDownloadResponse,
    DriveFileVersionItem,
    DriveFileVersionListResponse,
    DriveFileVersionRollbackRequest,
    DriveFileVersionRollbackResponse,
    DriveFileVersionUploadResponse,
)
from app.services.drive_version_service import (
    DriveVersionService,
    DriveVersionServiceError,
)

router = APIRouter(tags=["网盘文件版本"])


# ============================================================
# 1. 列出文件所有版本
# ============================================================


@router.get(
    "/versions/files/{file_id}/versions",
    response_model=DriveFileVersionListResponse,
)
async def list_file_versions(
    file_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """列出文件所有版本历史 (按 version_number desc)

    权限: 走 _can_see_file (private 仅 owner)
    返回: file_id + file_name + count + items[]
    """
    svc = DriveVersionService(db)
    try:
        result = await svc.list_versions(file_id=file_id, current_user_id=user.id)
    except DriveVersionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return result


# ============================================================
# 2. 上传新版本 (multipart form)
# ============================================================


@router.post(
    "/versions/files/{file_id}/versions",
    response_model=DriveFileVersionUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_new_version(
    file_id: int,
    file: UploadFile = File(..., description="新版本文件 bytes"),
    comment: Optional[str] = Form(None, description="版本备注 (可选, max 500)"),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """上传新版本 (multipart form: file + comment)

    流程:
    - 校验 file_id 存在 + 权限
    - 读 UploadFile bytes
    - 写 MinIO (uploads/drive/{owner_id}/v{N+1}_{hash}_{ts}{ext})
    - 创建 DriveFileVersion 行 (is_current=1)
    - 旧 current 行翻 0
    - 更新 Knowledge 主表行

    返回: 新版本 DriveFileVersionItem + new_version_number + file_id
    """
    svc = DriveVersionService(db)
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="上传文件为空")

    try:
        new_v = await svc.create_version(
            file_id=file_id,
            new_content=content,
            new_filename=file.filename or f"v{file_id}.bin",
            new_content_type=file.content_type or "application/octet-stream",
            uploader_id=user.id,
            comment=comment,
        )
    except DriveVersionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 重新查 cur_file 拿最新 file_size/file_name
    from app.models.knowledge import Knowledge
    cur = await db.get(Knowledge, file_id)

    return DriveFileVersionUploadResponse(
        version=DriveFileVersionItem(
            id=new_v.id,
            file_id=new_v.file_id,
            version_number=new_v.version_number,
            minio_object_key=new_v.minio_object_key,
            size=new_v.size,
            uploader_id=new_v.uploader_id,
            uploader_name=user.name,
            comment=new_v.comment,
            is_current=bool(new_v.is_current),
            created_at=new_v.created_at.isoformat() if new_v.created_at else "",
        ),
        file_id=file_id,
        new_version_number=new_v.version_number,
        file_name=cur.file_name if cur else None,
        file_size=new_v.size,
    )


# ============================================================
# 3. 下载指定版本 (返回 presigned URL)
# ============================================================


@router.get(
    "/versions/versions/{version_id}/download",
    response_model=DriveFileVersionDownloadResponse,
)
async def download_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """下载指定版本 (返回临时 URL, 1 小时有效)

    权限: 走 _can_see_file (private 仅 owner)
    返回: version_id + download_url (presigned) + file_name + size
    """
    svc = DriveVersionService(db)
    try:
        result = await svc.get_version_download(
            version_id=version_id, current_user_id=user.id,
        )
    except DriveVersionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return result


# ============================================================
# 4. 回滚到历史版本
# ============================================================


@router.post(
    "/versions/files/{file_id}/versions/{version_id}/rollback",
    response_model=DriveFileVersionRollbackResponse,
)
async def rollback_to_version(
    file_id: int,
    version_id: int,
    body: DriveFileVersionRollbackRequest = DriveFileVersionRollbackRequest(),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """回滚到历史版本

    流程:
    - 校验目标版本存在 + file_id 匹配
    - 权限: 创建人 OR 管理员
    - 从目标版本 minio_object_key copy_object 到新路径
    - 创建新 DriveFileVersion 行 (version_number=cur+1, is_current=1)
    - 旧 current 行翻 0
    - 更新 Knowledge 主表

    返回: 新版本 + rolled_back_from + new_version_number
    """
    svc = DriveVersionService(db)
    try:
        new_v = await svc.rollback(
            file_id=file_id,
            version_id=version_id,
            user_id=user.id,
            new_comment=body.new_comment,
        )
    except DriveVersionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

    # 拿被回滚的版本号
    target = await db.get(type(new_v), version_id)
    rolled_from = target.version_number if target else -1

    return DriveFileVersionRollbackResponse(
        version=DriveFileVersionItem(
            id=new_v.id,
            file_id=new_v.file_id,
            version_number=new_v.version_number,
            minio_object_key=new_v.minio_object_key,
            size=new_v.size,
            uploader_id=new_v.uploader_id,
            uploader_name=user.name,
            comment=new_v.comment,
            is_current=bool(new_v.is_current),
            created_at=new_v.created_at.isoformat() if new_v.created_at else "",
        ),
        rolled_back_from=rolled_from,
        new_version_number=new_v.version_number,
        file_id=file_id,
    )


# ============================================================
# 5. 删除指定版本
# ============================================================


@router.delete(
    "/versions/versions/{version_id}",
    response_model=DriveFileVersionDeleteResponse,
)
async def delete_version(
    version_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """删除指定版本

    限制:
    - 不能删 is_current=1 的当前版本
    - 只能删"最新非当前版本" (防误删中间版 → rollback 悬空)

    权限: 创建人 OR 管理员
    """
    svc = DriveVersionService(db)
    try:
        result = await svc.delete_version(version_id=version_id, user_id=user.id)
    except DriveVersionServiceError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    return result