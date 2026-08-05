"""tests/perf/test_hnsw_recall_calc.py — compute_recall_at_k 单元测试

阶段 A.2 单元测试 (硬门禁):

- test_recall_at_k_perfect: 预测 top-k 完全包含 ground_truth → recall=1.0
- test_recall_at_k_partial: 部分命中 → 命中数 / ground_truth 长度
- test_recall_at_k_zero: 完全不命中 → 0.0

边界:
- test_recall_at_k_length_mismatch_asserts: 长度不等 assert 报错
- test_recall_at_k_handles_empty_ground_truth: 空集合 skip, 不抛
"""
import pytest

from scripts.bench_hnsw_params import compute_recall_at_k  # type: ignore  # noqa: WPS433


def test_recall_at_k_perfect():
    """预测 top-k 完全包含真实 top-k → recall=1.0"""
    predicted = [[1, 2, 3, 4, 5]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 1.0


def test_recall_at_k_partial():
    """部分命中 → 0.6 (3 命中 / 5 ground truth)"""
    predicted = [[1, 2, 3, 9, 10]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 0.6


def test_recall_at_k_zero():
    """完全不命中 → 0.0"""
    predicted = [[9, 10, 11, 12, 13]]
    ground_truth = [[1, 2, 3, 4, 5]]
    assert compute_recall_at_k(predicted, ground_truth, k=5) == 0.0


def test_recall_at_k_multiple_queries_mean():
    """多 query mean 算术平均: (1.0 + 0.6) / 2 = 0.8"""
    predicted = [[1, 2, 3], [1, 2, 9]]
    ground_truth = [[1, 2, 3], [1, 2, 3]]
    # q1: predicted[:3]={1,2,3} & ground={1,2,3} = 1.0
    # q2: predicted[:3]={1,2,9} & ground={1,2,3} = 2/3 ≈ 0.6667
    r = compute_recall_at_k(predicted, ground_truth, k=3)
    assert abs(r - (1.0 + 2/3) / 2) < 1e-6


def test_recall_at_k_length_mismatch_asserts():
    """predicted/ground_truth 长度不等必须 assert."""
    with pytest.raises(AssertionError):
        compute_recall_at_k([[1, 2]], [[1, 2], [3, 4]], k=2)


def test_recall_at_k_handles_empty_ground_truth():
    """ground_truth 为空集合时 skip, 不抛 ZeroDivisionError, 返回 0.0."""
    predicted = [[1, 2, 3]]
    ground_truth: list[list[int]] = [[]]
    assert compute_recall_at_k(predicted, ground_truth, k=3) == 0.0


def test_recall_at_k_predicted_longer_than_k_truncates():
    """predicted 多于 k 个 ID 只取前 k 个参与交集."""
    predicted = [[1, 2, 3, 99, 100, 200]]  # 6 个 ID
    ground_truth = [[1, 2, 3]]  # 3 个
    # 取前 k=3: {1,2,3} 全部命中 → recall=1.0
    assert compute_recall_at_k(predicted, ground_truth, k=3) == 1.0


def test_recall_at_k_non_positive_k_asserts():
    """k<=0 必须 assert."""
    with pytest.raises(AssertionError):
        compute_recall_at_k([[1]], [[1]], k=0)
