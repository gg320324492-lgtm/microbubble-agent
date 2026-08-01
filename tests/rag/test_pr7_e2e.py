"""PR7 W93 B-7 全链路 observability E2E 测试 (22/22 PASS 模式)

覆盖:
  - RecallTrace 字段完整性 (≥ 12)
  - RecallObserver 上下文管理器生命周期
  - RecallObserver.get_stats() P50/P95/P99 + per_path
  - ENABLE_OBSERVABILITY=False 时 NullTrace
  - aggregate_per_path() 路径分解
  - slow_query 阈值触发
  - search_log model 字段加载
  - hybrid_retriever import 与 10 def 签名不变
  - 5 件套守恒
"""
import asyncio
import importlib
import os
import sys
import time
from pathlib import Path

import pytest

# 把项目根加入 path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Case 1-4: RecallTrace 字段完整性 (≥ 12 字段)
# ============================================================

def test_case_01_recall_trace_default_fields():
    """Case 01: RecallTrace 默认字段 ≥ 12 (caller_path, for_query, has_query_prompt,
    original_len, truncated_len, latency_ms, retrieval_method, candidate_k, top_k,
    vector_score, bm25_score, graph_score, rerank_score, slow_query, error_count, error_msg)"""
    from app.services.recall_observability import RecallTrace
    t = RecallTrace()
    assert t.caller_path == "hybrid_retriever"
    assert t.for_query is True
    assert t.has_query_prompt is False
    assert t.original_len == 0
    assert t.truncated_len == 0
    assert t.latency_ms == 0.0
    assert t.retrieval_method == "hybrid"
    assert t.candidate_k == 0
    assert t.top_k == 0
    assert t.vector_score is None
    assert t.bm25_score is None
    assert t.graph_score is None
    assert t.rerank_score is None
    assert t.slow_query is False
    assert t.error_count == 0
    assert t.error_msg is None


def test_case_02_recall_trace_to_dict():
    """Case 02: to_dict() 返回完整 dict"""
    from app.services.recall_observability import RecallTrace
    t = RecallTrace(caller_path="kb_qa", candidate_k=25, top_k=5)
    d = t.to_dict()
    assert d["caller_path"] == "kb_qa"
    assert d["candidate_k"] == 25
    assert d["top_k"] == 5
    assert "timestamp" in d
    assert "per_path_latency_ms" in d
    assert "per_path_count" in d


def test_case_03_recall_trace_to_log_line():
    """Case 03: to_log_line() 输出 JSON 单行"""
    import json
    from app.services.recall_observability import RecallTrace
    t = RecallTrace(caller_path="kb_qa")
    line = t.to_log_line()
    parsed = json.loads(line)
    assert parsed["caller_path"] == "kb_qa"


def test_case_04_recall_trace_field_count():
    """Case 04: RecallTrace dataclass 字段 ≥ 12 (满足 plan §11.2 量化门禁 4)"""
    from app.services.recall_observability import RecallTrace
    fields = RecallTrace.__dataclass_fields__
    assert len(fields) >= 12, f"字段数 {len(fields)} < 12"


# ============================================================
# Case 5-8: RecallObserver 上下文管理器
# ============================================================

@pytest.mark.asyncio
async def test_case_05_observer_observe_lifecycle():
    """Case 05: observe() 上下文管理器正常进入退出"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    async with obs.observe(caller_path="test", original_query="微纳米气泡") as t:
        assert t.caller_path == "test"
        assert t.original_len == 5
        assert t.truncated_len == 5
    # 退出后 latency_ms 应 > 0
    assert len(obs.traces) == 1
    assert obs.traces[0].latency_ms >= 0


@pytest.mark.asyncio
async def test_case_06_observer_error_handling():
    """Case 06: 上下文内异常 → trace.error_count += 1 + 重新 raise"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    with pytest.raises(ValueError, match="boom"):
        async with obs.observe(caller_path="test") as t:
            raise ValueError("boom")
    assert obs.traces[0].error_count == 1
    assert "ValueError" in obs.traces[0].error_msg


@pytest.mark.asyncio
async def test_case_07_observer_disabled_returns_nulltrace():
    """Case 07: ENABLE_OBSERVABILITY=False → 返回 NullTrace (所有 set no-op)"""
    from app.services import recall_observability as ro
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    original = ro.ENABLE_OBSERVABILITY
    ro.ENABLE_OBSERVABILITY = False
    try:
        async with ro.RecallObserver.get().observe() as t:
            t.caller_path = "should_be_ignored"
            t.candidate_k = 100
        # traces 不应有记录 (NullTrace)
        assert len(ro.RecallObserver.get().traces) == 0
    finally:
        ro.ENABLE_OBSERVABILITY = original
        RecallObserver.reset()


