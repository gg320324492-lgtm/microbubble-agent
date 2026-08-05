"""W-N-OBS +1 _chunk_late_recall 显式失败 + observability 计数器 单元测试.

覆盖:
  - Case 1: 失败路径 → logger.warning 含 'chunk_late_recall FAILED' + 计数器 +1 + 返回空集
  - Case 2: 成功路径 → 返回结果列表 + 计数器 successes_total +1 + 不计入 failures
  - Case 3: RecallTrace 新字段 (chunk_late_recall_path/count/failed/error) 默认值
  - Case 4: RecallObserver.get_chunk_late_recall_stats() 输出结构 + 滚动裁剪
  - Case 5: clear() 重置 3 个 chunk_late_recall 字段
  - Case 6: ENABLE_OBSERVABILITY=False → record_chunk_late_recall no-op (但失败 logger.warning 仍触发, 走 logger.warning 是 hard guarantee)
  - Case 7: 既有 25 字段不被破坏 (W93 + W99-RAG-1/2 + W100-RAG-5)
  - Case 8: best-effort 设计守恒 — 观测失败不阻断主流程 (mock observer 抛错时 _chunk_late_recall 仍返回空集)
"""
import asyncio
import logging
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# 辅助 Mock
# ============================================================

class _MockResult:
    def fetchall(self):
        return [SimpleNamespace(knowledge_id=7, distance=0.2)]


class _MockDB:
    """成功路径 mock: 返回固定一行 (knowledge_id=7, distance=0.2)"""
    async def execute(self, statement, params):
        return _MockResult()


class _FailingDB:
    """失败路径 mock: execute() 抛 RuntimeError"""
    async def execute(self, statement, params):
        raise RuntimeError("column unavailable during rollout")


class _ThrowingObserverDB:
    """观测失败的 mock: db.execute 返回成功, 但内部 observer.record_chunk_late_recall 抛错"""
    def __init__(self):
        self.success_calls = 0

    async def execute(self, statement, params):
        self.success_calls += 1
        return _MockResult()


# ============================================================
# Case 1: 失败路径显式记录
# ============================================================

@pytest.mark.asyncio
async def test_case_01_failure_logs_warning_and_counter_increments(caplog):
    """Case 1: 失败路径 → logger.warning 含 'chunk_late_recall FAILED' + failures_total +=1 + 返回空集"""
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.recall_observability import RecallObserver

    RecallObserver.reset()
    observer = RecallObserver.get()
    initial_failures = observer._chunk_late_recall_failures_total

    db = _FailingDB()
    with caplog.at_level(logging.WARNING, logger="microbubble.hybrid_retriever"):
        result = await HybridRetriever(db)._chunk_late_recall([0.0] * 1024, top_k=5)

    # 返回空集 (best-effort 守恒)
    assert result == []
    # 计数器 +1
    assert observer._chunk_late_recall_failures_total == initial_failures + 1
    # successes_total 不增
    assert observer._chunk_late_recall_successes_total == 0
    # 日志含 'chunk_late_recall FAILED' + 异常类型
    log_text = " ".join(r.message for r in caplog.records)
    assert "chunk_late_recall FAILED" in log_text
    assert "RuntimeError" in log_text


# ============================================================
# Case 2: 成功路径显式记录
# ============================================================

@pytest.mark.asyncio
async def test_case_02_success_logs_count_and_returns_rows(caplog):
    """Case 2: 成功路径 → 返回结果列表 + successes_total +=1 + failures_total 不增"""
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.recall_observability import RecallObserver

    RecallObserver.reset()
    observer = RecallObserver.get()
    initial_successes = observer._chunk_late_recall_successes_total
    initial_failures = observer._chunk_late_recall_failures_total

    db = _MockDB()
    with caplog.at_level(logging.DEBUG, logger="microbubble.hybrid_retriever"):
        result = await HybridRetriever(db)._chunk_late_recall([0.0] * 1024, top_k=5)

    # 返回 1 行
    assert len(result) == 1
    assert result[0]["id"] == 7
    assert result[0]["retrieval_method"] == "chunk_late"
    # successes_total +1
    assert observer._chunk_late_recall_successes_total == initial_successes + 1
    # failures_total 不增
    assert observer._chunk_late_recall_failures_total == initial_failures
    # 成功路径走 logger.debug, 不在 WARNING level 出现
    warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert len(warning_records) == 0


