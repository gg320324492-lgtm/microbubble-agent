"""声纹录入 API"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.core.exceptions import NotFoundException, ValidationException
from app.models.member import Member
from app.services.voiceprint_service import voiceprint_service
from app.utils.audio import decode_audio_to_float32

router = APIRouter()


@router.post("/voiceprint/enroll/{member_id}")
async def enroll_voiceprint(
    member_id: int,
    audio: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """录入成员声纹 — 上传 3-5 秒语音"""
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise ValidationException("请上传音频文件")

    try:
        audio_data = await audio.read()
        if len(audio_data) < 1000:
            raise ValidationException("音频太短，请录制至少 3 秒语音")

        # 复用 app/utils/audio.py 统一转 16kHz mono float32
        audio_array = await decode_audio_to_float32(audio_data, timeout=15.0)

        # 静音检测
        from app.utils.audio import is_audio_silent
        if is_audio_silent(audio_array):
            raise ValidationException("音频为静音，请重新录制")

        # 太短（< 1s）拒绝
        if len(audio_array) < 16000:
            raise ValidationException("音频太短，请录制至少 1 秒以上语音")

        success = await voiceprint_service.enroll_member(db, member_id, audio_array)
        if not success:
            raise NotFoundException("成员")

        return {"message": "声纹录入成功", "member_id": member_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"声纹录入失败: {str(e)}")


@router.get("/voiceprint/enrolled")
async def list_enrolled_members(
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取已录入声纹的成员列表"""
    members = await voiceprint_service.get_enrolled_members(db)
    return {"members": members}


@router.get("/voiceprint/fingerprints")
async def get_all_fingerprints(
    response: Response,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回所有成员的 192 维 embedding + 元数据（声纹库中心）"""
    from app.services.voiceprint_service import get_fingerprints
    # 防止浏览器缓存导致录入后看不到
    response.headers["Cache-Control"] = "max-age=0"
    return await get_fingerprints(db)


@router.get("/voiceprint/{member_id}/history")
async def get_member_voiceprint_history(
    member_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """返回该成员的声纹识别置信度历史（最近 N 次）"""
    from sqlalchemy import select, desc
    from app.models.voiceprint_history import VoiceprintHistory
    from app.models.meeting import Meeting
    stmt = (
        select(VoiceprintHistory, Meeting)
        .join(Meeting, VoiceprintHistory.meeting_id == Meeting.id)
        .where(VoiceprintHistory.member_id == member_id)
        .order_by(desc(VoiceprintHistory.recorded_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "meeting_id": h.meeting_id,
            "meeting_title": m.title,
            "confidence": h.confidence,
            "recorded_at": h.recorded_at.isoformat(),
        }
        for h, m in rows
    ]


@router.get("/voiceprint/search")
async def search_speaker(
    member_id: int,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: Member = Depends(get_current_user),
):
    """跨会议反查"该成员说过的内容" """
    from app.services.voiceprint_service import search_speaker_history
    return await search_speaker_history(db, member_id, limit)


@router.post("/voiceprint/test")
async def test_voiceprint_pipeline(
    audio: UploadFile = File(...),
    current_user: Member = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """声纹全链路测试 — 录音 → VAD → ASR → 声纹识别，返回每一步结果

    用于验证麦克风、VAD、ASR、声纹录入是否正常工作。
    """
    import numpy as np
    from app.utils.audio import decode_audio_to_float32, is_audio_silent

    result = {
        "steps": [],      # 每一步的详细结果
        "success": False,  # 最终是否成功识别出说话人
        "speaker": None,
        "confidence": 0.0,
        "transcript": "",
    }

    # Step 0: 解码音频
    try:
        audio_data = await audio.read()
        result["steps"].append({"name": "音频解码", "status": "ok", "detail": f"{len(audio_data)} bytes"})

        audio_array = await decode_audio_to_float32(audio_data, timeout=15.0)
        duration = len(audio_array) / 16000
        result["steps"].append({"name": "格式转换", "status": "ok", "detail": f"{duration:.1f}s, 16kHz mono"})
    except Exception as e:
        result["steps"].append({"name": "音频解码", "status": "error", "detail": str(e)})
        return result

    # Step 1: 静音检测
    if is_audio_silent(audio_array):
        result["steps"].append({"name": "静音检测", "status": "error", "detail": "音频为静音，请对着麦克风说话"})
        return result
    result["steps"].append({"name": "静音检测", "status": "ok", "detail": "检测到声音"})

    # Step 2: VAD（语音活动检测）
    try:
        from app.voice.vad import VADEngine
        vad = VADEngine()
        speech_segment = vad.process_chunk(audio_array)
        if speech_segment is None or len(speech_segment) == 0:
            result["steps"].append({"name": "VAD 检测", "status": "error", "detail": "未检测到有效语音段，请说话时间长一些"})
            return result
        vad_duration = len(speech_segment) / 16000
        result["steps"].append({"name": "VAD 检测", "status": "ok", "detail": f"检测到 {vad_duration:.1f}s 语音"})
    except Exception as e:
        result["steps"].append({"name": "VAD 检测", "status": "error", "detail": f"VAD 加载失败: {e}"})
        return result

    # Step 3: ASR（语音识别）
    try:
        from app.voice.asr import asr_service
        # 转 WAV 给 ASR
        import io, wave
        int16_data = (speech_segment * 32768.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(int16_data.tobytes())
        wav_data = buf.getvalue()

        asr_result = await asr_service.transcribe(wav_data, language="zh")
        text = asr_result.get("text", "").strip()
        if not text:
            result["steps"].append({"name": "语音识别", "status": "error", "detail": "未识别出文字，请说得更清晰"})
            return result
        result["steps"].append({"name": "语音识别", "status": "ok", "detail": text})
        result["transcript"] = text
    except Exception as e:
        result["steps"].append({"name": "语音识别", "status": "error", "detail": f"ASR 失败: {e}"})
        return result

    # Step 4: 声纹识别
    try:
        from app.services.voiceprint_service import voiceprint_service
        name, member_id, confidence = await voiceprint_service.identify_speaker(db, speech_segment)
        if name:
            result["steps"].append({"name": "声纹识别", "status": "ok", "detail": f"识别为: {name} (置信度 {confidence:.0%})"})
            result["success"] = True
            result["speaker"] = name
            result["confidence"] = confidence
        else:
            # 检查是否有已录入成员
            enrolled = await voiceprint_service.get_enrolled_members(db)
            if not enrolled:
                result["steps"].append({"name": "声纹识别", "status": "warn", "detail": "尚无声纹录入，请先在成员管理页面录入"})
            else:
                names = ", ".join(m["name"] for m in enrolled)
                result["steps"].append({"name": "声纹识别", "status": "warn", "detail": f"未匹配到已录入成员（已录入: {names}）。置信度: {confidence:.0%}"})
    except Exception as e:
        result["steps"].append({"name": "声纹识别", "status": "error", "detail": f"声纹服务异常: {e}"})

    return result
