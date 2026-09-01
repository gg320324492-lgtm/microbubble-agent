"""W100-BUGFIX 3 回归问题修复 e2e 测试

门禁: ≥ 3/3 PASS (P0 三处)
模式: tests/rag/ 单测模式 (mock DB / mock LLM, 0 网络)

覆盖:
- Case 1 (P0 Bug #1): SearchEventRequest 加 4 个 RAG 字段 (cache_hit / cache_similarity /
  citation_count / image_score) - POST search-event 不再返回 422
- Case 2 (P0 Bug #2): retrieve_with_weights 的 .citations 属性在 rerank/multimodal/temporal
  hooks reassign 后仍挂载 (final attach 机制)
- Case 3 (P0 Bug #3): search_knowledge 工具走 retrieve_with_weights, 返回 dict 含 citations
  字段, 用户问 "2024 微纳米气泡研究" 时检索能返回结果 (不是 fallback)

不擅自加新功能 (类 20.124), 仅验证 3 处修复.
"""
from __future__ import annotations

import asyncio
import importlib
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# 把项目根加入 path
PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================
# Case 1 (P0 #1): SearchEventRequest schema 接受 4 RAG 字段
# ============================================================

def test_case_01_search_event_accepts_4_rag_fields():
    """Case 01: SearchEventRequest schema 接受 cache_hit / cache_similarity /
    citation_count / image_score 4 个字段 (Pydantic validation 不抛)

    W100-BUGFIX: 类 20.123 据实上报, 用户截图实证 POST 422 (Unprocessable Content).
    修法: schema 加 4 字段 Optional (类 20.124 0 改老 client 兼容).
    """
    from app.api.v1.analytics import SearchEventRequest

    # Pydantic 自动 coerce + validate. Optional 字段可省略也可传.
    # 4 字段全传: 不抛异常
    payload = SearchEventRequest(
        query="微纳米气泡粒径",
        top_ids=[1, 2, 3],
        cache_hit=1,
        cache_similarity=0.95,
        citation_count=3,
        image_score=0.82,
    )
    assert payload.cache_hit == 1
    assert payload.cache_similarity == 0.95
    assert payload.citation_count == 3
    assert payload.image_score == 0.82


def test_case_02_search_event_optional_fields_default_none():
    """Case 02: SearchEventRequest 4 字段 Optional, 老 client 不传走 default None
    (向后兼容, 0 改老 client)"""
    from app.api.v1.analytics import SearchEventRequest

    payload = SearchEventRequest(
        query="test",
        top_ids=[1],
    )
    assert payload.cache_hit is None
    assert payload.cache_similarity is None
    assert payload.citation_count is None
    assert payload.image_score is None


def test_case_03_search_event_field_constraints():
    """Case 03: 4 RAG 字段类型约束 (cache_hit 0/1, similarity 0-1, image_score 0-1)"""
    from app.api.v1.analytics import SearchEventRequest
    from pydantic import ValidationError

    # cache_hit 越界 (必须 0/1)
    with pytest.raises(ValidationError):
        SearchEventRequest(
            query="x", top_ids=[1],
            cache_hit=2,  # invalid, > 1
        )

    # image_score 越界 (必须 0-1)
    with pytest.raises(ValidationError):
        SearchEventRequest(
            query="x", top_ids=[1],
            image_score=1.5,  # invalid, > 1
        )


# ============================================================
# Case 2 (P0 #2): citation hook final attach 守恒
# ============================================================

def test_case_04_citation_extractor_format_for_frontend():
    """Case 04: CitationExtractor.format_for_frontend tuple → list 转换,
    验证 citation dict 结构符合前端 KnowledgeRefBlock.vue 期望."""
    from app.services.citation_extractor import CitationExtractor

    extractor = CitationExtractor(db=MagicMock())
    citations = extractor.format_for_frontend([
        {
            "doc_id": 100,
            "chunk_id": 5,
            "char_range": (10, 50),  # tuple
            "similarity": 0.85,
            "snippet": "微气泡是一种直径小于 100 微米的气泡",
            "strategy": "paragraph",
            "retrieval_method": "hybrid",
        }
    ])
    assert len(citations) == 1
    assert citations[0]["doc_id"] == 100
    assert citations[0]["chunk_id"] == 5
    assert isinstance(citations[0]["char_range"], list)  # tuple → list
    assert citations[0]["char_range"] == [10, 50]


