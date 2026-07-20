"""录音会议 API — 创建/上传/停止/获取音频

录音机模式：零配置开录 → 上传 MinIO → 触发后处理
阶段 3（2026-06-12）：新增分片上传端点（边录边传）— PUT /audio-chunk,
POST /merge-chunks, GET /upload-status。
"""

from datetime import datetime, timezone
from fastapi import APIRouter, UploadFile, File, Query, HTTPException, Depends, Request
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
    request: Request,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建录音会议（零配置，自动生成标题）

    2026-07-16 +060: 加 Request 参数接收 User-Agent header 落库, 便于事后排查
       兼容性失败是哪类设备 (HarmonyOS ArkWeb / iOS Safari / 企业微信 X5 等)。
    """
    # 2026-07-16 +060: 截断 UA 防爆, VARCHAR(500) 上限
    user_agent = (request.headers.get('User-Agent') or '')[:500]
    now = datetime.now(timezone.utc).replace(tzinfo=None)  # 转为 naive datetime 适配 TIMESTAMP WITHOUT TIME ZONE
    meeting = Meeting(
        title="正在听会",  # 占位，commit 拿到 id 后补全为 "正在听会（ID {id}）"
        start_time=now,
        status="recording",
        recording_started_at=now,
        upload_status="pending",
        last_chunk_index=-1,  # 显式置 -1 便于孤儿扫描判断
        created_by=current_user.id,
        user_agent=user_agent,  # 2026-07-16 +060
    )
    db.add(meeting)
    await db.commit()
    await db.refresh(meeting)
    # 用真实 id 补全占位 title（与前端"正在听会（ID X）"格式对齐 — 旧版"听会 MM-DD HH:MM"
    # 时戳格式用户反馈不直观，"ID X" 明确表示录音中 + 数据库 id 标识）
    meeting.title = f"正在听会（ID {meeting.id}）"
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
    # 2026-07-16 修复 (安全加固): 越权守卫 — 任意登录用户可上传分片, 加 created_by 校验
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可上传分片")
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
    # 2026-07-16 修复 (安全加固): 越权守卫
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可合并分片")

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
    """
    停止录音，触发后处理。

    阶段 4 新增硬校验（2026-06-12 防御机制）：
    - 必须 last_chunk_index >= 0（至少收到一个 chunk）
    - 必须 audio_url 非空（旧版一次性上传）或 upload_status='completed'（新版 chunked）
    - 否则返回 400，会议保持 'recording' 状态（不触发 Celery）

    2026-07-16 安全加固: 加 created_by 越权守卫, 防止其他用户停止他人会议。
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    # 2026-07-16 修复 (安全加固): 越权守卫
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可停止录音")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    # ★ 校验：必须已上传音频
    last_idx = meeting.last_chunk_index
    has_audio = bool(meeting.audio_url) or (last_idx is not None and last_idx >= 0)
    if not has_audio:
        # 标 upload_status 让前端能区分失败原因
        meeting.upload_status = "never_uploaded"
        meeting.error_reason = "录音结束但未收到任何音频（last_chunk_index={}）".format(last_idx)
        await db.commit()
        raise HTTPException(
            status_code=400,
            detail=(
                "音频上传不完整 (last_chunk_index={}, audio_url={})。"
                " 请刷新页面让前端自动补传，或重新录制。"
            ).format(last_idx, meeting.audio_url)
        )

    # ★ 兜底：如果走 chunked 但还没 merge，尝试自动 merge
    if meeting.upload_status == "uploading" and not meeting.audio_url:
        try:
            logger.info(f"stop-recording 自动 merge 会议 {meeting_id} 的 chunks")
            await chunked_upload_service.merge_chunks(meeting_id)
            # 重新查 audio_url
            await db.refresh(meeting)
        except Exception as e:
            logger.error(f"自动 merge 失败: {e}")
            meeting.upload_status = "failed"
            meeting.error_reason = f"merge failed: {e}"
            await db.commit()
            raise HTTPException(status_code=500, detail=f"音频合并失败: {e}")

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


@router.post("/meetings/{meeting_id}/cancel-recording", status_code=200)
async def cancel_recording(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """录音启动失败时 rollback 会议 (status=recording → status=error)

    2026-07-16 新增 (#207 完整修复链): 前端 AudioRecorder.handleStart catch 块
      在录音启动失败 (getUserMedia timeout / MediaRecorder 不支持 / 权限拒绝)
      时调用此端点, 把已创建的会议从 recording 切到 error, 不留孤儿会议等
      Celery 60min 后自动清理。
    守卫: 仅 created_by=current_user 的 meeting 可取消。
    幂等: 非 recording 状态直接返 cancelled=False (不抛错)。

    2026-07-20 增 (P0): 同时清空 audio_url / last_chunk_index / total_chunks 字段
      防止"会议 status=error 但 DB 还有 audio_url 指向不存在的 MinIO 文件"导致
      MeetingDetailView AudioPlayer 永远 404。修法: 即使 start-recording 时 audio_url
      还没设置(只在首个 chunk 200 OK 后才写), 也防御性清空, 让前端不再有"audio_url
      字段存在但 MinIO 404"的孤儿状态。
    """
    import logging
    log = logging.getLogger("microbubble.meeting_recording")

    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可取消录音")
    if meeting.status != "recording":
        # 幂等: 已 stop / error / processing 不再处理
        return {"id": meeting.id, "status": meeting.status, "cancelled": False}
    meeting.status = "error"
    meeting.error_reason = "录音启动失败已取消 (前端 catch 块调用 cancel-recording)"
    # 2026-07-20 P0: 防御性清空音频字段, 防 7/11 MinIO wipe 类孤儿
    meeting.audio_url = None
    meeting.last_chunk_index = -1
    meeting.total_chunks = None
    meeting.upload_status = "cancelled"
    await db.commit()
    await db.refresh(meeting)
    log.info(
        f"Meeting {meeting_id} 取消录音: status recording → error, "
        f"audio_url/last_chunk_index/total_chunks 已清空"
    )
    return {
        "id": meeting.id,
        "status": meeting.status,
        "cancelled": True,
        "audio_url_cleared": True,
    }


import logging
logger = logging.getLogger("microbubble.meeting_recording")

