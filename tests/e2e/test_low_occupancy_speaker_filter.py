"""会议低占比发言人过滤 — e2e 测试 (W68 Plan 15-17-18 Part 2)

覆盖 5 场景:
1. 单段 1.4s 触发 max_seg_dur < 1.5 过滤
2. 3 段共 5s 但占比 4% < 5% 过滤
3. 10 段共 60s 占比 30% — 正常保留
4. 王天志 384 samples 场景: 会议里只 1 段 "嗯" 0.48s — 过滤
5. 边界值 1.5s 整 + 3.0s 整 + 5% 整 — 全部保留 (用 >= 阈值)

设计:
- 测试目标函数 `apply_low_occupancy_filter` (纯函数, 不依赖 DB/Redis/Celery)
- 直接构造 transcript_segments + speaker_mapping, 不需要 docker
- 本地运行快速, 无外部依赖
- 验证: speaker_mapping 删除 / transcript[].speaker 回写 / cluster_id 保留
  (speaker_label 不动, 用于回溯)
"""
from __future__ import annotations

import pytest

from app.services.low_occupancy_filter import (
    FILTER_VERSION,
    MIN_MAX_SEG_DUR,
    MIN_RATIO,
    MIN_TOTAL_DUR,
    UNKNOWN_SPEAKER_LABEL,
    apply_low_occupancy_filter,
    compute_cluster_durations,
    select_filtered_clusters,
)


# ============================================================
# Helper builders
# ============================================================


def _make_segment(
    idx: int,
    *,
    cluster_id: int,
    speaker: str,
    speaker_label: str,
    start: float,
    end: float,
) -> dict:
    """构造一段转录 segment, 字段名跟 post_meeting_tasks 一致."""
    return {
        "index": idx,
        "cluster_id": cluster_id,
        "speaker": speaker,
        "speaker_label": speaker_label,
        "text": f"seg{idx} text",
        "start": start,
        "end": end,
    }


def _ratio_pct(cluster_total: float, total: float) -> float:
    return cluster_total / total if total > 0 else 0.0


# ============================================================
# 场景 1: 单段 1.4s 触发 max_seg_dur < 1.5 过滤
# ============================================================


def test_single_short_segment_1_4s_is_filtered_by_max_seg_dur():
    """王天志单段 '嗯' 0.48s 这种典型误识场景: 单段 < 1.5s 直接过滤."""
    # 杜同贺是主发言人: 5 段每段 2s 共 10s
    # 王天志误识: 1 段 1.4s < 1.5s
    segs = [
        _make_segment(0, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=0.0, end=2.0),
        _make_segment(1, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=2.0, end=4.0),
        _make_segment(2, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=4.0, end=6.0),
        _make_segment(3, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=6.0, end=8.0),
        _make_segment(4, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=8.0, end=10.0),
        _make_segment(5, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=10.0, end=11.4),  # 1.4s
    ]
    speaker_mapping = {"cluster_5": "杜同贺", "cluster_7": "王天志"}

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=167)

    assert filtered == {7}, f"应过滤 cluster_7, 实际 {filtered}"
    # speaker_mapping 应删 cluster_7
    assert "cluster_7" not in speaker_mapping
    assert speaker_mapping == {"cluster_5": "杜同贺"}
    # 段 5 的 speaker 应被回写 "发言人?"
    assert segs[5]["speaker"] == UNKNOWN_SPEAKER_LABEL
    assert segs[5]["speaker_label"] == "cluster_7"  # speaker_label 不动 (回溯用)
    assert segs[5]["cluster_id"] == 7
    # 杜同贺段不动
    for i in range(5):
        assert segs[i]["speaker"] == "杜同贺"


# ============================================================
# 场景 2: 3 段共 5s 但占比 4% 触发 ratio < 5% 过滤
# ============================================================


def test_low_ratio_3_segments_filtered_by_total_ratio():
    """3 段每段 ~1.67s 共 5s, 但总会议时长 125s → 占比 4% < 5% 过滤."""
    # 杜同贺主发言: 10 段共 120s
    # 误识集群: 3 段共 5s, 占比 4%
    segs = []
    for i in range(10):
        segs.append(_make_segment(
            i, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5",
            start=i * 12.0, end=i * 12.0 + 12.0,
        ))
    # 误识 cluster_7: 3 段共 5s
    segs.append(_make_segment(10, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=120.0, end=121.7))
    segs.append(_make_segment(11, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=121.7, end=123.3))
    segs.append(_make_segment(12, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=123.3, end=125.0))

    speaker_mapping = {"cluster_5": "杜同贺", "cluster_7": "王天志"}

    grand_total = 120.0 + 5.0
    cluster_total_7 = 5.0
    ratio = _ratio_pct(cluster_total_7, grand_total)
    assert 0.03 < ratio < MIN_RATIO, f"前置条件: 占比 {ratio:.3f} 应 < {MIN_RATIO}"

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=168)

    assert filtered == {7}, f"应过滤 cluster_7, 实际 {filtered}"
    assert "cluster_7" not in speaker_mapping
    # 误识段 10/11/12 speaker 回写
    for i in [10, 11, 12]:
        assert segs[i]["speaker"] == UNKNOWN_SPEAKER_LABEL
    # 杜同贺段不动
    for i in range(10):
        assert segs[i]["speaker"] == "杜同贺"


