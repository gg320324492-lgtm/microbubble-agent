"""音频工具函数

- decode_audio_to_float32(bytes) -> np.ndarray
  接受任意 ffmpeg 支持的格式（webm/wav/mp3/amr/silk/...），
  转成 16kHz 单声道 float32 ndarray，供 3D-Speaker / Whisper 使用。

复用于：
- app/api/v1/voiceprint.py（前端上传音频）
- app/wechat/handler.py（企业微信语音消息）
"""

import io
import logging
import os
import subprocess
import tempfile

import numpy as np

logger = logging.getLogger("microbubble.utils.audio")

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


async def decode_audio_to_float32(
    audio_data: bytes,
    *,
    timeout: float = 15.0,
) -> np.ndarray:
    """把任意音频字节流转成 16kHz 单声道 float32 ndarray（范围 [-1, 1]）

    内部调用 ffmpeg 把任意输入转成 PCM s16le 16kHz mono，再用 numpy 转 float32。
    失败抛 RuntimeError，调用方负责 try/except。

    Args:
        audio_data: 原始音频字节流
        timeout: ffmpeg 转换超时（秒），默认 15s

    Returns:
        float32 ndarray，shape (n_samples,)，采样率 16kHz
    """
    if not audio_data or len(audio_data) < 100:
        raise ValueError(f"音频数据太短（{len(audio_data) if audio_data else 0} bytes）")

    tmp_path = None
    output_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".audio", delete=False) as tmp:
            tmp.write(audio_data)
            tmp_path = tmp.name
        output_path = tmp_path + ".s16le"

        # 在线程池中跑 ffmpeg（CPU 重活，避免阻塞事件循环）
        import asyncio
        await asyncio.to_thread(
            _run_ffmpeg,
            tmp_path,
            output_path,
            timeout,
        )

        with open(output_path, "rb") as f:
            raw = f.read()

        audio_array = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        logger.info(
            f"音频解码完成: {len(audio_data)} bytes → {len(audio_array)} samples "
            f"({len(audio_array) / TARGET_SAMPLE_RATE:.2f}s @ {TARGET_SAMPLE_RATE}Hz)"
        )
        return audio_array

    finally:
        for p in (tmp_path, output_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def _run_ffmpeg(input_path: str, output_path: str, timeout: float) -> None:
    """同步跑 ffmpeg，失败抛 RuntimeError"""
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", input_path,
                "-ar", str(TARGET_SAMPLE_RATE),
                "-ac", str(TARGET_CHANNELS),
                "-f", "s16le",
                "-v", "error",
                output_path,
            ],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(f"ffmpeg 转换超时（{timeout}s）") from e
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode("utf-8", errors="ignore") if e.stderr else ""
        raise RuntimeError(f"ffmpeg 转换失败: {stderr[:200]}") from e
    except FileNotFoundError:
        raise RuntimeError("ffmpeg 未安装或不在 PATH 中")


def is_audio_silent(audio: np.ndarray, threshold: float = 1e-4) -> bool:
    """快速判断音频是否为静音（能量低于阈值）"""
    if audio is None or len(audio) == 0:
        return True
    energy = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    return energy < threshold
