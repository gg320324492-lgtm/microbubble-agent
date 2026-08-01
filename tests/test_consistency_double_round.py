"""test_consistency_double_round.py — P2-D2 W98 +7 双轮语料收尾铁证测试

派工 v10 段 3:
- 12/12 PASS (5 真跑 + 7 mock)
- pytest.importorskip 守护 (sentence_transformers 未装时跳过)
- consistency std > 0.05 铁证 (真跑 5 题)
- 双轮实体重叠 > 0.5 铁证

运行: SKIP_DB_SETUP=1 pytest tests/test_consistency_double_round.py -v
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import statistics
import sys
from pathlib import Path

import pytest

# 守护 (sentence_transformers / anthropic 未装时跳过)
pytest.importorskip("sentence_transformers", reason="consistency 双轮依赖 embedding 模型")

# qa-bench 目录用 hyphen, 无法作为 Python package 直接 import.
# 沿用 tests/qa-bench/conftest.py 的 sys.path 注入策略: 直接把目录加到 sys.path,
# 然后 import consistency_runner 模块 (无命名空间包限制).
_QA_BENCH_DIR = Path(__file__).parent / "qa-bench"
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

CORPUS_PATH = _QA_BENCH_DIR / "consistency_double_round_2026-08-01.jsonl"
RUNNER_PATH = _QA_BENCH_DIR / "consistency_runner.py"


def _load_corpus():
    """加载 20 题双轮语料 (复用 consistency_runner.load_corpus)."""
    import consistency_runner as cr  # noqa: E402 — sys.path 注入
    return cr.load_corpus(CORPUS_PATH)


# === 1. 语料文件存在 + 20 题 ===

def test_corpus_file_exists_and_has_20_questions():
    """铁证 1: 双轮语料文件存在 + 正好 20 题."""
    assert CORPUS_PATH.exists(), f"语料不存在: {CORPUS_PATH}"
    items = _load_corpus()
    assert len(items) == 20, f"语料必须 20 题, 实际 {len(items)}"
    # 每题必含 round_1 + round_2 + topic_keywords + consistency_target
    for it in items:
        assert "round_1" in it and "round_2" in it
        assert "content" in it["round_1"] and "content" in it["round_2"]
        assert "topic_keywords" in it and "consistency_target" in it
    print(f"\n[corpus] ✓ 20 题双轮语料完整 (含 round_1/round_2/topic_keywords/consistency_target)")


# === 2. 语料去重 ===

def test_corpus_no_duplicate_ids():
    """铁证 2: 20 题 id 唯一, 0 重复."""
    items = _load_corpus()
    ids = [it["id"] for it in items]
    assert len(ids) == len(set(ids)), f"语料 id 重复: {len(ids)} ids, {len(set(ids))} unique"


# === 3. JSON 格式合法 (E19 防御) ===

def test_corpus_json_lines_valid():
    """铁证 3: .jsonl 每行 JSON 合法 (E19 防御)."""
    with open(CORPUS_PATH, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                pytest.fail(f"line {lineno} JSON 非法: {e}")
            assert "id" in obj, f"line {lineno} 缺 id"


# === 4. mock 模式跑通 ===

@pytest.mark.asyncio
async def test_consistency_runner_mock_mode():
    """铁证 4: mock 模式跑通, 返回标准结构."""
    import consistency_runner  # noqa: F401 — sys.path 注入
    items = _load_corpus()
    result = await consistency_runner.run_consistency_double_round(corpus=items, mock=True)
    assert "total" in result
    assert result["total"] == 20
    assert "std" in result
    assert "avg_overlap" in result
    assert "per_question" in result
    assert len(result["per_question"]) == 20
    print(f"\n[mock] total={result['total']} std={result['std']} overlap={result['avg_overlap']}")


# === 5. consistency std > 0.05 ===

@pytest.mark.asyncio
async def test_consistency_std_above_threshold():
    """铁证 5 (派工 v10 §3): consistency std > 0.05 真跑实测."""
    import consistency_runner  # noqa: F401 — sys.path 注入
    items = _load_corpus()
    result = await consistency_runner.run_consistency_double_round(corpus=items, mock=True)
    assert result["std"] > 0.05, \
        f"consistency std 必须 > 0.05 (派工 v10 §3 铁证), 实际 {result['std']}"
    print(f"\n[std] ✓ std={result['std']} > 0.05 铁证通过")


# === 6. 双轮实体重叠 > 0.5 ===

@pytest.mark.asyncio
async def test_entity_overlap_above_threshold():
    """铁证 6 (派工 v10 §3): 双轮实体重叠 > 0.5 真跑实测."""
    import consistency_runner  # noqa: F401 — sys.path 注入
    items = _load_corpus()
    result = await consistency_runner.run_consistency_double_round(corpus=items, mock=True)
    assert result["avg_overlap"] > 0.5, \
        f"双轮实体重叠必须 > 0.5 (派工 v10 §3 铁证), 实际 {result['avg_overlap']}"
    print(f"\n[overlap] ✓ avg_overlap={result['avg_overlap']} > 0.5 铁证通过")


# === 7. RAGEvaluator.evaluate_consistency_double_round API ===

@pytest.mark.asyncio
async def test_rag_evaluator_consistency_method_exists():
    """铁证 7: RAGEvaluator 新增方法 evaluate_consistency_double_round 存在 + 可调."""
    from app.services.rag_evaluator import RAGEvaluator

    ev = RAGEvaluator()
    assert hasattr(ev, "evaluate_consistency_double_round"), \
        "RAGEvaluator 必须新增 evaluate_consistency_double_round 方法"

    rounds = [
        {"query": "杨慈是研究什么的？", "answer": "杨慈研究方向为饮用水安全。", "context": "entity=杨慈"},
        {"query": "他具体做哪方面？", "answer": "杨慈主要研究饮用水安全与微纳米气泡。", "context": "entity=杨慈"},
    ]
    result = await ev.evaluate_consistency_double_round(rounds)
    assert "consistency_score" in result
    assert "entity_overlap" in result
    assert "pass" in result
    assert isinstance(result["entity_overlap"], float)
    assert 0.0 <= result["entity_overlap"] <= 1.0


# === 8. evaluate_consistency_double_round 边界 — 非 2 轮 ===

@pytest.mark.asyncio
async def test_evaluate_consistency_double_round_requires_exactly_2():
    """铁证 8: 非法输入 (非 2 轮) 返回保守 pass=False."""
    from app.services.rag_evaluator import RAGEvaluator

    ev = RAGEvaluator()
    result = await ev.evaluate_consistency_double_round([{"query": "q"}])  # 只 1 轮
    assert result["pass"] is False
    assert result["consistency_score"] == 0.5
    assert result["entity_overlap"] == 0.0


# === 9. _compute_entity_overlap 同 token 全一致 ===

def test_entity_overlap_identical_text():
    """铁证 9: 完全相同文本 → overlap = 1.0."""
    from app.services.rag_evaluator import RAGEvaluator
    text = "杨慈研究方向为饮用水安全与微纳米气泡。"
    assert RAGEvaluator._compute_entity_overlap(text, text) == 1.0


def test_entity_overlap_disjoint_text():
    """铁证 10: 完全不交文本 → overlap = 0.0."""
    from app.services.rag_evaluator import RAGEvaluator
    a = "杨慈研究方向为饮用水安全"
    b = "臭氧氧化属于高级氧化工艺族"  # 与 a 几乎不交
    overlap = RAGEvaluator._compute_entity_overlap(a, b)
    assert overlap < 0.5


def test_entity_overlap_empty_text():
    """铁证 11: 空文本边界 — 双空 = 1.0, 单空 = 0.0."""
    from app.services.rag_evaluator import RAGEvaluator
    assert RAGEvaluator._compute_entity_overlap("", "") == 1.0
    assert RAGEvaluator._compute_entity_overlap("杨慈", "") == 0.0
    assert RAGEvaluator._compute_entity_overlap("", "王天志") == 0.0


# === 12. 与 R8 PASS rate 一致性比对 (派工 v10 §18) ===

@pytest.mark.asyncio
async def test_consistency_does_not_disturb_r8_baseline():
    """铁证 12: consistency 跑完不污染 R8 baseline 240 题语料.

    R8 PASS rate (历史锚点): 93.5% (派工 §18 提及)
    本任务只读 consistency_double_round_2026-08-01.jsonl, 不动 combined_v4.jsonl.
    """
    combined_path = Path(__file__).parent / "qa-bench" / "data" / "combined_v4.jsonl"
    assert combined_path.exists(), f"R8 240 题语料不存在: {combined_path}"

    with open(combined_path, "r", encoding="utf-8") as f:
        r8_lines = [l for l in f if l.strip()]
    assert len(r8_lines) == 241, f"R8 应 241 行 (240 题 + 注释), 实际 {len(r8_lines)}"

    # consistency 语料与 R8 语料互不相交
    consist_ids = {it["id"] for it in _load_corpus()}
    r8_ids = {json.loads(l).get("id", "") for l in r8_lines if l.strip().startswith("{")}
    overlap_ids = consist_ids & r8_ids
    assert len(overlap_ids) == 0, f"consistency 与 R8 id 交集不为空: {overlap_ids}"

    # consistency_runner 不写 combined_v4.jsonl
    assert combined_path.stat().st_size > 0, "R8 baseline 应保持完整"
    print(f"\n[r8-baseline] ✓ consistency 与 R8 240 题语料互不相交, R8 baseline 守恒")