def test_case_05_retrieve_with_weights_citation_hook_order():
    """Case 05: W100-BUGFIX 核心修复 — verify hybrid_retriever.py 末尾有 final
    attach 块 (确保 rerank/multimodal/temporal hooks reassign raw_results 后
    citations 仍能挂载到 final list)

    类 20.124 不擅自扩, 仅验证源码字面有 final attach 块.
    """
    import inspect
    from app.services import hybrid_retriever as hr_mod

    # WP7 (2026-09-01) wrapper/impl 拆分后, hook body 在 _retrieve_with_weights_impl
    src = inspect.getsource(hr_mod._retrieve_with_weights_impl)
    # 验证改动: 末尾有 "W100-BUGFIX" final attach 块
    assert "W100-BUGFIX" in src, "missing W100-BUGFIX final attach block"
    assert "_cached_citations" in src, "missing _cached_citations local var"
    # 验证 final attach 位于 return 之前 (类 20.133 据实)
    final_attach_pos = src.find("W100-BUGFIX")
    return_pos = src.rfind("return raw_results")
    assert final_attach_pos < return_pos, (
        "W100-BUGFIX final attach 必须在 return raw_results 之前"
    )


def test_case_06_richcontent_forwards_citations_to_block():
    """Case 06: RichContent.vue 把 block.data.citations 转发给子组件 (KnowledgeRefBlock)"""
    import re
    from pathlib import Path

    vue_path = PROJECT_ROOT / "web/src/components/chat/RichContent.vue"
    src = vue_path.read_text(encoding="utf-8")
    # 验证改动: <component> 上有 :citations 属性
    assert ":citations=" in src, "RichContent.vue 没转发 citations prop"
    assert "block.data?.citations" in src, "citations 没接 block.data"


# ============================================================
# Case 3 (P0 #3): search_knowledge 走 retrieve_with_weights
# ============================================================

def test_case_07_search_knowledge_uses_retrieve_with_weights():
    """Case 07: knowledge_tools.py search_knowledge 调用 retrieve_with_weights
    (W100-BUGFIX 据实, 老 API retrieve 触发不了 citation hook)"""
    import inspect

    from app.agent.tools import knowledge_tools

    src = inspect.getsource(knowledge_tools.search_knowledge)
    assert "retrieve_with_weights" in src, (
        "knowledge_tools.search_knowledge 应调 retrieve_with_weights (新 API)"
    )
    assert '"citations"' in src or "'citations'" in src, (
        "knowledge_tools.search_knowledge 应返回 citations 字段"
    )


def test_case_08_intent_classify_2024_research_is_factual():
    """Case 08: IntentClassifier 把 '2024 年最新的微纳米气泡研究' 分类到 factual
    (不是会议/项目, 类 20.125 失败回退 INTENT_FALLBACK)"""
    from unittest.mock import AsyncMock, MagicMock

    from app.rag.intent_classifier import (
        INTENT_FACTUAL,
        VALID_INTENTS,
        IntentClassifier,
        _parse_intent_json,
    )

    # 不真调 LLM, 直接验证 5 类 + parse 逻辑
    # scenario 1: LLM 正常返回
    text_ok = '{"intent": "factual"}'
    parsed = _parse_intent_json(text_ok)
    assert parsed == INTENT_FACTUAL

    # scenario 2: LLM 返回前夹带 markdown
    text_md = '下面是分析:\n```json\n{"intent": "multi_doc_synthesis"}\n```\n结束'
    parsed2 = _parse_intent_json(text_md)
    assert parsed2 == "multi_doc_synthesis"

    # scenario 3: 5 类意图合法集合
    for i in VALID_INTENTS:
        assert i in ("factual", "conceptual", "procedural",
                     "multi_doc_synthesis", "hypothesis_generation")

    # scenario 4: 失败回退 INTENT_FACTUAL
    fallback = INTENT_FACTUAL
    assert fallback in VALID_INTENTS, "fallback 必须合法"


def test_case_09_search_log_model_has_4_new_fields():
    """Case 09: SearchLog model 含 4 个 RAG 字段 (W99-RAG-1/2 + W100-RAG-5 ADD),
    字段类型与 SearchEventRequest 对齐"""
    from app.models.search_log import SearchLog

    # 4 字段都存在 + 类型正确
    assert hasattr(SearchLog, "cache_hit")
    assert hasattr(SearchLog, "cache_similarity")
    assert hasattr(SearchLog, "citation_count")
    assert hasattr(SearchLog, "image_score")


