"""语音相关API"""

from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
import asyncio
import io
import json
import re
import time
import wave

import logging
import numpy as np
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

            # Wave 2b: 多设备订阅（2026-06-02 优化 2：加 transcript_polished 频道让 L3 全文精润广播给其他设备）
            from app.core.redis import get_redis
            r = await get_redis()
            pubsub = r.pubsub()
            await pubsub.subscribe(
                f"transcript:{meeting_id}",
                f"ai_reply:{meeting_id}",
                f"speaker_mapping:{meeting_id}",
                f"transcript_polished:{meeting_id}",  # 2026-06-02 L3 全文精润广播
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
    speaker: str = "未知说话人",  # 2026-06-02 修复：之前硬编码"发言人"丢失说话人信息
):
    """异步润色并推送结果"""
    try:
        result = await polish_segments_with_lock(
            meeting_id,
            [{"speaker": speaker, "text": text, "ts": ts}],
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


# ===== 反幻觉过滤系统（2026-06-03 重构） =====
#
# 问题：之前的 NOISE_PATTERNS 是纯文本黑名单，无法区分
#   "Whisper 在静音段臆造的幻觉" vs "用户真说了这些词"
# 导致：用户说"12345"被过滤（假阳性），"Yup""铁化铁"等误识别却漏过
#
# 方案：改为三重判定
#   1. STRONG 黑名单（99% 是幻觉）→ 无条件过滤
#   2. WEAK 黑名单（可能是真话）→ 仅在音频能量低时过滤
#   3. 结构性过滤（重复/乱码/数字串）→ 始终生效
#
# 能量阈值：RMS > 0.02 认为是真实语音（经验值，安静房间说话约 0.03-0.1）

# STRONG：99% 是幻觉的词（YouTube/B站结束语、菜谱等 Whisper 训练集记忆）
# 这些词在正常对话中几乎不会出现，无条件过滤
HALLUCINATION_STRONG = [
    "字幕", "志愿者", "谢谢观看", "观看谢谢", "中文字幕", "翻译", "字幕组",
    "明镜与点点", "明镜", "点点栏目",
    "点赞", "订阅", "转发", "打赏", "不吝",
    "MING PAO", "MING", "PAO",
    "Thanks for watching", "Please subscribe", "Like and subscribe",
    "请不吝", "支持明镜", "支持点点",
    "频道", "channel",
    "鲜奶油", "奶油", "锅里", "锅", "倒入", "翻面", "敲击", "盖起来",
    "下次见", "下次再见",
    "感谢观看",  # YouTube 结束语（不要单加"感谢"会误杀正常对话）
    "请勿模仿",
    "准备准备",  # "准备准备准备" 是 Whisper 幻觉，但单个"准备"是正常词
    "高级化链",  # 2026-06-03 Whisper 幻觉（"主要是为了使用高级化链和高级化链的关系而定性的销量"）
    "空气机器",  # 2026-06-03 Whisper 幻觉（"镜头是空气机器,不需要测量"）
]

# WEAK：可能是真话的词 → 仅在音频能量低（RMS < 0.02）时过滤
# 这些词在 Whisper 幻觉中常见，但用户也可能真说
HALLUCINATION_WEAK = [
    "1234", "12345", "123456", "1234567",  # 数字串：幻觉常见，但用户也可能真说
    "哈喽", "Hello", "hi", "Hi", "hello",  # 打招呼：幻觉常见，但用户也可能真说
    "测试", "TEST", "test", "Test",         # 测试词：幻觉常见，但用户也可能真说
    "嗯",                                    # 口头语：幻觉常见，但用户也可能真说
    "再见",                                  # 结束语：幻觉常见，但用户也可能真说
    "Yup", "yeah", "Yes",                   # 英文应答：幻觉常见
]

# 能量阈值：RMS 低于此值 + WEAK 黑名单匹配 → 过滤
# 安静房间说话 RMS 约 0.03-0.1，静音/噪音约 0.001-0.01
ENERGY_THRESHOLD_FOR_WEAK = 0.02

# 兼容旧代码：合并所有黑名单（用于兜底分支等不需要能量判定的场景）
NOISE_PATTERNS = HALLUCINATION_STRONG + HALLUCINATION_WEAK


def _is_repetitive_text(text: str, min_repeats: int = 2) -> bool:
    """检测重复模式：同一短子串重复 >= min_repeats 次视为 whisper hallucination

    例如：
    - "准备准备准备准备" → 子串"准备"重复 4 次
    - "锅里锅里锅里" → 子串"锅里"重复 3 次
    - "abcabcabc" → 子串"abc"重复 3 次
    - "你好世界" → 不重复，返回 False

    检测策略：
    - 先去掉中英文标点 + 空白（避免 "," "。" 重复触发）
    - 枚举所有 1-6 字子串，按子串长度用不同阈值：
      - 1 字 ≥ 4（"啊啊啊啊"）
      - 2-3 字 ≥ 3（"黑糖黑糖黑糖"）
      - 4-6 字 ≥ 3
    """
    if len(text) < 4:
        return False
    # 先去标点（避免"，。.空格"等被误判）
    text_clean = re.sub(r'[\s,。.!?:;,，！？；：、…\-"\']+', '', text)
    if len(text_clean) < 4:
        return False
    thresholds = {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 3}
    for substr_len, threshold in thresholds.items():
        for i in range(len(text_clean) - substr_len + 1):
            substr = text_clean[i:i + substr_len]
            count = 0
            pos = 0
            while True:
                idx = text_clean.find(substr, pos)
                if idx == -1:
                    break
                count += 1
                pos = idx + substr_len
            if count >= threshold:
                return True
    return False


def _is_alphanumeric_run(text: str, min_run: int = 4, max_ratio: float = 0.4) -> bool:
    """检测字母+数字纯串（whisper 把训练集 ID 列表臆造出来）

    例如：
    - "G6G7G10G11G12G13G14G15G16G17G18G19G20" → 一串字母+数字连写
    - "M1结果中心营业G6G7G10" → 主体是字母+数字
    - "1分钟后,1234567" → 数字串占主体

    判定：text 中 [A-Za-z0-9] 字符占比 > max_ratio 且存在连续 min_run+ 字母数字的 run
    """
    alnum_chars = [c for c in text if c.isalnum() and (c.isascii() or c.isdigit())]
    # 只算 ASCII alnum（中文不算）
    ascii_alnum = [c for c in text if c.isascii() and c.isalnum()]
    if not text:
        return False
    # 比例判定
    if len(ascii_alnum) / max(len(text), 1) > max_ratio:
        # 找连续 ASCII alnum run
        import re as _re
        runs = _re.findall(r'[A-Za-z0-9]{' + str(min_run) + r',}', text)
        if runs:
            return True
    return False


def _is_gibberish(text: str, min_length: int = 30, common_chars: str = "的了是我你在有和他她么也这那以及与或但而所以因为将把中后放入出到从给它其时时候上下前过做要不让没") -> bool:
    """检测长无意义乱码（whisper 训练集臆造的中文长文）

    例如：
    - "高级化铁管理仅次量測年的溶化能力和硬性的一个数据下測感应该是..."
    - "M1结果中心营业G6G7G10G11G12G13G14G15..."

    启发式（最严格档，避免误杀真实专业句）：
    - text 长度 ≥ 30 字符
    - 且 distinct 常见词（虚词 + 代词 + 动作词）= 0
    - 真实对话 30+ 字几乎必含至少一个"将/把/放/入/到/中/后/给""的/了/是/我/在"等

    注：微纳米气泡这类专业术语（"微纳米气泡的zeta电位是表征..."）含"的""是"等放过。
    """
    if len(text) < min_length:
        return False
    distinct_common = set(c for c in text if c in common_chars)
    if len(distinct_common) >= 1:
        return False
    return True


def _is_sentence_repetitive(text: str, min_repeats: int = 2) -> bool:
    """检测完整句子重复

    例如：
    - "它是一种气体。它是一种气体。它是一种气体。"
    - "是的。是的。"

    策略：按 。！？.!? 切分句子，去标点后任一句子（>=2 字）出现 >= min_repeats 次
    """
    if len(text) < 8:
        return False
    sentences = re.split(r'[。！？.!?]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 2]
    if len(sentences) < min_repeats:
        return False
    for s in sentences:
        if text.count(s) >= 2:  # 句子级 ≥ 2 次重复即判定（2026-06-03 从 3 降到 2，压制 Whisper 幻觉）
            return True
    return False


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

    # 2026-06-02 L2 聚批润色器：替代原"每段 1 次 Claude API"逐段触发
    # 攒批策略：每 30s 或攒满 5 段触发 1 次 LLM，复用 polish_segments_with_lock 的 Redis 锁 + 24h 缓存
    from app.services.meeting_batch_polisher import BatchPolisher
    batch_polisher = BatchPolisher(
        meeting_id=meeting_id,
        websocket=websocket,
        meeting_context={
            "title": meeting.title if meeting else "",
            # 2026-06-02 修复：meeting.participants 是 lazy relationship，
            # 在 async session 中访问会触发 sync IO → MissingGreenlet → WS 崩溃 → 客户端"重连中"循环
            # 润色 context 不强依赖 participants 列表，传空数组即可
            "participants": [],
        },
    )
    await batch_polisher.start()

    # 外层 try/except 兜底（2026-06-02 修复）：
    # 之前只捕获 WebSocketDisconnect；任何非 disconnect 异常（RuntimeError / KeyError /
    # await send_json 在客户端断后抛 ConnectionClosed 等）会逃逸到 Uvicorn 静默关闭 WS。
    # 现在用 outer try/except 捕获并记录，让运维有迹可循。
    try:
        return await _live_loop_inner(
            websocket, meeting_id, transcript_entries, audio_buffer, last_text,
            start_time, archive_writer, segmenter, pipeline, audio_queue, level_task,
            broadcast_task, pubsub, meeting, db, batch_polisher,
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
    broadcast_task, pubsub, meeting, db, batch_polisher,
):
    """_run_live_loop 内部主循环（被外层 try/except 包裹）"""
    try:
        while True:
            data = await websocket.receive()

            # 客户端断开连接（close frame）
            if data.get("type") == "websocket.disconnect":
                logger.info(f"meeting {meeting_id} WS 客户端发送 close frame")
                break

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
                        # 2026-06-02: hangup 时强制刷残余 + 停止 BatchPolisher
                        await batch_polisher.flush_remaining()
                        await batch_polisher.stop()
                        # L3 全文精润色（后台跑，**不 await** 让 WS 立即关闭）
                        try:
                            from app.services.meeting_full_polisher import run_full_polish_pipeline
                            from app.core.database import async_session
                            asyncio.create_task(
                                run_full_polish_pipeline(
                                    meeting_id, transcript_entries, async_session
                                )
                            )
                        except Exception as e:
                            logger.error(f"L3 触发失败: {e}")

                        # 更新会议状态 + 触发后处理 Celery 任务
                        try:
                            from app.services.progress_service import init_progress
                            from app.services.post_meeting_tasks import post_meeting_process
                            if meeting:
                                meeting.status = "completed"
                                meeting.end_time = __import__("datetime").datetime.utcnow()
                                if transcript_entries:
                                    meeting.transcript = transcript_entries
                                await db.commit()
                            await init_progress(meeting_id)
                            post_meeting_process.delay(meeting_id)
                            logger.info(f"meeting {meeting_id} hangup: 后处理任务已派发")
                        except Exception as e:
                            logger.error(f"hangup 后处理派发失败: {e}", exc_info=True)

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

                    # 2026-06-03 反幻觉三重判定（重构：黑名单 + 能量 + 结构性）
                    text = entry["text"].strip()
                    entry_start = entry.get("start", 0)
                    entry_end = entry.get("end", entry_start)
                    entry_duration = max(0, entry_end - entry_start)
                    audio_rms = entry.get("audio_rms", 0.0)

                    # 1. STRONG 黑名单（99% 是幻觉）→ 无条件过滤
                    if any(noise in text for noise in HALLUCINATION_STRONG):
                        continue
                    # 2. WEAK 黑名单（可能是真话）→ 仅在音频能量低时过滤
                    if audio_rms < ENERGY_THRESHOLD_FOR_WEAK and any(noise in text for noise in HALLUCINATION_WEAK):
                        continue
                    # 2. 极短 segment（< 0.3s）几乎都是噪声
                    if entry_duration < 0.3:
                        continue
                    # 3. 短文本（去掉标点和空格后 < 2 字符）— 真实语音至少 2 个字
                    text_no_punct = re.sub(r'[\s,。.!?:;,，！？；：、…\-"\']+', '', text)
                    if len(text_no_punct) < 2:
                        continue
                    # 4. 重复模式（"准备准备准备准备""锅里锅里锅里""啊啊啊啊啊啊"）— 阈值分级
                    if _is_repetitive_text(text_no_punct):
                        continue
                    # 5. 字母+数字纯串（whisper 把训练集 ID 列表臆造："G6G7G10G11..."）
                    if _is_alphanumeric_run(text):
                        continue
                    # 6. 长无意义乱码（30+ 字符但几乎不含常见中文虚词："高级化铁管理..."）
                    if _is_gibberish(text):
                        continue
                    # 7. 完整句子重复（"它是一种气体。它是一种气体。它是一种气体。"）
                    if _is_sentence_repetitive(text):
                        continue
                    # 8. 低置信度 + 短文本 → 大概率是 Whisper 幻觉（2026-06-03 新增）
                    # 声纹置信度 < 0.1 表示几乎没检测到人声，短文本更可能是臆造
                    speaker_confidence = entry.get("confidence", 0.0)
                    if speaker_confidence < 0.1 and len(text_no_punct) < 10:
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

                    # 异步润色（2026-06-02 改 BatchPolisher 攒批触发，替代逐段）
                    await batch_polisher.add({
                        "segment_id": segment_id,
                        "speaker": speaker,
                        "text": entry["text"],
                        "ts": entry["start"],
                    })

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
                        # 2026-06-03 反幻觉三重判定（兜底分支同步）
                        # 计算音频能量
                        fallback_rms = float(np.sqrt(np.mean(np.frombuffer(pcm_segment, dtype=np.int16).astype(np.float32) ** 2 / 32768.0**2))) if len(pcm_segment) > 0 else 0.0
                        if not text:
                            continue
                        if any(noise in text for noise in HALLUCINATION_STRONG):
                            continue
                        if fallback_rms < ENERGY_THRESHOLD_FOR_WEAK and any(noise in text for noise in HALLUCINATION_WEAK):
                            continue
                        text_no_punct = re.sub(r'[\s,。.!?:;,，！？；：、…\-"\']+', '', text)
                        if len(text_no_punct) < 2 or _is_repetitive_text(text_no_punct):
                            continue
                        if _is_alphanumeric_run(text) or _is_gibberish(text) or _is_sentence_repetitive(text):
                            continue
                        # 2026-06-02 修复：兜底段满检测分支也调用声纹识别（之前硬编码 "发言人"，
                        # 导致反幻觉过滤后所有 entry 都显示 "发言人" 不显示真实说话人）
                        from app.services.voiceprint_service import voiceprint_service
                        speaker_name, speaker_member_id, speaker_conf = await voiceprint_service.identify_speaker(db, pcm_segment)
                        if speaker_name is None:
                            speaker_label = "unknown"  # 触发 SpeakerUnidentifiedDialog
                            speaker = "未知说话人"
                            confidence = speaker_conf
                        else:
                            speaker_label = speaker_name
                            speaker = speaker_name
                            confidence = speaker_conf
                        # 应用 speaker_mapping（用户手动认领过的原始 label → 真实姓名）
                        if meeting and meeting.speaker_mapping and speaker_label != "unknown":
                            mapped = meeting.speaker_mapping.get(speaker_label)
                            if mapped:
                                speaker = mapped
                        segment_id = f"seg_{int(elapsed * 1000)}"
                        entry = {
                            "type": "transcript",
                            "segment_id": segment_id,
                            "speaker": speaker,
                            "speaker_label": speaker_label,
                            "speaker_confidence": confidence,
                            "member_id": speaker_member_id,
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
                                speaker=speaker,  # 2026-06-02 修复：传声纹识别结果
                            )
                        )
                        # 2026-06-02 也入队 BatchPolisher（兜底分支也攒批）
                        await batch_polisher.add({
                            "segment_id": segment_id,
                            "speaker": speaker,
                            "text": text,
                            "ts": elapsed,
                        })
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
                    # 2026-06-03 反幻觉三重判定（48000 字节兜底同步）
                    if any(p in text for p in HALLUCINATION_STRONG):
                        continue
                    # 48000 字节兜底无 audio_rms，用 buffer 能量估算
                    buf_rms = float(np.sqrt(np.mean(np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) ** 2 / 32768.0**2))) if len(audio_buffer) > 0 else 0.0
                    if buf_rms < ENERGY_THRESHOLD_FOR_WEAK and any(p in text for p in HALLUCINATION_WEAK):
                        continue
                    last_text = text

                    elapsed = time.time() - start_time
                    # 2026-06-02 修复：48000 字节兜底也调用声纹识别（与 LiveSegmenter 兜底一致）
                    from app.services.voiceprint_service import voiceprint_service
                    pcm_segment_fallback = np.frombuffer(audio_buffer, dtype=np.int16).astype(np.float32) / 32768.0
                    speaker_name, speaker_member_id, speaker_conf = await voiceprint_service.identify_speaker(db, pcm_segment_fallback)
                    if speaker_name is None:
                        speaker_label = "unknown"
                        speaker = "未知说话人"
                        confidence = speaker_conf
                    else:
                        speaker_label = speaker_name
                        speaker = speaker_name
                        confidence = speaker_conf
                    if meeting and meeting.speaker_mapping and speaker_label != "unknown":
                        mapped = meeting.speaker_mapping.get(speaker_label)
                        if mapped:
                            speaker = mapped
                    entry = {
                        "type": "transcript",
                        "speaker": speaker,
                        "speaker_label": speaker_label,
                        "speaker_confidence": confidence,
                        "member_id": speaker_member_id,
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

        # 2026-06-02: WS 断开时也强制刷 BatchPolisher 残余
        if batch_polisher is not None:
            try:
                await batch_polisher.flush_remaining()
                await batch_polisher.stop()
            except Exception as e:
                logger.warning(f"BatchPolisher flush/stop 失败: {e}")

        # 2026-06-02: WS 异常断开时也触发 L3 全文精润色（后台跑）
        if transcript_entries:
            try:
                from app.services.meeting_full_polisher import run_full_polish_pipeline
                from app.core.database import async_session
                asyncio.create_task(
                    run_full_polish_pipeline(
                        meeting_id, transcript_entries, async_session
                    )
                )
            except Exception as e:
                logger.error(f"L3 触发失败: {e}")

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

        # 保存转录到会议记录 + 派发 Celery 后处理任务
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
                from datetime import datetime as _dt
                meeting.end_time = _dt.utcnow()
                await db.commit()

            # 初始化进度 + 派发 Celery 后处理（不管有没有转录都要触发）
            from app.services.progress_service import init_progress
            from app.services.post_meeting_tasks import post_meeting_process
            await init_progress(meeting_id)
            post_meeting_process.delay(meeting_id)
            logger.info(f"meeting {meeting_id} WS 断开: 后处理任务已派发")
        except Exception as e:
            logger.error(f"WS 断开后处理派发失败: {e}", exc_info=True)

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
    """订阅 transcript / ai_reply / speaker_mapping / transcript_polished 频道，转发给本 WS"""
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
                elif channel.startswith("transcript_polished:"):  # 2026-06-02 L3 广播
                    # L3 全文精润色结果推给本 WS（前端 onFullPolished 处理）
                    await websocket.send_json({
                        "type": "transcript_full_polished",
                        "meeting_id": data.get("meeting_id"),
                        "polished_segments": data.get("polished_segments", []),
                    })
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.error(f"broadcast loop 异常: {e}")
            break
