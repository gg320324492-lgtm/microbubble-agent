"""文件上传 API"""

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.file_service import file_service
from app.services.drive_dedupe_service import (  # v2 PR17 文件秒传 (W68 第 14 批 B-1)
    check_dedupe,
    compute_bytes_hash,
    mark_dedupe_hit,
)

router = APIRouter()


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    prefix: str = Form("uploads", description="存储路径前缀"),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """通用文件上传

    v2 PR17 秒传: prefix 以 "drive" 开头时, 先算 sha256 查重 —
    命中当前用户已存在的活跃 drive 文件则秒返 (跳过 MinIO 上传, 零带宽).
    """
    if file.size and file.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"文件大小不能超过 {settings.MAX_UPLOAD_SIZE_MB}MB")

    file_data = await file.read()
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # v2 PR17: drive 场景先查重秒传 (user_id 隔离 + 已软删不命中, 在 service 层保证)
    file_hash = compute_bytes_hash(file_data)
    if prefix.startswith("drive"):
        hit = await check_dedupe(db, current_user.id, file_hash)
        if hit is not None:
            new_count = await mark_dedupe_hit(db, hit.id)
            return {
                "instant": True,
                "file_id": hit.id,
                "file_name": hit.file_name,
                "file_path": hit.file_path,
                "file_size": hit.file_size,
                "file_hash": file_hash,
                "dedupe_count": new_count,
            }

    try:
        result = await file_service.upload_file(
            file_data=file_data,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            prefix=prefix
        )
        # 回传 hash, 便于上游 create_file 写 knowledge.file_hash (后续秒传命中依据)
        if isinstance(result, dict):
            result.setdefault("file_hash", file_hash)
            result.setdefault("instant", False)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/upload/meeting/{meeting_id}")
async def upload_meeting_attachment(
    meeting_id: int,
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传会议附件"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    file_data = await file.read()
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    try:
        result = await file_service.upload_file(
            file_data=file_data,
            filename=file.filename or "unnamed",
            content_type=file.content_type or "application/octet-stream",
            prefix=f"meetings/{meeting_id}"
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.delete("/upload/{object_name:path}")
async def delete_file(
    object_name: str,
    current_user: Member = Depends(get_current_user)
):
    """删除文件"""
    try:
        file_service.delete_file(object_name)
        return {"message": "删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")
