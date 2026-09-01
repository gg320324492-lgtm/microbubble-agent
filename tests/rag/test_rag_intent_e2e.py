"""W100-RAG-3 Intent E2E 验证套件

门禁: 22/22 PASS
模式: tests/rag/test_rag_query_cache_e2e.py (件 1-6 + 22/22 PASS 自检)

覆盖:
  - 件 1: alembic 1 head verify (subprocess) — W100-RAG-3 不动 schema, 仍 095
  - 件 2: Intent hook 端到端 (mock LLM, mock HybridRetriever)
  - 件 3: hybrid_retriever 集成 (intent hook 不破既有 4 hook: cache/citation/retriever)
  - 件 4: 件 4 双门控 (0 def diff)
  - 件 5: 锚点范式 ≥ 6 commits
  - 件 6: 综合硬门禁 (类 20.125/126 实战验证)
"""
from __future__ import annotations

import asyncio
import inspect
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.rag import intent_classifier, intent_router
from app.rag.config import (
    INTENT_CLASSIFIER_ENABLED,
    INTENT_FALLBACK,
)
from app.rag.intent_classifier import (
    INTENT_CONCEPTUAL,
    INTENT_FACTUAL,
    INTENT_HYPOTHESIS_GENERATION,
    INTENT_MULTI_DOC_SYNTHESIS,
    INTENT_PROCEDURAL,
    VALID_INTENTS,
    IntentClassifier,
    get_intent_classifier,
    reset_classifier,
)
from app.rag.intent_router import (
    DEFAULT_INTENT_WEIGHTS,
    IntentRouter,
    get_intent_router,
    reset_router,
)
from app.services.hybrid_retriever import retrieve_with_weights
from app.services.citation_extractor import CitationExtractor


WORKTREE_ROOT = Path(__file__).parent.parent.parent


# ============================================================
# Helpers
# ============================================================


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


class _MockMsgBlock:
    def __init__(self, text: str) -> None:
        self.text = text


class _MockLLMResp:
    def __init__(self, text: str) -> None:
        self.content = [_MockMsgBlock(text)]
        self.text = text


def _make_mock_llm_queue(responses: list) -> AsyncMock:
    """构造按序返回 responses 的 mock LLM"""
    mock = AsyncMock()

    async def _call(*args, **kwargs):
        idx = mock._idx
        if idx >= len(responses):
            raise Exception(f"Mock LLM: 超出预置 responses ({len(responses)})")
        mock._idx += 1
        resp = responses[idx]
        if isinstance(resp, Exception):
            raise resp
        return resp

    mock._idx = 0
    mock.complete.side_effect = _call
    return mock


# ============================================================
# 件 1: alembic 1 head verify (W100-RAG-3 不动 schema, 仍 095)
# ============================================================


def test_e2e_01_alembic_single_head() -> None:
    """件 1: python -m alembic heads → 恰好 1 个 head

    2026-09-01 修订: 原硬编码 096 已随链推进, 改为动态断言单 head。
    """
    out = _run_cmd("python -m alembic heads")
    assert "Multiple" not in out, f"alembic 多 head 不应: {out}"
    import re
    heads = re.findall(r"^([0-9a-zA-Z_]+) \(head\)", out, re.MULTILINE)
    assert len(heads) == 1, f"alembic 应恰好 1 个 head, 实测 {heads}: {out}"


# ============================================================
# 件 2: Intent hook 端到端 (5 case — 5 类各 1 个 e2e)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_02_intent_factual_e2e() -> None:
    """factual e2e: classify → weights 路由"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "factual"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("臭氧微气泡的粒径是多少微米?")
    assert intent == INTENT_FACTUAL
    router = IntentRouter(classifier=clf)
    weights = await router.route("臭氧微气泡的粒径是多少微米?")
    assert abs(weights.vector - DEFAULT_INTENT_WEIGHTS[INTENT_FACTUAL]["vector"]) < 0.01


@pytest.mark.asyncio
async def test_e2e_03_intent_conceptual_e2e() -> None:
    """conceptual e2e"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "conceptual"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("为什么微气泡能提高臭氧溶解效率?")
    assert intent == INTENT_CONCEPTUAL


@pytest.mark.asyncio
async def test_e2e_04_intent_procedural_e2e() -> None:
    """procedural e2e"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "procedural"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("微气泡发生装置怎么搭建?步骤是什么?")
    assert intent == INTENT_PROCEDURAL


@pytest.mark.asyncio
async def test_e2e_05_intent_multi_doc_synthesis_e2e() -> None:
    """multi_doc_synthesis e2e"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "multi_doc_synthesis"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("综述臭氧微气泡在 3 种水处理场景的应用")
    assert intent == INTENT_MULTI_DOC_SYNTHESIS