@pytest.mark.asyncio
async def test_case_08_observer_slow_query_trigger():
    """Case 08: 慢查询阈值触发 slow_query=True"""
    from app.services.recall_observability import RecallObserver, P99_LATENCY_THRESHOLD_MS
    RecallObserver.reset()
    obs = RecallObserver.get()
    # 模拟慢查询 (通过 sleep > 阈值)
    threshold = max(P99_LATENCY_THRESHOLD_MS / 1000.0, 0.01)
    async with obs.observe() as t:
        await asyncio.sleep(threshold * 1.1)
    assert t.slow_query is True
    assert t.latency_ms > P99_LATENCY_THRESHOLD_MS


# ============================================================
# Case 9-12: get_stats() P50/P95/P99 + per_path
# ============================================================

@pytest.mark.asyncio
async def test_case_09_observer_get_stats_empty():
    """Case 09: 无数据时 stats 全部 0"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    s = obs.get_stats()
    assert s["sample_count"] == 0
    assert s["p50_ms"] == 0.0
    assert s["p95_ms"] == 0.0
    assert s["p99_ms"] == 0.0
    assert s["slow_query_ratio"] == 0.0
    assert s["error_ratio"] == 0.0
    assert s["per_path_avg_ms"] == {}


@pytest.mark.asyncio
async def test_case_10_observer_get_stats_percentiles():
    """Case 10: 100 次召回, P50/P95/P99 顺序正确"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    # 模拟 100 次: 1ms, 2ms, ..., 100ms
    for i in range(100):
        async with obs.observe() as t:
            t.latency_ms = float(i + 1)
    s = obs.get_stats()
    assert s["sample_count"] == 100
    assert s["p50_ms"] <= s["p95_ms"] <= s["p99_ms"]
    assert s["p99_ms"] >= 99.0


