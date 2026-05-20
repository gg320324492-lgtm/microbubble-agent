"""SILK v3 音频格式转换工具 - 将微信语音 SILK 格式转为 WAV"""

import asyncio
import logging
import os
import struct
import tempfile
import wave

logger = logging.getLogger("microbubble.voice.silk")


async def silk_to_wav(silk_data: bytes, sample_rate: int = 16000) -> bytes:
    """将 SILK v3 音频字节转换为 WAV 字节（16kHz mono，Whisper 格式）

    Args:
        silk_data: SILK 格式的原始音频字节
        sample_rate: SILK 解码采样率（默认 16000，与 Whisper 一致）

    Returns:
        WAV 格式的音频字节。如果输入已是 WAV 格式则原样返回。
    """
    logger.info(f"silk_to_wav 输入: size={len(silk_data)}, header={silk_data[:10].hex() if len(silk_data) >= 10 else silk_data.hex()}")

    # 快速路径：已经是 WAV 格式
    if len(silk_data) >= 4 and silk_data[:4] == b'RIFF':
        logger.info("音频已是 WAV 格式，跳过转换")
        return silk_data

    # 快速路径：AMR 格式（微信偶尔会发 AMR）
    if len(silk_data) >= 4 and silk_data[:4] == b'#!AM':
        logger.info(f"检测到 AMR 格式，大小 {len(silk_data)} bytes，通过 ffmpeg 转换")
        return await _amr_to_wav(silk_data)

    # 主路径：SILK 格式解码
    logger.debug(f"检测到 SILK 格式，大小 {len(silk_data)} bytes")
    return await _silk_decode_to_wav(silk_data, sample_rate)


async def _silk_decode_to_wav(silk_data: bytes, sample_rate: int = 16000) -> bytes:
    """使用 pilk 解码 SILK 为 WAV"""
    def _convert():
        silk_path = None
        pcm_path = None
        wav_path = None
        try:
            # 写入临时 SILK 文件
            with tempfile.NamedTemporaryFile(suffix=".silk", delete=False) as sf:
                sf.write(silk_data)
                silk_path = sf.name

            pcm_path = silk_path.replace(".silk", ".pcm")
            wav_path = silk_path.replace(".silk", ".wav")

            # 尝试 pilk 解码
            try:
                import pilk
                pilk.decode(silk_path, pcm_path, pcm_rate=sample_rate)
            except ImportError:
                logger.warning("pilk 未安装，尝试 silk-v3-decoder CLI")
                _decode_with_cli(silk_path, pcm_path, sample_rate)
            except Exception as e:
                logger.warning(f"pilk 解码失败: {e}，尝试 CLI 回退")
                _decode_with_cli(silk_path, pcm_path, sample_rate)

            # PCM 16-bit mono → WAV (16kHz for Whisper)
            with open(pcm_path, "rb") as f:
                pcm_data = f.read()

            target_rate = 16000  # Whisper 要求 16kHz
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(target_rate)
                wf.writeframes(pcm_data)

            with open(wav_path, "rb") as f:
                wav_bytes = f.read()

            logger.debug(f"SILK 转换完成: {len(silk_data)} -> {len(wav_bytes)} bytes")
            return wav_bytes

        finally:
            for p in [silk_path, pcm_path, wav_path]:
                if p and os.path.exists(p):
                    try:
                        os.unlink(p)
                    except OSError:
                        pass

    return await asyncio.to_thread(_convert)


def _decode_with_cli(silk_path: str, pcm_path: str, sample_rate: int) -> None:
    """使用 silk-v3-decoder CLI 工具解码"""
    import subprocess
    try:
        subprocess.run(
            ["silk-v3-decoder", silk_path, pcm_path, f"-rate={sample_rate}"],
            capture_output=True, check=True, timeout=30
        )
    except FileNotFoundError:
        raise RuntimeError(
            "SILK 解码失败：pilk 未安装且 silk-v3-decoder 不可用。"
            "请安装 pilk: pip install pilk"
        )


async def _amr_to_wav(amr_data: bytes) -> bytes:
    """使用 ffmpeg 将 AMR 转为 WAV"""
    def _convert():
        with tempfile.NamedTemporaryFile(suffix=".amr", delete=False) as af:
            af.write(amr_data)
            amr_path = af.name

        wav_path = amr_path.replace(".amr", ".wav")
        try:
            import subprocess
            subprocess.run([
                "ffmpeg", "-i", amr_path,
                "-ar", "16000", "-ac", "1", "-f", "wav", "-y", wav_path
            ], capture_output=True, check=True, timeout=30)

            with open(wav_path, "rb") as f:
                return f.read()
        finally:
            for p in [amr_path, wav_path]:
                if os.path.exists(p):
                    os.unlink(p)

    return await asyncio.to_thread(_convert)