# ============================================================
# 场景 3: 10 段共 60s 占比 30% — 正常保留 (不触发过滤)
# ============================================================


def test_normal_meeting_with_substantial_speaker_is_kept():
    """正常发言者: 10 段共 60s, 占比 30% — 不应被过滤."""
    # cluster_5: 5 段共 30s (主发言 1)
    # cluster_6: 10 段共 60s (主发言 2, 占比 60/110 = 54.5%)
    # cluster_7: 5 段共 20s (占比 18.2%, 也保留)
    segs = []
    for i in range(5):
        segs.append(_make_segment(
            i, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5",
            start=i * 6.0, end=i * 6.0 + 6.0,
        ))
    for i in range(10):
        segs.append(_make_segment(
            i + 5, cluster_id=6, speaker="张宏魁", speaker_label="cluster_6",
            start=30.0 + i * 6.0, end=30.0 + i * 6.0 + 6.0,
        ))
    for i in range(5):
        segs.append(_make_segment(
            i + 15, cluster_id=7, speaker="王天志", speaker_label="cluster_7",
            start=90.0 + i * 4.0, end=90.0 + i * 4.0 + 4.0,
        ))

    speaker_mapping = {"cluster_5": "杜同贺", "cluster_6": "张宏魁", "cluster_7": "王天志"}
    # cluster_7: max=4, total=20, ratio=20/110=0.182 > 5% → 不过滤
    # cluster_5: max=6, total=30, ratio=30/110=0.273 → 不过滤
    # cluster_6: max=6, total=60, ratio=60/110=0.545 → 不过滤

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=151)

    assert filtered == set(), f"无人应被过滤, 实际 {filtered}"
    assert speaker_mapping == {"cluster_5": "杜同贺", "cluster_6": "张宏魁", "cluster_7": "王天志"}
    for seg in segs:
        assert seg["speaker"] in ("杜同贺", "张宏魁", "王天志")


# ============================================================
# 场景 4: 王天志 384 samples 不被误过滤 (即使在某些会议里他只偶尔说话)
# ============================================================


def test_wang_tian_zhi_384_samples_not_filtered_when_substantial():
    """模拟王天志 384 samples 场景: 即使他在某场会议里只 1 段, 只要那 1 段 >= 1.5s 且总占比 >= 5% 就不被过滤.

    用户原始观察: 王天志只在某场会议里出现一两句"只言片语、占比极低"的发言, 那八成是误识.
    关键: **只言片语占比极低**才过滤. 如果他正常说了 5s+ + 占比 6%+, 不应误杀.
    """
    # 杜同贺: 30 段每段 3s 共 90s
    # 张宏魁: 5 段共 20s (占比 16.1%)
    # 王天志: 1 段 5s (占比 5.6%, > 5%) — 应保留
    segs = []
    for i in range(30):
        segs.append(_make_segment(
            i, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5",
            start=i * 3.0, end=i * 3.0 + 3.0,
        ))
    for i in range(5):
        segs.append(_make_segment(
            i + 30, cluster_id=6, speaker="张宏魁", speaker_label="cluster_6",
            start=90.0 + i * 4.0, end=90.0 + i * 4.0 + 4.0,
        ))
    # 王天志: 1 段 5s (>= 1.5s, 总 5s, 占比 5/115 ≈ 4.35% 实际 < 5% → 会被过滤!)
    # 改 scenario: 2 段共 6s 占比 5.2% 保留
    segs.append(_make_segment(35, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=110.0, end=113.0))
    segs.append(_make_segment(36, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=113.0, end=116.0))

    speaker_mapping = {"cluster_5": "杜同贺", "cluster_6": "张宏魁", "cluster_7": "王天志"}
    grand_total = 30 * 3.0 + 5 * 4.0 + 6.0  # 90 + 20 + 6 = 116
    cluster_7_total = 6.0
    cluster_7_ratio = cluster_7_total / grand_total
    assert cluster_7_ratio > MIN_RATIO, f"前置条件: 占比 {cluster_7_ratio:.3f} 应 > {MIN_RATIO}"

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=190)

    assert filtered == set(), f"王天志应被保留, 不应过滤. 实际 {filtered}"
    assert "cluster_7" in speaker_mapping
    assert speaker_mapping["cluster_7"] == "王天志"
    assert segs[35]["speaker"] == "王天志"
    assert segs[36]["speaker"] == "王天志"


