import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.meeting_broadcast_service import (
    publish_transcript,
    publish_ai_reply,
    publish_speaker_mapping,
)


@pytest.mark.asyncio
async def test_publish_transcript():
    """publish_transcript 调 Redis publish 到 transcript:{id} 频道"""
    r = MagicMock()
    r.publish = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.meeting_broadcast_service.get_redis", AsyncMock(return_value=r))
        await publish_transcript(meeting_id=42, entry={"speaker": "A", "text": "hi"})

    r.publish.assert_called_once()
    call_args = r.publish.call_args
    assert call_args[0][0] == "transcript:42"
    payload = json.loads(call_args[0][1])
    assert payload["speaker"] == "A"


@pytest.mark.asyncio
async def test_publish_ai_reply():
    """publish_ai_reply 调 Redis publish 到 ai_reply:{id} 频道"""
    r = MagicMock()
    r.publish = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.meeting_broadcast_service.get_redis", AsyncMock(return_value=r))
        await publish_ai_reply(meeting_id=42, reply={"action": "summarize_recent", "text": "..."})

    r.publish.assert_called_once()
    assert r.publish.call_args[0][0] == "ai_reply:42"


@pytest.mark.asyncio
async def test_publish_speaker_mapping():
    """publish_speaker_mapping 调 Redis publish 到 speaker_mapping:{id} 频道"""
    r = MagicMock()
    r.publish = AsyncMock()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("app.services.meeting_broadcast_service.get_redis", AsyncMock(return_value=r))
        await publish_speaker_mapping(meeting_id=42, mapping={"speaker_1": "张三"})

    r.publish.assert_called_once()
    assert r.publish.call_args[0][0] == "speaker_mapping:42"
