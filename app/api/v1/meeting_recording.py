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
from app.services.audio_metadata import ffprobe_duration_async

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
    user_agent = (request.headers.get('User-Agent') or '')[:settings.MEETING_USER_AGENT_MAX_LEN]
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
    """上传录音文件到 MinIO（兼容旧版一次性上传，新代码优先用 PUT /audio-chunk）

    2026-08-04 P0: 加上 created_by 越权守卫, 防止其他登录用户替换不属于自己的会议录音.
    一次性上传成功时同时置 total_chunks=1 / last_chunk_index=0, 避免与 `completed`
    状态字段语义不一致. 注意: 此端点不允许 admin 越权, 与 chunk/merge/stop 行为一致.
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    # 2026-08-04 P0: 越权守卫 (与其他端点一致)
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可上传录音")
    if meeting.status != "recording":
        raise HTTPException(status_code=400, detail="会议不在录音状态")

    file_data = await file.read()
    if len(file_data) == 0:
        raise HTTPException(status_code=400, detail="文件为空")

    # 2026-09-15 P0 (听会 09-14 事故): 一次性上传的体积守卫。
    # 事故现场: nginx client_max_body_size=50m 直接 RST 掉 162MB 的请求体,
    # 浏览器 axios 只抛 "Network Error" —— 用户完全不知道发生了什么, 也不知道该怎么自救。
    # 现在后端主动给一个 **带明确文案的 413**，前端拿到 detail 就能提示
    # "录音过大, 正在改用分片上传" 或引导用户重试。
    size_mb = len(file_data) / (1024 * 1024)
    if len(file_data) > settings.MAX_ONESHOT_UPLOAD_BYTES:
        logger.warning(
            f"一次性上传体积超限 (会议 {meeting_id}): {size_mb:.1f}MB > "
            f"{settings.MAX_ONESHOT_UPLOAD_BYTES / (1024 * 1024):.0f}MB, 拒绝并要求走分片"
        )
        raise HTTPException(
            status_code=413,
            detail=(
                f"录音体积 {size_mb:.0f}MB 超过一次性上传上限 "
                f"{settings.MAX_ONESHOT_UPLOAD_BYTES // (1024 * 1024)}MB。"
                "请改用分片上传（前端会自动切换），或缩短单次录音时长。"
            ),
        )

    # 上传到 MinIO
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # 2026-09-15 P0: 按真实容器定扩展名/MIME。原来硬编码 .webm + audio/webm，
    # 而 iOS Safari 的 MediaRecorder 只会产出 audio/mp4 —— 存成 webm 会让
    # 会议详情页的 <audio> 在 iOS 上无法回放。
    container_ext, container_mime = chunked_upload_service.sniff_audio_container(file_data)
    filename = f"recording_{meeting_id}_{timestamp}.{container_ext}"
    upload_result = await file_service.upload_file(
        file_data=file_data,
        filename=filename,
        content_type=file.content_type or container_mime,
        prefix="recordings"
    )

    # 保存 object_name（而非 presigned URL，后者会过期）
    meeting.audio_url = upload_result.get("object_name")
    meeting.upload_status = "completed"
    # 2026-08-04 P0: 一次性上传视为"整段上传完成 1 块", 避免 completed + last_chunk_index=-1/total_chunks=NULL 的矛盾状态
    meeting.last_chunk_index = 0
    meeting.total_chunks = 1
    # W2-7: 用 ffprobe 探测真实媒体时长，写入 media_duration_seconds
    # audio_duration 字段（墙钟差）保持不变，由 stop-recording 阶段写入
    try:
        media_dur = await ffprobe_duration_async(file_data)
        if media_dur is not None and media_dur > 0:
            meeting.media_duration_seconds = media_dur
    except Exception as e:  # noqa: BLE001 — best-effort 兜底
        logger.warning(f"upload-audio ffprobe 探测失败 (会议 {meeting_id}): {e}")
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


@router.post("/meetings/{meeting_id}/chunks/reset")
async def reset_chunks_endpoint(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """清空某会议已上传的所有 chunk，把分片计数复位。

    2026-09-15 P0 新增 (听会 09-14 事故修复链): iOS Safari 的 MediaRecorder
    不遵守 `start(timeslice)`，停止时只拿到一整段 blob。前端在"停止"阶段若
    判定实时分片流不完整，会改为把整段 blob 按固定字节数切片重传 —— 但此时
    MinIO 上可能残留早先零散上传的实时分片，且它们的 chunk_index 会与新切片
    撞号，导致最终 merge 出来的是两份录音交错拼接的垃圾。

    因此重传前必须先复位：删掉 MinIO 上该会议的全部 chunk，并把
    last_chunk_index / total_chunks / audio_url 归零。
    仅允许会议创建者调用；不改变 meeting.status。
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可重置分片")
    # 2026-09-15 P0: 状态守卫 —— reset 会把 audio_url/upload_status 清空,
    # 若会议已进入 processing/completed, 清空会直接毁掉已有录音与流水线结果。
    # 前端只在"停止上传前的重传准备"阶段调用, 此时 status 必然是 recording。
    if meeting.status != "recording":
        raise HTTPException(
            status_code=400,
            detail=f"会议不在录音状态 (status={meeting.status}), 拒绝重置分片",
        )

    try:
        deleted = await chunked_upload_service.delete_chunks(meeting_id)
    except Exception as e:
        logger.error(f"重置分片时删除 MinIO chunk 失败 (会议 {meeting_id}): {e}")
        raise HTTPException(status_code=500, detail=f"清空分片失败: {e}")

    # 同时清掉可能的 merged 产物，避免旧 merged 被误当成本次录音
    try:
        await chunked_upload_service.delete_merged(meeting_id)
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning(f"清理旧 merged 失败 (会议 {meeting_id}): {e}")

    meeting.last_chunk_index = -1
    meeting.total_chunks = 0
    meeting.audio_url = None
    meeting.upload_status = "pending"
    await db.commit()

    logger.info(f"会议 {meeting_id} 分片已复位: 删除 {deleted} 个 chunk")
    return {"meeting_id": meeting_id, "deleted_chunks": deleted, "reset": True}


