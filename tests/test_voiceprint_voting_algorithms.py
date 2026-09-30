"""tests/test_voiceprint_voting_algorithms.py — voiceprint_voting 算法层测试

背景 (2026-09-30 S3 第一项): `app/services/voiceprint_voting.py` 1,017 行
**零测试覆盖**。该模块是会议转写**说话人归属**的核心 —— 归属错了整份纪要就错了
(CLAUDE.md 的会议纪要规范要求 `【发言人】` 前缀, 发言人是谁来自这里)。

本次覆盖**可脱离 DB 的算法层**, 不碰需要 DB 的 `resolve_context_to_names` /
`get_recent_meeting_speakers` / `learn_from_*`:
- `_cosine_distance`: 距离度量, 含全零向量哨兵值 (999.0)
- `_cluster_center`: 聚类中心 = 均值 + L2 归一, 跳过 invalid
- `_merge_homogeneous_clusters`: union-find 合并过度相似的簇 (083 事件修复)
- `smart_select_k`: K 值选择的三因子分层评分
"""
from __future__ import annotations

import numpy as np
import pytest

from app.services.voiceprint_voting import (
    _cluster_center,
    _cosine_distance,
    _merge_homogeneous_clusters,
)


# ==========================================================================
# _cosine_distance
# ==========================================================================


class TestCosineDistance:
    def test_identical_vectors_zero(self):
        v = np.array([1.0, 2.0, 3.0])
        assert _cosine_distance(v, v) == pytest.approx(0.0, abs=1e-6)

    def test_orthogonal_is_one(self):
        a = np.array([1.0, 0.0])
        b = np.array([0.0, 1.0])
        assert _cosine_distance(a, b) == pytest.approx(1.0, abs=1e-6)

    def test_opposite_is_two(self):
        a = np.array([1.0, 0.0])
        b = np.array([-1.0, 0.0])
        assert _cosine_distance(a, b) == pytest.approx(2.0, abs=1e-6)

    def test_scale_invariance(self):
        """余弦距离只测方向, 与向量模长无关"""
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([10.0, 20.0, 30.0])
        assert _cosine_distance(a, b) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector_sentinel(self):
        """全零向量返回哨兵 999.0 —— 绝不返回 0 (否则会被判成'完全同一人')"""
        z = np.zeros(3)
        v = np.array([1.0, 2.0, 3.0])
        assert _cosine_distance(z, v) == 999.0
        assert _cosine_distance(v, z) == 999.0
        assert _cosine_distance(z, z) == 999.0

    def test_symmetric(self):
        a = np.array([1.0, 2.0, 3.0])
        b = np.array([3.0, 2.0, 1.0])
        assert _cosine_distance(a, b) == pytest.approx(_cosine_distance(b, a), abs=1e-9)

    def test_similar_vectors_below_threshold(self):
        """声纹同一人: 距离必须远低于在线匹配阈值 0.7 (CLAUDE.md 三层口径)"""
        base = np.array([1.0, 0.0, 0.0])
        same_person = base + np.array([0.01, 0.02, -0.01])
        assert _cosine_distance(base, same_person) < 0.1


# ==========================================================================
# _cluster_center
# ==========================================================================


class TestClusterCenter:
    def test_ignores_none_and_zero_vectors(self):
        """None / 全零段 embedding 必须被跳过 (坏段不能污染中心)"""
        vecs = [np.array([1.0, 0.0]), None, np.zeros(2), np.array([0.0, 1.0])]
        center = _cluster_center(vecs)
        assert center is not None
        # 只用两个有效向量 → 均值应是 (0.5, 0.5) 归一 → (0.707, 0.707)
        assert center == pytest.approx(np.array([0.70710678, 0.70710678]), abs=1e-6)

    def test_returns_none_when_all_invalid(self):
        assert _cluster_center([None, np.zeros(3), None]) is None
        assert _cluster_center([]) is None

    def test_output_is_l2_normalized(self):
        center = _cluster_center([np.array([1.0, 2.0, 3.0]), np.array([2.0, 4.0, 6.0])])
        assert np.linalg.norm(center) == pytest.approx(1.0, abs=1e-6)

    def test_single_vector(self):
        v = np.array([3.0, 4.0])
        center = _cluster_center([v])
        assert center == pytest.approx(np.array([0.6, 0.8]), abs=1e-6)

    def test_cancelling_vectors_do_not_divide_by_zero(self):
        """均值恰好为 0 向量时不得崩 (norm > 0 守卫)"""
        center = _cluster_center([np.array([1.0, 1.0]), np.array([-1.0, -1.0])])
        assert center is not None
        assert np.all(np.isfinite(center))


