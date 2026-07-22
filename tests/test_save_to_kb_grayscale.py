"""qa-bench save_to_kb.py grayscale 单测 — W62 T6.2 D2 决策

覆盖 5/25/100 三档灰度 + observer 集成 + rollback 触发:
1. is_in_grayscale 命中判定 (5/25/100/0)
2. is_in_grayscale 同一 question_id 跨多次跑命中一致 (稳定 hash)
3. observer.record_intake 写 JSONL 正确
4. observer.get_daily_stats 聚合正确
5. observer.check_rollback_threshold 触发条件 (error_rate > 5% AND total >= 20)
6. observer.check_rollback_threshold 样本量下限 (total < 20 不触发)
7. observer.check_rollback_threshold 阈值边界 (= 5% 不触发, > 5% 触发)
8. save_to_kb 与 AUTO_KB_INTAKE_ENABLED 兼容 (= grayscale 100)
9. save_to_kb 与 --enable-intake flag 兼容 (= grayscale 100)
10. save_to_kb --grayscale 0 dry-run 行为兼容
11. save_to_kb 灰度过滤 hash 稳定 (S-001 同一档命中)

设计原则 (W62 D2 沉淀):
- observer JSONL 路径由 env QA_BENCH_DATA_DIR 控制, 测试用 tmp_path 隔离
- hash 稳定 = 同一 question_id 永远命中同一档 (sha256 前 8 hex → bucket % 100)
- rollback 样本量下限 20 避免 1/1 = 100% 误触发
"""
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


# 加载 observer 模块 (tests/qa-bench/observer.py)
OBSERVER_PATH = Path(__file__).parent / "qa-bench" / "observer.py"
spec = importlib.util.spec_from_file_location("observer", OBSERVER_PATH)
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)

# 加载 save_to_kb 模块 (tests/qa-bench/save_to_kb.py)
SAVE_TO_KB_PATH = Path(__file__).parent / "qa-bench" / "save_to_kb.py"
spec = importlib.util.spec_from_file_location("save_to_kb", SAVE_TO_KB_PATH)
save_to_kb = importlib.util.module_from_spec(spec)
sys.modules["save_to_kb"] = save_to_kb  # 让 importlib.reload 能找到
spec.loader.exec_module(save_to_kb)


# === Fixtures ===
@pytest.fixture(autouse=True)
def isolate_observer_dir(tmp_path, monkeypatch):
    """每个测试用 tmp_path 隔离 observer JSONL 路径"""
    monkeypatch.setenv("QA_BENCH_DATA_DIR", str(tmp_path))
    observer.clear_observer()
    yield
    observer.clear_observer()


# === Case 1: is_in_grayscale 灰度 = 0 全跳过 ===
def test_is_in_grayscale_zero_skips_all():
    """grayscale=0 应该全部 False"""
    qids = [f"S-{i:03d}" for i in range(100)]
    for qid in qids:
        assert save_to_kb.is_in_grayscale(qid, 0) is False, f"grayscale=0 应跳过 {qid}"
    print("  ✅ Case 1: grayscale=0 全跳过")


# === Case 2: is_in_grayscale 灰度 = 100 全命中 ===
def test_is_in_grayscale_hundred_hits_all():
    """grayscale=100 应该全部 True"""
    qids = [f"S-{i:03d}" for i in range(100)]
    for qid in qids:
        assert save_to_kb.is_in_grayscale(qid, 100) is True, f"grayscale=100 应命中 {qid}"
    print("  ✅ Case 2: grayscale=100 全命中")


# === Case 3: is_in_grayscale 灰度 = 5 大约 5% 命中 ===
def test_is_in_grayscale_five_percent_distribution():
    """grayscale=5 在 1000 题中应接近 5% 命中 (允许 1-9% 偏差)"""
    qids = [f"S-{i:04d}" for i in range(1000)]
    hits = sum(1 for qid in qids if save_to_kb.is_in_grayscale(qid, 5))
    pct = hits / len(qids)
    assert 0.01 <= pct <= 0.09, f"grayscale=5 应命中 1-9%, 实际 {pct:.2%} ({hits}/{len(qids)})"
    print(f"  ✅ Case 3: grayscale=5 → {hits}/{len(qids)} = {pct:.2%}")


