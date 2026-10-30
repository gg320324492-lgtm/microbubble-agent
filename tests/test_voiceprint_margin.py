"""tests/test_voiceprint_margin.py — 声纹 margin 判据测试

背景 (2026-10-30, CLAUDE.md 类 20.243):
  生产判据原先是「离**最近**的 anchor < MATCH_THRESHOLD(0.65) 就认」,
  **完全不看第二名离得多近** ⇒ 模型在 top1/top2 几乎打平的段上其实"知道分不出来",
  却被"必须给个名字"逼着硬猜。
  用 8 场 2200 段人耳真值台账实测, 三条识别路径的错名率分别是:
      enrolled 池 + 0.7 (vote_with_quality_gates 主路径): 30.0%
      enrolled 池 + 0.65 (identify_speaker / _by_embedding): 27.5%
      anchor   池 + 0.65 (identify_speaker_anchored):          29.4%
  margin=0.10 后分别降到 11.6% / 11.5% / 16.5%。

本文件覆盖**脱离 DB 的算法层**:
  - `_margin_passes` (voiceprint_service): margin 的纯判定逻辑
  - `get_min_margin` (voiceprint_voting): 阈值来源 + 关闭开关
  - `vote_with_quality_gates`: 段级最近邻在 margin 下弃权 ⇒ 聚类拿不到名字
  - `identify_speaker_anchored`: margin 不足时返回「未识别」而非硬猜
"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.services.voiceprint_service import _margin_passes
from app.services.voiceprint_voting import get_min_margin, vote_with_quality_gates


# ==========================================================================
# _margin_passes
# ==========================================================================


class TestMarginPasses:
    def test_threshold_zero_always_passes(self, monkeypatch):
        """阈值关闭 ⇒ 完全回到改造前行为(永远认最近者)。"""
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.0)
        assert _margin_passes([0.1, 0.1])[0] is True
        assert _margin_passes([0.2, 0.21])[0] is True

    def test_single_candidate_passes(self, monkeypatch):
        """只有一个候选 ⇒ 没有"第二名"可比 ⇒ 直接通过(不能因此认不出人)。"""
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        ok, gap = _margin_passes([0.3])
        assert ok is True
        assert gap == float("inf")

    def test_gap_above_threshold_passes(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        ok, gap = _margin_passes([0.30, 0.55])
        assert ok is True
        assert gap == pytest.approx(0.25, abs=1e-6)

    def test_gap_below_threshold_fails(self, monkeypatch):
        """top1/top2 几乎打平 ⇒ 判据模糊 ⇒ 弃权(宁可未识别, 不猜错)。"""
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        ok, gap = _margin_passes([0.494, 0.495])
        assert ok is False
        assert gap == pytest.approx(0.001, abs=1e-6)

    def test_exact_threshold_boundary_passes(self, monkeypatch):
        """gap 恰好等于阈值 ⇒ 通过(用 >= 而非 >)。"""
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        assert _margin_passes([0.40, 0.50])[0] is True


# ==========================================================================
# get_min_margin
# ==========================================================================


class TestGetMinMargin:
    def test_reads_setting(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.15)
        assert get_min_margin() == pytest.approx(0.15)

    def test_zero_disables(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.0)
        assert get_min_margin() == 0.0


# ==========================================================================
# vote_with_quality_gates 的段级 margin
# ==========================================================================


def _enrolled():
    """两个正交的 enrolled 成员(最近邻难分的场景用)。"""
    return [
        (1, "甲", np.array([1.0, 0.0, 0.0], dtype=np.float32), 10),
        (2, "乙", np.array([0.0, 1.0, 0.0], dtype=np.float32), 10),
    ]


class TestVoteMargin:
    def test_ambiguous_segments_abstain_under_margin(self, monkeypatch):
        """每段都恰好在两人中间 ⇒ margin 下全部弃权 ⇒ 聚类拿不到名字。"""
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        amb = np.array([1.0, 1.0, 0.0], dtype=np.float32)
        segs = [amb, amb.copy(), amb.copy()]
        res = vote_with_quality_gates(segs, [0, 0, 0], _enrolled(),
                                      min_votes=3, votes_ratio_threshold=0.30)
        assert res[0][0] is None, "margin 不足时不该给名字"

    def test_same_segments_named_without_margin(self, monkeypatch):
        """同一个场景, 关闭 margin ⇒ 回到旧行为(会硬猜一个名字)。"""
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.0)
        amb = np.array([1.0, 1.0, 0.0], dtype=np.float32)
        segs = [amb, amb.copy(), amb.copy()]
        res = vote_with_quality_gates(segs, [0, 0, 0], _enrolled(),
                                      min_votes=3, votes_ratio_threshold=0.30)
        assert res[0][0] is not None, "margin=0 时应保持旧行为(给名字)"

    def test_clear_segments_named_under_margin(self, monkeypatch):
        """明显偏向甲的段 ⇒ gap 足够大 ⇒ margin 下仍然给名字(不能一刀切弃权)。"""
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        clear = np.array([1.0, 0.02, 0.0], dtype=np.float32)
        segs = [clear, clear.copy(), clear.copy()]
        res = vote_with_quality_gates(segs, [0, 0, 0], _enrolled(),
                                      min_votes=3, votes_ratio_threshold=0.30)
        assert res[0][0] == "甲"

    def test_explicit_min_margin_overrides_setting(self, monkeypatch):
        """显式传参优先于 settings(便于按会议/按场景灰度)。"""
        monkeypatch.setattr("app.services.voiceprint_voting.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        amb = np.array([1.0, 1.0, 0.0], dtype=np.float32)
        segs = [amb, amb.copy(), amb.copy()]
        res = vote_with_quality_gates(segs, [0, 0, 0], _enrolled(),
                                      min_votes=3, votes_ratio_threshold=0.30,
                                      min_margin=0.0)
        assert res[0][0] is not None


# ==========================================================================
# identify_speaker_anchored 的 margin (mock, 不连 DB)
# ==========================================================================


class TestAnchoredMargin:
    @staticmethod
    def _service(anchors, emb):
        from app.services.voiceprint_service import VoiceprintService

        svc = VoiceprintService.__new__(VoiceprintService)  # 绕过 __init__ 的模型加载
        svc._pipeline = None
        svc.extract_embedding = lambda audio: emb  # type: ignore[assignment]

        async def _get_anchors(db):
            return anchors

        svc.get_anchor_members = _get_anchors  # type: ignore[assignment]
        return svc

    @staticmethod
    def _anchor(mid, name, vec):
        return SimpleNamespace(id=mid, name=name, voice_embedding=np.array(vec, dtype=np.float32))

    @pytest.mark.asyncio
    async def test_margin_insufficient_returns_unknown(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        a = self._anchor(1, "甲", [1.0, 0.0, 0.0])
        b = self._anchor(2, "乙", [0.0, 1.0, 0.0])
        svc = self._service([a, b], np.array([1.0, 1.0, 0.0], dtype=np.float32))
        name, _mid, conf = await svc.identify_speaker_anchored(None, np.zeros(10, dtype=np.float32))
        assert name is None, "margin 不足 ⇒ 应返回未识别"
        assert conf > 0  # 置信度仍按最近者给出, 供调用方参考

    @pytest.mark.asyncio
    async def test_margin_sufficient_returns_name(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.10)
        a = self._anchor(1, "甲", [1.0, 0.0, 0.0])
        b = self._anchor(2, "乙", [0.0, 1.0, 0.0])
        svc = self._service([a, b], np.array([1.0, 0.02, 0.0], dtype=np.float32))
        name, mid, _conf = await svc.identify_speaker_anchored(None, np.zeros(10, dtype=np.float32))
        assert name == "甲"
        assert mid == 1

    @pytest.mark.asyncio
    async def test_margin_disabled_restores_old_behavior(self, monkeypatch):
        monkeypatch.setattr("app.services.voiceprint_service.settings.VOICEPRINT_MIN_MARGIN", 0.0)
        a = self._anchor(1, "甲", [1.0, 0.0, 0.0])
        b = self._anchor(2, "乙", [0.0, 1.0, 0.0])
        svc = self._service([a, b], np.array([1.0, 1.0, 0.0], dtype=np.float32))
        name, _mid, _conf = await svc.identify_speaker_anchored(None, np.zeros(10, dtype=np.float32))
        assert name is not None, "margin=0 ⇒ 保持旧行为"
