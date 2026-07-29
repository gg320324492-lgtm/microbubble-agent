"""RAG 召回可观测性埋点 (W93 PR7 B-7)

按路召回耗时分解埋点 + 慢查询自动告警 + 12+ 结构化字段.
对接 app/models/search_log.py 扩展字段, 不改已有字段.
仅在 HybridRetriever.retrieve() 头部加 hook 调用, 不改 10 个 def 签名.

设计目标:
  - grafana 6 面板数据源 (P50/P95/P99 + 按路耗时 + 召回候选数 + CTR + 错误率 + 慢查询)
  - 按路召回耗时覆盖 100% 检索请求 (vector / bm25 / graph / rerank)
  - P99 ≤ 200ms (1000 并发)
  - 日志结构化字段 ≥ 12

字段清单 (≥ 12):
  caller_path / for_query / has_query_prompt /
  original_len / truncated_len / latency_ms /
  retrieval_method / candidate_k / top_k /
  vector_score / bm25_score / graph_score / rerank_score /
  error_count / slow_query (P99 阈值 200ms)

对接点:
  - app/services/hybrid_retriever.py:retrieve() 头部 (3 行 hook)
  - app/models/search_log.py 新增可空字段 (不破坏已有 schema, 加列独立 commit)

严禁:
  - 改 hybrid_retriever.py 4 路开关默认值 (vector/bm25/graph/rerank)
  - 改 search_log.py 已有字段 (仅 ADD COLUMN nullable=True)
  - 把 grafana 面板硬塞 alembic (本 PR 不动 alembic)
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.recall_observability")


# ============================================================
# 配置 (环境变量兜底, 默认值与 plan §11.2 对齐)
# ============================================================

P99_LATENCY_THRESHOLD_MS = int(os.getenv("RECALL_P99_LATENCY_MS", "200"))
SLOW_QUERY_THRESHOLD_MS = int(os.getenv("RECALL_SLOW_QUERY_MS", "150"))
ENABLE_OBSERVABILITY = os.getenv("RECALL_OBSERVABILITY_ENABLED", "1") != "0"


# ============================================================
# 数据结构 (12+ 字段)
# ============================================================

@dataclass
class RecallTrace:
    """单次召回的完整可观测性 trace

    字段对照 plan §11.2:
      caller_path, for_query, has_query_prompt,
      original_len, truncated_len, latency_ms,
      retrieval_method, candidate_k, top_k,
      vector_score, bm25_score, graph_score, rerank_score,
      error_count, slow_query, error_msg
    """

    caller_path: str = "hybrid_retriever"
    for_query: bool = True
    has_query_prompt: bool = False
    original_len: int = 0
    truncated_len: int = 0
    latency_ms: float = 0.0
    retrieval_method: str = "hybrid"
    candidate_k: int = 0
    top_k: int = 0
    vector_score: Optional[float] = None
    bm25_score: Optional[float] = None
    graph_score: Optional[float] = None
    rerank_score: Optional[float] = None
    error_count: int = 0
    error_msg: Optional[str] = None
    slow_query: bool = False
    timestamp: float = field(default_factory=time.time)
    # 内部用: 按路耗时分解
    per_path_latency_ms: Dict[str, float] = field(default_factory=dict)
    per_path_count: Dict[str, int] = field(default_factory=dict)
    per_path_error: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_log_line(self) -> str:
        """结构化 JSON 单行日志, 供 grafana/loki 抓取"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)


# ============================================================
# 核心: RecallObserver
# ============================================================

