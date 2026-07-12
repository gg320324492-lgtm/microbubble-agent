"""测试 critic.py（方案 C Stage 1）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_critic.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.critic import (
    CritiqueResult,
    critique_response,
    critique_to_sse_event,
    inject_suggestion_to_system,
    should_retry,
)
from app.core.llm import parse_llm_json  # 2026-07-12 提取到 app.core.llm.parse_llm_json
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import RichBlock
from app.config import settings


class TestShouldRetry:
    """score < 阈值时触发 retry"""

    def test_high_score_no_retry(self):
        result = CritiqueResult(
            score=9, addresses_question=True, has_synthesis=True, has_citations=True,
        )
        assert should_retry(result) is False

    def test_low_score_needs_retry(self):
        result = CritiqueResult(
            score=5, addresses_question=True, has_synthesis=False, has_citations=False,
        )
        assert should_retry(result) is True

    def test_zero_score_no_retry(self):
        """score=0 表示 Reflection 失败，不重试"""
        result = CritiqueResult(
            score=0, addresses_question=True, has_synthesis=True, has_citations=False,
        )
        assert should_retry(result) is False

    def test_boundary_score(self):
        """边界值 = 阈值不重试，< 阈值才重试"""
        boundary = CritiqueResult(
            score=settings.AGENT_REFLECTION_THRESHOLD,
            addresses_question=True, has_synthesis=True, has_citations=True,
        )
        assert should_retry(boundary) is False
        below = CritiqueResult(
            score=settings.AGENT_REFLECTION_THRESHOLD - 1,
            addresses_question=True, has_synthesis=True, has_citations=True,
        )
        assert should_retry(below) is True


class TestInjectSuggestion:
    """把建议注入到 system prompt"""

    def test_no_suggestion_unchanged(self):
        system = "你是一个助手"
        result = inject_suggestion_to_system(system, "")
        assert result == system

    def test_with_suggestion_appended(self):
        system = "你是一个助手"
        result = inject_suggestion_to_system(system, "需要更多具体推荐")
        assert "需要更多具体推荐" in result
        assert "你是一个助手" in result
        assert "自评建议" in result


class TestCritiqueResponseMocked:
    """Mock LLM 测试 critique_response"""

    @pytest.mark.asyncio
    async def test_high_score_critique(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "score": 9,
            "addresses_question": True,
            "has_synthesis": True,
            "has_citations": True,
            "missing": [],
            "suggestion": "回答完整",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = mock_llm

        result = await critique_response(
            user_question="请教谁",
            intent=intent,
            response_text="推荐杨慈、宋洋、李锐远",
            rich_blocks=[],
            tool_calls=[],
            ctx=ctx,
        )
        assert result.score == 9
        assert result.addresses_question is True
        assert result.has_synthesis is True

    @pytest.mark.asyncio
    async def test_low_score_critique_with_suggestion(self):
        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "score": 5,
            "addresses_question": True,
            "has_synthesis": False,
            "has_citations": False,
            "missing": ["缺少具体推荐理由"],
            "suggestion": "请为每个推荐人附 1-2 句研究相关性理由",
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = mock_llm

        result = await critique_response(
            "请教谁", intent, "杨慈", [], [], ctx,
        )
        assert result.score == 5
        assert result.has_synthesis is False
        assert "研究相关性" in result.suggestion
        assert should_retry(result) is True

    @pytest.mark.asyncio
    async def test_critique_failure_does_not_block(self):
        """LLM 失败时降级 score=0，不阻塞主流程"""
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM 503"))

        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = mock_llm

        result = await critique_response("q", intent, "r", [], [], ctx)
        assert result.score == 0
        assert result.addresses_question is True  # 视为通过
        assert "failed" in result.suggestion.lower() or "失败" in result.suggestion


class TestCritiqueToSseEvent:
    """CritiqueResult → StreamEvent"""

    def test_high_score_event(self):
        result = CritiqueResult(
            score=9, addresses_question=True, has_synthesis=True, has_citations=True,
        )
        evt = critique_to_sse_event(result)
        assert evt.type == "critique"
        assert evt.critique["score"] == 9
        assert "9/10" in evt.label
        assert "⚠️" not in evt.label  # 高分不带警告

    def test_low_score_event_has_warning(self):
        result = CritiqueResult(
            score=5, addresses_question=True, has_synthesis=False, has_citations=False,
            suggestion="需要更多推荐理由",
        )
        evt = critique_to_sse_event(result)
        assert "5/10" in evt.label
        assert "⚠️" in evt.label  # 低分带警告
