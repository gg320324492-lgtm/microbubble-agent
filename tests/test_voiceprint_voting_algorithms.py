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
    smart_select_k,
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

    def test_no_center_cluster_when_merge_happens(self):
        """⚠️ 契约不干净之处 (2026-09-30 评审定性, 非 bug):

        `root_to_cids` 只从 `cids_with_center` 构建, 所以**合并路径**下 center=None 的
        簇会从 `new_cluster_info` 里整个消失; 而 `cid_to_root` 仍保留它 —— 两条路径
        输出契约不一致 (不合并时保留, 合并时丢失)。

        实务影响为零, 因为: ①无 center 的簇其 name_votes/seg_confs 必为空
        (vote_with_quality_gates 第 328 行预过滤掉了 None/全零段), 丢的不是票;
        ②下游遍历时有 `if center is None: continue` 兜底 (同文件第 397 行)。

        本用例把**当前行为固定下来**: 若将来有人修这个不一致, 此用例会红, 提醒
        同步更新契约说明。
        """
        ci = {
            0: _info([1.0, 0.0]),
            1: _info([0.98, 0.2]),        # 与 0 高度相似 → 触发合并
            2: {"center": None, "total": 1, "name_votes": {}, "seg_confs": {}},
        }
        out, mapping = _merge_homogeneous_clusters(ci, [0, 1, 2])
        # 0/1 合并成一组; cid 2 因无 center 不参与 cos 比较, 自己成组
        assert mapping[0] == mapping[1], "0/1 高度相似应合并 (cos≈0.980)"
        assert mapping[2] == 2, "无 center 的簇不参与合并, 保持独立"
        assert set(mapping.keys()) == {0, 1, 2}, "cid_to_root 仍含全部 cid"
        assert 2 not in out, "当前行为: 合并路径下无 center 的簇被丢弃 (见 docstring)"

    def test_threshold_is_configurable(self):
        """阈值可调: 同一对向量在低阈值下不合并 (此处 cos≈0.898)"""
        ci = {0: _info([1.0, 0.0]), 1: _info([0.9, 0.44])}  # cos ≈ 0.898
        _, m_low = _merge_homogeneous_clusters(ci, [0, 1], merge_threshold=0.99)
        _, m_high = _merge_homogeneous_clusters(ci, [0, 1], merge_threshold=0.85)
        assert len(set(m_low.values())) == 2
        assert len(set(m_high.values())) == 1


# ==========================================================================
# smart_select_k
# ==========================================================================


def _blobs(n_per: int, centers: list, dim: int = 8, seed: int = 0) -> list:
    """构造可聚类的 embedding: 每个 center 周围撒 n_per 个点"""
    rng = np.random.default_rng(seed)
    out = []
    for c in centers:
        base = np.zeros(dim)
        base[: len(c)] = c
        for _ in range(n_per):
            out.append(base + rng.normal(0, 0.08, dim))
    return out


class TestSmartSelectK:
    def test_degenerate_few_samples(self):
        """有效样本 < 2 时必须降级, 不能抛异常"""
        labels, k, score, meta = smart_select_k([np.array([1.0, 0.0])])
        assert labels == [-1] and k == 1 and score == -1.0
        assert meta["_meta"]["low_quality"] is True

    def test_all_invalid_segments(self):
        labels, k, score, meta = smart_select_k([None, np.zeros(4), np.zeros(4)])
        assert labels == [-1, -1, -1]
        assert k == 1 and meta["_meta"]["low_quality"] is True

    def test_empty_input(self):
        labels, k, _, meta = smart_select_k([])
        assert labels == [] and k == 1 and meta["_meta"]["low_quality"] is True

    def test_recovers_obvious_three_speaker_structure(self):
        """三个明显分离的团 → 应选出 K=3 (n_expected=3 时 proximity 也指向 3)"""
        embs = _blobs(8, [[1, 0, 0, 0, 0, 0, 0, 0],
                          [0, 1, 0, 0, 0, 0, 0, 0],
                          [0, 0, 1, 0, 0, 0, 0, 0]])
        labels, k, score, all_scores = smart_select_k(embs, n_expected=3)
        assert len(labels) == len(embs)
        assert k == 3, f"应识别出 3 个说话人, 实际 K={k}"
        assert len(set(labels)) == 3
        assert "_meta" in all_scores
        assert {"low_quality", "best_sil", "best_k"} <= set(all_scores["_meta"]), (
            f"_meta 至少含三项质量元数据, 实际 {sorted(all_scores['_meta'])}"
        )
        assert all_scores["_meta"]["best_k"] == k, "_meta.best_k 应与返回值 k 一致"

    def test_recovers_obvious_two_speaker_structure(self):
        embs = _blobs(8, [[1, 0, 0, 0, 0, 0, 0, 0],
                          [0, 1, 0, 0, 0, 0, 0, 0]])
        _, k, _, _ = smart_select_k(embs, n_expected=2)
        assert k == 2

    def test_labels_length_equals_input(self):
        """labels 必须与 seg_embs 等长 (无效段标 -1), 下游按位置对齐"""
        embs = _blobs(5, [[1, 0, 0, 0, 0, 0, 0, 0], [0, 1, 0, 0, 0, 0, 0, 0]])
        embs.insert(3, None)          # 混入一个无效段
        labels, _, _, _ = smart_select_k(embs, n_expected=2)
        assert len(labels) == len(embs)
        assert labels[3] == -1, "无效段应标 -1"

    def test_low_quality_flag_when_structure_is_amorphous(self):
        """无结构的均匀随机点 → silhouette 低 → low_quality=True"""
        rng = np.random.default_rng(7)
        embs = list(rng.normal(0, 1, (30, 8)))
        _, _, _, all_scores = smart_select_k(embs, n_expected=3)
        assert all_scores["_meta"]["low_quality"] is True, "无结构数据应标记低质量"

    def test_n_expected_shifts_k_up(self):
        """同样的数据, n_expected 越大越倾向选更大的 K (proximity 因子)"""
        embs = _blobs(8, [[1, 0, 0, 0, 0, 0, 0, 0],
                          [0, 1, 0, 0, 0, 0, 0, 0],
                          [0, 0, 1, 0, 0, 0, 0, 0]])
        _, k_low, _, _ = smart_select_k(embs, n_expected=2)
        _, k_high, _, _ = smart_select_k(embs, n_expected=4)
        assert k_high >= k_low, f"n_expected=4 的 K({k_high}) 不应小于 n_expected=2 的 K({k_low})"
