"""语音识别模块 - 调用 Whisper 服务或本地模型"""

import time
import numpy as np
from typing import Optional
import httpx

from app.config import settings
from app.voice.postprocess import postprocess_result


WHISPER_SERVICE_URL = settings.WHISPER_SERVICE_URL

# 领域提示词 - 帮助 Whisper 识别专业术语
INITIAL_PROMPT = "微纳米气泡，zeta电位，表面活性剂，空化效应，气液界面，传质效率，溶解氧，粒径分布，含气量，界面张力"


class SpeechRecognizer:
    """语音识别服务 - 优先调用远程 Whisper 服务，回退到本地模型"""

    def __init__(self):
        self._local_model = None
        self._use_remote: Optional[bool] = None
        self._remote_check_time: float = 0

    async def _check_remote(self) -> bool:
        """检测远程 Whisper 服务是否可用（60秒 TTL）"""
        if self._use_remote is not None and time.time() - self._remote_check_time < 60:
            return self._use_remote
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{WHISPER_SERVICE_URL}/health")
                self._use_remote = resp.status_code == 200
        except Exception:
            self._use_remote = False
        self._remote_check_time = time.time()
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
        task: str = "transcribe",
        skip_convert: bool = False
    ) -> dict:
        """语音识别

        Args:
            audio_data: 音频字节数据
            language: 语言代码
            task: 任务类型 (transcribe/translate)
            skip_convert: 跳过 ffmpeg 转码（调用方已转为 16kHz WAV 时使用）
        """
        if await self._check_remote():
            try:
                return await self._transcribe_remote(audio_data, language, task)
            except Exception:
                pass  # 远程失败，回退本地
        return await self._transcribe_local(audio_data, language, task, skip_convert)

    async def _transcribe_remote(self, audio_data: bytes, language: str, task: str) -> dict:
        """调用远程 Whisper 服务"""
        import logging
        logger = logging.getLogger("microbubble.asr")
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{WHISPER_SERVICE_URL}/transcribe",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                data={"language": language, "task": task}
            )
            if resp.status_code != 200:
                logger.error(f"Whisper 服务返回错误: status={resp.status_code}, body={resp.text[:500]}, audio_size={len(audio_data)}")
            resp.raise_for_status()
            return resp.json()

    async def _transcribe_local(self, audio_data: bytes, language: str, task: str, skip_convert: bool = False) -> dict:
        """使用本地模型识别"""
        import asyncio

        def _run():
            self._init_local_model()
            if skip_convert:
                # 调用方已转为 16kHz WAV，直接读取
                import wave
                import tempfile
                import os
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    tmp.write(audio_data)
                    tmp_path = tmp.name
                try:
                    with wave.open(tmp_path, "rb") as wf:
                        audio_array = np.frombuffer(
                            wf.readframes(wf.getnframes()), dtype=np.int16
                        ).astype(np.float32) / 32768.0
                finally:
                    os.unlink(tmp_path)
            else:
                audio_array = self._bytes_to_array(audio_data)

            segments, info = self._local_model.transcribe(
                audio_array, language=language, task=task,
                beam_size=3,
                # 2026-06-03 关闭 Whisper 内置 VAD：已有 silero-vad 做 VAD
                vad_filter=False,
                initial_prompt=INITIAL_PROMPT,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                temperature=0,
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
            result = {
                "text": full_text.strip(),
                "language": info.language,
                "language_probability": info.language_probability,
                "duration": info.duration,
                "segments": segments_list
            }
            return postprocess_result(result)

        return await asyncio.to_thread(_run)

    async def transcribe_stream(self, audio_chunk: bytes):
        """流式语音识别（仅本地模型支持）"""
        import asyncio

        def _run():
            self._init_local_model()
            audio_array = self._bytes_to_array(audio_chunk)
            segments, _ = self._local_model.transcribe(
                audio_array, language="zh", beam_size=3,
                vad_filter=False,  # 2026-06-03 关闭 Whisper 内置 VAD
                initial_prompt=INITIAL_PROMPT,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                temperature=0,
            )
            return [{"start": s.start, "end": s.end, "text": s.text.strip()} for s in segments]

        for seg in await asyncio.to_thread(_run):
            yield seg

    async def transcribe_wechat_voice(self, audio_data: bytes, language: str = "zh") -> dict:
        """识别微信语音消息（自动检测 SILK/AMR/WAV 格式并转换为 WAV 后识别）

        Args:
            audio_data: 原始音频字节（可能是 SILK、AMR 或 WAV 格式）
            language: 语言代码

        Returns:
            识别结果 dict，包含 text 字段
        """
        from app.voice.silk import silk_to_wav
        import logging
        logger = logging.getLogger("microbubble.asr")

        # 检测格式
        header = audio_data[:4] if len(audio_data) >= 4 else b''
        logger.info(f"微信语音: size={len(audio_data)}, header={header.hex()}")

        # WAV 格式直接识别
        if header == b'RIFF':
            logger.info("WAV 格式，直接识别")
            return await self.transcribe(audio_data, language=language, skip_convert=True)

        # SILK 格式：pilk 解码 → WAV
        if header != b'#!AM':
            logger.info("SILK 格式，pilk 解码为 WAV")
            wav_data = await silk_to_wav(audio_data)
            return await self.transcribe(wav_data, language=language, skip_convert=True)

        # AMR 格式：通过 silk_to_wav 内部的 ffmpeg 转换为 WAV
        logger.info("AMR 格式，通过 ffmpeg 转 WAV")
        wav_data = await silk_to_wav(audio_data)
        return await self.transcribe(wav_data, language=language, skip_convert=True)

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
