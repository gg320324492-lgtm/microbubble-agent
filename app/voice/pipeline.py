"""实时声纹会议流水线 — VAD → 声纹识别 → ASR → 实时输出

集成 silero-vad + 3D-Speaker + faster-whisper，通过 WebSocket 流式输出。
"""

import asyncio
import json
import logging
import time
from typing import Optional

import numpy as np

from app.voice.vad import SAMPLE_RATE, vad_engine

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
    """实时会议流水线"""

    def __init__(self):
        self._asr_model = None
        self._voiceprint = None

    def _load_asr(self):
        if self._asr_model is not None:
            return
        from faster_whisper import WhisperModel
        from app.config import settings as s
        from app.voice.asr import INITIAL_PROMPT

        logger.info(f"加载 faster-whisper: {s.WHISPER_MODEL_SIZE}")
        self._asr_model = WhisperModel(
            s.WHISPER_MODEL_SIZE,
            device=s.WHISPER_DEVICE,
            compute_type="float16" if s.WHISPER_DEVICE == "cuda" else "int8",
        )
        self._init_prompt = INITIAL_PROMPT

    async def _get_voiceprint(self):
        if self._voiceprint is not None:
            return self._voiceprint
        from app.services.voiceprint_service import voiceprint_service
        self._voiceprint = voiceprint_service
        return self._voiceprint

    async def process_audio(
        self,
        audio_chunk: bytes,
        db,
        elapsed: float,
    ) -> list[dict]:
        """处理单个音频块，返回检测到的语音结果列表。

        Returns:
            [{type: "transcript", speaker: str, text: str, confidence: float, start: float, end: float}, ...]
        """
        # 将 WebM/opus bytes 转为 numpy float32
        audio_array = self._bytes_to_float32(audio_chunk)
        if audio_array is None or len(audio_array) == 0:
            return []

        # VAD 检测
        speech_segment = vad_engine.process_chunk(audio_array)
        if speech_segment is None or len(speech_segment) < SAMPLE_RATE * 0.3:
            return []

        # 声纹识别
        vp = await self._get_voiceprint()
        speaker_name, member_id, confidence = await vp.identify_speaker(db, speech_segment)

        if not speaker_name:
            speaker_name = "发言人"
            confidence = 0.0

        # ASR 转写
        self._load_asr()
        text = await self._transcribe(speech_segment)

        if not text.strip():
            return []

        # 计算时间戳
        segment_duration = len(speech_segment) / SAMPLE_RATE
        start_time = elapsed - segment_duration

        return [{
            "type": "transcript",
            "speaker": speaker_name,
            "speaker_id": member_id,
            "speaker_confidence": round(confidence, 3),
            "text": text.strip(),
            "start": round(start_time, 2),
            "end": round(elapsed, 2),
        }]

    async def _transcribe(self, audio: np.ndarray) -> str:
        """将语音段转写为文本（线程池中运行）。"""
        async def _run():
            segments, _ = self._asr_model.transcribe(
                audio,
                language="zh",
                beam_size=3,
                vad_filter=False,  # 已由 silero-vad 预处理
                initial_prompt=self._init_prompt,
            )
            parts = []
            for seg in segments:
                parts.append(seg.text.strip())
            return "".join(parts)

        return await asyncio.to_thread(_run)

    def _bytes_to_float32(self, data: bytes) -> Optional[np.ndarray]:
        """将音频 bytes 转为 float32 numpy 数组。

        优先尝试直接解析 PCM Int16（前端 AudioWorklet 默认格式），
        失败时回退到 ffmpeg 转码。
        """
        if not data:
            return None

        # 1. 尝试直接解析 Int16 PCM（前端 MeetingRoom 发送的原生格式）
        if len(data) >= 2:
            pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            if len(pcm) > 0 and not np.all(pcm == 0):
                return pcm

        # 2. 回退到 ffmpeg 转码
        import subprocess, tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(data)
            tmp_path = tmp.name

        try:
            try:
                import shutil
                if shutil.which("ffmpeg") is None:
                    logger.warning("ffmpeg 未安装，无法转码音频")
                    return None
            except Exception:
                pass

            output_path = tmp_path + ".wav"
            result = subprocess.run([
                "ffmpeg", "-y", "-i", tmp_path,
                "-ar", str(SAMPLE_RATE), "-ac", "1",
                "-f", "s16le", "-v", "error",
                output_path,
            ], capture_output=True, timeout=5)

            if result.returncode != 0 or not os.path.exists(output_path):
                return None

            with open(output_path, "rb") as f:
                raw = f.read()
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        except Exception as e:
            logger.error(f"音频转码失败: {e}")
            return None
        finally:
            for p in [tmp_path, tmp_path + ".wav"]:
                if os.path.exists(p):
                    try: os.unlink(p)
                    except Exception: pass

    def reset(self):
        """重置流水线状态"""
        vad_engine.reset()


# 全局单例
meeting_pipeline = MeetingPipeline()
