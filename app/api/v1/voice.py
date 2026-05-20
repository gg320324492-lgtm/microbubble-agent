"""语音相关API"""

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
import io
import json

import logging
from app.voice.asr import asr_service
from app.voice.tts import tts_service
from app.voice.recorder import recorder_manager
from app.agent.core import agent
from app.core.database import get_db, async_session
from app.core.security import get_current_user, decode_token
from app.models.member import Member
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
    """会议实时转写WebSocket"""
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

    try:
        while True:
            data = await websocket.receive_bytes()

            recorder.recorder.add_audio_data(data)

            async for segment in asr_service.transcribe_stream(data):
                speaker = "参会者"

                entry = {
                    "text": segment["text"],
                    "start": segment["start"],
                    "end": segment["end"],
                    "speaker": speaker
                }
                recorder.add_transcript_entry(entry)

                await websocket.send_json({
                    "type": "transcript",
                    **entry
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