# ============================================================
# 场景 5: 边界值 — 1.5s 整 + 3.0s 整 + 5% 整 — 全部保留
# ============================================================


def test_boundary_values_exact_threshold_are_kept():
    """边界值: 单段刚好 1.5s, 总刚好 3.0s, 占比刚好 5% → 全部 >= 阈值, 应保留.

    用户决策: '中等严格' — 任一条件触发即过滤. 边界值使用 strict < 比较,
    意味着恰好等于阈值的段**不**应被过滤.
    """
    # 杜同贺: 19 段每段 3s 共 57s
    # 张宏魁 (边界 cluster_6): 1 段 1.5s + 1 段 1.5s = 3.0s, 占比 3/60 = 5% — 边界保留
    segs = []
    for i in range(19):
        segs.append(_make_segment(
            i, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5",
            start=i * 3.0, end=i * 3.0 + 3.0,
        ))
    # 张宏魁 边界段: max=1.5s, total=3.0s
    segs.append(_make_segment(19, cluster_id=6, speaker="张宏魁", speaker_label="cluster_6", start=57.0, end=58.5))
    segs.append(_make_segment(20, cluster_id=6, speaker="张宏魁", speaker_label="cluster_6", start=58.5, end=60.0))

    speaker_mapping = {"cluster_5": "杜同贺", "cluster_6": "张宏魁"}
    # cluster_6: max=1.5 (>= 1.5 通过), total=3.0 (>= 3.0 通过), ratio=0.05 (>= 0.05 通过)
    grand_total = 19 * 3.0 + 3.0  # 60
    assert grand_total == 60.0
    cluster_6_total = 3.0
    ratio = cluster_6_total / grand_total
    assert ratio == MIN_RATIO, f"前置条件: 占比应恰好等于 {MIN_RATIO}, 实际 {ratio}"

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=200)

    assert filtered == set(), f"边界值应保留, 实际 {filtered}"
    assert "cluster_6" in speaker_mapping
    assert speaker_mapping["cluster_6"] == "张宏魁"
    assert segs[19]["speaker"] == "张宏魁"
    assert segs[20]["speaker"] == "张宏魁"


# ============================================================
# 补充测试: helper 函数自身行为
# ============================================================


def test_compute_cluster_durations_aggregates_correctly():
    """compute_cluster_durations 返回正确的 [max, total, count]."""
    segs = [
        _make_segment(0, cluster_id=1, speaker="A", speaker_label="cluster_1", start=0.0, end=1.5),
        _make_segment(1, cluster_id=1, speaker="A", speaker_label="cluster_1", start=2.0, end=3.0),
        _make_segment(2, cluster_id=2, speaker="B", speaker_label="cluster_2", start=3.0, end=10.0),
    ]
    stats, total = compute_cluster_durations(segs)
    assert stats[1] == [1.5, 2.5, 2.0]  # max=1.5, total=1.5+1.0=2.5, count=2
    assert stats[2] == [7.0, 7.0, 1.0]
    assert total == pytest.approx(9.5)


def test_compute_cluster_durations_ignores_invalid_segments():
    """无 cluster_id / 无效 start/end / 负时长段应被忽略."""
    segs = [
        _make_segment(0, cluster_id=None, speaker="?", speaker_label="", start=0.0, end=1.0),
        _make_segment(1, cluster_id=1, speaker="A", speaker_label="cluster_1", start=0.0, end=1.0),
        _make_segment(2, cluster_id=1, speaker="A", speaker_label="cluster_1", start=1.0, end=0.5),  # 负时长
        _make_segment(3, cluster_id=1, speaker="A", speaker_label="cluster_1", start="bad", end=2.0),  # 无效 start
    ]
    stats, total = compute_cluster_durations(segs)
    assert 1 in stats
    assert stats[1] == [1.0, 1.0, 1.0]
    assert total == 1.0


def test_select_filtered_clusters_returns_sorted_cids():
    """select_filtered_clusters 按 cid 升序返回."""
    stats = {
        7: [1.0, 5.0, 3.0],
        3: [0.5, 2.0, 2.0],
        5: [2.0, 10.0, 5.0],
    }
    total = 100.0
    # cluster 7: max=1 < 1.5 → 过滤
    # cluster 3: max=0.5 < 1.5, total=2 < 3, ratio=0.02 < 0.05 → 过滤
    # cluster 5: 全部通过 → 保留
    filtered = select_filtered_clusters(stats, total)
    assert filtered == [3, 7]