class RecallObserver:
    """全局召回可观测性收集器

    用法:
      async with RecallObserver.observe(caller_path="hybrid", for_query=True) as trace:
          # 在 HybridRetriever.retrieve() 头部启用
          trace.set_candidate(top_k=5, candidate_k=25)
          # ... 实际检索 ...
          trace.record_path("vector", latency_ms=..., count=..., score=...)
    """

    _instance: Optional["RecallObserver"] = None

    def __init__(self) -> None:
        self.traces: List[RecallTrace] = []
        self._lock = asyncio.Lock()
        # 滚动统计 (用于 grafana)
        self.recent_latencies_ms: List[float] = []
        self.max_recent = 1000

    @classmethod
    def get(cls) -> "RecallObserver":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """测试用: 重置全局单例"""
        cls._instance = None

    @asynccontextmanager
    async def observe(
        self,
        caller_path: str = "hybrid_retriever",
        for_query: bool = True,
        has_query_prompt: bool = False,
        original_query: str = "",
    ):
        """观测上下文管理器

        进入: 创建 RecallTrace, 启动计时
        退出: 计算总耗时, 记录到滚动缓冲, 慢查询打 WARNING 日志
        """
        if not ENABLE_OBSERVABILITY:
            # 关闭时返回空 trace (不记录)
            yield _NullTrace()
            return

        trace = RecallTrace(
            caller_path=caller_path,
            for_query=for_query,
            has_query_prompt=has_query_prompt,
            original_len=len(original_query),
            truncated_len=len(original_query[:6000]),
        )
        start = time.perf_counter()
        try:
            yield trace
        except Exception as e:
            trace.error_count += 1
            trace.error_msg = f"{type(e).__name__}: {e}"
            raise
        finally:
            # 若 trace.latency_ms 未被调用方显式设置 (> 0 视为已设置), 才用 perf_counter
            if trace.latency_ms <= 0.0:
                trace.latency_ms = round((time.perf_counter() - start) * 1000, 3)
            trace.slow_query = trace.latency_ms > P99_LATENCY_THRESHOLD_MS
            await self._record(trace)

    async def _record(self, trace: RecallTrace) -> None:
        """记录 trace + 滚动缓冲"""
        async with self._lock:
            self.traces.append(trace)
            self.recent_latencies_ms.append(trace.latency_ms)
            # 滚动裁剪
            if len(self.recent_latencies_ms) > self.max_recent:
                self.recent_latencies_ms = self.recent_latencies_ms[-self.max_recent:]

        # 结构化日志 (供 grafana loki 抓取)
        logger.info("recall_trace %s", trace.to_log_line())

        # 慢查询告警
        if trace.slow_query:
            logger.warning(
                "slow_recall_query caller=%s latency_ms=%.2f threshold_ms=%d paths=%s",
                trace.caller_path,
                trace.latency_ms,
                P99_LATENCY_THRESHOLD_MS,
                json.dumps(trace.per_path_latency_ms),
            )

    # ============================================================
    # 统计查询 (供 grafana / health check 使用)
    # ============================================================

    def get_stats(self) -> Dict[str, Any]:
        """汇总统计 (P50 / P95 / P99 + 慢查询比例 + 错误率 + 按路平均耗时)"""
        if not self.recent_latencies_ms:
            return {
                "sample_count": 0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "slow_query_ratio": 0.0,
                "error_ratio": 0.0,
                "per_path_avg_ms": {},
            }

        latencies = sorted(self.recent_latencies_ms)
        n = len(latencies)

        def _percentile(p: float) -> float:
            idx = min(int(n * p), n - 1)
            return round(latencies[idx], 3)

        slow_count = sum(1 for t in self.traces if t.slow_query)
        error_count = sum(1 for t in self.traces if t.error_count > 0)

        # 按路平均耗时
        path_totals: Dict[str, float] = {}
        path_counts: Dict[str, int] = {}
        for t in self.traces:
            for path, ms in t.per_path_latency_ms.items():
                path_totals[path] = path_totals.get(path, 0.0) + ms
                path_counts[path] = path_counts.get(path, 0) + 1
        per_path_avg = {
            p: round(path_totals[p] / path_counts[p], 3)
            for p in path_totals
            if path_counts[p] > 0
        }

        return {
            "sample_count": n,
            "p50_ms": _percentile(0.50),
            "p95_ms": _percentile(0.95),
            "p99_ms": _percentile(0.99),
            "slow_query_ratio": round(slow_count / n, 4) if n > 0 else 0.0,
            "error_ratio": round(error_count / n, 4) if n > 0 else 0.0,
            "per_path_avg_ms": per_path_avg,
        }

    def clear(self) -> None:
        """测试用: 清空 traces + 滚动缓冲"""
        self.traces.clear()
        self.recent_latencies_ms.clear()


# ============================================================
# 测试用 NullTrace (observability 关闭时)
# ============================================================

class _NullTrace:
    """ENABLE_OBSERVABILITY=False 时返回的 stub, 所有 setter no-op"""

    def __setattr__(self, key: str, value: Any) -> None:
        pass

    def record_path(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_candidate(self, *args: Any, **kwargs: Any) -> None:
        pass

    def set_score(self, *args: Any, **kwargs: Any) -> None:
        pass


# ============================================================
# 辅助: 简化 trace 记录 (HybridRetriever 内部用)
# ============================================================

def make_recall_trace(
    caller_path: str = "hybrid_retriever",
    for_query: bool = True,
    has_query_prompt: bool = False,
    original_query: str = "",
) -> RecallTrace:
    """快速构造 RecallTrace (便于测试和直接调用)"""
    return RecallTrace(
        caller_path=caller_path,
        for_query=for_query,
        has_query_prompt=has_query_prompt,
        original_len=len(original_query),
        truncated_len=len(original_query[:6000]),
    )


def aggregate_per_path(
    trace: RecallTrace,
    path_results: Dict[str, List[Dict[str, Any]]],
    path_latencies_ms: Dict[str, float],
) -> None:
    """聚合 per-path 耗时与命中数

    path_results: {"vector": [...], "bm25": [...], "graph": [...]}
    path_latencies_ms: {"vector": 12.3, "bm25": 8.1, "graph": 25.0}
    """
    for path, results in path_results.items():
        trace.per_path_count[path] = len(results)
        trace.per_path_latency_ms[path] = round(path_latencies_ms.get(path, 0.0), 3)

    # 设置路径对应分数 (取 top-1 分数, 无则 None)
    for path, results in path_results.items():
        if not results:
            continue
        top = results[0]
        score = top.get("score") or top.get("normalized_score")
        if path == "vector":
            trace.vector_score = score
        elif path == "bm25":
            trace.bm25_score = score
        elif path == "graph":
            trace.graph_score = score
        elif path == "rerank":
            trace.rerank_score = score


__all__ = [
    "RecallObserver",
    "RecallTrace",
    "P99_LATENCY_THRESHOLD_MS",
    "SLOW_QUERY_THRESHOLD_MS",
    "ENABLE_OBSERVABILITY",
    "make_recall_trace",
    "aggregate_per_path",
]