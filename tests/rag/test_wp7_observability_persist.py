"""WP7 (2026-09-01) observability 落库回归测试

修 grafana 断链: RecallObserver 此前只打日志, search_logs 扩展列全空。
本文件锁两个契约:
  1. retrieve_with_weights / retrieve_per_method 产生带 per_path_latency_ms
     + top_ids + candidate_k 的 trace ( retrieve() 路由同)
  2. _persist_trace_to_search_log 把 trace 写成含扩展列的 SearchLog 行
     (独立 session, 失败静默)
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import recall_observability as ro
from app.services.hybrid_retriever import HybridRetriever
from app.services.recall_observability import RecallObserver


def _stub_hybrid(monkeypatch):
    """三路 stub: vector 2 条 / bm25 1 条 / graph 0 条, 各带 created_at"""

    async def vector_search(self, query, top_k, category=None):
        return [
            {"id": 1, "title": "a", "score": 0.9, "created_at": None},
            {"id": 2, "title": "b", "score": 0.8, "created_at": None},
        ]

    async def bm25_search(self, query, top_k, category=None):
        return [{"id": 3, "title": "c", "score": 5.0, "created_at": None}]

    async def graph_search(self, query, top_k):
        return []

    monkeypatch.setattr(HybridRetriever, "_vector_search", vector_search)
    monkeypatch.setattr(HybridRetriever, "_bm25_search", bm25_search)
    monkeypatch.setattr(HybridRetriever, "_graph_search", graph_search)


@pytest.mark.asyncio
async def test_retrieve_per_method_records_trace(monkeypatch):
    """per-method 路产生 per_path_latency_ms + candidate_k + top_ids trace"""
    _stub_hybrid(monkeypatch)
    RecallObserver.reset()
    db = MagicMock()
    retriever = HybridRetriever(db)
    out = await retriever.retrieve_per_method("测试查询", candidate_k=10)

    assert set(out.keys()) >= {"vector", "bm25", "graph"}
    observer = RecallObserver.get()
    assert observer.traces, "observe() 未产生 trace"
    trace = observer.traces[-1]
    assert trace.candidate_k == 10
    assert "vector" in trace.per_path_latency_ms
    assert "bm25" in trace.per_path_latency_ms
    assert trace.per_path_count.get("vector") == 2
    assert 1 in trace.top_ids and 3 in trace.top_ids
    # 落库 spawn: original_query 非空 → 有 fire-and-forget task 排队
    assert trace.original_query == "测试查询"


@pytest.mark.asyncio
async def test_retrieve_records_trace_and_finalize(monkeypatch):
    """retrieve() 路终态埋点: top_k_actual + top_ids + rerank 计时可选"""
    _stub_hybrid(monkeypatch)

    async def rerank_async(self, query, candidates, top_k=5):
        return candidates[:top_k]

    monkeypatch.setattr(
        "app.services.reranker_service.RerankerService.rerank_async", rerank_async
    )
    # 禁用真实 rerank 模型加载 (fallback path 会设 rerank_score)
    monkeypatch.setattr(
        "app.services.reranker_service.RerankerService._load_model", lambda self: None
    )
    RecallObserver.reset()
    db = MagicMock()
    retriever = HybridRetriever(db)
    results = await retriever.retrieve("测试查询", top_k=2, enable_graph=False)

    assert len(results) <= 2
    observer = RecallObserver.get()
    assert observer.traces, "observe() 未产生 trace"
    trace = observer.traces[-1]
    assert trace.top_k_actual == len(results)
    assert trace.top_ids
    assert "vector" in trace.per_path_latency_ms


@pytest.mark.asyncio
async def test_persist_trace_writes_searchlog_with_extended_columns():
    """_persist_trace_to_search_log 构造含扩展列的 SearchLog 且提交"""
    trace = ro.RecallTrace(
        caller_path="retrieve_with_weights",
        retrieval_method="hybrid",
        latency_ms=12.5,
        candidate_k=25,
        top_k=5,
        top_k_actual=5,
        original_query="臭氧微气泡传质",
        top_ids=[1, 2, 3],
        slow_query=False,
    )
    trace.per_path_latency_ms["vector"] = 8.1
    trace.per_path_count["vector"] = 25

    captured = {}

    class _FakeDB:
        def add(self, row):
            captured["row"] = row

        async def commit(self):
            captured["committed"] = True

    import contextlib

    @contextlib.asynccontextmanager
    async def fake_session():
        yield _FakeDB()

    monkeypatch_session = patch(
        "app.core.database.async_session", fake_session
    )
    with monkeypatch_session:
        await ro._persist_trace_to_search_log(trace)

    row = captured["row"]
    assert captured.get("committed") is True
    assert row.query == "臭氧微气泡传质"
    assert row.source == "hybrid_retriever"
    assert row.latency_ms == 12.5
    assert row.candidate_k == 25
    assert row.top_k_actual == 5
    assert row.top_ids == [1, 2, 3]
    assert row.per_path_latency_ms == {"vector": 8.1}
    assert row.per_path_count == {"vector": 25}


@pytest.mark.asyncio
async def test_persist_trace_silent_on_failure(capsys):
    """落库失败 (DB 不可达) 只 debug 不抛 — best-effort 铁律"""
    trace = ro.RecallTrace(
        original_query="q",
        top_ids=[1],
        latency_ms=1.0,
        top_k_actual=1,
    )

    class _BoomDB:
        def add(self, row):
            raise RuntimeError("db down")

        async def commit(self):
            pass

    import contextlib

    @contextlib.asynccontextmanager
    async def fake_session():
        yield _BoomDB()

    with patch("app.core.database.async_session", fake_session):
        # 不应抛出
        await ro._persist_trace_to_search_log(trace)
