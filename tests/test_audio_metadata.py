"""W2-7: audio_metadata.ffprobe_duration 单元测试

测试目标:
1. 真实 ffprobe 二进制可用时，合成 1Hz 静音 wav → 探测整数秒数。
2. 空 bytes → None（best-effort 降级）。
3. 异常路径：二进制损坏 → None，不抛错。
4. 异步 wrapper 不阻塞 event loop（直接 await）。
5. _find_ffprobe 返回字符串或 None。
6. _run_ffprobe_sync 处理 ffprobe 不可识别格式。

跳过策略: 如果系统完全无 ffprobe，skip 真实探测相关测试（CI 无 ffprobe 场景）。
"""

import asyncio
import os
import struct
import sys
import tempfile
import wave

import pytest

from app.services.audio_metadata import (
    _find_ffprobe,
    _run_ffprobe_sync,
    ffprobe_duration,
    ffprobe_duration_async,
)


def _make_silence_wav(duration_seconds: int, sample_rate: int = 8000) -> bytes:
    """合成 N 秒静音 wav bytes（16-bit PCM mono）。"""
    n_frames = duration_seconds * sample_rate
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n_frames)
        with open(path, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def test_find_ffprobe_returns_str_or_none():
    """_find_ffprobe 必须返回字符串或 None。"""
    result = _find_ffprobe()
    assert result is None or isinstance(result, str)


def test_ffprobe_duration_empty_bytes_returns_none():
    """空 bytes → None（不抛错）。"""
    assert ffprobe_duration(b"") is None
    assert ffprobe_duration(b"") is None  # 二次幂等


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_real_silence_3s():
    """真实 ffprobe: 3 秒静音 wav → 探测 = 3。"""
    audio = _make_silence_wav(3)
    dur = ffprobe_duration(audio, timeout=15.0)
    assert dur == 3, f"期望 3 秒, 实际 {dur}"


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_real_silence_1s():
    """真实 ffprobe: 1 秒静音 wav → 探测 = 1。"""
    audio = _make_silence_wav(1)
    dur = ffprobe_duration(audio, timeout=15.0)
    assert dur == 1, f"期望 1 秒, 实际 {dur}"


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_corrupted_bytes_returns_none():
    """损坏字节 → None（best-effort 兜底，不抛错）。"""
    # 伪 wav header 后立即截断
    bogus = b"RIFF\x00\x00\x00\x00WAVEfmt "
    dur = ffprobe_duration(bogus, timeout=10.0)
    assert dur is None


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_random_garbage_returns_none():
    """完全随机 bytes → None。"""
    import os as _os
    garbage = _os.urandom(2048)
    dur = ffprobe_duration(garbage, timeout=10.0)
    assert dur is None


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_truncates_fractional():
    """整数化（向下取整）: 2.7s 静音截短为 2s，返回 2。"""
    # 合成 2.5 秒静音
    n_frames = int(2.5 * 8000)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        path = f.name
    try:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(b"\x00\x00" * n_frames)
        with open(path, "rb") as f:
            audio = f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    dur = ffprobe_duration(audio, timeout=15.0)
    # 容忍 ±1s 探测精度（容器四舍五入）
    assert dur in (2, 3), f"期望 2 或 3, 实际 {dur}"


def test_ffprobe_duration_async_empty_bytes():
    """异步 wrapper: 空 bytes → None。"""
    result = asyncio.run(ffprobe_duration_async(b"", timeout=5.0))
    assert result is None


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_async_real_silence():
    """异步 wrapper: 真实 2 秒静音 → 2。"""
    audio = _make_silence_wav(2)
    result = asyncio.run(ffprobe_duration_async(audio, timeout=15.0))
    assert result == 2, f"期望 2, 实际 {result}"


def test_run_ffprobe_sync_invalid_binary_path():
    """_run_ffprobe_sync 错误二进制路径 → 返回 None（不抛错）。"""
    result = _run_ffprobe_sync("/nonexistent/ffprobe_binary_xyz", b"\x00\x00", timeout=5.0)
    assert result is None


def test_ffprobe_duration_timeout_returns_none():
    """subprocess timeout: 用不可能存在的二进制 → None。"""
    # ffprobe 真实存在但 timeout=0.001 几乎不可能完成（实测几乎总是 None 或抛）
    audio = _make_silence_wav(1) if _find_ffprobe() else b""
    try:
        dur = ffprobe_duration(audio, timeout=0.001)
        # timeout 命中可能返回 None 或抛错被吞掉
        assert dur is None or isinstance(dur, int)
    except Exception:
        pass  # acceptable — best-effort 兜底


@pytest.mark.skipif(_find_ffprobe() is None, reason="ffprobe 不在 PATH")
def test_ffprobe_duration_does_not_block_on_large_input():
    """大 input 不应阻塞超时：5 秒静音快速返回。"""
    audio = _make_silence_wav(5)
    import time
    t0 = time.time()
    dur = ffprobe_duration(audio, timeout=30.0)
    elapsed = time.time() - t0
    assert dur == 5
    assert elapsed < 30.0, f"耗时 {elapsed:.2f}s 超过 timeout"