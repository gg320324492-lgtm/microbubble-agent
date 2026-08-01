"""测试 intent_classifier.py — CHAT-P0-C (2026-07-31)

覆盖：
- C1 降级修复: 分类失败/低置信 → 默认 CASUAL_CHAT, 检索特征 query 仍走 SEARCH_INFO
- C2 续讲意图 follow_up: 正则前置规则 + LLM 第 8 类兜底
- 既有 7 类回归保护 (recommend_person / search_info / explain_concept /
  execute_action / data_query / casual_chat / team_overview)

跑法：SKIP_DB_SETUP=1 pytest tests/test_intent_classifier.py -q
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.intent_classifier import (
    IntentCategory,
    IntentResult,
    _category_zh,
    _degraded_result,
    _looks_like_retrieval,
    _map_category,
    _match_follow_up,
    classify_intent,
    intent_to_sse_event,
)


def _mock_llm(category_zh: str, confidence: float = 0.9, tools=None):
    """构造返回指定类别的 mock LLM"""
    mock_response = MagicMock()
    mock_block = MagicMock()
    mock_block.text = json.dumps({
        "category": category_zh,
        "confidence": confidence,
        "keywords": ["测试"],
        "suggested_tools": tools or [],
        "reasoning": "mock",
    }, ensure_ascii=False)
    mock_response.content = [mock_block]
    mock_llm = MagicMock()
    mock_llm.complete = AsyncMock(return_value=mock_response)
    return mock_llm


def _ctx(mock_llm):
    ctx = MagicMock()
    ctx.redis = None
    ctx.llm = mock_llm
    return ctx


# ============================================================================
# C2 follow_up 续讲意图 — 正则前置规则
# ============================================================================


class TestFollowUpPattern:
    """正则前置规则：命中 → follow_up, 零 LLM 调用"""

    @pytest.mark.parametrize("q", [
        "再多介绍一些", "再介绍下", "再讲讲", "再详细说下",
        "继续", "继续讲", "继续说", "接着说",
        "展开讲讲", "展开说一下",
        "详细说说", "详细点", "详细展开",
        "具体点", "说详细点",
        "多介绍下", "多说点", "再多讲些",
        "然后呢", "那然后", "还有呢",
    ])
    def test_follow_up_phrases_match(self, q):
        assert _match_follow_up(q), f"{q!r} 应命中 follow_up 规则"

    @pytest.mark.parametrize("q", [
        "为什么", "为啥", "那为什么",
    ])
    def test_bare_why_matches(self, q):
        """「为什么」单独出现 → 续讲（追问上一句结论）"""
        assert _match_follow_up(q), f"{q!r} 应命中 follow_up 规则"

    @pytest.mark.parametrize("q", [
        "什么是微纳米气泡", "什么是 zeta 电位",
        "微气泡怎么生成", "臭氧消毒的原理是什么",
        "如何检测羟基自由基", "为什么微气泡稳定",
        "你好", "谢谢", "再见",
        "帮我创建任务", "列出所有任务",
        "微气泡传质系数多少", "哪些成员研究水处理",
    ])
    def test_non_follow_up_not_matched(self, q):
        """普通疑问/闲聊/操作类 query 不应被 follow_up 规则拦截"""
        assert not _match_follow_up(q), f"{q!r} 不应命中 follow_up 规则"

    @pytest.mark.asyncio
    async def test_classify_follow_up_no_llm_call(self):
        """「再多介绍一些」→ follow_up, 且完全不调 LLM"""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock()  # 不应被调用

        result = await classify_intent("再多介绍一些", _ctx(mock_llm))
        assert result.category == IntentCategory.FOLLOW_UP
        assert result.confidence == 0.95
        assert result.suggested_tools == []  # 与 casual_chat 同, 严禁填工具
        mock_llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_classify_bare_why_follow_up(self):
        result = await classify_intent("为什么", _ctx(_mock_llm("找资料")))
        assert result.category == IntentCategory.FOLLOW_UP

    @pytest.mark.asyncio
    async def test_classify_follow_up_writes_cache(self):
        """follow_up 规则命中同样写 5min 缓存（命中不调 LLM）"""
        mock_redis = MagicMock()
        mock_redis.setex = AsyncMock()
        ctx = MagicMock()
        ctx.redis = mock_redis
        ctx.llm = MagicMock()
        ctx.llm.complete = AsyncMock()

        result = await classify_intent("展开讲讲", ctx)
        assert result.category == IntentCategory.FOLLOW_UP
        mock_redis.setex.assert_called_once()
        ctx.llm.complete.assert_not_called()

    @pytest.mark.asyncio
    async def test_normal_question_still_calls_llm(self):
        """「什么是微纳米气泡」不被正则拦截, 正常走 LLM 分类"""
        result = await classify_intent("什么是微纳米气泡", _ctx(_mock_llm("解释概念")))
        assert result.category == IntentCategory.EXPLAIN_CONCEPT


# ============================================================================
# C1 降级修复 — 失败/低置信 → CASUAL_CHAT (检索特征例外)
# ============================================================================


class TestDegradedResult:
    """_degraded_result 规则表"""

    @pytest.mark.parametrize("q", [
        "你好", "谢谢", "哈哈", "在吗", "嗯", "天气不错",
        "随便聊聊", "帮我想想", "再说一遍",
    ])
    def test_default_casual_chat(self, q):
        result = _degraded_result(q, "intent classification failed: test")
        assert result.category == IntentCategory.CASUAL_CHAT
        assert result.confidence == 0.0
        assert result.suggested_tools == []

    @pytest.mark.parametrize("q", [
        "什么是微纳米气泡", "微气泡怎么生成",
        "臭氧消毒的原理是什么", "如何检测羟基自由基",
        "为什么微气泡稳定", "传质系数怎么算",
        "纳米气泡在膜处理中的参数是多少",
    ])
    def test_retrieval_feature_keeps_search_info(self, q):
        """疑问词 + 领域词 → 低置信也走 SEARCH_INFO"""
        result = _degraded_result(q, "intent classification failed: test")
        assert result.category == IntentCategory.SEARCH_INFO, f"{q!r} 应走 SEARCH_INFO"

    @pytest.mark.asyncio
    async def test_llm_error_fallback_casual_chat(self):
        """验收: LLM 失败时「你好」→ casual_chat 零检索"""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM 503"))

        result = await classify_intent("你好", _ctx(mock_llm))
        assert result.category == IntentCategory.CASUAL_CHAT
        assert result.confidence == 0.0
        assert result.suggested_tools == []
        assert "casual_chat" in result.reasoning

    @pytest.mark.asyncio
    async def test_llm_error_retrieval_query_keeps_search_info(self):
        """验收: LLM 失败时「什么是微纳米气泡」→ 即使低置信也 SEARCH_INFO"""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM 503"))

        result = await classify_intent("什么是微纳米气泡", _ctx(mock_llm))
        assert result.category == IntentCategory.SEARCH_INFO
        assert result.confidence == 0.0
        assert "search_info" in result.reasoning

    @pytest.mark.asyncio
    async def test_unknown_category_maps_to_search_info(self):
        """LLM 返回未知类别 → _map_category 兜底 SEARCH_INFO (既有行为保留)"""
        result = await classify_intent("随机内容", _ctx(_mock_llm("不存在类别")))
        assert result.category == IntentCategory.SEARCH_INFO


# ============================================================================
# 既有 7 类回归保护
# ============================================================================


class TestCategoriesRegression:
    def test_eight_categories_defined(self):
        cats = list(IntentCategory)
        assert len(cats) == 8
        assert IntentCategory.RECOMMEND_PERSON in cats
        assert IntentCategory.SEARCH_INFO in cats
        assert IntentCategory.EXPLAIN_CONCEPT in cats
        assert IntentCategory.EXECUTE_ACTION in cats
        assert IntentCategory.DATA_QUERY in cats
        assert IntentCategory.CASUAL_CHAT in cats
        assert IntentCategory.TEAM_OVERVIEW in cats
        assert IntentCategory.FOLLOW_UP in cats  # C2 新增第 8 类

    def test_map_category_all_zh(self):
        assert _map_category("推荐人") == "recommend_person"
        assert _map_category("找资料") == "search_info"
        assert _map_category("解释概念") == "explain_concept"
        assert _map_category("执行操作") == "execute_action"
        assert _map_category("数据查询") == "data_query"
        assert _map_category("闲聊") == "casual_chat"
        assert _map_category("团队概览") == "team_overview"
        assert _map_category("续讲") == "follow_up"  # C2 新增

    def test_category_zh_display(self):
        assert _category_zh(IntentCategory.FOLLOW_UP) == "续讲"
        assert _category_zh(IntentCategory.CASUAL_CHAT) == "闲聊"

    @pytest.mark.asyncio
    async def test_classify_recommend_person(self):
        result = await classify_intent("我想学习饮用水相关内容，可以请教谁？", _ctx(_mock_llm("推荐人", tools=["query_members"])))
        assert result.category == IntentCategory.RECOMMEND_PERSON

    @pytest.mark.asyncio
    async def test_classify_search_info(self):
        result = await classify_intent("zeta 电位怎么测？", _ctx(_mock_llm("找资料", tools=["search_knowledge"])))
        assert result.category == IntentCategory.SEARCH_INFO
        assert result.suggested_tools == ["search_knowledge"]

    @pytest.mark.asyncio
    async def test_classify_explain_concept(self):
        result = await classify_intent("什么是 zeta 电位？", _ctx(_mock_llm("解释概念")))
        assert result.category == IntentCategory.EXPLAIN_CONCEPT

    @pytest.mark.asyncio
    async def test_classify_data_query(self):
        result = await classify_intent("列出我所有任务", _ctx(_mock_llm("数据查询", tools=["query_tasks"])))
        assert result.category == IntentCategory.DATA_QUERY

    @pytest.mark.asyncio
    async def test_classify_casual_chat(self):
        result = await classify_intent("你好", _ctx(_mock_llm("闲聊")))
        assert result.category == IntentCategory.CASUAL_CHAT
        assert result.suggested_tools == []

    @pytest.mark.asyncio
    async def test_classify_team_overview(self):
        result = await classify_intent("详细介绍本课题组", _ctx(_mock_llm("团队概览", tools=["query_members", "list_projects", "search_knowledge"])))
        assert result.category == IntentCategory.TEAM_OVERVIEW

    @pytest.mark.asyncio
    async def test_follow_up_category_from_llm(self):
        """LLM 兜底路径: 未命中正则短语时 LLM 返回「续讲」类别也能正确映射"""
        result = await classify_intent("再详细介绍下微气泡的制备工艺", _ctx(_mock_llm("续讲")))
        assert result.category == IntentCategory.FOLLOW_UP


class TestIntentToSseEvent:
    def test_follow_up_sse_event(self):
        result = IntentResult(category=IntentCategory.FOLLOW_UP, confidence=0.95)
        evt = intent_to_sse_event(result)
        assert evt.type == "intent_detected"
        assert evt.intent["category"] == "follow_up"
        assert "续讲" in evt.label

    def test_sse_event_serializes(self):
        result = IntentResult(category=IntentCategory.SEARCH_INFO, confidence=0.5)
        sse = intent_to_sse_event(result).to_sse()
        assert "intent_detected" in sse
        assert "search_info" in sse


# ============================================================================
# 辅助函数直接测试
# ============================================================================


class TestLookLikeRetrieval:
    @pytest.mark.parametrize("q", [
        "什么是微纳米气泡", "怎么生成微气泡", "臭氧消毒原理",
        "羟基自由基如何检测", "传质系数怎么算",
        "膜处理参数是多少", "为什么微气泡稳定",
    ])
    def test_retrieval_true(self, q):
        assert _looks_like_retrieval(q)

    @pytest.mark.parametrize("q", [
        "你好", "谢谢", "在吗", "帮我创建任务", "再见",
        "微气泡"  # 有领域词无疑问词
    ])
    def test_retrieval_false(self, q):
        assert not _looks_like_retrieval(q)