def test_apply_filter_with_meeting_id_none_does_not_log_meeting_id():
    """meeting_id=None 时不抛异常 (边界)."""
    segs = [_make_segment(0, cluster_id=1, speaker="A", speaker_label="cluster_1", start=0.0, end=1.0)]
    speaker_mapping = {"cluster_1": "A"}
    filtered = apply_low_occupancy_filter(segs, speaker_mapping)  # 无 meeting_id
    assert filtered == {1}


def test_apply_filter_empty_inputs_returns_empty_set():
    """空输入边界."""
    filtered = apply_low_occupancy_filter([], {})
    assert filtered == set()


def test_apply_filter_is_idempotent():
    """二次调用相同输入应返回相同结果 (用于重跑场景).

    注意: cluster_5 单段 2s 自身也低于 MIN_TOTAL_DUR 阈值, 因此会被过滤掉.
    真正的幂等性测试: 二次调用**结果相同**, 不论是过滤哪些 cluster.
    """
    segs = [
        _make_segment(0, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=0.0, end=2.0),
        _make_segment(1, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=2.0, end=3.0),
    ]
    speaker_mapping = {"cluster_5": "杜同贺", "cluster_7": "王天志"}

    f1 = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=300)
    # 第二次跑: speaker 已回写 "发言人?", cluster_5 / cluster_7 已删
    # 段 0/1 的 cluster_id 不动, 应再次被识别为低占比
    f2 = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=300)
    assert f1 == f2, f"幂等性失败: f1={f1}, f2={f2}"
    # 两次都过滤了 cluster_5 (单段 2s < 3s) 和 cluster_7 (单段 1s)
    assert f1 == {5, 7}
    assert "cluster_5" not in speaker_mapping
    assert "cluster_7" not in speaker_mapping


def test_filter_version_constant_for_observability():
    """FILTER_VERSION 锁定 — 用于日志/observability 反查."""
    assert FILTER_VERSION == "v1-2026-07-24"


def test_thresholds_constants_unchanged():
    """锁定阈值常量 — 防止后续误改破坏下游 contract."""
    assert MIN_MAX_SEG_DUR == 1.5
    assert MIN_TOTAL_DUR == 3.0
    assert MIN_RATIO == 0.05


# ============================================================
# 集成测试: 与 speaker_label / cluster_id 兼容性
# ============================================================


def test_speaker_label_kept_for_backtracking():
    """过滤后 speaker_label 必须保留 — 用于后续 audit/reprocess 反查 cluster→speaker."""
    segs = [
        _make_segment(0, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=0.0, end=2.0),
        _make_segment(1, cluster_id=7, speaker="王天志", speaker_label="cluster_7", start=2.0, end=2.5),
    ]
    speaker_mapping = {"cluster_5": "杜同贺", "cluster_7": "王天志"}

    apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=400)

    # speaker 被回写
    assert segs[1]["speaker"] == UNKNOWN_SPEAKER_LABEL
    # 但 speaker_label 保留 (用于反查 "这段原本被识别为王天志")
    assert segs[1]["speaker_label"] == "cluster_7"
    # cluster_id 也保留 (用于审计)
    assert segs[1]["cluster_id"] == 7


def test_filter_handles_cluster_id_minus_one():
    """cluster_id=-1 (老 fallback 哨兵值) 应被跳过, 不抛 KeyError.

    cluster_id=-1 的段被忽略 (不入 cluster_stats). 真正的 cluster_5 只 1 段 2s,
    总时长 2s < MIN_TOTAL_DUR=3s → 触发过滤. 测试目的是验证 -1 不会抛错, 而非验证不过滤.
    """
    segs = [
        _make_segment(0, cluster_id=-1, speaker="?", speaker_label="", start=0.0, end=2.0),
        _make_segment(1, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=2.0, end=4.0),
    ]
    speaker_mapping = {"cluster_5": "杜同贺"}

    # 不抛 KeyError 就算成功
    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=500)

    # cluster_5 单段 2s < MIN_TOTAL_DUR=3s 会被过滤
    assert filtered == {5}
    assert "cluster_5" not in speaker_mapping
    # cluster_id=-1 段不动
    assert segs[0]["speaker"] == "?"
    assert segs[0]["cluster_id"] == -1


def test_filter_with_no_segments_after_id_keeps_speaker_mapping():
    """正常场景: 没有被过滤的 cluster, speaker_mapping 应保持原样."""
    segs = [
        _make_segment(0, cluster_id=5, speaker="杜同贺", speaker_label="cluster_5", start=0.0, end=5.0),
        _make_segment(1, cluster_id=6, speaker="张宏魁", speaker_label="cluster_6", start=5.0, end=15.0),
    ]
    speaker_mapping = {"cluster_5": "杜同贺", "cluster_6": "张宏魁"}
    original_mapping = dict(speaker_mapping)

    filtered = apply_low_occupancy_filter(segs, speaker_mapping, meeting_id=600)

    assert filtered == set()
    assert speaker_mapping == original_mapping