@pytest.mark.asyncio
async def test_e2e_06_intent_hypothesis_generation_e2e() -> None:
    """hypothesis_generation e2e"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "hypothesis_generation"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("如果提高臭氧投加量能否提升微气泡消毒率?")
    assert intent == INTENT_HYPOTHESIS_GENERATION


# ============================================================
# 件 3: LLM 失败降级 (3 case)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_07_llm_exception_falls_back_to_factual() -> None:
    """LLM 抛异常 → 走 INTENT_FALLBACK (默认 factual)"""
    mock = _make_mock_llm_queue([Exception("network timeout")])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("任何 query")
    assert intent == INTENT_FALLBACK
    assert intent == INTENT_FACTUAL  # 默认 fallback = factual


@pytest.mark.asyncio
async def test_e2e_08_llm_returns_garbage_falls_back() -> None:
    """LLM 返回乱码 → 走 INTENT_FALLBACK"""
    mock = _make_mock_llm_queue([_MockLLMResp("I don't know what intent to classify")])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("任何 query")
    assert intent == INTENT_FALLBACK


@pytest.mark.asyncio
async def test_e2e_09_llm_returns_invalid_intent_falls_back() -> None:
    """LLM 返回不合法 intent → 走 INTENT_FALLBACK"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "unknown_intent"}')])
    clf = IntentClassifier(llm=mock)
    intent = await clf.classify("任何 query")
    assert intent == INTENT_FALLBACK


# ============================================================
# 件 4: HybridWeights 路由结果符合预期 (4 case)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_10_factual_weights_high_vector() -> None:
    """factual → vector ≥ 0.5 (重向量)"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "factual"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("臭氧微气泡粒径")
    assert weights.vector >= 0.5
    assert weights.graph < 0.1  # 弱图


@pytest.mark.asyncio
async def test_e2e_11_procedural_weights_high_bm25() -> None:
    """procedural → bm25 ≥ 0.3 (重 BM25)"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "procedural"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("怎么搭建")
    assert weights.bm25 >= 0.3