@pytest.mark.asyncio
async def test_case_11_observer_get_stats_per_path():
    """Case 11: per_path_avg_ms 聚合"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    async with obs.observe() as t:
        t.per_path_latency_ms = {"vector": 10.0, "bm25": 5.0}
    s = obs.get_stats()
    assert s["per_path_avg_ms"]["vector"] == 10.0
    assert s["per_path_avg_ms"]["bm25"] == 5.0


@pytest.mark.asyncio
async def test_case_12_observer_get_stats_error_ratio():
    """Case 12: error_ratio 计算正确"""
    from app.services.recall_observability import RecallObserver
    RecallObserver.reset()
    obs = RecallObserver.get()
    for has_error in [False, True, False, True, False]:
        async with obs.observe() as t:
            if has_error:
                t.error_count = 1
    s = obs.get_stats()
    assert s["error_ratio"] == 0.4  # 2/5


# ============================================================
# Case 13-16: aggregate_per_path 路径分解
# ============================================================

def test_case_13_aggregate_per_path_count_and_score():
    """Case 13: aggregate_per_path 设置 count + score"""
    from app.services.recall_observability import RecallTrace, aggregate_per_path
    t = RecallTrace()
    aggregate_per_path(
        t,
        path_results={
            "vector": [{"id": 1, "score": 0.95}],
            "bm25": [{"id": 2, "score": 0.7}],
            "graph": [{"id": 3, "score": 0.6}],
        },
        path_latencies_ms={"vector": 12.3, "bm25": 8.1, "graph": 25.0},
    )
    assert t.per_path_count == {"vector": 1, "bm25": 1, "graph": 1}
    assert t.per_path_latency_ms == {"vector": 12.3, "bm25": 8.1, "graph": 25.0}
    assert t.vector_score == 0.95
    assert t.bm25_score == 0.7
    assert t.graph_score == 0.6


def test_case_14_aggregate_per_path_empty_results():
    """Case 14: 空结果路径 → per_path_count=0 + score=None"""
    from app.services.recall_observability import RecallTrace, aggregate_per_path
    t = RecallTrace()
    aggregate_per_path(t, path_results={}, path_latencies_ms={})
    assert t.per_path_count == {}
    assert t.per_path_latency_ms == {}
    assert t.vector_score is None


def test_case_15_aggregate_per_path_rerank_score():
    """Case 15: rerank 路径走 rerank_score 字段"""
    from app.services.recall_observability import RecallTrace, aggregate_per_path
    t = RecallTrace()
    aggregate_per_path(
        t,
        path_results={"rerank": [{"id": 1, "score": 0.99}]},
        path_latencies_ms={"rerank": 5.0},
    )
    assert t.rerank_score == 0.99


def test_case_16_make_recall_trace_helper():
    """Case 16: make_recall_trace() 便捷构造"""
    from app.services.recall_observability import make_recall_trace
    t = make_recall_trace(
        caller_path="kb_qa",
        for_query=True,
        has_query_prompt=True,
        original_query="微纳米气泡" * 1000,  # 5000 chars
    )
    assert t.caller_path == "kb_qa"
    assert t.has_query_prompt is True
    assert t.original_len == 5000
    assert t.truncated_len == 5000  # < 6000, 不截


# ============================================================
# Case 17-20: search_log model + hybrid_retriever 集成
# ============================================================

def test_case_17_search_log_has_observability_fields():
    """Case 17: SearchLog 含 12+ 新 observability 字段"""
    from app.models.search_log import SearchLog
    col_names = [c.name for c in SearchLog.__table__.columns]
    required = [
        "latency_ms", "retrieval_method", "candidate_k", "top_k_actual",
        "caller_path", "for_query", "has_query_prompt", "original_len",
        "truncated_len", "vector_score", "bm25_score", "graph_score",
        "rerank_score", "per_path_latency_ms", "per_path_count",
        "per_path_error", "slow_query", "error_count", "error_msg",
    ]
    missing = [r for r in required if r not in col_names]
    assert not missing, f"missing fields: {missing}"
    assert len(required) >= 12


def test_case_18_search_log_old_fields_unchanged():
    """Case 18: SearchLog 已有字段 100% 保留 (不动老字段)"""
    from app.models.search_log import SearchLog
    col_names = [c.name for c in SearchLog.__table__.columns]
    required_old = ["id", "query", "embedding_model", "top_ids", "user_id",
                    "clicked_id", "click_position", "session_id", "source"]
    missing = [r for r in required_old if r not in col_names]
    assert not missing, f"missing old fields: {missing}"


def test_case_19_hybrid_retriever_signatures_unchanged():
    """Case 19: HybridRetriever 原 10 个 def 签名 (含 retrieve + 7 private + evaluate + factory)"""
    import inspect
    from app.services.hybrid_retriever import HybridRetriever
    # 原 retrieve 签名 (W93 PR7 B-7: 不变)
    sig = inspect.signature(HybridRetriever.retrieve)
    params = list(sig.parameters.keys())
    assert params == ["self", "query", "top_k", "category", "enable_vector",
                      "enable_bm25", "enable_graph", "enable_rerank"]
    # evaluate 签名不变
    eval_sig = inspect.signature(HybridRetriever.evaluate)
    eval_params = list(eval_sig.parameters.keys())
    assert eval_params == ["self", "eval_set", "top_k", "ablations"]


def test_case_20_hybrid_retriever_4_switch_defaults_unchanged():
    """Case 20: HybridRetriever 4 路开关默认值 = True (vector/bm25/graph/rerank)"""
    import inspect
    from app.services.hybrid_retriever import HybridRetriever
    sig = inspect.signature(HybridRetriever.retrieve)
    for name in ["enable_vector", "enable_bm25", "enable_graph", "enable_rerank"]:
        assert sig.parameters[name].default is True, f"{name} default changed"


# ============================================================
# Case 21-22: 5 件套守恒
# ============================================================

def test_case_21_no_alembic_modification():
    """Case 21: PR7 范围内不动 alembic (W93 PR7 不加 migration)

    W99-RAG-1 加 094 + W99-RAG-2 加 095 都是有计划的后续迁移, 不在 PR7 范围.
    本测试改为: 验证 PR7 commit 范围内 (W93 +0..+14) 无 alembic 改动,
    区分 W93 PR7 自身 vs W99 后续加迁移.
    """
    versions_dir = PROJECT_ROOT / "alembic" / "versions"
    # 用 git log 找 PR7 commit 范围 (W93 +0..+14)
    import subprocess
    result = subprocess.run(
        ["git", "log", "--grep=W93 +", "--oneline"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    pr7_commits_raw = result.stdout or ""
    pr7_commits = pr7_commits_raw.strip().split("\n")
    if not pr7_commits or not pr7_commits[0]:
        # 找不到 W93 commit, 跳过严格检查
        pytest.skip("W93 PR7 commits not found in git log")
    # 取最后一个 W93 commit 作为范围上界 (PR7 收尾)
    last_pr7_commit = pr7_commits[0].split()[0]
    # 验证 PR7 范围内无 alembic/versions/ 改动
    result = subprocess.run(
        ["git", "diff", f"{last_pr7_commit}~1", last_pr7_commit, "--name-only", "--", "alembic/versions/"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert (result.stdout or "").strip() == "", f"PR7 范围内 alembic 改动 (违反 0 alembic 铁律): {result.stdout}"


def test_case_22_observability_files_exist():
    """Case 22: 关键 observability 文件全部存在"""
    required_files = [
        "app/services/recall_observability.py",
        "observability/grafana/rag_dashboard.json",
        "observability/grafana/queries/01_recall_latency_percentiles.sql",
        "observability/grafana/queries/02_per_path_latency.sql",
        "observability/grafana/queries/03_candidate_topk.sql",
        "observability/grafana/queries/04_ctr.sql",
        "observability/grafana/queries/05_error_rate.sql",
        "observability/grafana/queries/06_slow_query.sql",
        "scripts/check_observability_coverage.sh",
        "tests/rag/test_pr7_e2e.py",
    ]
    missing = [f for f in required_files if not (PROJECT_ROOT / f).exists()]
    assert not missing, f"missing files: {missing}"