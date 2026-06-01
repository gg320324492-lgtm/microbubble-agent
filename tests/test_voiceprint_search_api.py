import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.voiceprint_service import record_confidence, search_speaker_history


@pytest.mark.asyncio
async def test_record_confidence_basic():
    """record_confidence 写 VoiceprintHistory 行"""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = AsyncMock()

    await record_confidence(db, meeting_id=1, member_id=5, confidence=0.85)

    db.add.assert_called_once()
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_search_speaker_history_basic():
    """search_speaker_history 返回该 member_id 发言过的会议条目"""
    db = MagicMock()
    meeting = MagicMock()
    meeting.id = 1
    meeting.title = "周会"
    meeting.transcript = [
        {"speaker": "张三", "member_id": 5, "text": "你好", "ts": 100, "confidence": 0.85},
        {"speaker": "李四", "member_id": 6, "text": "世界", "ts": 200, "confidence": 0.9},
    ]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [meeting]
    db.execute = AsyncMock(return_value=mock_result)

    result = await search_speaker_history(db, member_id=5, limit=10)

    assert len(result) == 1
    assert result[0]["meeting_id"] == 1
    assert result[0]["text"] == "你好"
    assert result[0]["speaker"] == "张三"
    assert result[0]["confidence"] == 0.85


@pytest.mark.asyncio
async def test_search_speaker_history_empty():
    """transcript 为空时返回 []"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await search_speaker_history(db, member_id=5, limit=10)
    assert result == []
