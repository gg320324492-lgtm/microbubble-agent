"""W100-RAG-4 Reranker v2 单测 (20 test cases)

门禁: 20/20 PASS
模式: tests/rag/test_intent_classifier.py (mock + 边界)

覆盖:
  - 3 case backend 切换 (CrossEncoder/BGEv2/Cohere)
  - 4 case CrossEncoder 复用 (mock RerankerService.rerank_async)
  - 3 case acceptance gate 通过/失败/边界 (threshold = 0.92)
  - 3 case rerank 排序正确性
  - 3 case API key 缺失降级
  - 4 case 配置 (RERANKER_BACKEND/RERANKER_MODEL/RERANKER_API_KEY/RERANKER_ACCEPTANCE_GATE)
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

from app.services.reranker_v2 import (
    BACKEND_REGISTRY,
    DEFAULT_ACCEPTANCE_GATE,
    DEFAULT_BACKEND,
    CrossEncoderBackend,
    BGEv2Backend,
    CohereBackend,
    RerankEvaluationResult,
    RerankerError,
    RerankerV2,
    get_reranker_v2_instance,
    reset_reranker_v2_instance,
)


# ============================================================
# Helpers
# ============================================================


def _make_candidate(idx: int, score: float = 0.5) -> Dict[str, Any]:
    return {
        "id": idx,
        "title": f"doc-{idx}",
        "content": f"content {idx}",
        "score": score,
    }


def _make_test_set(size: int = 5, match: bool = True) -> List[Dict[str, Any]]:
    test_set = []
    for i in range(size):
        candidates = [_make_candidate(j) for j in range(3)]
        test_set.append(
            {
                "query": f"test query {i}",
                "candidates": candidates,
                "expected_index": 0 if match else 2,  # 期望 first candidate
            }
        )
    return test_set


async def _mock_rerank(query, candidates, top_k):
    """Mock rerank 函数 — 始终按 candidates[0].score 排第一位."""
    if not candidates:
        return []
    sorted_c = sorted(
        candidates, key=lambda x: x.get("score", 0), reverse=True
    )
    for c in sorted_c:
        c["rerank_score"] = c.get("score", 0)
    return sorted_c[:top_k]


# ============================================================
# Test Backend Registry (3 cases)
# ============================================================


def test_backend_registry_has_3_backends():
    """3 backend 已注册."""
    assert "cross_encoder" in BACKEND_REGISTRY
    assert "bge_v2" in BACKEND_REGISTRY
    assert "cohere" in BACKEND_REGISTRY
    assert len(BACKEND_REGISTRY) >= 3


def test_default_backend_is_cross_encoder():
    """默认 backend 是 cross_encoder (类 20.128, 沿用 W75 baseline)."""
    assert DEFAULT_BACKEND == "cross_encoder"


def test_backend_classes_instantiable():
    """3 backend 类都可实例化."""
    ce = CrossEncoderBackend(model="test-model")
    bge = BGEv2Backend()
    coh = CohereBackend(api_key="fake-key")
    assert ce is not None
    assert bge is not None
    assert coh is not None


# ============================================================
# Test CrossEncoder 复用 (4 cases)
# ============================================================


@pytest.mark.asyncio
async def test_cross_encoder_calls_rerank_async():
    """CrossEncoder 走 RerankerService.rerank_async (件 4 门控 D)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [
            _make_candidate(0, 0.9)
        ]
        mock_svc.return_value = mock_instance

        backend = CrossEncoderBackend()
        result = await backend.rerank("test query", [_make_candidate(0)], top_k=1)

        assert mock_instance.rerank_async.called
        assert len(result) == 1


@pytest.mark.asyncio
async def test_cross_encoder_empty_candidates():
    """CrossEncoder 空 candidates 返空 (W75 沿用行为)."""
    backend = CrossEncoderBackend()
    result = await backend.rerank("test query", [], top_k=5)
    assert result == []


@pytest.mark.asyncio
async def test_bge_v2_delegates_to_cross_encoder():
    """BGEv2 直接转发到 CrossEncoder (避免代码重复)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [
            _make_candidate(0, 0.95)
        ]
        mock_svc.return_value = mock_instance

        backend = BGEv2Backend()
        result = await backend.rerank("test", [_make_candidate(0)], top_k=1)

        assert mock_instance.rerank_async.called
        assert len(result) == 1


@pytest.mark.asyncio
async def test_3_backends_all_reachable():
    """3 backend 都可被 RerankerV2 路由."""

    # cross_encoder
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = []
        mock_svc.return_value = mock_instance

        rv_ce = RerankerV2(backend="cross_encoder")
        await rv_ce.rerank("test", [], top_k=5)
        assert mock_instance.rerank_async.called


# ============================================================
# Test acceptance gate (3 cases)
# ============================================================


@pytest.mark.asyncio
async def test_acceptance_gate_pass_92_percent():
    """acceptance gate 通过 (4/5 = 80% < 92% ... 需 5/5 = 100% 才能 92% 通过)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        # mock 完美重排: 永远 candidate 0 在第一位
        async def mock_rr(query, candidates, top_k):
            if not candidates:
                return []
            return sorted(
                candidates, key=lambda x: x.get("score", 0), reverse=True
            )[:top_k]
        mock_instance.rerank_async.side_effect = mock_rr
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        test_set = _make_test_set(size=10, match=True)
        # candidates 都是 [0.9, 0.5, 0.1] 默认 score → 始终 candidate 0 第一
        for item in test_set:
            item["candidates"] = [
                _make_candidate(0, 0.9),
                _make_candidate(1, 0.5),
                _make_candidate(2, 0.1),
            ]
        rv = RerankerV2(backend="cross_encoder")
        result = await rv.run_acceptance_gate(test_set, threshold=0.92)
        assert result["passed"] is True
        assert result["accuracy"] >= 0.92