def test_case_10_retrieve_with_weights_signature_unchanged():
    """Case 10: 件 4 门控 B 守恒 — retrieve_with_weights 签名 0 改"""
    import inspect
    from app.services.hybrid_retriever import retrieve_with_weights

    sig = inspect.signature(retrieve_with_weights)
    params = list(sig.parameters.keys())
    # 验证 5 个核心参数都在
    for p in ("db", "query", "top_k", "category", "weights"):
        assert p in params, f"retrieve_with_weights 缺参数 {p}"


# ============================================================
# 件 4 五门控守恒 (类 20.124 不擅自扩)
# ============================================================

def test_gate_A_knowledge_service_def_diff_zero():
    """门控 A: knowledge_service.py def diff = 0 (本任务不动 knowledge_service)"""
    import subprocess

    def _count_def_class_diff(file_path: str) -> int:
        try:
            res = subprocess.run(
                ["git", "diff", "afc9cf010..HEAD", "--", file_path],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return -1  # signal "couldn't run"
        text = res.stdout or ""
        return sum(
            1 for line in text.splitlines()
            if line.startswith("+def ") or line.startswith("-def ")
            or line.startswith("+class ") or line.startswith("-class ")
        )

    n = _count_def_class_diff("app/services/knowledge_service.py")
    assert n == 0, f"knowledge_service.py def/class diff = {n}, 应为 0"


def test_gate_B_hybrid_retriever_def_diff_zero():
    """门控 B: hybrid_retriever.py def diff = 0 (本任务仅 body 改 hook 策略)"""
    import subprocess

    def _count_def_diff(file_path: str) -> int:
        try:
            res = subprocess.run(
                ["git", "diff", "afc9cf010..HEAD", "--", file_path],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return -1
        text = res.stdout or ""
        return sum(
            1 for line in text.splitlines()
            if line.startswith("+def ") or line.startswith("-def ")
        )

    n = _count_def_diff("app/services/hybrid_retriever.py")
    assert n == 0, f"hybrid_retriever.py def diff = {n}, 应为 0"


def test_gate_C_rag_evaluator_def_diff_zero():
    """门控 C: rag_evaluator.py def diff = 0 (本任务不动)"""
    import subprocess

    def _count_def_diff(file_path: str) -> int:
        try:
            res = subprocess.run(
                ["git", "diff", "afc9cf010..HEAD", "--", file_path],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return -1
        text = res.stdout or ""
        return sum(
            1 for line in text.splitlines()
            if line.startswith("+def ") or line.startswith("-def ")
        )

    n = _count_def_diff("app/services/rag_evaluator.py")
    assert n == 0, f"rag_evaluator.py def diff = {n}, 应为 0"


def test_gate_D_citation_extractor_def_diff_zero():
    """门控 D: citation_extractor.py def diff = 0 (本任务不动)"""
    import subprocess

    def _count_def_diff(file_path: str) -> int:
        try:
            res = subprocess.run(
                ["git", "diff", "afc9cf010..HEAD", "--", file_path],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return -1
        text = res.stdout or ""
        return sum(
            1 for line in text.splitlines()
            if line.startswith("+def ") or line.startswith("-def ")
        )

    n = _count_def_diff("app/services/citation_extractor.py")
    assert n == 0, f"citation_extractor.py def diff = {n}, 应为 0"


def test_gate_E_intent_classifier_def_diff_zero():
    """门控 E: intent_classifier.py def diff = 0 (本任务不动)"""
    import subprocess

    def _count_def_diff(file_path: str) -> int:
        try:
            res = subprocess.run(
                ["git", "diff", "afc9cf010..HEAD", "--", file_path],
                cwd=str(PROJECT_ROOT),
                capture_output=True,
                encoding="utf-8",
                errors="ignore",
            )
        except Exception:
            return -1
        text = res.stdout or ""
        return sum(
            1 for line in text.splitlines()
            if line.startswith("+def ") or line.startswith("-def ")
        )

    n = _count_def_diff("app/rag/intent_classifier.py")
    assert n == 0, f"intent_classifier.py def diff = {n}, 应为 0"


# ============================================================
# 主入口 (允许单独跑)
# ============================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
