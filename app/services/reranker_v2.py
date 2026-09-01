"""Reranker v2 多 backend 抽象层 (W100-RAG-4)

设计目标:
  - 统一 rerank 入口, 支持 3 种 backend (CrossEncoder / BGEv2 / Cohere)
  - 复用 W75 B-1 既有 RerankerService (93.5% W61 baseline + OpenAI compat)
  - 92% acceptance gate 验证 (类 20.127: 失败必 raise, 不静默降级)
  - CrossEncoder 是默认 backend, 不破坏 W75 baseline (类 20.128)
  - 仅 ADD 新文件, 不动 RerankerService 任何签名 (件 4 门控 D)

派工 v6 §13.3 假设禁令已遵守:
  - RerankerService 接口实测 = rerank_async (派工 plan 偏差据实上报)
  - CrossEncoder 既有实现 0 重写, 复用 rerank_async

3 backend:
  - CrossEncoderBackend (默认, 沿用 RerankerService.rerank_async)
  - BGEv2Backend (BAAI/bge-reranker-v2-m3, 与 CrossEncoder 同 backend 直接走 CrossEncoder)
  - CohereBackend (云端 rerank-v3.0 / rerank-english-v3.0)

类 20.127: 92% acceptance gate 失败必 raise RuntimeError, 不静默降级
类 20.128: CrossEncoder 默认 backend 不破坏 W75 93.5% baseline
类 20.123: 派工 plan 偏差据实 (rerank_async 不是 rerank)
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("microbubble.reranker_v2")

# ===== 模块级常量 (env 兜底) =====
# 默认 backend 沿用 RerankerService (W75 B-1)
DEFAULT_BACKEND: str = os.getenv("RERANKER_BACKEND", "cross_encoder")
DEFAULT_MODEL: str = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
DEFAULT_API_KEY: str = os.getenv("RERANKER_API_KEY", "")
# 92% acceptance gate (W75 baseline 93.5%, +0.5pp 缓冲防回归)
DEFAULT_ACCEPTANCE_GATE: float = float(
    os.getenv("RERANKER_ACCEPTANCE_GATE", "0.92")
)

# Cohere API endpoint
COHERE_RERANK_ENDPOINT: str = "https://api.cohere.ai/v1/rerank"


@dataclass
class RerankEvaluationResult:
    """单次 acceptance gate 评估结果."""

    backend: str
    accuracy: float
    passed: bool
    threshold: float
    num_correct: int
    num_total: int
    failures: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "backend": self.backend,
            "accuracy": self.accuracy,
            "passed": self.passed,
            "threshold": self.threshold,
            "num_correct": self.num_correct,
            "num_total": self.num_total,
            "failures": self.failures,
        }


class RerankerError(RuntimeError):
    """Reranker 异常基类 (失败必 raise, 类 20.127)."""


class CrossEncoderBackend:
    """默认 backend — 复用 W75 RerankerService.rerank_async (0 重写).

    派工 plan 偏差据实: W75 接口是 `rerank_async` 不是 `rerank`.
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self._model = model  # 透传给 RerankerService (RERANKER_MODEL_NAME env 优先)
        self._api_key = api_key  # CrossEncoder 无 API key, 仅占位对齐接口

    async def rerank(
        self, query: str, candidates: List[dict], top_k: int = 5
    ) -> List[dict]:
        """复用 W75 RerankerService.rerank_async (件 4 门控 D 守恒).

        Args:
            query: 原始查询
            candidates: 候选文档列表
            top_k: 返回条数

        Returns:
            按 CrossEncoder 分数重排序的 top_k 列表 (与 W75 行为一致)
        """
        if not candidates:
            return []
        # 复用现有 RerankerService (W75 B-1 已建, 0 重写 CrossEncoder)
        from app.services.reranker_service import get_reranker_service

        service = get_reranker_service()
        return await service.rerank_async(
            query=query, candidates=candidates, top_k=top_k
        )


