import json
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


@pytest.mark.asyncio
async def test_polish_segments_cache_hit():
    """二次调用相同 segment 应走缓存，不调 LLM"""
    import hashlib
    from app.services.meeting_ai_polish import polish_segments_with_cache

    segments = [{"speaker": "张三", "text": "测试缓存", "ts": 1.0}]
    context = {"title": "测试", "participants": [], "topic": None}
    segment_hash = hashlib.sha1(json.dumps(segments, sort_keys=True).encode()).hexdigest()[:16]

    # 预填缓存
    from app.core.redis import get_redis
    r = await get_redis()
    cached = {
        "polished": [{"speaker": "张三", "text": "缓存版", "ts": 1.0}],
        "key_points": [],
        "boundary_after_index": None,
        "summary": None,
    }
    await r.set(f"polish:test_meeting:{segment_hash}", json.dumps(cached), ex=60)

    try:
        with patch("app.services.meeting_ai_polish.get_anthropic_client") as mock_factory:
            mock_factory.assert_not_called()  # 关键：不应调用 LLM
            result = await polish_segments_with_cache(1, segments, context)

        assert result["polished"][0]["text"] == "缓存版"
        mock_factory.assert_not_called()
    finally:
        await r.delete(f"polish:test_meeting:{segment_hash}")