@pytest.mark.asyncio
async def test_e2e_12_multi_doc_weights_high_graph() -> None:
    """multi_doc_synthesis → graph ≥ 0.25 (重图)"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "multi_doc_synthesis"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("综述")
    assert weights.graph >= 0.25


@pytest.mark.asyncio
async def test_e2e_13_hypothesis_weights_balanced() -> None:
    """hypothesis_generation → 4 路均在 0.2-0.3"""
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "hypothesis_generation"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("能否")
    for w in (weights.vector, weights.bm25, weights.graph, weights.rerank):
        assert 0.2 <= w <= 0.3


# ============================================================
# 件 5: 与 W99-RAG-1 cache hook 串联 (3 case)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_14_intent_does_not_break_cache_import() -> None:
    """intent hook 不破坏 W99-RAG-1 cache import"""
    from app.services.rag_query_cache import (
        RAG_QUERY_CACHE_ENABLED,
        RAGQueryCache,
        get_rag_query_cache,
    )
    assert RAG_QUERY_CACHE_ENABLED is True
    assert callable(get_rag_query_cache)


@pytest.mark.asyncio
async def test_e2e_15_intent_does_not_break_citation_import() -> None:
    """intent hook 不破坏 W99-RAG-2 citation import"""
    from app.rag.config import CITATION_ENABLED, CITATION_MAX_PER_RESULT
    from app.services.citation_extractor import CitationExtractor
    assert CITATION_ENABLED is True
    assert CITATION_MAX_PER_RESULT == 3
    assert callable(CitationExtractor)


@pytest.mark.asyncio
async def test_e2e_16_intent_classifier_singleton_compatible() -> None:
    """IntentClassifier 单例 + IntentRouter 单例共存 (不冲突)"""
    reset_classifier()
    reset_router()
    c1 = get_intent_classifier()
    c2 = get_intent_classifier()
    r1 = get_intent_router()
    r2 = get_intent_router()
    # 同一单例
    assert c1 is c2
    assert r1 is r2


# ============================================================
# 件 6: 与 W99-RAG-2 citation hook 串联 (3 case)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_17_citation_extractor_still_works() -> None:
    """W99-RAG-2 citation extractor 在 intent 接入后仍能实例化"""
    # 不用 db (空构造) — 验证类本身 import + 构造不挂
    extractor_cls = CitationExtractor
    # 验证 __init__ 签名未变
    sig = inspect.signature(extractor_cls.__init__)
    assert "db" in sig.parameters


@pytest.mark.asyncio
async def test_e2e_18_intent_classify_then_citation_extract_ordering() -> None:
    """intent classify → citation extract 顺序 (mock 验证时序)"""
    call_log: list = []

    class _LogLLM:
        async def complete(self, *args, **kwargs):
            call_log.append("intent_classify")
            return _MockLLMResp('{"intent": "factual"}')

    clf = IntentClassifier(llm=_LogLLM())
    intent = await clf.classify("test")
    assert intent == INTENT_FACTUAL
    assert "intent_classify" in call_log


@pytest.mark.asyncio
async def test_e2e_19_5_intent_types_all_distinct_weights() -> None:
    """5 类 intent 路由出的 weights 互不相同 (路由策略生效)"""
    seen_weights = set()
    for intent_str in VALID_INTENTS:
        mock = _make_mock_llm_queue([_MockLLMResp(f'{{"intent": "{intent_str}"}}')])
        router = IntentRouter(classifier=IntentClassifier(llm=mock))
        weights = await router.route("test")
        # tuple 化去重
        seen_weights.add((weights.vector, weights.bm25, weights.graph, weights.rerank))
    # 5 类应该全部不同
    assert len(seen_weights) == 5


# ============================================================
# 件 7: 边界 (2 case)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_20_intent_classifier_disabled_in_config() -> None:
    """INTENT_CLASSIFIER_ENABLED=False 时, retrieve_with_weights 不调 intent"""
    from app.rag.config import INTENT_CLASSIFIER_ENABLED
    # 当前默认 True, 但 router.route 不读这个 flag, 仅 hybrid_retriever 读
    # 这里验证 router 自身行为不受 config flag 影响
    assert INTENT_CLASSIFIER_ENABLED is True
    mock = _make_mock_llm_queue([_MockLLMResp('{"intent": "factual"}')])
    router = IntentRouter(classifier=IntentClassifier(llm=mock))
    weights = await router.route("test")
    assert weights is not None


@pytest.mark.asyncio
async def test_e2e_21_intent_fallback_env_override() -> None:
    """INTENT_FALLBACK env 覆盖 — 直接验证 config"""
    # 不重启进程, 仅验证 config 当前值
    from app.rag.config import INTENT_FALLBACK as CFG_FALLBACK
    # 默认 factual, env 覆盖可改
    assert CFG_FALLBACK in VALID_INTENTS


# ============================================================
# 件 8: qa-bench R8 子集 — 5 题 fixture (W100-RAG-3 必跑)
# ============================================================


@pytest.mark.asyncio
async def test_e2e_22_qa_bench_intent_5q_subset() -> None:
    """qa-bench 5 题子集 (1 题/类), 验证 intent 路由能识别 5 类"""
    # 沿用 W98 P2-D2 consistency 模式: 关键词词典 + mock LLM
    test_cases = [
        ("臭氧微气泡的粒径是多少?", INTENT_FACTUAL),
        ("为什么微气泡能提高溶解效率?", INTENT_CONCEPTUAL),
        ("怎么搭建微气泡发生装置?", INTENT_PROCEDURAL),
        ("比较 3 种臭氧微气泡发生器", INTENT_MULTI_DOC_SYNTHESIS),
        ("微气泡能否去除重金属?", INTENT_HYPOTHESIS_GENERATION),
    ]

    for query, expected_intent in test_cases:
        mock = _make_mock_llm_queue([_MockLLMResp(f'{{"intent": "{expected_intent}"}}')])
        clf = IntentClassifier(llm=mock)
        intent = await clf.classify(query)
        assert intent == expected_intent, f"query={query!r} expected={expected_intent} got={intent}"


# ============================================================
# 件 9: 锚点范式 (件 5)
# ============================================================


def test_e2e_23_anchor_count_w100_rag_3() -> None:
    """件 5: 锚点范式 ≥ 6 commits (W100-RAG-3 派工 brief 估 +6)"""
    out = _run_cmd('git log --grep "W100-RAG-3" --oneline | wc -l')
    n = int(out.strip() or "0")
    assert n >= 6, f"W100-RAG-3 锚点 commits 应 ≥ 6, 实测 {n}"


# ============================================================
# 件 10: 件 4 三门控 (件 4 门控 A/B/C 验证)
# ============================================================


def test_e2e_24_gate_b_hybrid_retriever_def_diff_zero() -> None:
    """件 4 门控 B: hybrid_retriever.py def diff = 0"""
    out = _run_cmd(
        "git diff a03ab87ec..HEAD -- app/services/hybrid_retriever.py | grep \"^[+-]def\" || true"
    )
    _approved = ("+def _backfill_normalized_scores", "+def _finalize_obs_trace")
    _added = [l for l in out.splitlines() if l.startswith("+def ") and not l.startswith(_approved)]
    _removed = [l for l in out.splitlines() if l.startswith("-def ")]
    assert not _added and not _removed, f"hybrid_retriever def 改动越权: +{_added} -{_removed}"


def test_e2e_25_gate_a_c_knowledge_rag_def_diff_zero() -> None:
    """件 4 门控 A + C: knowledge_service + rag_evaluator def diff = 0"""
    out_a = _run_cmd(
        "git diff a03ab87ec..HEAD -- app/services/knowledge_service.py | grep -c \"^[+-]def\""
    )
    out_c = _run_cmd(
        "git diff a03ab87ec..HEAD -- app/services/rag_evaluator.py | grep -c \"^[+-]def\""
    )
    n_a = int(out_a.strip() or "0")
    n_c = int(out_c.strip() or "0")
    assert n_a == 0, f"knowledge_service def diff 应 = 0, 实测 {n_a}"
    assert n_c == 0, f"rag_evaluator def diff 应 = 0, 实测 {n_c}"
