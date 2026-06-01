import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from app.services.voiceprint_service import get_fingerprints


@pytest.mark.asyncio
async def test_get_fingerprints_basic():
    """get_fingerprints 返回所有录入声纹的成员"""
    db = MagicMock()
    m1 = MagicMock()
    m1.id = 1
    m1.name = "张三"
    m1.avatar = "url1"
    m1.voice_embedding = [0.1] * 256
    m1.voice_enrolled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    m1.voice_sample_count = 3
    m1.is_active = True

    m2 = MagicMock()
    m2.id = 2
    m2.name = "李四"
    m2.avatar = "url2"
    m2.voice_embedding = [0.2] * 256
    m2.voice_enrolled_at = None
    m2.voice_sample_count = 0
    m2.is_active = True

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [m1, m2]
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_fingerprints(db)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[0]["name"] == "张三"
    assert len(result[0]["embedding"]) == 256
    assert result[0]["sample_count"] == 3
    assert result[1]["enrolled_at"] is None
