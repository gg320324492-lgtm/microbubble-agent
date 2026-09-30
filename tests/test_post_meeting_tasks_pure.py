"""tests/test_post_meeting_tasks_pure.py — post_meeting_tasks 纯函数层测试

背景 (2026-09-30 S3 第一项): `app/services/post_meeting_tasks.py` 1,131 行
(其中 `post_meeting_process` Celery task 占 1,046 行) **零测试覆盖** —— 而
`docs/plans/2026-09-30-phase-closeout-plan.md` S3 清单把它列为待补测试的模块。

本次只覆盖**纯函数层** (零依赖、可直接验证契约), 不碰 Celery task 主体:
- `_numpy_to_wav_bytes`: float32 PCM → WAV bytes, 声纹/转写链路的编码入口
- `_apply_text_corrections`: 转写后文本纠错映射
- `_edit_distance`: 名字模糊匹配的 Levenshtein 距离

后续若补 Celery task 集成测试 (需 DB + celery eager + ffmpeg), 应另立文件。
"""
from __future__ import annotations

import io
import wave

import numpy as np
import pytest

from app.services.post_meeting_tasks import (
    _apply_text_corrections,
    _edit_distance,
    _numpy_to_wav_bytes,
)


# ==========================================================================
# _numpy_to_wav_bytes
# ==========================================================================


class TestNumpyToWavBytes:
    def test_returns_valid_wav_container(self):
        audio = np.zeros(1600, dtype=np.float32)
        out = _numpy_to_wav_bytes(audio, sample_rate=16000)
        assert isinstance(out, bytes)
        assert out[:4] == b"RIFF" and out[8:12] == b"WAVE", "必须是合法 WAV 容器头"

    def test_header_params(self):
        """声道/采样宽/采样率必须与声纹链路约定一致 (mono / 16bit / 调用方传入 sr)"""
        out = _numpy_to_wav_bytes(np.zeros(800, dtype=np.float32), sample_rate=24000)
        with wave.open(io.BytesIO(out), "rb") as wf:
            assert wf.getnchannels() == 1
            assert wf.getsampwidth() == 2
            assert wf.getframerate() == 24000

    def test_frame_count_matches_input(self):
        n = 3200
        out = _numpy_to_wav_bytes(np.zeros(n, dtype=np.float32), sample_rate=16000)
        with wave.open(io.BytesIO(out), "rb") as wf:
            assert wf.getnframes() == n, "帧数必须等于输入采样点数 (丢帧会让音频时长错位)"

    def test_amplitude_scaling_signed(self):
        """float32 [-1,1] → int16: 正峰接近 +32767, 负峰接近 -32768"""
        audio = np.array([0.0, 1.0, -1.0], dtype=np.float32)
        out = _numpy_to_wav_bytes(audio)
        with wave.open(io.BytesIO(out), "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        assert pcm[0] == 0
        assert pcm[1] == 32767, f"正峰应为 32767, 实际 {pcm[1]}"
        assert pcm[2] == -32768, f"负峰应 clip 到 -32768, 实际 {pcm[2]}"

    def test_clip_out_of_range_input(self):
        """越界输入必须被 clip 而非 int16 回绕 (回绕会把爆音变成反向噪声)"""
        audio = np.array([5.0, -5.0], dtype=np.float32)
        out = _numpy_to_wav_bytes(audio)
        with wave.open(io.BytesIO(out), "rb") as wf:
            pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
        assert pcm[0] == 32767 and pcm[1] == -32768

    def test_empty_array(self):
        out = _numpy_to_wav_bytes(np.array([], dtype=np.float32))
        with wave.open(io.BytesIO(out), "rb") as wf:
            assert wf.getnframes() == 0


# ==========================================================================
# _apply_text_corrections
# ==========================================================================


class TestApplyTextCorrections:
    def test_no_match_returns_unchanged(self):
        assert _apply_text_corrections("微气泡实验", {}) == "微气泡实验"
        assert _apply_text_corrections("微气泡实验", {"臭氧": "O3"}) == "微气泡实验"

    def test_single_replacement(self):
        assert _apply_text_corrections("使用臭氧发生器", {"臭氧": "O3"}) == "使用O3发生器"

    def test_replaces_all_occurrences(self):
        assert _apply_text_corrections("臭氧和臭氧", {"臭氧": "O3"}) == "O3和O3"

    def test_chained_replacement_applies_in_order(self):
        """dict 迭代序 = 插入序; 后一条规则作用于前一条的结果"""
        result = _apply_text_corrections("AB", {"A": "X", "B": "Y"})
        assert result == "XY"

    def test_empty_text(self):
        assert _apply_text_corrections("", {"a": "b"}) == ""

    def test_value_can_be_empty_string(self):
        """把某个词删掉是合法用途 (转写里剔除口头禅)"""
        assert _apply_text_corrections("那个嗯就是", {"嗯": ""}) == "那个就是"


# ==========================================================================
# _edit_distance (Levenshtein)
# ==========================================================================


class TestEditDistance:
    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("", "", 0),
            ("abc", "abc", 0),
            ("abc", "", 3),
            ("", "abc", 3),
            ("kitten", "sitting", 3),       # 经典用例
            ("王天志", "王天之", 1),          # 单字替换 — 声纹典型场景
            ("张三", "李四", 2),
            ("声纹识别", "声纹识别系统", 2),
        ],
    )
    def test_known_values(self, a, b, expected):
        assert _edit_distance(a, b) == expected

    def test_symmetric(self):
        """编辑距离对称 — 若不对称说明 DP 数组被就地改写污染"""
        for a, b in [("kitten", "sitting"), ("王天志", "王天之"), ("abc", "xyz")]:
            assert _edit_distance(a, b) == _edit_distance(b, a)

    def test_identical_long_strings(self):
        s = "陈金薪" * 50
        assert _edit_distance(s, s) == 0

    def test_repeated_calls_are_stable(self):
        """DP 用一维数组原地更新, 若实现有状态污染, 重复调用结果会漂移

        (注: 原想断言"输入字符串未被改写", 但 Python str 不可变, 那条是空断言 —— 改为
        验证可观测的等价性质: 同一输入重复调用结果一致)
        """
        a, b = "kitten", "sitting"
        first = _edit_distance(a, b)
        assert all(_edit_distance(a, b) == first for _ in range(5))

    def test_longer_string_order_matters_for_result_not_inputs(self):
        """长度差异大时的对称性 (DP 数组复用是否残留脏数据)"""
        # 60 个 x → 5 个 y: 替换 60 次 (不能用删除+插入更省, Levenshtein 不允许交换)
        a, b = "x" * 60, "y" * 5
        assert _edit_distance(a, b) == _edit_distance(b, a) == 60
        # 中间插入调用后, 短串结果不得被污染
        assert _edit_distance("abc", "abd") == 1