@router.post("/meetings/{meeting_id}/merge-chunks")
async def merge_chunks_endpoint(
    meeting_id: int,
    mode: str = Query(
        "auto",
        pattern="^(auto|ffmpeg|raw)$",
        description="auto=按首片容器嗅探自动选; ffmpeg=concat demuxer (实时 webm 分片); "
                    "raw=字节级拼接 (整段 blob 的字节切片)",
    ),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    合并该会议的所有 chunk 成完整音频文件。

    调用时机：用户点"结束听会"（在 stop-recording 之前调一次）。
    失败模式：若 MinIO 上无 chunk，返回 400（前端应 fallback 提示）。

    2026-09-15 P0: 新增 `mode` 参数。这是听会 09-14 事故的第二段修复 ——
    - 桌面 Chrome 实时分片: 每片是独立的 WebM cluster 序列 → ffmpeg concat 可用
    - iOS Safari 整段切片: 每片只是同一个 MP4 容器的**原始字节区间**，不是
      独立可解析的媒体文件 → ffmpeg 解析必失败，必须走字节级拼接
    `auto` 会下载首片嗅探文件头自动选择，并在 ffmpeg 失败时回退到 raw。
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

    # auto: 嗅探首片决定合并策略
    effective_mode = mode
    if mode == "auto":
        effective_mode = "ffmpeg"
        try:
            chunks = await chunked_upload_service.list_chunks(meeting_id)
            if chunks:
                first = await file_service.download_file(chunks[0]["object_name"])
                ext, _ = chunked_upload_service.sniff_audio_container(first or b"")
                # mp4/m4a = 整段 blob 的字节切片 (iOS Safari) → 必须字节拼接
                effective_mode = "raw" if ext in ("m4a", "mp3", "ogg", "wav") else "ffmpeg"
        except Exception as e:  # noqa: BLE001 — 嗅探失败退回 ffmpeg 老路径
            logger.warning(f"合并模式嗅探失败 (会议 {meeting_id}): {e}, 退回 ffmpeg")

    try:
        if effective_mode == "raw":
            merged_object_name = await chunked_upload_service.merge_chunks_raw(meeting_id)
        else:
            try:
                merged_object_name = await chunked_upload_service.merge_chunks(meeting_id)
            except Exception as ffmpeg_err:
                # 兜底: ffmpeg 解析不了的分片集合，用字节拼接再试一次
                logger.warning(
                    f"ffmpeg 合并失败, 回退字节拼接 (会议 {meeting_id}): {ffmpeg_err}"
                )
                effective_mode = "raw"
                merged_object_name = await chunked_upload_service.merge_chunks_raw(meeting_id)
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
    # W2-7: 下载合并后的文件，ffprobe 探测真实媒体时长写入 media_duration_seconds
    # audio_duration（墙钟差）由 stop-recording 阶段写入，此处不动
    try:
        merged_bytes = await file_service.download_file(merged_object_name)
        if merged_bytes:
            media_dur = await ffprobe_duration_async(merged_bytes)
            if media_dur is not None and media_dur > 0:
                meeting.media_duration_seconds = media_dur
    except Exception as e:  # noqa: BLE001 — best-effort 兜底
        logger.warning(f"merge-chunks ffprobe 探测失败 (会议 {meeting_id}): {e}")
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
        "merge_mode": effective_mode,
    }


