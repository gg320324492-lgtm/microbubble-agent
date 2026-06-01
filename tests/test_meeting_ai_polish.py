import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.services.meeting_ai_polish import polish_segments


@pytest.mark.asyncio
async def test_polish_segments_basic():
    """基础调用：传入 ASR 段，调用 Claude，返回结构化结果"""
    segments = [
        {"speaker": "张三", "text": "呃，那个，我觉得这个方案可以。", "ts": 1.0},
        {"speaker": "李四", "text": "嗯，就是说，我们下周开始做。", "ts": 5.0},
    ]
    context = {"title": "项目讨论", "participants": ["张三", "李四"], "topic": None}

    mock_response_text = """{
        "polished": [
            {"speaker": "张三", "text": "我认为这个方案可以。", "ts": 1.0},
            {"speaker": "李四", "text": "我们下周开始做。", "ts": 5.0}
        ],
        "key_points": [
            {"text": "决定下周开始做", "ts": 5.0, "kind": "decision"}
        ],
        "boundary_after_index": null,
        "summary": "讨论方案并决定下周开始"
    }"""

    with patch("app.services.meeting_ai_polish.get_anthropic_client") as mock_client_factory:
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text=mock_response_text)]
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_client_factory.return_value = mock_client

        result = await polish_segments(segments, context)

    assert len(result["polished"]) == 2
    assert result["polished"][0]["text"] == "我认为这个方案可以。"
    assert result["key_points"][0]["kind"] == "decision"
    assert result["summary"] == "讨论方案并决定下周开始"