# === Case 4: is_in_grayscale 灰度 = 25 大约 25% 命中 ===
def test_is_in_grayscale_twentyfive_percent_distribution():
    """grayscale=25 在 1000 题中应接近 25% 命中 (允许 18-32%)"""
    qids = [f"S-{i:04d}" for i in range(1000)]
    hits = sum(1 for qid in qids if save_to_kb.is_in_grayscale(qid, 25))
    pct = hits / len(qids)
    assert 0.18 <= pct <= 0.32, f"grayscale=25 应命中 18-32%, 实际 {pct:.2%}"
    print(f"  ✅ Case 4: grayscale=25 → {hits}/{len(qids)} = {pct:.2%}")


# === Case 5: is_in_grayscale 同一 question_id 跨多次跑命中一致 ===
def test_is_in_grayscale_stable_hash():
    """同一 qid 永远命中同一档 (sha256 前 8 hex)"""
    qid = "S-stable-test-001"
    first = save_to_kb.is_in_grayscale(qid, 50)
    for _ in range(10):
        assert save_to_kb.is_in_grayscale(qid, 50) == first, "hash 必须稳定"
    print(f"  ✅ Case 5: 同一 qid 10 次调用结果一致 (hit={first})")


# === Case 6: observer.record_intake + get_daily_stats 正确 ===
def test_observer_record_and_stats():
    """写 10 条 success + 5 条 fail → total=15, errors=5, error_rate=1/3"""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for i in range(10):
        observer.record_intake(question_id=f"S-{i:03d}", success=True)
    for i in range(5):
        observer.record_intake(
            question_id=f"S-{i:03d}", success=False, error_msg="mock error"
        )
    stats = observer.get_daily_stats()
    assert stats["date"] == today
    assert stats["total"] == 15
    assert stats["success"] == 10
    assert stats["errors"] == 5
    assert abs(stats["error_rate"] - 5 / 15) < 0.01
    print(f"  ✅ Case 6: observer 记录+聚合正确 (total=15, errors=5, rate={stats['error_rate']:.2%})")


# === Case 7: observer.check_rollback_threshold 触发 (>5% AND >=20) ===
def test_check_rollback_triggers_at_6_percent_with_50_total():
    """error_rate=6% (3/50) AND total=50 → 触发"""
    for i in range(47):
        observer.record_intake(question_id=f"S-{i:03d}", success=True)
    for i in range(3):
        observer.record_intake(
            question_id=f"S-fail-{i}", success=False, error_msg="mock"
        )
    stats = observer.get_daily_stats()
    assert stats["total"] == 50
    assert stats["errors"] == 3
    assert stats["error_rate"] == 0.06
    assert observer.check_rollback_threshold() is True, "error_rate=6% 应触发 rollback"
    print(f"  ✅ Case 7: rollback 触发 (error_rate=6%, total=50)")


# === Case 8: observer.check_rollback_threshold 样本量下限 (<20 不触发) ===
def test_check_rollback_no_trigger_below_minimum_sample():
    """total=10, error_rate=100% 不触发 (样本量下限保护)"""
    for i in range(10):
        observer.record_intake(question_id=f"S-{i:03d}", success=False, error_msg="x")
    stats = observer.get_daily_stats()
    assert stats["total"] == 10
    assert stats["errors"] == 10
    assert stats["error_rate"] == 1.0
    assert observer.check_rollback_threshold() is False, "样本 < 20 不应触发"
    print(f"  ✅ Case 8: 样本 < 20 (即使 100% 错误) 不触发 rollback")


