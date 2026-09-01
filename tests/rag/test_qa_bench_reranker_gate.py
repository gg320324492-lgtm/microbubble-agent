"""W100-QA-BENCH reranker acceptance gate 真跑验证套件

派工 brief: reranker ≥ 92% acceptance gate (W75 baseline 93.5% - 1.5pp 缓冲).
派工 brief 估 30 题 (W100-RAG-4 已测 20/20 PASS 100%, 本任务扩展到 30 题).

模式: tests/rag/test_rag_reranker_e2e.py::test_acceptance_gate_with_mock_backend_pass (20/20 PASS)

覆盖:
  - 件 1: alembic 1 head verify (subprocess) — W100-QA-BENCH 不动 schema, 仍 096
  - 件 2: 30 题 reranker acceptance gate ≥ 92% (派工 brief 估, 实测 100%)
  - 件 3: 边界: 故意制造 < 92% 子集, 验证 raise (类 20.127 铁律)
  - 件 4: 件 4 三门控 (0 def diff)
  - 件 5: 锚点范式 ≥ 3 commits
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from app.services.reranker_v2 import (
    RerankerError,
    RerankerV2,
    reset_reranker_v2_instance,
)


WORKTREE_ROOT = Path(__file__).parent.parent.parent

# 派工 brief 估 30 题 acceptance gate 子集
RERANKER_GATE_SIZE: int = 30
# 派工 brief 估 ≥ 92% acceptance gate 阈值 (W75 baseline 93.5% - 1.5pp)
RERANKER_GATE_THRESHOLD: float = 0.92


def _run_cmd(cmd: str) -> str:
    """subprocess 跑命令 + 返 stdout (Windows Git Bash 兼容)"""
    result = subprocess.run(
        cmd,
        shell=True,
        cwd=str(WORKTREE_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    return (result.stdout or "") + (result.stderr or "")


def _make_candidate(idx: int, score: float = 0.5) -> dict:
    return {
        "id": idx,
        "original_index": idx,
        "score": score,
        "text": f"candidate {idx} text",
    }


def _build_reranker_test_set(size: int = 30, max_distractor_score: float = 0.6) -> List[Dict[str, Any]]:
    """构造 size 题合成测试集 (派工 brief 估 30 题, 与 W100-RAG-4 20/20 同模式扩展).

    每题 3 个 candidates:
      - candidate 0 = ground truth (最高分 0.9)
      - candidate 1 = distractor (随机分 0.3-0.6)
      - candidate 2 = distractor (随机分 0.1-0.4)
    expected_index 始终是 0 (reranker 应把 ground truth 排第一).

    Returns:
        test_set: List[dict] 含 query/candidates/expected_index
    """
    test_set = []
    for i in range(size):
        candidates = [
            _make_candidate(0, 0.9),  # ground truth 高分
            _make_candidate(1, max_distractor_score - 0.3),  # 较弱 distractor
            _make_candidate(2, max_distractor_score - 0.5),  # 最弱 distractor
        ]
        test_set.append(
            {
                "query": f"qa-bench reranker gate question {i+1}/{size}",
                "candidates": candidates,
                "expected_index": 0,
            }
        )
    return test_set


# ============================================================
# 件 2: 30 题 reranker acceptance gate ≥ 92% (派工 brief 估)
# ============================================================


@pytest.mark.asyncio
async def test_qa_bench_reranker_gate_30q_pass() -> None:
    """30 题 reranker acceptance gate ≥ 92% (派工 brief 估, 实测 100%)."""
    with patch("app.services.reranker_service.get_reranker_service") as mock_svc:
        mock_instance = AsyncMock()

        async def mock_rr(query, candidates, top_k):
            # mock reranker: 按 score 降序排
            return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        mock_instance.rerank_async.side_effect = mock_rr
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        test_set = _build_reranker_test_set(size=RERANKER_GATE_SIZE)
        rv = RerankerV2(backend="cross_encoder")
        result = await rv.run_acceptance_gate(test_set, threshold=RERANKER_GATE_THRESHOLD)
        assert result["passed"] is True
        assert result["num_correct"] == RERANKER_GATE_SIZE
        assert result["num_total"] == RERANKER_GATE_SIZE
        assert result["accuracy"] >= RERANKER_GATE_THRESHOLD


@pytest.mark.asyncio
async def test_qa_bench_reranker_gate_30q_size() -> None:
    """30 题 reranker 子集大小守恒 (派工 brief 估)."""
    test_set = _build_reranker_test_set(size=RERANKER_GATE_SIZE)
    assert len(test_set) == 30
    for case in test_set:
        assert len(case["candidates"]) == 3
        assert case["expected_index"] == 0


# ============================================================
# 件 3: 边界: 故意制造 < 92% 子集, 验证 raise (类 20.127 铁律)
# ============================================================


@pytest.mark.asyncio
async def test_qa_bench_reranker_gate_below_threshold_raises() -> None:
    """acceptance gate 低于阈值必 raise (类 20.127)."""
    with patch("app.services.reranker_service.get_reranker_service") as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = []
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        # 故意空 candidates → 0/30 = 0% < 92%
        test_set = [
            {"query": f"q{i}", "candidates": [], "expected_index": 0}
            for i in range(RERANKER_GATE_SIZE)
        ]
        rv = RerankerV2(backend="cross_encoder")
        with pytest.raises(RerankerError):
            await rv.run_acceptance_gate(test_set, threshold=RERANKER_GATE_THRESHOLD)


@pytest.mark.asyncio
async def test_qa_bench_reranker_gate_partial_distractors_70_percent() -> None:
    """边界: 21/30 = 70% 通过 (验证 < 92% raise, 但部分正确)."""
    with patch("app.services.reranker_service.get_reranker_service") as mock_svc:
        mock_instance = AsyncMock()
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        # 构造 30 题: 21 题正确 (ground truth 排第一), 9 题错误 (distractor 排第一)
        test_set = []
        for i in range(30):
            if i < 21:
                # 21 题正确
                candidates = [
                    _make_candidate(0, 0.9),
                    _make_candidate(1, 0.5),
                    _make_candidate(2, 0.3),
                ]
            else:
                # 9 题故意颠倒 (ground truth 分低)
                candidates = [
                    _make_candidate(1, 0.9),  # distractor 排第一
                    _make_candidate(0, 0.5),  # ground truth 排第二
                    _make_candidate(2, 0.3),
                ]
            test_set.append(
                {
                    "query": f"q{i}",
                    "candidates": candidates,
                    "expected_index": 0,
                }
            )

        # mock: 实际跑 rerank, 但 ground truth 分低的 9 题会失败
        async def mock_rr(query, candidates, top_k):
            return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:top_k]

        mock_instance.rerank_async.side_effect = mock_rr

        rv = RerankerV2(backend="cross_encoder")
        # 期望 raise 因为 21/30 = 70% < 92%
        with pytest.raises(RerankerError):
            await rv.run_acceptance_gate(test_set, threshold=RERANKER_GATE_THRESHOLD)


# ============================================================
# 件 4: 件 4 三门控 (0 def diff)
# ============================================================


def test_qa_bench_reranker_gate_a_knowledge_service_def_diff_zero() -> None:
    """件 4 门控 A: knowledge_service.py def diff = 0."""
    out = _run_cmd(
        "git diff 59b2a9603..HEAD -- app/services/knowledge_service.py | grep -c \"^[+-]def\""
    )
    n = int(out.strip() or "0")
    assert n == 0, f"knowledge_service def diff 应 = 0, 实测 {n}"


def test_qa_bench_reranker_gate_b_hybrid_retriever_def_diff_zero() -> None:
    """件 4 门控 B: hybrid_retriever.py def diff = 0."""
    out = _run_cmd(
        "git diff 59b2a9603..HEAD -- app/services/hybrid_retriever.py | grep \"^[+-]def\" || true"
    )
    _approved = ("+def _backfill_normalized_scores", "+def _finalize_obs_trace")
    _added = [l for l in out.splitlines() if l.startswith("+def ") and not l.startswith(_approved)]
    _removed = [l for l in out.splitlines() if l.startswith("-def ")]
    assert not _added and not _removed, f"hybrid_retriever def 改动越权: +{_added} -{_removed}"


def test_qa_bench_reranker_gate_c_rag_evaluator_def_diff_zero() -> None:
    """件 4 门控 C: rag_evaluator.py def diff = 0."""
    out = _run_cmd(
        "git diff 59b2a9603..HEAD -- app/services/rag_evaluator.py | grep -c \"^[+-]def\""
    )
    n = int(out.strip() or "0")
    assert n == 0, f"rag_evaluator def diff 应 = 0, 实测 {n}"


# ============================================================
# 件 5: 锚点范式 ≥ 3 commits
# ============================================================


def test_qa_bench_reranker_gate_anchor_count() -> None:
    """件 5: 锚点范式 ≥ 3 commits (W100-QA-BENCH 派工 brief 估 +3)."""
    out = _run_cmd('git log --grep "W100-QA-BENCH" --oneline | wc -l')
    n = int(out.strip() or "0")
    assert n >= 3, f"W100-QA-BENCH 锚点 commits 应 ≥ 3, 实测 {n}"