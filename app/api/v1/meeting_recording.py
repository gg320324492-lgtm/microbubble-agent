"""录音会议 API — 创建/上传/停止/获取音频

录音机模式：零配置开录 → 上传 MinIO → 触发后处理
"""

from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.file_service import file_service

router = APIRouter()


@router.post("/meetings/start-recording")
async def start_recording(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建录音会议（零配置，自动生成标题）"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # 转为 naive datetime 适配 TIMESTAMP WITHOUT TIME ZONE
    meeting = Meeting(
        title=f"听会 {now.strftime('%m-%d %H:%M')}",
        start_time=now,
        status="recording",
        recording_started_at=now,
        created_by=current_user.id,
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    return {
        "id": meeting.id,
        "title": meeting.title,
        "status": meeting.status,
        "recording_started_at": meeting.recording_started_at.isoformat(),
    }


@router.post("/meetings/{meeting_id}/upload-audio")
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """上传录音文件到 MinIO"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    file_data = await file.read()
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 上传到 MinIO
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"recording_{meeting_id}_{timestamp}.webm"
    upload_result = await file_service.upload_file(
        file_data=file_data,
        filename=filename,
        content_type=file.content_type or "audio/webm",
        prefix="recordings"
    )

    # 保存 object_name（而非 presigned URL，后者会过期）
    meeting.audio_url = upload_result.get("object_name")
    await db.commit()

    return {"audio_url": meeting.audio_url, "size": len(file_data)}


@router.post("/meetings/{meeting_id}/stop-recording")
async def stop_recording(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止录音，触发后处理"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # 转为 naive datetime 适配 TIMESTAMP WITHOUT TIME ZONE
    meeting.recording_ended_at = now
    meeting.end_time = now
    meeting.status = "processing"

    # 计算录音时长
    if meeting.recording_started_at:
        delta = now - meeting.recording_started_at
        meeting.audio_duration = int(delta.total_seconds())

    await db.commit()

    # 触发 Celery 后处理
    from app.services.post_meeting_tasks import post_meeting_process
    post_meeting_process.delay(meeting.id)

    return {
        "id": meeting.id,
        "status": "processing",
        "audio_duration": meeting.audio_duration,
    }


@router.get("/meetings/{meeting_id}/audio")
async def get_audio_url(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取录音文件 URL（回放用）"""
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if not meeting.audio_url:
        raise HTTPException(status_code=404, detail="无录音文件")

    # 生成 presigned URL（1 小时有效）
    url = file_service.get_url(meeting.audio_url, expires=3600)
    return {"audio_url": url, "duration": meeting.audio_duration}
