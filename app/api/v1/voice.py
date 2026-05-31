"""语音相关API"""

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import io
import time

import logging
from app.voice.asr import asr_service
from app.voice.tts import tts_service
from app.voice.recorder import recorder_manager
from app.voice.pipeline import meeting_pipeline, RingBuffer, SAMPLE_RATE
from app.agent.core import agent
from app.core.database import get_db, async_session
from app.core.security import get_current_user, decode_token
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.meeting_service import MeetingService

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

    start_time = time.time()
    transcript_entries = []
    audio_buffer = b""
    last_text = ""

    # 噪音过滤黑名单
    NOISE_PATTERNS = ["字幕", "志愿者", "谢谢观看", "观看谢谢", "中文字幕", "翻译", "字幕组"]

    try:
        while True:
            data = await websocket.receive()

            # 文字控制消息
            if "text" in data:
                try:
                    msg = __import__("json").loads(data["text"])
                    if msg.get("type") == "ai_chat":
                        user_text = msg.get("text", "")
                        if user_text.strip():
                            ai_response = await agent.chat(
                                message=f"[会议实时对话] {user_text}", db=None)
                            await websocket.send_json({
                                "type": "ai_reply",
                                "text": ai_response.get("content", "")[:200],
                                "speaker": "小气助手",
                            })
                except Exception:
                    pass
                continue

            # 音频数据 — 直接 ASR 转写
            if "bytes" not in data:
                continue

            audio_buffer += data["bytes"]

            # 每积累约 3 秒音频转写一次
            if len(audio_buffer) >= 48000:
                try:
                    # 将 Int16 PCM 转为 WAV 后调用本地 ASR
                    import io as _io, wave as _wave, struct as _struct
                    wav_buf = _io.BytesIO()
                    with _wave.open(wav_buf, "wb") as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(16000)
                        wf.writeframes(audio_buffer)
                    wav_bytes = wav_buf.getvalue()

                    result = await asr_service.transcribe(wav_bytes, language="zh", skip_convert=True)
                    text = result.get("text", "").strip()
                    audio_buffer = b""

                    # 噪音过滤
                    if len(text) < 2: continue
                    if text == last_text: continue
                    if any(p in text for p in NOISE_PATTERNS): continue
                    last_text = text

                    if text:
                        elapsed = time.time() - start_time
                        entry = {
                            "type": "transcript",
                            "speaker": "发言人",
                            "speaker_confidence": 0,
                            "text": text,
                            "start": max(0, elapsed - 3),
                            "end": elapsed,
                        }
                        transcript_entries.append(entry)
                        await websocket.send_json(entry)
                except Exception as e:
                    logger.error(f"ASR 转写失败: {e}")
                    audio_buffer = b""  # 清空避免无限重试

    except WebSocketDisconnect:
        # 保存转录到会议记录，自动分析
        analysis_result = None
        try:
            async with async_session() as db:
                result = await db.execute(
                    select(Meeting).where(Meeting.id == meeting_id)
                )
                meeting = result.scalar_one_or_none()
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
                        # 自动生成标题
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

        meeting_pipeline.reset()
        try:
            await websocket.send_json({
                "type": "meeting_ended",
                "meeting_id": meeting_id,
                "entries": len(transcript_entries),
                "analysis": analysis_result,
            })
        except Exception:
            pass
