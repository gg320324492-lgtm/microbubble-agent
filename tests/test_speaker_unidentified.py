"""测试 speaker_unidentified_service.get_unenrolled_participants

任务 6 — TDD 红灯：先写失败的测试。
验证：
1. 无未录入成员时返回空列表
2. 查询 WHERE 条件包含 is_active == True 过滤
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.speaker_unidentified_service import get_unenrolled_participants


@pytest.mark.asyncio
async def test_get_unenrolled_participants_empty():
    """无未录入成员时返回空列表"""
    db = MagicMock()
    # Mock query result 为空
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    result = await get_unenrolled_participants(db, meeting_id=1)

    assert result == []


@pytest.mark.asyncio
async def test_get_unenrolled_participants_filters_inactive():
    """is_active=False 的成员不返回"""
    db = MagicMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)

    await get_unenrolled_participants(db, meeting_id=1)

    # 验证 SQL WHERE 含 is_active == True
    call_args = db.execute.call_args
    assert "is_active" in str(call_args)
