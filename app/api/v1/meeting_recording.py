"""录音会议 API — 创建/上传/停止/获取音频

录音机模式：零配置开录 → 上传 MinIO → 触发后处理
阶段 3（2026-06-12）：新增分片上传端点（边录边传）— PUT /audio-chunk,
POST /merge-chunks, GET /upload-status。
"""

from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.file_service import file_service
from app.services.chunked_upload_service import chunked_upload_service

router = APIRouter()


@router.post("/meetings/start-recording")
async def start_recording(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建录音会议（零配置，自动生成标题）"""
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # 转为 naive datetime 适配 TIMESTAMP WITHOUT TIME ZONE
    # 标题使用北京时间（UTC+8）
    local_now = now + timedelta(hours=8)
    meeting = Meeting(
        title=f"听会 {local_now.strftime('%m-%d %H:%M')}",
        start_time=now,
        status="recording",
        recording_started_at=now,
        upload_status="pending",
        last_chunk_index=-1,  # 显式置 -1 便于孤儿扫描判断
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
    """上传录音文件到 MinIO（兼容旧版一次性上传，新代码优先用 PUT /audio-chunk）"""
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
    meeting.upload_status = "completed"
    await db.commit()

    return {"audio_url": meeting.audio_url, "size": len(file_data)}


@router.put("/meetings/{meeting_id}/audio-chunk")
async def upload_audio_chunk(
    meeting_id: int,
    chunk_index: int = Query(..., ge=0),
    file: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    上传单个分片（边录边传，2026-06-12 新增）。

    前端每 5s 调一次此端点，MinIO 上存储路径为
    `recordings/{meeting_id}/chunks/chunk_{idx:05d}.webm`。

    失败模式：
    - 4xx 客户端错（参数错 / 状态错）→ 立即抛错，前端停止后续 chunk
    - 5xx 服务端错 → 前端按指数退避重试
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.status not in ("recording",):
        raise HTTPException(status_code=400, detail=f"会议不在录音状态 (status={meeting.status})")

    blob = await file.read()
    if not blob:
        raise HTTPException(status_code=400, detail="chunk 为空")

    # 写 MinIO
    await chunked_upload_service.save_chunk(meeting_id, chunk_index, blob)

    # 原子更新 last_chunk_index（允许乱序到达，保留最大值）
    if (meeting.last_chunk_index is None) or (chunk_index > meeting.last_chunk_index):
        meeting.last_chunk_index = chunk_index
    meeting.total_chunks = (meeting.total_chunks or 0) + 1
    meeting.upload_status = "uploading"
    await db.commit()

    return {
        "chunk_index": chunk_index,
        "size": len(blob),
        "last_chunk_index": meeting.last_chunk_index,
        "total_chunks": meeting.total_chunks,
    }


@router.post("/meetings/{meeting_id}/merge-chunks")
async def merge_chunks_endpoint(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    合并该会议的所有 chunk 成完整 webm 文件。

    调用时机：用户点"结束听会"（在 stop-recording 之前调一次）。
    失败模式：若 MinIO 上无 chunk，返回 400（前端应 fallback 提示）。
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")

    if (meeting.last_chunk_index is None) or (meeting.last_chunk_index < 0):
        raise HTTPException(
            status_code=400,
            detail=f"无可合并的 chunk (last_chunk_index={meeting.last_chunk_index})"
        )

    try:
        merged_object_name = await chunked_upload_service.merge_chunks(meeting_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"合并 chunk 失败: {e}")
        meeting.upload_status = "failed"
        meeting.error_reason = f"merge failed: {e}"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"合并失败: {e}")

    # 更新会议字段
    meeting.audio_url = merged_object_name
    meeting.upload_status = "completed"
    meeting.audio_size_bytes = None  # 让后处理阶段重新计算
    await db.commit()

    # 顺手清掉 chunks
    try:
        deleted = await chunked_upload_service.delete_chunks(meeting_id)
        logger.info(f"会议 {meeting_id} 合并后清理 {deleted} 个 chunk")
    except Exception as e:
        logger.warning(f"清理 chunk 失败 (会议 {meeting_id}): {e}")

    return {
        "audio_url": meeting.audio_url,
        "chunks_merged": meeting.last_chunk_index + 1,
    }


@router.get("/meetings/{meeting_id}/upload-status")
async def get_upload_status(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    查询分片上传状态。供前端刷新页面后恢复上传使用。
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    return {
        "meeting_id": meeting_id,
        "status": meeting.status,
        "upload_status": meeting.upload_status,
        "last_chunk_index": meeting.last_chunk_index,
        "total_chunks": meeting.total_chunks,
        "audio_url": meeting.audio_url,
    }


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


import logging
logger = logging.getLogger("microbubble.meeting_recording")