# ==========================================================================
# _merge_homogeneous_clusters (083 事件修复)
# ==========================================================================


def _info(center, total=1, votes=None):
    return {
        "center": np.asarray(center, dtype=float),
        "total": total,
        "name_votes": votes or {},
        "seg_confs": {},
    }


class TestMergeHomogeneousClusters:
    def test_single_cluster_untouched(self):
        ci = {0: _info([1.0, 0.0])}
        out, mapping = _merge_homogeneous_clusters(ci, [0])
        assert out is ci and mapping == {0: 0}

    def test_empty_input(self):
        out, mapping = _merge_homogeneous_clusters({}, [])
        assert out == {} and mapping == {}

    def test_dissimilar_clusters_not_merged(self):
        """正交簇: cos sim = 0 远低于阈值, 必须保持独立"""
        ci = {0: _info([1.0, 0.0]), 1: _info([0.0, 1.0])}
        out, mapping = _merge_homogeneous_clusters(ci, [0, 1])
        assert set(mapping.values()) == {0, 1}, "不相似的簇不应被合并"

    def test_near_identical_clusters_merged(self):
        """083 事故场景: cos 0.92+ 的强分簇实为同一说话人, 必须合并"""
        ci = {
            0: _info([1.0, 0.0]),
            1: _info([0.98, 0.20]),   # cos ≈ 0.98 > 0.85
        }
        out, mapping = _merge_homogeneous_clusters(ci, [0, 1])
        assert len(set(mapping.values())) == 1, "高度相似的簇必须合并成一个说话人"
        assert "merged_from" in list(out.values())[0]

    def test_merge_sums_totals(self):
        ci = {0: _info([1.0, 0.0], total=3), 1: _info([0.98, 0.2], total=5)}
        out, _ = _merge_homogeneous_clusters(ci, [0, 1])
        assert sum(v["total"] for v in out.values()) == 8

    def test_transitive_merge_three_clusters(self):
        """union-find 语义: A~B, B~C ⇒ 三者同组 (链式传递)"""
        ci = {
            0: _info([1.0, 0.0]),
            1: _info([0.98, 0.2]),
            2: _info([0.97, 0.24]),
        }
        out, mapping = _merge_homogeneous_clusters(ci, [0, 1, 2])
        assert len(set(mapping.values())) == 1

    def test_cluster_without_center_skipped(self):
        """center=None 的簇不能参与 cos 比较, 但仍应出现在映射里"""
        ci = {0: _info([1.0, 0.0]), 1: {"center": None, "total": 1, "name_votes": {}, "seg_confs": {}}}
        out, mapping = _merge_homogeneous_clusters(ci, [0, 1])
        assert set(mapping.keys()) == {0, 1}

    def test_threshold_is_configurable(self):
        """阈值可调: 同一对向量在低阈值下不合并"""
        ci = {0: _info([1.0, 0.0]), 1: _info([0.9, 0.44])}  # cos ≈ 0.915
        _, m_low = _merge_homogeneous_clusters(ci, [0, 1], merge_threshold=0.99)
        _, m_high = _merge_homogeneous_clusters(ci, [0, 1], merge_threshold=0.85)
        assert len(set(m_low.values())) == 2
        assert len(set(m_high.values())) == 1