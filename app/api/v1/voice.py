"""语音相关API"""

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import asyncio
import io
import json
import time
import wave

import logging
from app.voice.asr import asr_service
from app.voice.tts import tts_service
from app.voice.recorder import recorder_manager
from app.voice.pipeline import meeting_pipeline, MeetingPipeline, RingBuffer, SAMPLE_RATE
from app.voice.vad import VADEngine
from app.voice.segmenter import LiveSegmenter
from app.agent.core import agent
from app.core.database import get_db, async_session
from app.core.security import get_current_user, decode_token
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.meeting_service import MeetingService
from app.services.meeting_ai_polish import polish_segments_with_lock
from app.services.speaker_unidentified_service import get_unenrolled_participants

logger = logging.getLogger("microbubble.voice")

router = APIRouter()


class TTSRequest(BaseModel):
    """语音合成请求"""
    text: str
    voice: str = "xiaoxiao"
    rate: str = "+0%"
    volume: str = "+0%"


class ASRResponse(BaseModel):
    """语音识别响应"""
    text: str
    language: str
    language_probability: float
    duration: float


@router.post("/voice/asr", response_model=ASRResponse)
async def speech_to_text(
    audio: UploadFile = File(...),
    language: str = "zh",
    current_user: Member = Depends(get_current_user)
):
    """语音识别（ASR）"""
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail="请上传音频文件")

    audio_data = await audio.read()

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        result = await asr_service.transcribe(
            audio_data=audio_data,
            language=language
        )

        return ASRResponse(
            text=result["text"],
            language=result["language"],
            language_probability=result["language_probability"],
            duration=result["duration"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音识别失败: {str(e)}")


@router.post("/voice/tts")
async def text_to_speech(
    request: TTSRequest,
    current_user: Member = Depends(get_current_user)
):
    """语音合成（TTS）"""
    try:
        audio_data = await tts_service.synthesize(
            text=request.text,
            voice=request.voice,
            rate=request.rate,
            volume=request.volume
        )

        return StreamingResponse(
            io.BytesIO(audio_data),
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "attachment; filename=speech.mp3"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")


@router.post("/voice/chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = "default",
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """语音对话（端到端）"""
    audio_data = await audio.read()

    if len(audio_data) == 0:
        raise HTTPException(status_code=400, detail="音频文件为空")

    try:
        asr_result = await asr_service.transcribe(audio_data)
        user_text = asr_result["text"]

        if not user_text.strip():
            return {
                "input_text": "",
                "response_text": "我没有听清，请再说一遍。",
                "audio_url": None
            }

        agent_result = await agent.chat(
            message=user_text,
            session_id=session_id,
            db=db
        )
        response_text = agent_result["content"]

        audio_response = await tts_service.synthesize(text=response_text)

        return StreamingResponse(
            io.BytesIO(audio_response),
            media_type="audio/mpeg",
            headers={
                "X-User-Text": user_text,
                "X-Response-Text": response_text,
                "Content-Disposition": "attachment; filename=response.mp3"
            }
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"语音对话失败: {str(e)}")


@router.get("/voice/voices")
async def get_voices(
    current_user: Member = Depends(get_current_user)
):
    """获取可用语音列表"""
    return {
        "voices": tts_service.get_voice_options()
    }


@router.websocket("/ws/voice/{user_id}")
async def voice_websocket(websocket: WebSocket, user_id: str, token: str = ""):
    """实时语音对话WebSocket"""
    # 认证：从query参数获取token
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    session_id = f"voice_{user_id}"

    from app.core.database import async_session
    async with async_session() as db:
        try:
            while True:
                data = await websocket.receive_bytes()

                try:
                    asr_result = await asr_service.transcribe(data)
                    user_text = asr_result["text"]

                    await websocket.send_json({
                        "type": "asr",
                        "text": user_text
                    })

                    if not user_text.strip():
                        continue

                    agent_result = await agent.chat(
                        message=user_text,
                        session_id=session_id,
                        db=db
                    )
                    response_text = agent_result["content"]

                    await websocket.send_json({
                        "type": "chat",
                        "text": response_text
                    })

                    audio_data = await tts_service.synthesize(text=response_text)
                    await websocket.send_bytes(audio_data)

                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })

        except WebSocketDisconnect:
            await agent.clear_session(session_id)


@router.websocket("/ws/meeting/{meeting_id}/transcript")
async def meeting_transcript_ws(
    websocket: WebSocket,
    meeting_id: int,
    token: str = ""
):
    """会议实时转写WebSocket — 支持发言者切换"""
    # 认证：从query参数获取token
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    recorder = await recorder_manager.start_meeting_recording(meeting_id)
    current_speaker = "参会者"

    try:
        while True:
            data = await websocket.receive()

            if "text" in data:
                # JSON 控制消息（发言者切换等）
                try:
                    msg = __import__("json").loads(data["text"])
                    if msg.get("type") == "speaker_change":
                        current_speaker = msg.get("speaker", "参会者")
                except Exception:
                    pass
                continue

            if "bytes" in data:
                # 音频数据
                audio_bytes = data["bytes"]
                recorder.recorder.add_audio_data(audio_bytes)

                async for segment in asr_service.transcribe_stream(audio_bytes):
                    entry = {
                        "text": segment["text"],
                        "start": segment["start"],
                        "end": segment["end"],
                        "speaker": current_speaker,
                    }
                    recorder.add_transcript_entry(entry)

                    await websocket.send_json({
                        "type": "transcript",
                        **entry,
                    })

    except WebSocketDisconnect:
        result = await recorder_manager.stop_meeting_recording()

        # 保存转写结果到会议记录，并自动分析
        analysis_result = None
        if result and result.get("transcript"):
            try:
                async with async_session() as db:
                    from sqlalchemy import select
                    meeting_result = await db.execute(
                        select(Meeting).where(Meeting.id == meeting_id)
                    )
                    meeting = meeting_result.scalar_one_or_none()
                    if meeting:
                        meeting.transcript = result["transcript"]
                        meeting.status = "completed"
                        await db.commit()

                        # 自动分析转写内容，提取摘要、要点、任务
                        try:
                            meeting_service = MeetingService(db)
                            analysis_result = await meeting_service.process_meeting_transcript(meeting_id)
                            logger.info(f"会议 {meeting_id} 分析完成: {len(analysis_result.get('tasks_created', []))} 个任务已创建")
                        except Exception as e:
                            logger.error(f"会议转写分析失败: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"保存会议转写失败: {e}")

        try:
            ended_msg = {
                "type": "meeting_ended",
                "meeting_id": meeting_id,
                "duration": result.get("duration", 0) if result else 0
            }
            if analysis_result:
                ended_msg["analysis"] = analysis_result
            await websocket.send_json(ended_msg)
        except Exception:
            pass


@router.websocket("/ws/meeting/{meeting_id}/live")
async def meeting_live_ws(
    websocket: WebSocket,
    meeting_id: int,
    token: str = ""
):
    """会议实时声纹转写 WebSocket — VAD + 声纹识别 + ASR

    支持文字消息控制：
    - {"type": "ai_chat", "text": "用户问题"} — AI 实时对话
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4001)
            return
    except Exception:
        await websocket.close(code=4001)
        return

    await websocket.accept()

    # 顶层 try/except（2026-06-02 修复）：
    # 之前函数体无顶层兜底，VAD 加载 / transcript_history 发送 / pubsub.subscribe
    # 等任何异常会静默逃逸到 Uvicorn，WS 立即关闭且无错误日志
    try:
        # Wave 2b: 发送 transcript_history（最近 60s 拉历史）
        from app.services.meeting_transcript_buffer import get_recent_transcript
        history = await get_recent_transcript(meeting_id, seconds=60)
        await websocket.send_json({"type": "transcript_history", "entries": history})

        # 创建段满检测器（每条 WS 独立实例，无状态污染）
        segmenter = LiveSegmenter(silence_threshold_ms=1500, max_segment_ms=8000)

        # 创建 per-WS VAD + MeetingPipeline 实例（避免 VAD 状态污染，wave 2a 任务 5）
        vad = VADEngine()
        pipeline = MeetingPipeline(
            vad_engine=vad,
            asr_service=asr_service,
            voiceprint_service=None,  # 使用默认 voiceprint_service（DI 注入默认）
        )

        # audio_level 旁路推送（每 100ms 推最近音频的 RMS，wave 2a 任务 10）
        audio_queue: asyncio.Queue = asyncio.Queue(maxsize=20)
        level_task = asyncio.create_task(_audio_level_loop(websocket, audio_queue))

        # 每条 WS 独立 DB 会话（声纹识别 + speaker_mapping 查询需要）
        async with async_session() as db:
            # 预加载 meeting（speaker_mapping 用于将原始声纹 label 映射为真实姓名）
            meeting = None
            try:
                meeting = await db.get(Meeting, meeting_id)
            except Exception as e:
                logger.error(f"加载 meeting {meeting_id} 失败: {e}")

            # Wave 2b: 多设备订阅
            from app.core.redis import get_redis
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe(
                f"transcript:{meeting_id}",
                f"ai_reply:{meeting_id}",
                f"speaker_mapping:{meeting_id}",
            )
            broadcast_task = asyncio.create_task(
                _broadcast_loop(websocket, pubsub, meeting, db)
            )

            return await _run_live_loop(
                websocket, meeting_id, db, meeting,
                segmenter, pipeline, audio_queue, level_task,
                broadcast_task, pubsub,
            )
    except WebSocketDisconnect:
        # 客户端主动断开，无需记录
        logger.info(f"meeting {meeting_id} live WS 客户端断开")
    except Exception as e:
        # 任何其他异常（VAD 加载失败 / transcript_history 失败 / pubsub.subscribe 失败等）
        # 之前会静默逃逸导致 WS 立即关闭且无错误日志；现在捕获并记录
        logger.error(f"meeting {meeting_id} live WS 异常崩溃: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)  # 1011 = internal error
        except Exception:
            pass
        return


async def _polish_and_send(
    websocket, meeting_id: int, segment_id: str,
    text: str, ts: float, context: dict,
):
    """异步润色并推送结果"""
    try:
        result = await polish_segments_with_lock(
            meeting_id,
            [{"speaker": "发言人", "text": text, "ts": ts}],
            context,
        )
        await websocket.send_json({
            "type": "transcript_polished",
            "segment_id": segment_id,
            "polished": result["polished"],
            "key_points": result["key_points"],
            "boundary_after_index": result["boundary_after_index"],
        })
    except Exception as e:
        logger.error(f"润色失败: {e}")
        try:
            await websocket.send_json({
                "type": "transcript_polished_error",
                "segment_id": segment_id,
                "error": str(e),
            })
        except Exception:
            pass


def pcm_to_wav(pcm_int16: bytes, sample_rate: int = 16000) -> bytes:
    """Int16 PCM 转 WAV 字节流"""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_int16)
    return buf.getvalue()


# 噪音过滤黑名单
# 2026-06-02 扩展：补全 YouTube/B站常见结束语（whisper hallucination 频发）
# 这些是 faster-whisper 在静音/低能量片段上臆造的"训练集记忆"
# 即便 whisper_server 已加 condition_on_previous_text=False + no_speech_prob 过滤，
# 后端这里再兜一层（防御纵深）
NOISE_PATTERNS = [
    "字幕", "志愿者", "谢谢观看", "观看谢谢", "中文字幕", "翻译", "字幕组",
    "明镜与点点", "明镜", "点点栏目",
    "点赞", "订阅", "转发", "打赏", "不吝",
    "MING PAO", "MING", "PAO",
    "Thanks for watching", "Please subscribe", "Like and subscribe",
    "请不吝", "支持明镜", "支持点点",
    "频道", "channel",
]


async def _run_live_loop(
    websocket: WebSocket,
    meeting_id: int,
    db: AsyncSession,
    meeting,
    segmenter: LiveSegmenter,
    pipeline: MeetingPipeline,
    audio_queue: asyncio.Queue,
    level_task: asyncio.Task,
    broadcast_task: asyncio.Task = None,
    pubsub=None,
):
    """会议 /live WS 主循环（wave 2a 任务 9 重构版）

    设计：
    - 主流程：MeetingPipeline（per-WS VAD + 声纹 + ASR）
    - 兜底：LiveSegmenter + 18000 字节 ASR（pipeline 未输出时使用）
    - 收到 ai_chat JSON → 调用 agent 回复
    - audio_level 旁路推送：每次收到 PCM 推入 audio_queue，_audio_level_loop 消费
    """
    start_time = time.time()
    transcript_entries = []
    audio_buffer = b""
    last_text = ""

    # Wave 2b: 音频归档 writer
    from app.services.file_service import file_service
    from app.services.audio_archive_service import AudioArchiveWriter
    archive_writer = AudioArchiveWriter(meeting_id, file_service)

    # 外层 try/except 兜底（2026-06-02 修复）：
    # 之前只捕获 WebSocketDisconnect；任何非 disconnect 异常（RuntimeError / KeyError /
    # await send_json 在客户端断后抛 ConnectionClosed 等）会逃逸到 Uvicorn 静默关闭 WS。
    # 现在用 outer try/except 捕获并记录，让运维有迹可循。
    try:
        return await _live_loop_inner(
            websocket, meeting_id, transcript_entries, audio_buffer, last_text,
            start_time, archive_writer, segmenter, pipeline, audio_queue, level_task,
            broadcast_task, pubsub, meeting, db,
        )
    except WebSocketDisconnect:
        # 客户端正常断开，走原有的清理流程（保存转录/取消 task/广播 meeting_ended）
        # 实际清理逻辑在 _live_loop_inner 的 except WebSocketDisconnect 分支
        logger.info(f"meeting {meeting_id} live WS 客户端断开")
    except Exception as e:
        logger.error(f"meeting {meeting_id} _run_live_loop 未捕获异常: {e}", exc_info=True)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
        # 尽力清理
        for t in [level_task, broadcast_task]:
            if t is not None:
                t.cancel()
        if pubsub is not None:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass
        return None
    return None


async def _live_loop_inner(
    websocket, meeting_id, transcript_entries, audio_buffer, last_text,
    start_time, archive_writer, segmenter, pipeline, audio_queue, level_task,
    broadcast_task, pubsub, meeting, db,
):
    """_run_live_loop 内部主循环（被外层 try/except 包裹）"""
    try:
        while True:
            data = await websocket.receive()

            # 文字控制消息
            if "text" in data:
                try:
                    msg = json.loads(data["text"])
                    msg_type = msg.get("type")

                    if msg_type == "ai_command":
                        # Wave 2b: AI 互动 4 能力
                        from app.services.meeting_ai_interactive import (
                            ask_agent, summarize_now, summarize_recent, translate,
                        )
                        from app.services.meeting_broadcast_service import publish_ai_reply
                        from app.voice.tts import tts_service

                        action = msg.get("action")
                        reply = None
                        try:
                            if action == "summarize_recent":
                                text = await summarize_recent(
                                    meeting_id, msg.get("seconds", 30)
                                )
                                reply = {"type": "ai_reply", "action": action, "text": text}
                            elif action == "translate":
                                text = msg.get("text", "")
                                translated = await translate(
                                    text, "zh", msg.get("lang", "en")
                                )
                                reply = {
                                    "type": "ai_reply",
                                    "action": action,
                                    "text": translated,
                                    "original": text,
                                }
                            elif action == "summarize_now":
                                result = await summarize_now(meeting_id)
                                reply = {"type": "ai_reply", "action": action, **result}
                            elif action == "ask":
                                answer = await ask_agent(
                                    meeting_id, msg.get("question", "")
                                )
                                reply = {
                                    "type": "ai_reply",
                                    "action": action,
                                    "text": answer,
                                }

                            if reply:
                                # 1. 推给本 WS
                                await websocket.send_json(reply)
                                # 2. 多设备广播
                                await publish_ai_reply(meeting_id, reply)
                                # 3. TTS 推送（summarize_recent 和 ask 才推送）
                                if action in ("summarize_recent", "ask"):
                                    try:
                                        mp3 = await asyncio.to_thread(
                                            tts_service.synthesize, reply.get("text", "")
                                        )
                                        await websocket.send_bytes(mp3)
                                    except Exception as e:
                                        logger.error(f"TTS 失败: {e}")
                        except Exception as e:
                            logger.error(f"AI command 失败: {e}")
                            await websocket.send_json({
                                "type": "ai_reply",
                                "action": action,
                                "text": f"（处理失败：{str(e)[:50]}）",
                            })

                    elif msg_type == "hangup":
                        await websocket.close()
                        return

                    elif msg_type == "speaker_claim":
                        # 写入 speaker_mapping：将原始声纹 label 绑定到成员
                        member_id = msg.get("member_id")
                        speaker_label = msg.get("speaker_label")
                        segment_id = msg.get("segment_id")
                        if member_id and speaker_label and meeting is not None:
                            member = await db.get(Member, member_id)
                            if member:
                                if meeting.speaker_mapping is None:
                                    meeting.speaker_mapping = {}
                                mapping = dict(meeting.speaker_mapping)
                                mapping[speaker_label] = member.name
                                meeting.speaker_mapping = mapping
                                await db.commit()
                                logger.info(
                                    f"speaker_claim 写入: {speaker_label} -> {member.name}"
                                )
                                await websocket.send_json({
                                    "type": "speaker_claim_ack",
                                    "segment_id": segment_id,
                                    "speaker_label": speaker_label,
                                    "member_id": member.id,
                                    "member_name": member.name,
                                })
                            else:
                                logger.warning(f"speaker_claim: member {member_id} 不存在")
                        else:
                            logger.warning(
                                f"speaker_claim 参数缺失: member_id={member_id} "
                                f"speaker_label={speaker_label} meeting={meeting is not None}"
                            )
                except Exception as e:
                    logger.error(f"文字消息处理失败: {e}")
                continue

            # 音频数据
            if "bytes" not in data:
                continue

            pcm_chunk = data["bytes"]
            audio_buffer += pcm_chunk

            # Wave 2b: 累积 PCM 到 archive writer
            archive_writer.feed_pcm(pcm_chunk)

            # 入队 audio_level（旁路推送，每 100ms 推一次）
            try:
                audio_queue.put_nowait(pcm_chunk)
            except asyncio.QueueFull:
                pass  # 队列满时丢弃旧数据

            # 主流程：MeetingPipeline（VAD + 声纹 + ASR）
            pipeline_emitted = False
            try:
                elapsed = time.time() - start_time
                entries = await pipeline.process_audio(pcm_chunk, db, elapsed)
                for entry in entries:
                    pipeline_emitted = True

                    # 噪音过滤
                    if any(noise in entry["text"] for noise in NOISE_PATTERNS):
                        continue

                    segment_id = f"seg_{int(entry['start'] * 1000)}"
                    speaker_label = entry.get("speaker") or "unknown"
                    speaker = speaker_label
                    confidence = entry.get("confidence", 0.0)

                    # 应用 speaker_mapping
                    if meeting and meeting.speaker_mapping:
                        mapped = meeting.speaker_mapping.get(speaker_label)
                        if mapped:
                            speaker = mapped

                    # 推 transcript（含 speaker + 置信度 + 原始 label + member_id）
                    transcript_entry = {
                        "type": "transcript",
                        "segment_id": segment_id,
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_confidence": confidence,
                        "text": entry["text"],
                        "start": entry["start"],
                        "end": entry.get("end", entry["start"] + 3),
                        "polish_status": "pending",
                    }
                    # Wave 3a: 带 member_id 字段（用于跨会议反查）
                    if entry.get("member_id"):
                        transcript_entry["member_id"] = entry["member_id"]
                    transcript_entries.append(transcript_entry)
                    await websocket.send_json(transcript_entry)

                    # Wave 3a: 记录置信度历史（仅成功识别时记录）
                    if entry.get("member_id") and entry.get("confidence"):
                        from app.services.voiceprint_service import record_confidence
                        try:
                            await record_confidence(
                                db, meeting_id, entry["member_id"], entry["confidence"]
                            )
                        except Exception as e:
                            logger.error(f"record_confidence 失败: {e}")

                    # Wave 2b: 写滑窗 + 多设备广播
                    from app.services.meeting_transcript_buffer import append_transcript
                    from app.services.meeting_broadcast_service import publish_transcript
                    await append_transcript(meeting_id, transcript_entry)
                    await publish_transcript(meeting_id, transcript_entry)

                    # 异步润色
                    asyncio.create_task(
                        _polish_and_send(
                            websocket, meeting_id, segment_id,
                            entry["text"], entry["start"], {},
                        )
                    )

                    # 声纹未识别 + 有未录入成员 → 推 speaker_unidentified
                    if speaker_label == "unknown" or confidence < 0.4:
                        try:
                            candidates = await get_unenrolled_participants(db, meeting_id)
                            if candidates:
                                await websocket.send_json({
                                    "type": "speaker_unidentified",
                                    "segment_id": segment_id,
                                    "speaker_label": speaker_label,
                                    "candidates": [
                                        {
                                            "id": c.id,
                                            "name": c.name,
                                            "avatar": c.avatar,
                                        }
                                        for c in candidates
                                    ],
                                    "transcript_text": entry["text"],
                                })
                        except Exception as e:
                            logger.error(f"speaker_unidentified 推送失败: {e}")

            except Exception as e:
                logger.error(f"pipeline.process_audio 失败: {e}")

            # 兜底：LiveSegmenter（pipeline 未输出时使用）
            if not pipeline_emitted:
                try:
                    if segmenter.feed(pcm_chunk):
                        pcm_segment = segmenter.drain()
                        elapsed = time.time() - start_time
                        wav_data = pcm_to_wav(pcm_segment)
                        asr_result = await asr_service.transcribe(
                            wav_data, language="zh", skip_convert=True
                        )
                        text = asr_result.get("text", "").strip()
                        if not text or any(noise in text for noise in NOISE_PATTERNS):
                            continue
                        segment_id = f"seg_{int(elapsed * 1000)}"
                        entry = {
                            "type": "transcript",
                            "segment_id": segment_id,
                            "speaker": "发言人",
                            "speaker_label": "发言人",
                            "speaker_confidence": 0,
                            "text": text,
                            "start": max(0, elapsed - 3),
                            "end": elapsed,
                            "polish_status": "pending",
                        }
                        transcript_entries.append(entry)
                        await websocket.send_json(entry)

                        # Wave 2b: 写滑窗 + 多设备广播
                        from app.services.meeting_transcript_buffer import append_transcript
                        from app.services.meeting_broadcast_service import publish_transcript
                        await append_transcript(meeting_id, entry)
                        await publish_transcript(meeting_id, entry)

                        asyncio.create_task(
                            _polish_and_send(
                                websocket, meeting_id, segment_id,
                                text, elapsed, {},
                            )
                        )
                except Exception as e:
                    logger.error(f"兜底段满检测失败: {e}")

            # 老 fallback：48000 字节兜底 ASR
            if not pipeline_emitted and len(audio_buffer) >= 48000:
                try:
                    import io as _io, wave as _wave
                    wav_buf = _io.BytesIO()
                    with _wave.open(wav_buf, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(audio_buffer)
                    wav_bytes = wav_buf.getvalue()

                    result = await asr_service.transcribe(
                        wav_bytes, language="zh", skip_convert=True
                    )
                    text = result.get("text", "").strip()
                    audio_buffer = b""

                    if len(text) < 2 or text == last_text:
                        last_text = text
                        continue
                    if any(p in text for p in NOISE_PATTERNS):
                        continue
                    last_text = text

                    elapsed = time.time() - start_time
                    entry = {
                        "type": "transcript",
                        "speaker": "发言人",
                        "speaker_label": "发言人",
                        "speaker_confidence": 0,
                        "text": text,
                        "start": max(0, elapsed - 3),
                        "end": elapsed,
                    }
                    transcript_entries.append(entry)
                    await websocket.send_json(entry)
                except Exception as e:
                    logger.error(f"48000 字节兜底 ASR 失败: {e}")
                    audio_buffer = b""

    except WebSocketDisconnect:
        # 关闭 audio_level 推送
        level_task.cancel()
        try:
            await level_task
        except (asyncio.CancelledError, Exception):
            pass

        # Wave 2b: 取消 broadcast_task
        if broadcast_task is not None:
            broadcast_task.cancel()
            try:
                await broadcast_task
            except asyncio.CancelledError:
                pass
        if pubsub is not None:
            try:
                await pubsub.unsubscribe()
                await pubsub.aclose()
            except Exception:
                pass

        # 保存转录到会议记录，自动分析
        analysis_result = None
        try:
            if meeting and transcript_entries:
                meeting.transcript = [
                    {"speaker": e["speaker"], "text": e["text"],
                     "start": e.get("start"), "end": e.get("end"),
                     "confidence": e.get("speaker_confidence", 0)}
                    for e in transcript_entries
                ]
                meeting.status = "completed"
                await db.commit()

                if transcript_entries:
                    meeting_service = MeetingService(db)
                    analysis_result = await meeting_service.process_meeting_transcript(meeting_id)
                    try:
                        from app.services.meeting_analysis_service import meeting_analysis
                        transcript_text = meeting_service._transcript_to_text(meeting.transcript)
                        new_title = await meeting_analysis.generate_title(transcript_text)
                        if new_title and new_title != "未命名会议":
                            meeting.title = new_title
                            await db.commit()
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"保存会议转录失败: {e}")

        # 清理 per-WS pipeline 状态
        try:
            pipeline.reset()
        except Exception:
            pass

        # Wave 2b: 归档音频
        try:
            await archive_writer.finalize(db)
        except Exception as e:
            logger.error(f"音频归档失败: {e}")

        try:
            await websocket.send_json({
                "type": "meeting_ended",
                "meeting_id": meeting_id,
                "entries": len(transcript_entries),
                "analysis": analysis_result,
            })
        except Exception:
            pass


async def _audio_level_loop(websocket: WebSocket, audio_queue: asyncio.Queue):
    """每 100ms 计算最近音频的 RMS（0-1 归一化），推 audio_level 消息

    供前端可视化音量条使用。WS 断开或异常时退出。
    """
    BYTES_PER_SAMPLE = 2
    RMS_NORMALIZATION = 10000  # 经验系数（Int16 PCM 的典型语音 RMS 约 3000-8000）

    while True:
        try:
            data = await asyncio.wait_for(audio_queue.get(), timeout=0.5)
            if not data:
                level = 0.0
            else:
                num_samples = len(data) // BYTES_PER_SAMPLE
                if num_samples == 0:
                    level = 0.0
                else:
                    total_sq = 0
                    for i in range(0, num_samples * BYTES_PER_SAMPLE, BYTES_PER_SAMPLE):
                        sample = int.from_bytes(
                            data[i:i + BYTES_PER_SAMPLE], "little", signed=True
                        )
                        total_sq += sample * sample
                    rms = (total_sq / num_samples) ** 0.5
                    level = min(1.0, rms / RMS_NORMALIZATION)
        except asyncio.TimeoutError:
            level = 0.0
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"audio_level 异常: {e}")
            break

        try:
            await websocket.send_json({"type": "audio_level", "level": round(level, 3)})
        except Exception:
            break

        await asyncio.sleep(0.1)


async def _broadcast_loop(websocket: WebSocket, pubsub, meeting, db):
    """订阅 transcript / ai_reply / speaker_mapping 频道，转发给本 WS"""
    while True:
        try:
            msg = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                timeout=30.0,
            )
            if msg:
                channel = msg["channel"].decode() if isinstance(msg["channel"], bytes) else msg["channel"]
                data = json.loads(msg["data"])
                if channel.startswith("transcript:"):
                    await websocket.send_json({"type": "transcript_others", "data": data})
                elif channel.startswith("ai_reply:"):
                    await websocket.send_json({"type": "ai_reply_others", "data": data})
                elif channel.startswith("speaker_mapping:"):
                    # 刷新 meeting 对象
                    try:
                        await db.refresh(meeting)
                    except Exception:
                        pass
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"broadcast loop 异常: {e}")
            break
