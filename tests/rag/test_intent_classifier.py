"""W100-RAG-3 IntentClassifier 单测 + IntentRouter 单测

门禁: 25/25 PASS
模式: tests/rag/test_hybrid_weight_config.py (件 1-2 + 25/25 PASS 自检)

覆盖:
  - 5 case 基础 (5 类各 1 个 classify 调用, mock LLM)
  - 3 case LLM 失败回退 (mock LLM 抛异常 → INTENT_FALLBACK)
  - 3 case parse_llm_json 异常处理
  - 4 case 边界 (空 query / 超长 query / Unicode / 中文 mixed)
  - 5 case IntentRouter 路由策略 (5 类各 1 个)
  - 3 case yaml config 加载 (这里改成 module-level dict 验证)
  - 2 case keyword-only intent 参数透传 (W100-RAG-3 接入点)

类 20.115 假设禁令: 所有 mock 都基于实测 LLMClient.complete 返回对象 (有 .text 或 .content 字段)
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.rag.intent_classifier import (
    INTENT_CLASSIFY_PROMPT,
    INTENT_CONCEPTUAL,
    INTENT_FACTUAL,
    INTENT_HYPOTHESIS_GENERATION,
    INTENT_MULTI_DOC_SYNTHESIS,
    INTENT_PROCEDURAL,
    VALID_INTENTS,
    IntentClassifier,
    _parse_intent_json,
    get_intent_classifier,
    reset_classifier,
)
from app.rag.intent_router import (
    DEFAULT_INTENT_WEIGHTS,
    IntentRouter,
    get_intent_router,
    reset_router,
)


WORKTREE_ROOT = Path(__file__).parent.parent.parent


# ============================================================
# Mock helpers
# ============================================================


class _MockMessageBlock:
    """模拟 Anthropic Message content block"""

    def __init__(self, text: str) -> None:
        self.text = text


class _MockResponse:
    """模拟 LLMClient.complete 返回值 (有 .content 列表)"""

    def __init__(self, text: str) -> None:
        self.content = [_MockMessageBlock(text)]
        # 也支持 text 字段 (类 20.115 兼容)
        self.text = text


def _make_mock_llm(responses: list) -> AsyncMock:
    """构造 mock LLM, 按序返回 responses 列表"""
    mock = AsyncMock()
    mock._responses = list(responses)
    mock._idx = 0

    async def _call(*args, **kwargs):
        idx = mock._idx
        if idx >= len(mock._responses):
            raise Exception(f"Mock LLM: 超出预置 responses 数 ({len(mock._responses)})")
        mock._idx += 1
        resp = mock._responses[idx]
        if isinstance(resp, Exception):
            raise resp
        return resp

    mock.complete.side_effect = _call
    return mock


# ============================================================
# 件 1: 基础 — 5 类各 1 个 classify 调用 (mock LLM)
# ============================================================


@pytest.mark.asyncio
async def test_classify_factual_mock() -> None:
    """factual 类 — mock LLM 返回 '{"intent": "factual"}'"""
    mock = _make_mock_llm([_MockResponse('{"intent": "factual"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("臭氧微气泡粒径是多少?")
    assert result == INTENT_FACTUAL


@pytest.mark.asyncio
async def test_classify_conceptual_mock() -> None:
    """conceptual 类"""
    mock = _make_mock_llm([_MockResponse('{"intent": "conceptual"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("为什么微气泡能提高溶解效率?")
    assert result == INTENT_CONCEPTUAL


@pytest.mark.asyncio
async def test_classify_procedural_mock() -> None:
    """procedural 类"""
    mock = _make_mock_llm([_MockResponse('{"intent": "procedural"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("微气泡发生装置怎么搭建?")
    assert result == INTENT_PROCEDURAL


@pytest.mark.asyncio
async def test_classify_multi_doc_synthesis_mock() -> None:
    """multi_doc_synthesis 类"""
    mock = _make_mock_llm([_MockResponse('{"intent": "multi_doc_synthesis"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("比较 3 种臭氧微气泡发生器的优缺点")
    assert result == INTENT_MULTI_DOC_SYNTHESIS


@pytest.mark.asyncio
async def test_classify_hypothesis_generation_mock() -> None:
    """hypothesis_generation 类"""
    mock = _make_mock_llm([_MockResponse('{"intent": "hypothesis_generation"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("微气泡能否用于去除重金属?")
    assert result == INTENT_HYPOTHESIS_GENERATION


# ============================================================
# 件 2: LLM 失败回退 (3 case)
# ============================================================


@pytest.mark.asyncio
async def test_classify_llm_exception_fallback_factual() -> None:
    """LLM 抛异常 → 走 fallback (默认 factual)"""
    mock = _make_mock_llm([Exception("network error")])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("任何问题")
    assert result == INTENT_FACTUAL


@pytest.mark.asyncio
async def test_classify_llm_timeout_fallback() -> None:
    """LLM 超时 → 走 fallback"""
    mock = _make_mock_llm([asyncio.TimeoutError()])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("任何问题")
    assert result == INTENT_FACTUAL


@pytest.mark.asyncio
async def test_classify_custom_fallback() -> None:
    """自定义 fallback (e.g. operational override)"""
    mock = _make_mock_llm([Exception("boom")])
    clf = IntentClassifier(llm=mock, fallback=INTENT_CONCEPTUAL)
    result = await clf.classify("任何问题")
    assert result == INTENT_CONCEPTUAL


# ============================================================
# 件 3: parse_llm_json 异常处理 (3 case)
# ============================================================


def test_parse_intent_clean_json() -> None:
    """干净 JSON"""
    assert _parse_intent_json('{"intent": "factual"}') == INTENT_FACTUAL


def test_parse_intent_markdown_wrapped() -> None:
    """markdown 代码块包裹"""
    text = "```json\n{\"intent\": \"conceptual\"}\n```"
    assert _parse_intent_json(text) == INTENT_CONCEPTUAL


def test_parse_intent_with_surrounding_text() -> None:
    """前后夹带说明文字 (regex 兜底)"""
    text = '根据分析: {"intent": "procedural"} 综上所述如上。'
    assert _parse_intent_json(text) == INTENT_PROCEDURAL


# ============================================================
# 件 4: 边界 (4 case)
# ============================================================


@pytest.mark.asyncio
async def test_classify_empty_query_no_llm_call() -> None:
    """空 query: 不调 LLM, 直接返 fallback"""
    mock = _make_mock_llm([])  # 0 responses, 不应被调
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("")
    assert result == INTENT_FACTUAL
    assert mock._idx == 0  # 确认 LLM 未被调


@pytest.mark.asyncio
async def test_classify_whitespace_query() -> None:
    """纯空白 query: 视为空, 走 fallback"""
    mock = _make_mock_llm([])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("   \n\t  ")
    assert result == INTENT_FACTUAL


@pytest.mark.asyncio
async def test_classify_unicode_query() -> None:
    """Unicode (emoji) query: 仍能调 LLM"""
    mock = _make_mock_llm([_MockResponse('{"intent": "hypothesis_generation"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify("微气泡🌊 在水处理中🧪 的作用❓")
    assert result == INTENT_HYPOTHESIS_GENERATION


@pytest.mark.asyncio
async def test_classify_very_long_query() -> None:
    """超长 query: 不截断, 仍能调 LLM"""
    long_q = "微气泡" * 2000
    mock = _make_mock_llm([_MockResponse('{"intent": "multi_doc_synthesis"}')])
    clf = IntentClassifier(llm=mock)
    result = await clf.classify(long_q)
    assert result == INTENT_MULTI_DOC_SYNTHESIS


# ============================================================
# 件 5: IntentRouter 路由策略 (5 case)
# ============================================================


@pytest.mark.asyncio
async def test_router_factual() -> None:
    """factual → 重 vector"""
    mock = _make_mock_llm([_MockResponse('{"intent": "factual"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("臭氧微气泡粒径")
    # factual: vector=0.6, bm25=0.2, graph=0.0, rerank=0.2
    assert abs(weights.vector - 0.6) < 0.01
    assert abs(weights.bm25 - 0.2) < 0.01
    assert abs(weights.graph - 0.0) < 0.01
    assert abs(weights.rerank - 0.2) < 0.01


@pytest.mark.asyncio
async def test_router_conceptual() -> None:
    """conceptual → vector+BM25+graph 均衡"""
    mock = _make_mock_llm([_MockResponse('{"intent": "conceptual"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("为什么")
    assert abs(weights.vector - 0.4) < 0.01
    assert abs(weights.bm25 - 0.3) < 0.01


@pytest.mark.asyncio
async def test_router_procedural() -> None:
    """procedural → 重 BM25"""
    mock = _make_mock_llm([_MockResponse('{"intent": "procedural"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("怎么搭建")
    assert abs(weights.bm25 - 0.4) < 0.01


@pytest.mark.asyncio
async def test_router_multi_doc_synthesis() -> None:
    """multi_doc_synthesis → 重 graph"""
    mock = _make_mock_llm([_MockResponse('{"intent": "multi_doc_synthesis"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("比较")
    assert abs(weights.graph - 0.3) < 0.01


@pytest.mark.asyncio
async def test_router_hypothesis_generation() -> None:
    """hypothesis_generation → 4 路均衡"""
    mock = _make_mock_llm([_MockResponse('{"intent": "hypothesis_generation"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("能否")
    assert abs(weights.vector - 0.25) < 0.01
    assert abs(weights.bm25 - 0.25) < 0.01
    assert abs(weights.graph - 0.25) < 0.01
    assert abs(weights.rerank - 0.25) < 0.01


# ============================================================
# 件 6: yaml/config 加载 (3 case) — module-level dict 验证
# ============================================================


def test_default_intent_weights_5_keys() -> None:
    """DEFAULT_INTENT_WEIGHTS 含 5 类"""
    assert len(DEFAULT_INTENT_WEIGHTS) == 5
    for intent in VALID_INTENTS:
        assert intent in DEFAULT_INTENT_WEIGHTS


def test_default_intent_weights_sum() -> None:
    """每类 weights 4 路和 ≈ 1.0 (允许 ±0.05 误差)"""
    for intent, weights in DEFAULT_INTENT_WEIGHTS.items():
        total = weights["vector"] + weights["bm25"] + weights["graph"] + weights["rerank"]
        assert abs(total - 1.0) < 0.05, f"{intent} sum={total} 应 ≈ 1.0"


def test_intent_weights_overridable() -> None:
    """类 20.126 铁律: weights_map 可被覆盖"""
    custom_weights = {
        INTENT_FACTUAL: {"vector": 0.99, "bm25": 0.01, "graph": 0.0, "rerank": 0.0},
    }
    mock = _make_mock_llm([_MockResponse('{"intent": "factual"}')])
    router = IntentRouter(
        classifier=IntentClassifier(llm=mock),
        weights_map=custom_weights,
    )
    weights = asyncio.run(router.route("test"))
    assert abs(weights.vector - 0.99) < 0.01


# ============================================================
# 件 7: keyword-only intent 参数透传 (2 case)
# ============================================================


def test_retrieve_with_weights_signature_intent_compatible() -> None:
    """retrieve_with_weights 签名仍兼容 (件 4 门控 B 守恒)

    W100-RAG-3 任务: 不引入新参数, intent 通过 weights=None 触发自动推断
    """
    from app.services.hybrid_retriever import retrieve_with_weights
    import inspect
    sig = inspect.signature(retrieve_with_weights)
    # 既有参数全保留
    assert "db" in sig.parameters
    assert "query" in sig.parameters
    assert "weights" in sig.parameters
    # weights 仍是 Optional (允许 None 触发 intent 推断)
    assert sig.parameters["weights"].default is None


def test_intent_hook_wiring_smoke() -> None:
    """intents 模块存在 + 5 类常量可导入 (件 4 门控 B 验证: 不破坏 import)"""
    from app.rag import intent_classifier, intent_router  # noqa: F401
    # 5 类常量全在 VALID_INTENTS
    assert len(VALID_INTENTS) == 5
    # 模块级工厂存在
    assert callable(get_intent_classifier)
    assert callable(get_intent_router)
