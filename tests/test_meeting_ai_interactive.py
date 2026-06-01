import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.meeting_ai_interactive import (
    summarize_recent,
    translate,
    summarize_now,
    ask_agent,
)


@pytest.mark.asyncio
async def test_summarize_recent_basic():
    """summarize_recent 调 Claude"""
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "你好", "ts": 0},
        {"speaker": "B", "text": "世界", "ts": 1},
    ])), patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="简短总结")):
        result = await summarize_recent(meeting_id=1, seconds=30)
    assert result == "简短总结"


@pytest.mark.asyncio
async def test_translate_zh_to_en():
    """translate 中→英"""
    with patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="Hello world")):
        result = await translate("你好世界", src="zh", dst="en")
    assert result == "Hello world"


@pytest.mark.asyncio
async def test_summarize_now_returns_structured():
    """summarize_now 返回 summary + key_points"""
    mock_result = {"summary": "会议总结", "key_points": ["要点1", "要点2"]}
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "1", "ts": 0}
    ])), patch("app.services.meeting_analysis_service.meeting_analysis") as mock_ma:
        mock_ma.analyze_transcript = AsyncMock(return_value=mock_result)
        result = await summarize_now(meeting_id=1)
    assert result["summary"] == "会议总结"
    assert len(result["key_points"]) == 2


@pytest.mark.asyncio
async def test_ask_returns_short_answer():
    """ask_agent 限制 50 字"""
    with patch("app.services.meeting_ai_interactive.get_recent_transcript", AsyncMock(return_value=[
        {"speaker": "A", "text": "上下文", "ts": 0}
    ])), patch("app.services.meeting_ai_interactive._simple_llm_call", AsyncMock(return_value="简短回答")):
        result = await ask_agent(meeting_id=1, question="问题")
    assert result == "简短回答"
