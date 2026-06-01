import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from app.services.meeting_service import create_meeting_with_reminder, link_related_meetings


@pytest.mark.asyncio
async def test_create_meeting_basic():
    """只创建会议，不创建 reminder（remind_minutes=0）"""
    db = MagicMock()
    with patch("app.services.meeting_service.Meeting") as MockMeeting:
        mock_meeting = MagicMock()
        mock_meeting.id = 1
        mock_meeting.start_time = None
        MockMeeting.return_value = mock_meeting
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_meeting_with_reminder(
            db, meeting_data={"title": "test", "status": "scheduled"},
            remind_minutes_before=0,
        )

    assert result.id == 1
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_create_meeting_with_5min_reminder():
    """创建会议 + 自动创建 5min 前 reminder"""
    db = MagicMock()
    with patch("app.services.meeting_service.Meeting") as MockMeeting, \
         patch("app.services.meeting_service.Reminder") as MockReminder, \
         patch("app.services.meeting_service.reminder_scheduler") as mock_sched:
        mock_meeting = MagicMock()
        mock_meeting.id = 1
        mock_meeting.start_time = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
        MockMeeting.return_value = mock_meeting
        mock_sched.add = AsyncMock()
        mock_reminder = MagicMock()
        MockReminder.return_value = mock_reminder

        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()

        result = await create_meeting_with_reminder(
            db,
            meeting_data={"title": "test", "status": "scheduled"},
            remind_minutes_before=5,
        )

    assert result.id == 1
    assert db.add.call_count == 2
    mock_sched.add.assert_called_once()


@pytest.mark.asyncio
async def test_link_related_meetings_writes_field():
    """link_related_meetings 写入 meeting.related_meeting_ids"""
    db = MagicMock()
    meeting = MagicMock()
    db.get = AsyncMock(return_value=meeting)
    db.commit = AsyncMock()

    await link_related_meetings(db, meeting_id=1, related_ids=[2, 3, 4])

    assert meeting.related_meeting_ids == [2, 3, 4]
    db.commit.assert_called_once()
