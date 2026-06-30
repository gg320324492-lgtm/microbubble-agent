"""语音识别模块 - SenseVoice 单后端 (2026-06-30 ASR 迁移完成)

迁移背景:
- 旧版: Whisper large-v3 8 GB VRAM + 本地模型 fallback
- 新版: SenseVoice-Small 1.1 GB VRAM, 长音频自动 chunked (60s)
- 详见 docs/asr-benchmark-2026-06-30.md + plan woolly-pondering-muffin.md
"""
import asyncio
import logging
import time
import wave
import subprocess
import tempfile
import os
from typing import Optional

import httpx
import numpy as np

from app.config import settings
from app.voice.asr_filters import apply_7_layers

logger = logging.getLogger("microbubble.asr")

# SenseVoice HTTP 服务 URL (docker 内网域名, 通过 docker-compose.yml 解析)
SENSEVOICE_SERVICE_URL = settings.SENSEVOICE_SERVICE_URL

# 领域提示词 (SenseVoice 不直接支持 initial_prompt, 仅作为后处理参考)
DOMAIN_TERMS = (
    "微纳米气泡,zeta电位,表面活性剂,空化效应,气液界面,传质效率,"
    "溶解氧,粒径分布,含气量,界面张力"
)


class SpeechRecognizer:
    """
    语音识别服务 - SenseVoice 单后端 HTTP 调用.

    设计:
    - 单一后端, 无 fallback (2026-06-30 单模型策略)
    - 长音频自动 chunked (服务器端处理, 客户端无感)
    - 7 层幻觉过滤集成在客户端
    - SenseVoice 服务在 docker sensevoice 容器 (port 8003)
    """

    def __init__(self):
        self._healthy: Optional[bool] = None
        self._health_check_time: float = 0
        # 长音频阈值 (秒): 超过此值会在服务端走 chunked 路径
        self.long_audio_threshold_sec = 300  # 5 min

    async def _check_remote(self) -> bool:
        """检测 SenseVoice 服务健康 (60 秒 TTL 缓存)"""
        if self._healthy is not None and time.time() - self._health_check_time < 60:
            return self._healthy
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(f"{SENSEVOICE_SERVICE_URL}/health")
                self._healthy = resp.status_code == 200
        except Exception as e:
            logger.warning(f"[asr] SenseVoice health check failed: {e}")
            self._healthy = False
        self._health_check_time = time.time()
        return self._healthy

    async def transcribe(
        self,
        audio_data: bytes,
        language: str = "zh",
        task: str = "transcribe",
        skip_convert: bool = False,
    ) -> dict:
        """
        语音识别主入口 (单后端 SenseVoice HTTP).

        Args:
            audio_data: 音频字节数据
            language: 语言代码 (zh / en / yue / ja / ko / auto)
            task: 任务类型 (保留参数, SenseVoice 不区分)
            skip_convert: 跳过 ffmpeg 转码 (调用方已转 16kHz WAV 时用)

        Returns:
            SenseVoice 标准响应: {
                "text": "...",
                "raw_text": "...",
                "language": "zh",
                "duration": 12.3,
                "segments": [...],
                "_backend": "sensevoice",
                "_inference_mode": "single" | "chunked",
                "_n_chunks": 1 | 174,
            }
        """
        if not await self._check_remote():
            raise RuntimeError(
                f"SenseVoice service not available at {SENSEVOICE_SERVICE_URL}. "
                "Check docker compose ps sensevoice."
            )

        return await self._transcribe_remote(audio_data, language, task, skip_convert)

    async def _transcribe_remote(
        self, audio_data: bytes, language: str, task: str, skip_convert: bool
    ) -> dict:
        """
        调用 SenseVoice HTTP 服务.

        长音频 (>= 5min) 在服务端自动 chunked (60s × N).
        客户端只关心 response schema, 不需关心推理路径.
        """
        # 若调用方未转码, 客户端先转 16kHz mono WAV (降低服务负载)
        if not skip_convert:
            audio_data = self._bytes_to_wav(audio_data)

        # HTTP 上传给 SenseVoice 服务
        async with httpx.AsyncClient(timeout=600) as client:  # 10 min timeout (3h 会议 < 60s)
            resp = await client.post(
                f"{SENSEVOICE_SERVICE_URL}/transcribe",
                files={"audio": ("audio.wav", audio_data, "audio/wav")},
                data={"language": language, "task": task},
            )
            if resp.status_code != 200:
                logger.error(
                    f"[asr] SenseVoice 服务错误: status={resp.status_code}, "
                    f"body={resp.text[:500]}, audio_size={len(audio_data)}"
                )
            resp.raise_for_status()
            result = resp.json()

        # 后处理: 7 层幻觉过滤 (CLAUDE.md memory/asr-benchmark-2026-06-30)
        result["text"] = apply_7_layers(
            result.get("text", ""),
            audio_rms=1.0,  # SenseVoice 不返回 per-segment RMS, 用 1.0 跳过弱幻觉过滤
        )
        # segments 也过滤
        if "segments" in result and isinstance(result["segments"], list):
            result["segments"] = [
                {**seg, "text": apply_7_layers(seg.get("text", ""), audio_rms=1.0)}
                for seg in result["segments"]
                if seg.get("text", "").strip()
            ]
        return result

    async def transcribe_stream(self, audio_chunk: bytes):
        """
        流式语音识别 - 当前实现: 每个 chunk 单独调 HTTP /transcribe.
        SenseVoice 60s chunk 推理 ~60ms, 30s 批延迟可接受 (实测).
        未来如需更低延迟, 可扩展 SenseVoice 服务端 WebSocket 端点.
        """
        result = await self.transcribe(audio_chunk)
        for seg in result.get("segments", []):
            yield seg

    async def transcribe_wechat_voice(self, audio_data: bytes, language: str = "zh") -> dict:
        """
        识别微信语音消息 (SILK/AMR/WAV 自动检测 + 转换为 WAV)

        2026-06-30 ASR 迁移: 底层从本地 Whisper 改为 SenseVoice HTTP.
        """
        from app.voice.silk import silk_to_wav

        # 检测格式
        header = audio_data[:4] if len(audio_data) >= 4 else b""
        logger.info(f"[asr] 微信语音: size={len(audio_data)}, header={header.hex()}")

        # WAV 格式直接识别
        if header == b"RIFF":
            return await self.transcribe(audio_data, language=language, skip_convert=True)

        # SILK / AMR 格式: 走 silk_to_wav 转换
        wav_data = await silk_to_wav(audio_data)
        return await self.transcribe(wav_data, language=language, skip_convert=True)

    def _bytes_to_wav(self, audio_data: bytes) -> bytes:
        """任意格式音频 → 16kHz mono WAV bytes (降低服务负载, 节省网络)"""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_in:
            tmp_in.write(audio_data)
            tmp_in_path = tmp_in.name
        tmp_out_path = tmp_in_path + ".16k.wav"
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", tmp_in_path,
                    "-ar", "16000", "-ac", "1", "-f", "wav", tmp_out_path,
                ],
                check=True, capture_output=True,
            )
            with open(tmp_out_path, "rb") as f:
                return f.read()
        finally:
            for p in [tmp_in_path, tmp_out_path]:
                if os.path.exists(p):
                    os.unlink(p)


# 全局实例
asr_service = SpeechRecognizer()