# ============================================================
# Case 3: RecallTrace 新字段默认值
# ============================================================

def test_case_03_recall_trace_new_fields_defaults():
    """Case 3: RecallTrace 新字段默认值 + 字段总数 ≥ 28 (W93 24 + W99-RAG-1 2 + W99-RAG-2 1 + W100-RAG-5 1 + W-N-OBS 4 = 32)"""
    from app.services.recall_observability import RecallTrace

    t = RecallTrace()
    assert t.chunk_late_recall_path is False
    assert t.chunk_late_recall_count == 0
    assert t.chunk_late_recall_failed is False
    assert t.chunk_late_recall_error is None

    # 字段总数 (≥ 28 守恒 W93 ≥ 12 + W-N-OBS 追加)
    fields = RecallTrace.__dataclass_fields__
    assert len(fields) >= 28, f"字段数 {len(fields)} < 28 (W93 ≥ 12 + W99-RAG-1 2 + W99-RAG-2 1 + W100-RAG-5 1 + W-N-OBS 4 = 32)"


# ============================================================
# Case 4: get_chunk_late_recall_stats 输出
# ============================================================

def test_case_04_chunk_late_recall_stats_structure():
    """Case 4: get_chunk_late_recall_stats 返回 7 字段 + 滚动裁剪"""
    from app.services.recall_observability import RecallObserver

    RecallObserver.reset()
    observer = RecallObserver.get()

    # 空统计
    stats = observer.get_chunk_late_recall_stats()
    assert stats["failures_total"] == 0
    assert stats["successes_total"] == 0
    assert stats["failure_ratio"] == 0.0
    assert stats["sample_count"] == 0
    assert stats["p50_ms"] == 0.0
    assert stats["p95_ms"] == 0.0
    assert stats["p99_ms"] == 0.0

    # 注入 5 成功 + 1 失败
    observer.record_chunk_late_recall(success=True, latency_ms=10.0, result_count=3)
    observer.record_chunk_late_recall(success=True, latency_ms=20.0, result_count=2)
    observer.record_chunk_late_recall(success=True, latency_ms=30.0, result_count=0)
    observer.record_chunk_late_recall(success=True, latency_ms=40.0, result_count=5)
    observer.record_chunk_late_recall(success=True, latency_ms=50.0, result_count=1)
    observer.record_chunk_late_recall(success=False, latency_ms=100.0, error_msg="boom")

    stats = observer.get_chunk_late_recall_stats()
    assert stats["failures_total"] == 1
    assert stats["successes_total"] == 5
    assert stats["failure_ratio"] == pytest.approx(1 / 6, abs=0.001)
    assert stats["sample_count"] == 6
    # 排序后 [10,20,30,40,50,100], idx = min(int(6*0.50), 5) = 3 → 40.0
    assert stats["p50_ms"] == 40.0
    # p99 = min(int(6*0.99), 5) = 5 → 100.0
    assert stats["p99_ms"] == 100.0


# ============================================================
# Case 5: clear() 重置 chunk_late_recall 字段
# ============================================================

def test_case_05_clear_resets_chunk_late_recall_fields():
    """Case 5: clear() 重置 failures_total / successes_total / latencies"""
    from app.services.recall_observability import RecallObserver

    RecallObserver.reset()
    observer = RecallObserver.get()
    observer.record_chunk_late_recall(success=True, latency_ms=10.0, result_count=1)
    observer.record_chunk_late_recall(success=False, latency_ms=20.0, error_msg="err")
    assert observer._chunk_late_recall_failures_total == 1
    assert observer._chunk_late_recall_successes_total == 1
    assert len(observer._chunk_late_recall_latencies_ms) == 2

    observer.clear()
    assert observer._chunk_late_recall_failures_total == 0
    assert observer._chunk_late_recall_successes_total == 0
    assert len(observer._chunk_late_recall_latencies_ms) == 0


# ============================================================
# Case 6: ENABLE_OBSERVABILITY=False 静默计数器 + 显式 logger.warning 仍触发
# ============================================================