@router.post("/meetings/{meeting_id}/recording-heartbeat")
async def recording_heartbeat(
    meeting_id: int,
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """录音存活心跳（2026-09-15 P0 新增）。

    修的问题：会议 250 在 09-14 19:38:34 由杜同贺（iPhone）创建并开始听会，
    20:14:58 被 orphan_meeting_cleanup 判定"录音超过 30min 未 stop"标记为 error
    —— 但用户当时**仍在录音中**（21:18 才点停止）。原因是孤儿清理只看
    `recording_started_at < now - 30min`，完全不关心前端是否还活着，
    于是任何超过 30 分钟的会议都会被误杀。

    这里提供一个低成本存活信号：录音页面每 60s 调一次本端点，写一个
    Redis key（TTL 300s）。cleanup 扫描时若 key 仍存在则跳过该会议。
    这样"长会议"和"真孤儿（刷新/关页面走后无人再发心跳）"可以区分开。

    只做 Redis 写 + 轻量 DB 校验，不 commit，不污染 updated_at。
    """
    result = await db.execute(select(Meeting).where(Meeting.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="会议不存在")
    if meeting.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="仅创建者可上报录音心跳")

    from app.services.recording_heartbeat import touch_recording_heartbeat
    ok = await touch_recording_heartbeat(meeting_id)
    return {"meeting_id": meeting_id, "alive": bool(ok), "status": meeting.status}


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
    # 2026-09-15 P0 修复: 原实现只调 merge_chunks() 然后 db.refresh()，但 service 层
    # 不回写 Meeting 字段 → refresh 后 audio_url 依然是 None，会议"有音频但库里没记录"。
    # 现在显式接收 service 返回的 object_name 并落库；同时对 ffmpeg 解析不了的分片
    # 集合回退到字节级拼接（iOS Safari 整段 blob 切片场景）。
    if meeting.upload_status == "uploading" and not meeting.audio_url:
        try:
            logger.info(f"stop-recording 自动 merge 会议 {meeting_id} 的 chunks")
            try:
                merged_name = await chunked_upload_service.merge_chunks(meeting_id)
            except Exception as ffmpeg_err:
                logger.warning(
                    f"stop-recording ffmpeg 合并失败, 回退字节拼接 (会议 {meeting_id}): {ffmpeg_err}"
                )
                merged_name = await chunked_upload_service.merge_chunks_raw(meeting_id)
            meeting.audio_url = merged_name
            meeting.upload_status = "completed"
            await db.commit()
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

    # 2026-09-15 P0: 录音正常收尾 → 清心跳，避免 key 残留让真孤儿永远不被清理
    try:
        from app.services.recording_heartbeat import clear_recording_heartbeat
        await clear_recording_heartbeat(meeting_id)
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning(f"清录音心跳失败 (会议 {meeting_id}): {e}")

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

    # 2026-09-15 P0: 取消录音 → 清心跳（否则会一直"装活"挡住孤儿清理）
    try:
        from app.services.recording_heartbeat import clear_recording_heartbeat
        await clear_recording_heartbeat(meeting_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"取消录音时清心跳失败 (会议 {meeting_id}): {e}")
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

