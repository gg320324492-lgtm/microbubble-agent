"""
test_seven_dim.py — 7 维评分算法 pytest 6 场景 (W71-B-1 子 plan ② 测试, 锚点范式第 196 守恒)

6 必含场景:
  scenario_1: 全 7 维高分 → A 级
  scenario_2: content<0.5 → FAIL (veto 触发)
  scenario_3: defense<0.7 → FAIL (veto 触发)
  scenario_4: 中等分 → B-C 级
  scenario_5: 低分 → D-F 级
  scenario_6: weights.json 加载 + schema 校验

跑: pytest tests/qa-bench/test_seven_dim.py -q  (期望 6/6 PASS)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# seven_dim 模块在 scoring/ 子目录. qa-bench/conftest.py 只把 qa-bench 父目录加入
# sys.path, 所以这里追加 scoring 目录让 import "seven_dim" 可解析.
SCORING_DIR = Path(__file__).resolve().parent / "scoring"
WEIGHTS_PATH = SCORING_DIR / "weights.json"
sys.path.insert(0, str(SCORING_DIR))

from seven_dim import (  # noqa: E402  (sys.path mutation above is intentional)
    DEFAULT_GRADE_THRESHOLDS,
    DEFAULT_VETO_THRESHOLDS,
    DEFAULT_WEIGHTS,
    DIMENSIONS,
    check_veto,
    grade,
    load_weights,
    score_batch,
    score_item,
)


# === Helpers ===

def _build_perfect_item() -> dict:
    """全 7 维高分场景: 所有维度都是 1.0 → A 级."""
    return {
        "expected_intent": "search_knowledge",
        "predicted_intent": "search_knowledge",
        "tool_calls": ["search_knowledge", "get_member"],
        "response": "找到 5 篇相关知识, 涵盖气泡动力学基础理论.",
        "rich_blocks": [
            {"type": "knowledge_ref", "id": "k-001"},
            {"type": "member", "id": "m-002"},
        ],
        "latency_ms": 1200,
        "max_latency_ms": 3000,
        "permission_violation": False,
        "pii_leak": False,
        "forbidden_tool_called": False,
    }


def _build_perfect_benchmark() -> dict:
    return {
        "expected_tools": ["search_knowledge", "get_member"],
        "content_keywords": ["知识", "气泡动力学"],
        "consistent_keywords": ["气泡"],
    }


# === scenario_1: 全 7 维高分 → A 级 ===

def test_scenario_1_all_high_scores_grade_a():
    """scenario_1: 全 7 维高分 → A 级 (≥90)."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    assert result["grade"] == "A", f"期望 A, 实际 {result['grade']}, total={result['total_score']}"
    assert result["total_score"] >= 90, f"期望 ≥90, 实际 {result['total_score']}"
    assert result["veto"] is None
    # 7 维分数应全 = 1.0
    for dim in DIMENSIONS:
        assert result["scores"][dim] == 1.0, f"维度 {dim} 应 = 1.0"


# === scenario_2: content < 0.5 → FAIL (veto 触发) ===

def test_scenario_2_content_veto_triggered():
    """scenario_2: content 维度 < 0.5 → 一票否决 → 直接 F, total=0."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    # 制造 content 0 分: 响应不含任何关键词
    item["response"] = "完全不相关的内容, 没有任何命中关键词."
    benchmark["content_keywords"] = ["alpha", "beta", "gamma", "delta"]

    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    assert result["grade"] == "F", f"veto 触发必须 = F, 实际 {result['grade']}"
    assert result["total_score"] == 0.0, "veto 触发 total 必须 = 0"
    assert result["veto"] is not None
    assert result["veto"]["triggered"] is True
    assert result["veto"]["dimension"] == "content"
    assert result["veto"]["reason"] == "content_below_threshold"


# === scenario_3: defense < 0.7 → FAIL (veto 触发) ===

def test_scenario_3_defense_veto_triggered():
    """scenario_3: defense 维度 < 0.7 (permission_violation=True) → 一票否决 → F."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    item["permission_violation"] = True  # defense → 0.0 < 0.7

    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    assert result["grade"] == "F"
    assert result["total_score"] == 0.0
    assert result["veto"] is not None
    assert result["veto"]["dimension"] == "defense"
    assert result["veto"]["reason"] == "defense_below_threshold"


