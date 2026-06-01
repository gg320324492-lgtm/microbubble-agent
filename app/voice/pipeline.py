"""实时声纹会议流水线 — VAD → 声纹识别 → ASR → 实时输出

集成 silero-vad + 3D-Speaker + faster-whisper，通过 WebSocket 流式输出。

设计要点：
- MeetingPipeline 构造函数接受注入的 vad/asr/voiceprint 服务
- 未注入时使用懒加载默认（向后兼容 module-level `meeting_pipeline` 单例）
- 推荐在 /live WebSocket 端点显式注入 per-instance VAD，避免共享状态
"""

import asyncio
import io
import json
import logging
import time
import wave
from typing import Optional

import numpy as np

from app.voice.vad import SAMPLE_RATE

logger = logging.getLogger("microbubble.pipeline")


class RingBuffer:
    """环形音频缓冲区"""

    def __init__(self, max_seconds: float = 3.0):
        self.max_samples = int(SAMPLE_RATE * max_seconds)
        self._buf = np.array([], dtype=np.float32)

    def append(self, data: np.ndarray):
        self._buf = np.concatenate([self._buf, data])
        if len(self._buf) > self.max_samples * 2:
            self._buf = self._buf[-self.max_samples :]

    def get_all(self) -> np.ndarray:
        return self._buf.copy()

    def consume(self, n_samples: int) -> np.ndarray:
        chunk = self._buf[:n_samples].copy()
        self._buf = self._buf[n_samples:]
        return chunk

    def __len__(self) -> int:
        return len(self._buf)


class MeetingPipeline:
    """实时会议流水线

    构造函数支持依赖注入：调用方可显式传入 vad_engine / asr_service / voiceprint_service，
    避免共享全局单例状态（VAD 累积 buffer 污染）。未注入时使用懒加载默认实例。
    """

    def __init__(
        self,
        vad_engine=None,
        asr_service=None,
        voiceprint_service=None,
    ):
        """
        接受注入的依赖。如未提供，使用懒加载默认。
        推荐在 /live 端点显式注入以避免 VAD 状态污染。
        """
        from app.voice.vad import VADEngine, get_vad_engine
        from app.voice.asr import asr_service as default_asr
        from app.services.voiceprint_service import voiceprint_service as default_vp

        self.vad = vad_engine if vad_engine is not None else get_vad_engine()
        self.asr = asr_service if asr_service is not None else default_asr
        self.vp = voiceprint_service if voiceprint_service is not None else default_vp

    async def process_audio(self, audio_chunk: bytes, db, elapsed: float) -> list[dict]:
        # 1. 转换 Int16 PCM bytes → float32 ndarray
        if isinstance(audio_chunk, bytes):
            audio_array = np.frombuffer(audio_chunk, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            audio_array = audio_chunk

        # 2. VAD（per-instance）
        speech_segment = self.vad.process_chunk(audio_array)
        if speech_segment is None or len(speech_segment) == 0:
            return []

        # 3. ASR
        wav_data = self._to_wav(speech_segment)
        try:
            asr_result = await self.asr.transcribe(wav_data, language="zh")
            text = asr_result.get("text", "").strip()
        except Exception as e:
            logger.error(f"ASR 失败: {e}")
            return []

        if not text:
            return []

        # 4. Voiceprint
        try:
            name, member_id, confidence = await self.vp.identify_speaker(db, speech_segment)
        except Exception as e:
            logger.error(f"Voiceprint 失败: {e}")
            name, member_id, confidence = None, None, 0.0

        return [{
            "type": "transcript",
            "speaker": name or "unknown",
            "member_id": member_id,
            "confidence": confidence,
            "text": text,
            "start": elapsed,
            "end": elapsed + len(speech_segment) / 16000,
        }]

    def _to_wav(self, audio_float32: np.ndarray) -> bytes:
        """float32 ndarray → WAV bytes"""
        int16_data = (audio_float32 * 32768.0).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(int16_data.tobytes())
        return buf.getvalue()

    def reset(self):
        """重置流水线状态"""
        self.vad.reset()


# 全局默认（懒加载向后兼容）
meeting_pipeline = MeetingPipeline()
