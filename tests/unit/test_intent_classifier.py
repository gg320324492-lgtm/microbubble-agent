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
    """7 种闭集分类（2026-07-15 #P2: 新增 team_overview）"""

    def test_seven_categories_defined(self):
        cats = list(IntentCategory)
        # 2026-07-15 #P2: 6 类 → 7 类（新增 TEAM_OVERVIEW 课题组概览）
        assert len(cats) == 7
        assert IntentCategory.RECOMMEND_PERSON in cats
        assert IntentCategory.SEARCH_INFO in cats
        assert IntentCategory.EXPLAIN_CONCEPT in cats
        assert IntentCategory.EXECUTE_ACTION in cats
        assert IntentCategory.DATA_QUERY in cats
        assert IntentCategory.CASUAL_CHAT in cats
        assert IntentCategory.TEAM_OVERVIEW in cats  # 2026-07-15 #P2 新增


class TestMapCategory:
    """中文 → enum 映射"""

    def test_chinese_to_enum(self):
        assert _map_category("推荐人") == "recommend_person"
        assert _map_category("找资料") == "search_info"
        assert _map_category("解释概念") == "explain_concept"
        assert _map_category("执行操作") == "execute_action"
        assert _map_category("数据查询") == "data_query"
        assert _map_category("闲聊") == "casual_chat"
        # 2026-07-15 #P2: 团队概览
        assert _map_category("团队概览") == "team_overview"

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

    # === 2026-06-15 「X 呢？」简写延续分类（杜同贺痛点修复）===

    @pytest.mark.asyncio
    async def test_classify_x_ne_member_followup(self):
        """「X 呢？」简写延续 → search_info（找人/查资料）
        背景：用户前一轮问"谁在做饮用水安全研究"，第二轮问"杜同贺呢？"
        intent 分类器应正确返回 search_info + suggested_tools=[get_member_profile]
        防止 LLM 误读为「杜同贺在做什么（任务）」→ query_tasks 错位
        """
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "category": "找资料",
            "confidence": 0.88,
            "keywords": ["杜同贺"],
            "suggested_tools": ["get_member_profile"],
            "reasoning": "「X 呢？」是延续研究主题的简写，默认理解为研究方向/资料查询",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        result = await classify_intent("杜同贺呢？", ctx)
        assert result.category == IntentCategory.SEARCH_INFO
        assert "get_member_profile" in result.suggested_tools
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_classify_x_zenmeyang_member_profile(self):
        """「X 怎么样」/「X 做什么」/「X 是谁」简写 → search_info
        覆盖 Member Query Rules 中列出的所有简写延续模式
        """
        for question in ["李松泽怎么样", "王天志做什么", "周之超是谁", "贾琦介绍下"]:
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.text = json.dumps({
                "category": "找资料",
                "confidence": 0.85,
                "keywords": [question[:2]],
                "suggested_tools": ["get_member_profile"],
                "reasoning": "简写延续，问成员资料",
            }, ensure_ascii=False)
            mock_response.content = [mock_block]
            mock_llm = MagicMock()
            mock_llm.complete = AsyncMock(return_value=mock_response)

            ctx = MagicMock()
            ctx.redis = None
            ctx.llm = mock_llm

            result = await classify_intent(question, ctx)
            assert result.category == IntentCategory.SEARCH_INFO, \
                f"question={question!r} should be SEARCH_INFO, got {result.category}"

    @pytest.mark.asyncio
    async def test_classify_x_tasks_explicit(self):
        """显式问任务「X 的任务」/「X 的工作清单」→ data_query
        确保新增的「X 呢？」→ search_info 规则**不**误伤显式任务查询
        """
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "category": "数据查询",
            "confidence": 0.9,
            "keywords": ["杜同贺", "任务"],
            "suggested_tools": ["query_tasks"],
            "reasoning": "显式问任务",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        for question in ["杜同贺的任务", "杜同贺的工作清单"]:
            result = await classify_intent(question, ctx)
            assert result.category == IntentCategory.DATA_QUERY, \
                f"question={question!r} should be DATA_QUERY, got {result.category}"

    @pytest.mark.asyncio
    async def test_classify_all_member_tasks_team(self):
        """「所有成员任务」/「团队任务」→ data_query + query_all_member_tasks
        防止 Member Query Rules 新增的「绝不能调 query_all_member_tasks 查单人」
        被反过来误读为"也不能调 query_all_member_tasks" — 显式团队查询仍允许
        """
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "category": "数据查询",
            "confidence": 0.95,
            "keywords": ["团队", "任务"],
            "suggested_tools": ["query_all_member_tasks"],
            "reasoning": "显式问团队任务总览",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        ctx = MagicMock()
        ctx.redis = None
        ctx.llm = mock_llm

        for question in ["所有成员任务", "团队任务进度", "大家都在做什么任务"]:
            result = await classify_intent(question, ctx)
            assert result.category == IntentCategory.DATA_QUERY, \
                f"question={question!r} should be DATA_QUERY, got {result.category}"
            assert "query_all_member_tasks" in result.suggested_tools, \
                f"question={question!r} should suggest query_all_member_tasks"


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
