"""测试 intent_classifier.py（方案 C Stage 1）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_intent_classifier.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.intent_classifier import (
    IntentCategory,
    IntentResult,
    _cache_key,
    _map_category,
    classify_intent,
    intent_to_sse_event,
)


class TestIntentCategory:
    """6 种闭集分类"""

    def test_six_categories_defined(self):
        cats = list(IntentCategory)
        assert len(cats) == 6
        assert IntentCategory.RECOMMEND_PERSON in cats
        assert IntentCategory.SEARCH_INFO in cats
        assert IntentCategory.EXPLAIN_CONCEPT in cats
        assert IntentCategory.EXECUTE_ACTION in cats
        assert IntentCategory.DATA_QUERY in cats
        assert IntentCategory.CASUAL_CHAT in cats


class TestMapCategory:
    """中文 → enum 映射"""

    def test_chinese_to_enum(self):
        assert _map_category("推荐人") == "recommend_person"
        assert _map_category("找资料") == "search_info"
        assert _map_category("解释概念") == "explain_concept"
        assert _map_category("执行操作") == "execute_action"
        assert _map_category("数据查询") == "data_query"
        assert _map_category("闲聊") == "casual_chat"

    def test_english_passthrough(self):
        assert _map_category("recommend_person") == "recommend_person"
        assert _map_category("search_info") == "search_info"

    def test_unknown_falls_back_to_search(self):
        assert _map_category("未知类别") == "search_info"
        assert _map_category("") == "search_info"


class TestCacheKey:
    """Redis 缓存 key 稳定性"""

    def test_same_question_same_key(self):
        k1 = _cache_key("请教谁研究饮用水")
        k2 = _cache_key("请教谁研究饮用水")
        assert k1 == k2

    def test_different_question_different_key(self):
        k1 = _cache_key("请教谁研究饮用水")
        k2 = _cache_key("什么是 zeta 电位")
        assert k1 != k2

    def test_key_format(self):
        k = _cache_key("test")
        assert k.startswith("intent:")
        assert len(k) == len("intent:") + 32  # md5 hex


class TestClassifyIntentMocked:
    """Mock LLM 测试 classify_intent"""

    @pytest.mark.asyncio
    async def test_classify_recommend_person(self):
        """LLM 返回 recommend_person → 同名 IntentResult"""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "category": "推荐人",
            "confidence": 0.92,
            "keywords": ["饮用水", "学习"],
            "suggested_tools": ["query_members"],
            "reasoning": "用户问请教谁，是推荐人意图",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        result = await classify_intent("我想学习饮用水相关内容，可以请教谁？", ctx)
        assert result.category == IntentCategory.RECOMMEND_PERSON
        assert result.confidence == 0.92
        assert "饮用水" in result.keywords

    @pytest.mark.asyncio
    async def test_classify_search_info(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "category": "找资料",
            "confidence": 0.85,
            "keywords": ["zeta电位"],
            "suggested_tools": ["search_knowledge"],
            "reasoning": "问概念是找资料",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        result = await classify_intent("zeta 电位怎么测？", ctx)
        assert result.category == IntentCategory.SEARCH_INFO
        assert result.confidence == 0.85

    @pytest.mark.asyncio
    async def test_classify_fallback_on_llm_error(self):
        """LLM 失败时降级返回 SEARCH_INFO + confidence=0"""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM 503"))

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        result = await classify_intent("任意问题", ctx)
        assert result.category == IntentCategory.SEARCH_INFO
        assert result.confidence == 0.0
        assert "failed" in result.reasoning.lower() or "失败" in result.reasoning

    @pytest.mark.asyncio
    async def test_classify_handles_markdown_codeblock(self):
        """LLM 返回 ```json ... ``` 包裹时能正确解析"""
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = "```json\n" + json.dumps({
            "category": "解释概念",
            "confidence": 0.9,
            "keywords": ["气泡"],
            "suggested_tools": ["search_knowledge"],
            "reasoning": "问原理",
        }, ensure_ascii=False) + "\n```"
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        result = await classify_intent("什么是 zeta 电位？", ctx)
        assert result.category == IntentCategory.EXPLAIN_CONCEPT
        assert result.confidence == 0.9


class TestIntentToSseEvent:
    """IntentResult → StreamEvent"""

    def test_sse_event_has_correct_type(self):
        result = IntentResult(
            category=IntentCategory.RECOMMEND_PERSON,
            confidence=0.92,
            keywords=["饮用水"],
            suggested_tools=["query_members"],
            reasoning="推荐人",
        )
        evt = intent_to_sse_event(result)
        assert evt.type == "intent_detected"
        assert evt.intent["category"] == "recommend_person"
        assert evt.intent["confidence"] == 0.92
        assert "推荐人" in evt.label

    def test_sse_event_serializes_to_sse(self):
        result = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            confidence=0.5,
        )
        evt = intent_to_sse_event(result)
        sse = evt.to_sse()
        assert "intent_detected" in sse
        assert "search_info" in sse