class BGEv2Backend:
    """BGEv2 backend — 与 CrossEncoder 同模型直接复用 (避免冗余 import).

    派工 plan 假设"BGEv2 是独立 backend", 实测 W75 默认就是 BAAI/bge-reranker-v2-m3.
    处置: BGEv2 backend 直接路由到 CrossEncoder (保持 1 个真实 backend, 0 重复代码).
    类 20.128 沿用: 不破坏 W75 baseline.
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        # BGEv2 与 CrossEncoder 同 backend (W75 默认模型就是 BGE m3)
        self._cross_encoder = CrossEncoderBackend(
            model=model or "BAAI/bge-reranker-v2-m3",
            api_key=api_key,
        )

    async def rerank(
        self, query: str, candidates: List[dict], top_k: int = 5
    ) -> List[dict]:
        """直接转发到 CrossEncoder (避免重复代码)."""
        return await self._cross_encoder.rerank(query, candidates, top_k)


class CohereBackend:
    """Cohere 云端 rerank backend (API key via env).

    API key 缺失时降级警告, 不抛错 (与 W75 graceful degradation 一致).
    实际 HTTP 调用不在 acceptance gate 测试范围 (test mock 即可).
    """

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self._model = model or "rerank-english-v3.0"
        self._api_key = api_key or DEFAULT_API_KEY

    async def rerank(
        self, query: str, candidates: List[dict], top_k: int = 5
    ) -> List[dict]:
        """Cohere rerank (API key 缺失时降级按原始 score 排序)."""
        if not candidates:
            return []
        if not self._api_key:
            logger.warning(
                "[W100-RAG-4] Cohere API key missing, "
                "fallback to original score sort (类 20.128 graceful degradation)"
            )
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]

        # 注: 实际 HTTP 调用延迟 + 网络依赖不在 acceptance gate mock 范围
        # 留接口以备未来扩展, 当前测试用 mock
        try:
            import aiohttp  # type: ignore[import-untyped]

            async with aiohttp.ClientSession() as session:
                payload = {
                    "model": self._model,
                    "query": query,
                    "documents": [
                        f"{c.get('title', '')} {c.get('content', '')}"
                        for c in candidates
                    ],
                    "top_n": top_k,
                }
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
                async with session.post(
                    COHERE_RERANK_ENDPOINT, json=payload, headers=headers
                ) as resp:
                    data = await resp.json()
                results_map = {
                    r["index"]: r["relevance_score"] for r in data.get("results", [])
                }
                for i, c in enumerate(candidates):
                    c["rerank_score"] = round(float(results_map.get(i, 0.0)), 4)
                reranked = sorted(
                    candidates, key=lambda x: x["rerank_score"], reverse=True
                )
                return reranked[:top_k]
        except ImportError:
            logger.warning(
                "[W100-RAG-4] aiohttp not installed, fallback to score sort"
            )
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]
        except Exception as e:
            logger.error(f"[W100-RAG-4] Cohere API failed: {e}, fallback to score sort")
            sorted_candidates = sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )
            for c in sorted_candidates:
                c["rerank_score"] = c.get("score", 0)
            return sorted_candidates[:top_k]


BACKEND_REGISTRY: Dict[str, type] = {
    "cross_encoder": CrossEncoderBackend,
    "bge_v2": BGEv2Backend,
    "cohere": CohereBackend,
}


class RerankerV2:
    """Reranker v2 主入口 (W100-RAG-4).

    后端切换通过 env RERANKER_BACKEND 或构造 backend 参数.
    92% acceptance gate 必跑, 失败 raise RerankerError (类 20.127).
    """

    def __init__(
        self,
        db: Any = None,
        backend: Optional[str] = None,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self._db = db  # 当前 backend 不需要 db (留口给未来实体链 reranker)
        self._backend_name = backend or DEFAULT_BACKEND
        self._model = model or DEFAULT_MODEL
        self._api_key = api_key or DEFAULT_API_KEY
        self._instance = self._build_backend()

    def _build_backend(self):
        cls = BACKEND_REGISTRY.get(self._backend_name)
        if cls is None:
            raise RerankerError(
                f"Unknown reranker backend: {self._backend_name}. "
                f"Available: {list(BACKEND_REGISTRY.keys())}"
            )
        return cls(model=self._model, api_key=self._api_key)

    @property
    def backend_name(self) -> str:
        return self._backend_name

    @property
    def model(self) -> str:
        return self._model

    async def rerank(
        self, query: str, candidates: List[dict], top_k: int = 5
    ) -> List[dict]:
        """异步 rerank, 委托给当前 backend.

        Args:
            query: 原始查询
            candidates: 候选文档列表
            top_k: 返回条数

        Returns:
            按 backend 分数重排序的 top_k 列表

        Raises:
            RerankerError: backend 内部异常
        """
        try:
            return await self._instance.rerank(
                query=query, candidates=candidates, top_k=top_k
            )
        except RerankerError:
            raise
        except Exception as e:
            raise RerankerError(
                f"Reranker {self._backend_name} failed: {e}"
            ) from e

    async def run_acceptance_gate(
        self,
        test_set: List[Dict[str, Any]],
        threshold: float = DEFAULT_ACCEPTANCE_GATE,
    ) -> Dict[str, Any]:
        """跑 acceptance gate 验证 (92% 阈值, W75 baseline +0.5pp).

        Args:
            test_set: 测试集, 每条必含 query + candidates + expected_index 字段
                expected_index: 期望 rerank 后 top-1 的候选在 candidates 中的索引
            threshold: 通过阈值, 默认 0.92

        Returns:
            dict 含 backend/accuracy/passed/threshold/num_correct/num_total/failures

        Raises:
            RerankerError: accuracy < threshold 时必 raise (类 20.127)
        """
        if not test_set:
            raise RerankerError(
                "[W100-RAG-4] test_set is empty, cannot run acceptance gate"
            )

        num_correct = 0
        num_total = len(test_set)
        failures: List[Dict[str, Any]] = []

        for i, item in enumerate(test_set):
            query = item.get("query", "")
            candidates = item.get("candidates", [])
            expected_index = item.get("expected_index", 0)

            if not candidates:
                failures.append(
                    {"index": i, "reason": "empty candidates", "query": query[:50]}
                )
                continue

            try:
                reranked = await self.rerank(query, candidates, top_k=1)
                # 取 rerank 后 top-1 的原始索引
                # 2026-09-01 修复: 原实现 top1.get("original_index", expected_index)
                # 在 candidates 无 original_index 时 fallback 到 expected_index 自己
                # → gate 永远 100% 通过 (形同虚设)。现在: 优先 original_index,
                # 缺失时按 candidate id 在 candidates 中查真实下标, 查不到记 failure。
                top1 = reranked[0] if reranked else None
                if top1 is None:
                    failures.append(
                        {
                            "index": i,
                            "reason": "rerank returned empty",
                            "query": query[:50],
                        }
                    )
                    continue

                if "original_index" in top1:
                    top1_index = top1["original_index"]
                else:
                    top1_id = top1.get("id")
                    top1_index = next(
                        (idx for idx, c in enumerate(candidates) if c.get("id") == top1_id),
                        None,
                    )
                if top1_index is None:
                    failures.append(
                        {
                            "index": i,
                            "reason": "cannot resolve top1 original index",
                            "query": query[:50],
                        }
                    )
                    continue

                if top1_index == expected_index:
                    num_correct += 1
                else:
                    failures.append(
                        {
                            "index": i,
                            "query": query[:50],
                            "expected_index": expected_index,
                            "got_index": top1_index,
                        }
                    )
            except Exception as e:
                failures.append(
                    {
                        "index": i,
                        "reason": f"rerank exception: {e}",
                        "query": query[:50],
                    }
                )

        accuracy = num_correct / num_total if num_total else 0.0
        passed = accuracy >= threshold
        result = RerankEvaluationResult(
            backend=self._backend_name,
            accuracy=accuracy,
            passed=passed,
            threshold=threshold,
            num_correct=num_correct,
            num_total=num_total,
            failures=failures,
        )

        # 类 20.127: 失败必 raise, 不静默降级
        if not passed:
            raise RerankerError(
                f"[W100-RAG-4] Reranker acceptance gate FAILED: "
                f"{self._backend_name} accuracy {accuracy:.2%} < threshold {threshold:.2%} "
                f"({num_correct}/{num_total}). Failures: {len(failures)}"
            )

        logger.info(
            f"[W100-RAG-4] Acceptance gate PASSED: "
            f"{self._backend_name} accuracy {accuracy:.2%} >= {threshold:.2%} "
            f"({num_correct}/{num_total})"
        )
        return result.to_dict()


# ============================================================
# 模块级工厂 (供 reranker_service.py get_reranker_instance 调用)
# ============================================================
_reranker_v2_instance: Optional[RerankerV2] = None


def get_reranker_v2_instance(
    backend: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> RerankerV2:
    """获取 RerankerV2 实例 (process-local singleton, 沿用 W75 工厂模式).

    用于 hybrid_retriever 注入式调用 (W100-RAG-4 hook).
    """
    global _reranker_v2_instance
    if _reranker_v2_instance is None:
        _reranker_v2_instance = RerankerV2(
            backend=backend, model=model, api_key=api_key
        )
    return _reranker_v2_instance


def reset_reranker_v2_instance() -> None:
    """重置单例 (测试用)."""
    global _reranker_v2_instance
    _reranker_v2_instance = None
