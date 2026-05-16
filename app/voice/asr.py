"""语音识别模块 - 调用 Whisper 服务或本地模型"""

import io
import numpy as np
from typing import Optional
import httpx

from app.config import settings


WHISPER_SERVICE_URL = "http://whisper:8002"


class SpeechRecognizer:
    """语音识别服务 - 优先调用远程 Whisper 服务，回退到本地模型"""

    def __init__(self):
        self._local_model = None
        self._use_remote: Optional[bool] = None

    async def _check_remote(self) -> bool:
        """检测远程 Whisper 服务是否可用"""
        if self._use_remote is not None:
            return self._use_remote
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{WHISPER_SERVICE_URL}/health")
                self._use_remote = resp.status_code == 200
        except Exception:
            self._use_remote = False
        return self._use_remote

    def _init_local_model(self):
        """延迟加载本地 Whisper 模型"""
        if self._local_model is not None:
            return
        from faster_whisper import WhisperModel
        print(f"正在加载本地 Whisper 模型: {settings.WHISPER_MODEL_SIZE}")
        self._local_model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type="float16" if settings.WHISPER_DEVICE == "cuda" else "int8"
        )
        print("本地 Whisper 模型加载完成")

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh",
        task: str = "transcribe"
    ) -> dict:
        """语音识别"""
        if await self._check_remote():
            return await self._transcribe_remote(audio_data, language, task)
        return await self._transcribe_local(audio_data, language, task)

    async def _transcribe_remote(self, audio_data: bytes, language: str, task: str) -> dict:
        """调用远程 Whisper 服务"""
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{WHISPER_SERVICE_URL}/transcribe",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                data={"language": language, "task": task}
            )
            resp.raise_for_status()
            return resp.json()

    async def _transcribe_local(self, audio_data: bytes, language: str, task: str) -> dict:
        """使用本地模型识别"""
        import asyncio

        def _run():
            self._init_local_model()
            audio_array = self._bytes_to_array(audio_data)
            segments, info = self._local_model.transcribe(
                audio_array, language=language, task=task,
                beam_size=5, vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )
            segments_list = []
            full_text = ""
            for segment in segments:
                segments_list.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text.strip()
                })
                full_text += segment.text
            return {
                "text": full_text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": segments_list
            }

        return await asyncio.to_thread(_run)

    async def transcribe_stream(self, audio_chunk: bytes):
        """流式语音识别（仅本地模型支持）"""
        import asyncio

        def _run():
            self._init_local_model()
            audio_array = self._bytes_to_array(audio_chunk)
            segments, _ = self._local_model.transcribe(
                audio_array, language="zh", beam_size=5, vad_filter=True
            )
            return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]

        for seg in await asyncio.to_thread(_run):
            yield seg

    def _bytes_to_array(self, audio_data: bytes) -> np.ndarray:
        """将音频字节数据转换为numpy数组"""
        import subprocess
        import tempfile
        import os
        import wave

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            output_path = tmp_path + ".converted.wav"
            subprocess.run([
                "ffmpeg", "-i", tmp_path,
                "-ar", "16000", "-ac", "1", "-f", "wav", "-y", output_path
            ], capture_output=True, check=True)

            with wave.open(output_path, "rb") as wf:
                audio_array = np.frombuffer(
                    wf.readframes(wf.getnframes()), dtype=np.int16
                ).astype(np.float32) / 32768.0
            return audio_array
        finally:
            for p in [tmp_path, output_path]:
                if os.path.exists(p):
                    os.unlink(p)


# 全局实例
asr_service = SpeechRecognizer()
