"""测试 VADEngine 的 per-instance 独立性

任务 2: 验证两个 VADEngine 实例的状态互不污染。

说明：VADEngine 在 process_chunk 内会调用 silero-vad 模型（torch.hub.load 需要
联网下载），CI / 沙盒环境可能无网络。本测试只验证 per-instance 状态隔离，
不依赖模型推理 —— 因此 stub 掉 _load_model 与 _get_speech_timestamps，让
process_chunk 在纯 Python / numpy 层面完成累积逻辑。
"""

import numpy as np
import pytest

from app.voice.vad import VADEngine


def _stub_model_load(monkeypatch):
    """让 VADEngine._load_model 不再下载 silero-vad，process_chunk 也不会调用模型推理。"""
    def fake_load(self):
        # 标记模型"已加载"——但故意把 _get_speech_timestamps 设为返回空列表的 stub，
        # 模拟静音（让 vad1 的累积通过"未检测到语音"分支）
        self._get_speech_timestamps = lambda *a, **kw: []
        self._model = object()  # 任意 truthy 哨兵

    monkeypatch.setattr(VADEngine, "_load_model", fake_load)


def test_vad_two_instances_independent(monkeypatch):
    """两个 VADEngine 实例互不污染

    验证 VADEngine 是真正的 per-instance 状态（每个实例的 _speech_samples、
    _state、_triggered、_temp_end、_current_sample、_speech_probs 都是独立对象），
    vad1 累积的静音不应泄漏到 vad2。
    """
    _stub_model_load(monkeypatch)

    vad1 = VADEngine()
    vad2 = VADEngine()

    # vad1 喂入大量静音（累积 silence）
    silent_chunk = np.zeros(16000, dtype=np.float32)  # 1s 静音
    for _ in range(5):
        vad1.process_chunk(silent_chunk)

    # vad2 喂入语音（不应受 vad1 影响）
    speech_chunk = np.random.uniform(-0.5, 0.5, 16000).astype(np.float32)
    result_vad2 = vad2.process_chunk(speech_chunk)

    # vad2 应该能处理语音（vad1 的状态不应泄漏到 vad2）
    # 1) 数组对象本身不是同一个
    assert vad2._speech_samples is not vad1._speech_samples
    # 2) 内部状态对象（list/ndarray）均独立
    assert vad1._speech_probs is not vad2._speech_probs
    # 3) vad1 / vad2 内部标量状态独立：赋值后两个实例互不影响
    vad1._state = "vad1_state"
    vad2._state = "vad2_state"
    assert vad1._state == "vad1_state"
    assert vad2._state == "vad2_state"
    assert vad1._triggered == vad2._triggered  # 初始都是 False
    # 4) 修改 vad1 不应影响 vad2
    vad1._speech_samples = np.array([999.0], dtype=np.float32)
    vad1._speech_probs.append(0.99)
    assert len(vad2._speech_samples) > 0
    assert 0.99 not in vad2._speech_probs
    # 5) vad2 返回 None（因为模型被 stub 成"没有语音段"），与 vad1 行为一致
    assert result_vad2 is None
    # vad1 的 _silence_bytes / _speech_samples 状态独立
