import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.meeting_service import compute_and_store_embedding, find_related_meetings


@pytest.mark.asyncio
async def test_compute_and_store_embedding_basic():
    """compute_and_store_embedding 计算并设置 meeting.embedding"""
    db = MagicMock()
    meeting = MagicMock()
    meeting.id = 1
    meeting.title = "周会"
    meeting.summary = "讨论项目"
    meeting.key_points = ["要点1"]
    meeting.decisions = ["决策1"]
    meeting.embedding = None
    db.get = AsyncMock(return_value=meeting)
    db.commit = AsyncMock()

    mock_embedding = [0.1] * 768
    with patch("app.services.embedding_service.generate_embedding", new=AsyncMock(return_value=mock_embedding)) as mock_gen:
        await compute_and_store_embedding(db, meeting_id=1)
    mock_gen.assert_called_once()

    assert meeting.embedding == mock_embedding
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_find_related_meetings_returns_top_k():
    """find_related_meetings 返回 top-3 相似会议"""
    db = MagicMock()
    current = MagicMock()
    current.id = 1
    current.embedding = [0.1] * 768
    db.get = AsyncMock(return_value=current)

    m1 = MagicMock(); m1.id = 2; m1.title = "M2"; m1.start_time = None; m1.summary = "s"
    m2 = MagicMock(); m2.id = 3; m2.title = "M3"; m2.start_time = None; m2.summary = "s"
    m3 = MagicMock(); m3.id = 4; m3.title = "M4"; m3.start_time = None; m3.summary = "s"
    mock_row = MagicMock()
    mock_row.all.return_value = [
        (m1, 0.1),
        (m2, 0.2),
        (m3, 0.3),
    ]
    db.execute = AsyncMock(return_value=mock_row)

    result = await find_related_meetings(db, meeting_id=1, top_k=3)

    assert len(result) == 3
    assert result[0]["id"] == 2
    assert result[0]["similarity"] == 0.9


@pytest.mark.asyncio
async def test_find_related_returns_empty_when_no_embedding():
    """当前会议无 embedding → []"""
    db = MagicMock()
    current = MagicMock()
    current.id = 1
    current.embedding = None
    db.get = AsyncMock(return_value=current)

    result = await find_related_meetings(db, meeting_id=1, top_k=3)
    assert result == []