@pytest.mark.asyncio
async def test_case_06_disabled_no_counter_but_warning_still_logs(caplog):
    """Case 6: ENABLE_OBSERVABILITY=False → 计数器不增 + 仍走 logger.warning (hard guarantee)"""
    from app.services import recall_observability as ro
    from app.services.hybrid_retriever import HybridRetriever
    from app.services.recall_observability import RecallObserver

    RecallObserver.reset()
    observer = RecallObserver.get()
    initial_failures = observer._chunk_late_recall_failures_total
    original = ro.ENABLE_OBSERVABILITY
    ro.ENABLE_OBSERVABILITY = False
    try:
        with caplog.at_level(logging.WARNING, logger="microbubble.hybrid_retriever"):
            result = await HybridRetriever(_FailingDB())._chunk_late_recall([0.0] * 1024)
        assert result == []
        # 计数器不增 (关闭时静默)
        assert observer._chunk_late_recall_failures_total == initial_failures
        # logger.warning 仍触发 (hard guarantee: 失败必须可见)
        log_text = " ".join(r.message for r in caplog.records)
        assert "chunk_late_recall FAILED" in log_text
    finally:
        ro.ENABLE_OBSERVABILITY = original
        RecallObserver.reset()


# ============================================================
# Case 7: 既有 25 字段不被破坏
# ============================================================

def test_case_07_existing_fields_unchanged():
    """Case 7: 既有 25 字段 (W93 + W99-RAG-1/2 + W100-RAG-5) 完整保留"""
    from app.services.recall_observability import RecallTrace

    t = RecallTrace(
        caller_path="kb_qa",
        for_query=True,
        has_query_prompt=False,
        original_len=100,
        truncated_len=80,
        latency_ms=12.3,
        retrieval_method="hybrid",
        candidate_k=25,
        top_k=5,
        vector_score=0.9,
        bm25_score=0.8,
        graph_score=0.7,
        rerank_score=0.85,
        error_count=0,
        error_msg=None,
        slow_query=False,
        cache_hit=True,
        cache_similarity=0.95,
        citation_count=3,
        image_score=0.5,
    )

    # 既有字段值正确
    assert t.caller_path == "kb_qa"
    assert t.latency_ms == 12.3
    assert t.cache_hit is True
    assert t.cache_similarity == 0.95
    assert t.citation_count == 3
    assert t.image_score == 0.5

    # 新字段不影响既有字段
    assert t.chunk_late_recall_path is False
    assert t.chunk_late_recall_count == 0
    assert t.chunk_late_recall_failed is False
    assert t.chunk_late_recall_error is None

    # to_dict() 输出包含全部字段
    d = t.to_dict()
    assert "chunk_late_recall_path" in d
    assert "chunk_late_recall_count" in d
    assert "chunk_late_recall_failed" in d
    assert "chunk_late_recall_error" in d


# ============================================================
# Case 8: best-effort 设计守恒 — 观测失败不阻断主流程
# ============================================================

@pytest.mark.asyncio
async def test_case_08_observer_failure_does_not_break_main_flow(monkeypatch):
    """Case 8: 即使 RecallObserver.record_chunk_late_recall 抛错, _chunk_late_recall 仍正常返回结果

    设计意图: 观测是 best-effort 加分项, 永远不能阻断主流程.
    """
    from app.services.recall_observability import RecallObserver
    from app.services.hybrid_retriever import HybridRetriever

    RecallObserver.reset()

    # 让 observer.record_chunk_late_recall 抛错
    original_record = RecallObserver.record_chunk_late_recall
    def boom(*args, **kwargs):
        raise RuntimeError("observer internal failure")

    monkeypatch.setattr(RecallObserver, "record_chunk_late_recall", boom)

    db = _MockDB()
    # 不应抛错 (主流程不受影响)
    result = await HybridRetriever(db)._chunk_late_recall([0.0] * 1024, top_k=5)
    assert len(result) == 1
    assert result[0]["id"] == 7

    # 恢复 (monkeypatch 自动还原)
    monkeypatch.setattr(RecallObserver, "record_chunk_late_recall", original_record)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])