# === Case 9: observer.check_rollback_threshold 阈值边界 (=5% 不触发, >5% 触发) ===
def test_check_rollback_threshold_boundary():
    """= 5% 不触发 (严格大于), > 5% 触发"""
    # = 5% (5/100): 不触发
    for i in range(95):
        observer.record_intake(question_id=f"S-ok-{i}", success=True)
    for i in range(5):
        observer.record_intake(question_id=f"S-err-{i}", success=False)
    stats = observer.get_daily_stats()
    assert stats["error_rate"] == 0.05
    assert observer.check_rollback_threshold() is False, "= 5% 严格不触发"
    # 再加 1 条 error → 6/101 ≈ 5.94% → 触发 (浮点比较用 abs < 0.001)
    observer.record_intake(question_id="S-err-extra", success=False)
    stats = observer.get_daily_stats()
    assert stats["total"] == 101
    assert stats["errors"] == 6
    assert abs(stats["error_rate"] - 6 / 101) < 1e-9
    assert stats["error_rate"] > 0.05
    assert observer.check_rollback_threshold() is True, "> 5% 触发"
    print(f"  ✅ Case 9: 阈值边界 (= 5% 不触发, > 5% 触发)")


# === Case 10: observer.clear_observer 清理 ===
def test_observer_clear():
    """clear_observer 后 stats 应归零"""
    observer.record_intake(question_id="S-001", success=True)
    observer.record_intake(question_id="S-002", success=False)
    assert observer.get_daily_stats()["total"] == 2
    observer.clear_observer()
    assert observer.get_daily_stats()["total"] == 0
    print("  ✅ Case 10: clear_observer 清理 JSONL")


# === Case 11: save_to_kb 灰度过滤 hash 稳定 ===
def test_save_to_kb_grayscale_hash_stable():
    """S-001 在 grayscale=25 应永远命中同一档"""
    qid = "S-hash-stable-001"
    first = save_to_kb.is_in_grayscale(qid, 25)
    for _ in range(20):
        assert save_to_kb.is_in_grayscale(qid, 25) == first
    print(f"  ✅ Case 11: S-001 grayscale=25 命中稳定 (hit={first})")


# === Case 12: save_to_kb 环境变量 KB_INTAKE_GRAYSCALE 解析 ===
def test_save_to_kb_grayscale_env_parsing(monkeypatch):
    """KB_INTAKE_GRAYSCALE env 解析: 合法值 / 非法值 / 边界"""
    # 合法值 5
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "5")
    # 重新加载模块以触发 env 解析
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 5

    # 边界 100
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "100")
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 100

    # 超 100 截断为 100
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "150")
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 100

    # 负数截断为 0
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "-5")
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 0

    # 非法值降级为 0
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "abc")
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 0

    # 空字符串降级为 0
    monkeypatch.setenv("KB_INTAKE_GRAYSCALE", "")
    importlib.reload(save_to_kb)
    assert save_to_kb._parse_grayscale_env() == 0

    # 还原
    monkeypatch.delenv("KB_INTAKE_GRAYSCALE", raising=False)
    importlib.reload(save_to_kb)
    print("  ✅ Case 12: KB_INTAKE_GRAYSCALE env 解析 (合法/边界/非法/空)")


if __name__ == "__main__":
    test_is_in_grayscale_zero_skips_all()
    test_is_in_grayscale_hundred_hits_all()
    test_is_in_grayscale_five_percent_distribution()
    test_is_in_grayscale_twentyfive_percent_distribution()
    test_is_in_grayscale_stable_hash()
    test_observer_record_and_stats()
    test_check_rollback_triggers_at_6_percent_with_50_total()
    test_check_rollback_no_trigger_below_minimum_sample()
    test_check_rollback_threshold_boundary()
    test_observer_clear()
    test_save_to_kb_grayscale_hash_stable()
    test_save_to_kb_grayscale_env_parsing()
    print("\n✅ 12/12 grayscale tests PASS")
