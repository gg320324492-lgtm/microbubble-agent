import pytest
from app.voice.segmenter import LiveSegmenter


def make_silent_pcm(duration_ms: int) -> bytes:
    """生成静音 PCM (16kHz, int16)"""
    num_samples = int(16000 * duration_ms / 1000)
    return b"\x00\x00" * num_samples


def make_speech_pcm(duration_ms: int) -> bytes:
    """生成有声音 PCM (16kHz, int16)"""
    num_samples = int(16000 * duration_ms / 1000)
    # 振幅 8000 (50% 音量)
    return (b"\x20\x1f" * num_samples)


def test_segmenter_silence_threshold():
    """静音 > 1.5s 触发 True"""
    seg = LiveSegmenter(silence_threshold_ms=1500, max_segment_ms=8000)
    # 说话 500ms
    assert seg.feed(make_speech_pcm(500)) is False
    # 静音 1.5s
    assert seg.feed(make_silent_pcm(1500)) is True


def test_segmenter_max_length():
    """累积 > 8s 强制触发 True（即使没静音）"""
    seg = LiveSegmenter(silence_threshold_ms=1500, max_segment_ms=8000)
    # 持续说话 7.9s
    assert seg.feed(make_speech_pcm(7900)) is False
    # 再加 200ms 累计 8.1s
    assert seg.feed(make_speech_pcm(200)) is True


def test_segmenter_drain():
    """drain 后 buffer 清空"""
    seg = LiveSegmenter()
    seg.feed(make_speech_pcm(500))
    seg.feed(make_speech_pcm(500))
    drained = seg.drain()
    assert len(drained) == 16000 * 2  # 1s
    # 再次 drain 应为空
    assert seg.drain() == b""


def test_segmenter_silence_resets_on_speech():
    """说话会重置静音计数器"""
    seg = LiveSegmenter(silence_threshold_ms=1500)
    seg.feed(make_silent_pcm(1000))
    seg.feed(make_speech_pcm(100))  # 重置
    # 再次静音 1500ms 才触发
    assert seg.feed(make_silent_pcm(1499)) is False
    assert seg.feed(make_silent_pcm(1)) is True