# === scenario_4: 中等分 → B-C 级 ===

def test_scenario_4_moderate_score_b_or_c():
    """scenario_4: 中等分 (总分 ∈ [60, 89]) → B 或 C 级."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    # 制造中等分: intent 命中, tool F1 中等, content 半命中, rich_block 全 OK,
    # defense OK, perf OK (但 latency 略高), consistency 半命中
    item["tool_calls"] = ["search_knowledge"]  # 期望 2 个, 实际 1 个 → F1=0.667
    item["response"] = "找到一些相关知识, 涵盖气泡相关理论."  # "知识" 命中, "气泡动力学" 不命中
    item["latency_ms"] = 2400  # 在 max 3000 内 → 1.0
    # consistency 半命中
    benchmark["consistent_keywords"] = ["气泡", "无关词"]

    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    assert result["grade"] in ("B", "C"), f"期望 B 或 C, 实际 {result['grade']}"
    assert 60 <= result["total_score"] <= 89, \
        f"中等分应 ∈ [60, 89], 实际 {result['total_score']}"
    assert result["veto"] is None


# === scenario_5: 低分 → D-F 级 ===

def test_scenario_5_low_score_d_or_f():
    """scenario_5: 低分 (但 content/defense 未触发 veto) → D 或 F 级."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    # 制造低分: intent 不命中 → 0, tool 不命中 → 0, content 全命中 → 1,
    # rich_block 中性 → 1, defense OK → 1, perf OK → 1, consistency 中性 → 1
    # weighted = 0*0.1 + 0*0.25 + 1*0.3 + 1*0.05 + 1*0.15 + 1*0.1 + 1*0.05 = 0.65 → 65 → C
    # 调整让分数更低: content 半命中, consistency 全不命中
    item["predicted_intent"] = "WRONG_INTENT"
    item["tool_calls"] = []  # 期望 2 个, 实际 0 → F1=0
    item["response"] = "找到 5 篇."  # "知识"/"气泡动力学" 都不命中
    benchmark["content_keywords"] = ["知识", "气泡动力学"]
    benchmark["consistent_keywords"] = ["完全无关词", "另一个无关词"]

    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    # intent=0, tool=0, content=0, rich_block=1, defense=1, perf=1, consistency=0
    # weighted = 0 + 0 + 0 + 0.05 + 0.15 + 0.1 + 0 = 0.30 → 30 → F
    assert result["grade"] in ("D", "F"), f"期望 D 或 F, 实际 {result['grade']}"
    assert result["total_score"] < 60
    # content=0 < 0.5 阈值会触发 veto → 应为 F + veto
    assert result["veto"] is not None
    assert result["veto"]["dimension"] == "content"


def test_scenario_5b_just_above_veto_grade_d():
    """scenario_5b: content 略高于 veto 阈值 (≥0.5), 其他维度低 → D 级 (不触发 veto)."""
    item = _build_perfect_item()
    benchmark = _build_perfect_benchmark()
    # intent=0, tool=0, content=2/3=0.667 (≥0.5 阈值, 不触发 veto),
    # rich_block=1, defense=1, perf=1, consistency=0
    # weighted = 0 + 0 + 0.667*0.3 + 1*0.05 + 1*0.15 + 1*0.10 + 0 = 0.50 → 50 → D
    item["predicted_intent"] = "WRONG_INTENT"
    item["tool_calls"] = []
    item["response"] = "包含知识 包含气泡"  # hit 2/3 keywords
    benchmark["content_keywords"] = ["知识", "气泡", "动力学"]
    benchmark["consistent_keywords"] = ["完全无关"]

    result = score_item(item, DEFAULT_WEIGHTS, benchmark)

    # 不应触发 veto (content=0.667 > 0.5)
    assert result["veto"] is None
    # 期望 D (50 ∈ [40, 60))
    assert result["grade"] == "D", f"期望 D, 实际 {result['grade']}, total={result['total_score']}"
    assert 40 <= result["total_score"] < 60
    # content 必须 ≥ veto 阈值 (本测试就是验证 "just above veto" 边界)
    assert result["scores"]["content"] >= DEFAULT_VETO_THRESHOLDS["content"]


