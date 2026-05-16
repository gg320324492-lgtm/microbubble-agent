"""语音识别模块 - 基于 faster-whisper"""

import io
import numpy as np
from typing import Optional, Tuple
from faster_whisper import WhisperModel

from app.config import settings


class SpeechRecognizer:
    """语音识别服务"""

    def __init__(self):
        self.model = None
        self._initialized = False

    def _init_model(self):
        """延迟初始化模型"""
        if self._initialized:
            return

        print(f"正在加载Whisper模型: {settings.WHISPER_MODEL_SIZE}")
        self.model = WhisperModel(
            settings.WHISPER_MODEL_SIZE,
            device=settings.WHISPER_DEVICE,
            compute_type="float16" if settings.WHISPER_DEVICE == "cuda" else "int8"
        )
        self._initialized = True
        print("Whisper模型加载完成")

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh",
        task: str = "transcribe"
    ) -> dict:
        """
        语音识别

        Args:
            audio_data: 音频数据（支持wav, mp3, m4a等格式）
            language: 语言代码，默认中文
            task: 任务类型 - transcribe(转写) 或 translate(翻译)

        Returns:
            识别结果，包含文本、语言、时间段等信息
        """
        self._init_model()

        # 将音频数据转换为numpy数组
        audio_array = self._bytes_to_array(audio_data)

        # 执行识别
        segments, info = self.model.transcribe(
            audio_array,
            language=language,
            task=task,
            beam_size=5,
            vad_filter=True,  # 启用VAD过滤静音
            vad_parameters=dict(
                min_silence_duration_ms=500
            )
        )

        # 收集结果
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

    async def transcribe_stream(self, audio_chunk: bytes):
        """
        流式语音识别（用于实时转写）

        Args:
            audio_chunk: 音频数据块

        Yields:
            识别的文本片段
        """
        self._init_model()

        # 将音频块转换为numpy数组
        audio_array = self._bytes_to_array(audio_chunk)

        # 执行识别
        segments, _ = self.model.transcribe(
            audio_array,
            language="zh",
            beam_size=5,
            vad_filter=True
        )

        for segment in segments:
            yield {
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip()
            }

    def _bytes_to_array(self, audio_data: bytes) -> np.ndarray:
        """
        将音频字节数据转换为numpy数组

        支持多种音频格式，自动使用ffmpeg转换
        """
        import subprocess
        import tempfile
        import os

        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name

        try:
            # 使用ffmpeg转换为wav格式
            output_path = tmp_path + ".converted.wav"
            subprocess.run([
                "ffmpeg", "-i", tmp_path,
                "-ar", "16000",  # 采样率16kHz
                "-ac", "1",      # 单声道
                "-f", "wav",
                "-y",
                output_path
            ], capture_output=True, check=True)

            # 读取wav文件
            import wave
            with wave.open(output_path, "rb") as wf:
                audio_array = np.frombuffer(
                    wf.readframes(wf.getnframes()),
                    dtype=np.int16
                ).astype(np.float32) / 32768.0

            return audio_array

        finally:
            # 清理临时文件
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            if os.path.exists(output_path):
                os.unlink(output_path)


# 全局实例
asr_service = SpeechRecognizer()
