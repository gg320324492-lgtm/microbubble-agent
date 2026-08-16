"""#P5 聊天图片附件上传端点

用户发图时:
1. 前端先 POST /api/v1/chat/upload-image (multipart form)
2. 后端存到 MinIO + 返回永久 URL
3. 前端把 URL 放到 userMsg.imageUrl (替代 blob URL)
4. 刷新后 imageUrl 仍有效 → 消息历史显示缩略图

路由:
- POST /api/v1/chat/upload-image  (multipart, 单张图)
"""
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.services.file_service import file_service


router = APIRouter(prefix="/chat", tags=["chat-image-upload"])


class ChatImageUploadResponse(BaseModel):
    """返回永久 URL + 元数据"""
    url: str
    filename: str
    size: int
    content_type: str
    width: Optional[int] = None
    height: Optional[int] = None


# 10MB 上限 (与 chat/image 端点一致)
MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@router.post("/upload-image", response_model=ChatImageUploadResponse)
async def upload_chat_image(
    image: UploadFile = File(..., description="图片文件 (jpg/png/gif/webp, ≤10MB)"),
    session_id: Optional[str] = Form(None, description="聊天 session id (便于按 session 分目录)"),
    current_user: Member = Depends(get_current_user),
):
    """上传聊天图片到 MinIO, 返回永久 URL。

    2026-08-16 #P5+: 解决"刷新后图片消失"问题 — 之前用 blob URL,
    刷新后失效; 改为 MinIO 永久 URL + 入库 chat_messages.image_url 字段。
    """
    if not image.content_type or image.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {image.content_type}。仅支持: {', '.join(ALLOWED_CONTENT_TYPES)}",
        )

    data = await image.read()
    if len(data) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"图片过大: {len(data)} bytes (上限 {MAX_IMAGE_SIZE // 1024 // 1024} MB)",
        )

    # 生成 object_name: chat_images/<user_id>/<ts>_<rand>.<ext>
    ext = (image.filename or "image").split(".")[-1] if "." in (image.filename or "") else "png"
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        ext = "png"
    ts = int(time.time() * 1000)
    rand = uuid.uuid4().hex[:8]
    user_id_str = str(current_user.id)
    object_name = f"chat_images/{user_id_str}/{ts}_{rand}.{ext}"

    # 上传到 MinIO
    try:
        from io import BytesIO
        file_service.client.put_object(
            file_service.bucket,
            object_name,
            BytesIO(data),
            length=len(data),
            content_type=image.content_type,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MinIO 上传失败: {str(e)}")

    # 生成前端可访问的 URL
    url = file_service.get_url(object_name)

    return ChatImageUploadResponse(
        url=url,
        filename=image.filename or f"image.{ext}",
        size=len(data),
        content_type=image.content_type,
    )