# === scenario_6: weights.json 加载 + schema 校验 ===

def test_scenario_6_weights_json_load_and_validate():
    """scenario_6: weights.json 加载 + 权重和 = 1.0 + 7 维齐全 + 阈值结构齐全."""
    cfg = load_weights(WEIGHTS_PATH)

    # 权重
    assert set(cfg["weights"].keys()) == set(DIMENSIONS), \
        f"权重维度集合必须 = {DIMENSIONS}, 实际 {set(cfg['weights'].keys())}"
    weight_sum = sum(cfg["weights"].values())
    assert abs(weight_sum - 1.0) < 1e-9, f"权重和必须 = 1.0, 实际 {weight_sum}"
    # 关键维度权重符合预期 (content 0.3, tool 0.25)
    assert cfg["weights"]["content"] == 0.30
    assert cfg["weights"]["tool"] == 0.25

    # veto 阈值
    assert "content" in cfg["veto_thresholds"]
    assert "defense" in cfg["veto_thresholds"]
    assert cfg["veto_thresholds"]["content"] == 0.5
    assert cfg["veto_thresholds"]["defense"] == 0.7

    # grade 阈值 (A/B/C/D 顺序)
    assert cfg["grade_thresholds"]["A"] > cfg["grade_thresholds"]["B"] > \
           cfg["grade_thresholds"]["C"] > cfg["grade_thresholds"]["D"]


def test_weights_json_breaks_on_invalid_sum():
    """weights.json 权重和 ≠ 1.0 时 load_weights 必须 raise ValueError."""
    # 临时构造坏 weights
    bad = {
        "version": "bad",
        "weights": {d: 0.1 for d in DIMENSIONS},  # sum = 0.7
        "veto_thresholds": DEFAULT_VETO_THRESHOLDS,
        "grade_thresholds": DEFAULT_GRADE_THRESHOLDS,
    }
    bad_path = SCORING_DIR / "weights_bad_test.json"
    bad_path.write_text(json.dumps(bad), encoding="utf-8")
    try:
        with pytest.raises(ValueError, match="权重和"):
            load_weights(bad_path)
    finally:
        bad_path.unlink()


# === 辅助 API: grade + check_veto + score_batch 独立单测 ===

def test_grade_boundaries():
    """grade() 边界值测试."""
    thresholds = DEFAULT_GRADE_THRESHOLDS
    assert grade(90.0, thresholds) == "A"
    assert grade(89.99, thresholds) == "B"
    assert grade(75.0, thresholds) == "B"
    assert grade(74.99, thresholds) == "C"
    assert grade(60.0, thresholds) == "C"
    assert grade(59.99, thresholds) == "D"
    assert grade(40.0, thresholds) == "D"
    assert grade(39.99, thresholds) == "F"
    assert grade(0.0, thresholds) == "F"


def test_check_veto_no_trigger():
    """check_veto 在所有维度 ≥ 阈值时返回 None."""
    scores = {dim: 1.0 for dim in DIMENSIONS}
    assert check_veto(scores) is None


def test_score_batch_runs_in_order():
    """score_batch 批量评分: 返回 list 长度 = 输入长度, 顺序对齐."""
    items = [_build_perfect_item(), _build_perfect_item()]
    benchmarks = [_build_perfect_benchmark(), _build_perfect_benchmark()]
    results = score_batch(items, DEFAULT_WEIGHTS, benchmarks)
    assert len(results) == 2
    assert all(r["grade"] == "A" for r in results)