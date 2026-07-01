"""file_requests REST API (PR7)

端点:
  POST   /api/v1/file-requests                           创建文件请求 (登录)
  GET    /api/v1/file-requests/my                       我创建的请求列表 (登录)
  POST   /api/v1/file-requests/{id}/deactivate          关闭请求 (owner only)
  GET    /api/v1/file-requests/{token}/info             公开信息 (无需登录)
  POST   /api/v1/file-requests/{token}/submit           公开上传 (无需登录, multipart)

错误统一响应:
  404 token 不存在
  410 inactive / expired
  422 字段缺失 / 扩展名不符 / 大小超限
"""
import logging
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, get_current_user_optional
from app.models.member import Member
from app.services.file_request_service import file_request_service

logger = logging.getLogger("microbubble.file_requests_api")
router = APIRouter(prefix="/file-requests", tags=["文件请求"])


# === Schemas ===

class CreateFileRequestBody(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    target_folder_id: Optional[int] = None
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)
    allowed_extensions: Optional[List[str]] = None
    require_uploader_name: bool = True
    max_file_size_mb: Optional[int] = Field(None, ge=1, le=500)


# === 登录端点 ===

@router.post("", status_code=201)
async def create_request(
    body: CreateFileRequestBody,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """创建文件请求

    返回含 token (公开 URL 用)
    """
    try:
        req = await file_request_service.create_request(
            db,
            created_by=user.id,
            title=body.title,
            description=body.description,
            target_folder_id=body.target_folder_id,
            expires_in_days=body.expires_in_days,
            allowed_extensions=body.allowed_extensions,
            require_uploader_name=body.require_uploader_name,
            max_file_size_mb=body.max_file_size_mb,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return {
        "id": req.id,
        "token": req.token,
        "title": req.title,
        "description": req.description,
        "target_folder_id": req.target_folder_id,
        "expires_at": req.expires_at.isoformat() if req.expires_at else None,
        "allowed_extensions": req.allowed_extensions or [],
        "require_uploader_name": req.require_uploader_name,
        "max_file_size_mb": req.max_file_size_mb,
        "submission_count": req.submission_count,
        "is_active": req.is_active,
        "created_at": req.created_at.isoformat() if req.created_at else None,
    }


@router.get("/my")
async def list_my_requests(
    include_inactive: bool = Query(False),
    limit: int = Query(100, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """我创建的文件请求列表"""
    items = await file_request_service.list_my_requests(
        db,
        created_by=user.id,
        include_inactive=include_inactive,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


@router.post("/{request_id}/deactivate", status_code=204)
async def deactivate_request(
    request_id: int,
    db: AsyncSession = Depends(get_db),
    user: Member = Depends(get_current_user),
):
    """关闭文件请求 (创建者 only)"""
    ok = await file_request_service.deactivate(
        db, request_id=request_id, user_id=user.id
    )
    if not ok:
        raise HTTPException(status_code=404, detail="不存在或越权")


# === 公开端点 (无需登录) ===

@router.get("/{token}/info")
async def get_public_info(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """公开查文件请求信息 (无需登录)

    404: token 不存在
    """
    info = await file_request_service.get_by_token(db, token=token)
    if not info:
        raise HTTPException(status_code=404, detail="文件请求不存在")
    return info


@router.post("/{token}/submit", status_code=201)
async def submit_file_public(
    token: str,
    uploader_name: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """公开提交文件 (无需登录, multipart)

    表单字段:
      file: 文件二进制
      uploader_name: 上传者姓名 (require_uploader_name=False 时可选)

    错误码:
      404: token 不存在
      410: inactive 或 expired
      422: 字段缺失 / 扩展名不符 / 大小超限 / 其他业务错误
    """
    # 读文件内容 (UploadFile 必须 await read())
    content = await file.read()
    file_size = len(content)
    file_name = file.filename or "upload.bin"
    content_type = file.content_type or "application/octet-stream"

    try:
        result = await file_request_service.submit_file(
            db,
            token=token,
            uploader_name=uploader_name,
            file_content=content,
            file_name=file_name,
            content_type=content_type,
            file_size=file_size,
        )
    except ValueError as e:
        err = str(e)
        # 区分 404 / 410 / 422
        if "不存在" in err:
            raise HTTPException(status_code=404, detail=err)
        if "关闭" in err or "过期" in err:
            raise HTTPException(status_code=410, detail=err)
        raise HTTPException(status_code=422, detail=err)

    return result