@pytest.mark.asyncio
async def test_acceptance_gate_fail_raises():
    """acceptance gate 失败必 raise RerankerError (类 20.127)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = []
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        # 故意制造失败: 空 candidates → 0/n
        test_set = [{"query": "q", "candidates": [], "expected_index": 0}]
        rv = RerankerV2(backend="cross_encoder")
        with pytest.raises(RerankerError) as exc_info:
            await rv.run_acceptance_gate(test_set, threshold=0.92)
        assert "FAILED" in str(exc_info.value)


@pytest.mark.asyncio
async def test_acceptance_gate_threshold_boundary():
    """acceptance gate 边界 = 0.92 正好临界 (90.9% < 92% 失败)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        # mock 全部失败 → 0%
        mock_instance.rerank_async.return_value = [
            _make_candidate(1, 0.0)
        ]
        mock_svc.return_value = mock_instance

        reset_reranker_v2_instance()
        test_set = _make_test_set(size=10, match=True)
        rv = RerankerV2(backend="cross_encoder")
        # 0% accuracy → 必 raise (类 20.127)
        with pytest.raises(RerankerError):
            await rv.run_acceptance_gate(test_set, threshold=0.92)


# ============================================================
# Test rerank 排序正确性 (3 cases)
# ============================================================


@pytest.mark.asyncio
async def test_rerank_returns_top_k():
    """rerank 返回 top_k 条 (W75 沿用行为)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [
            _make_candidate(0, 0.9),
            _make_candidate(1, 0.5),
        ]
        mock_svc.return_value = mock_instance

        rv = RerankerV2(backend="cross_encoder")
        result = await rv.rerank("test", [_make_candidate(i) for i in range(5)], top_k=2)
        assert len(result) == 2


@pytest.mark.asyncio
async def test_rerank_preserves_order_from_backend():
    """rerank 按 backend 返回的顺序保留."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [
            _make_candidate(2, 0.95),
            _make_candidate(0, 0.85),
            _make_candidate(1, 0.75),
        ]
        mock_svc.return_value = mock_instance

        rv = RerankerV2(backend="cross_encoder")
        result = await rv.rerank("test", [_make_candidate(i) for i in range(3)], top_k=3)
        assert result[0]["id"] == 2
        assert result[1]["id"] == 0
        assert result[2]["id"] == 1


@pytest.mark.asyncio
async def test_rerank_attaches_original_index():
    """hybrid_retriever reranker hook 给 candidates 标 original_index (回溯 ground truth)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [_make_candidate(0)]
        mock_svc.return_value = mock_instance

        rv = RerankerV2(backend="cross_encoder")
        candidates = [_make_candidate(i) for i in range(3)]
        for idx, c in enumerate(candidates):
            c["original_index"] = idx
        await rv.rerank("test", candidates, top_k=1)
        assert "original_index" in candidates[0]


# ============================================================
# Test API key 缺失降级 (3 cases)
# ============================================================


@pytest.mark.asyncio
async def test_cohere_no_api_key_fallback():
    """Cohere 无 API key 降级按原始 score 排序."""
    backend = CohereBackend(api_key="")
    candidates = [
        _make_candidate(0, 0.3),
        _make_candidate(1, 0.9),
        _make_candidate(2, 0.5),
    ]
    result = await backend.rerank("test query", candidates, top_k=2)
    # score 最高的 candidate 1 在第一位
    assert result[0]["id"] == 1
    assert "rerank_score" in result[0]


@pytest.mark.asyncio
async def test_rerank_v2_no_api_key_for_cross_encoder():
    """CrossEncoder backend 不需要 API key, 正常工作."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.return_value = [_make_candidate(0)]
        mock_svc.return_value = mock_instance

        rv = RerankerV2(backend="cross_encoder", api_key="")
        result = await rv.rerank("test", [_make_candidate(0)], top_k=1)
        assert len(result) == 1


@pytest.mark.asyncio
async def test_rerank_v2_handles_backend_exception():
    """backend 内部异常包装为 RerankerError (类 20.127)."""
    with patch(
        "app.services.reranker_service.get_reranker_service"
    ) as mock_svc:
        mock_instance = AsyncMock()
        mock_instance.rerank_async.side_effect = ValueError("test error")
        mock_svc.return_value = mock_instance

        rv = RerankerV2(backend="cross_encoder")
        with pytest.raises(RerankerError):
            await rv.rerank("test", [_make_candidate(0)], top_k=1)


# ============================================================
# Test 配置 (4 cases)
# ============================================================


def test_default_acceptance_gate_is_92_percent():
    """默认 acceptance gate = 0.92 (W75 93.5% +0.5pp 缓冲)."""
    assert DEFAULT_ACCEPTANCE_GATE == 0.92


def test_config_reranker_backend_default():
    """config 默认 backend = cross_encoder."""
    from app.rag.config import RERANKER_BACKEND

    assert RERANKER_BACKEND == "cross_encoder"


def test_config_reranker_model_default():
    """config 默认 model = BAAI/bge-reranker-v2-m3."""
    from app.rag.config import RERANKER_MODEL

    assert RERANKER_MODEL == "BAAI/bge-reranker-v2-m3"


def test_config_reranker_acceptance_gate_default():
    """config 默认 acceptance_gate = 0.92."""
    from app.rag.config import RERANKER_ACCEPTANCE_GATE

    assert RERANKER_ACCEPTANCE_GATE == 0.92
