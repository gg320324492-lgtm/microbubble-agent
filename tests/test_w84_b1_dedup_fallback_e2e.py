"""W84 第 1 批 B-1 P1-7 — drive_notification_dedup_service fallback 监控.

派工前提铁律 12: dedup DB 异常必须 log + 返 True (允许发送) 不静默吞.
"""
from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


@pytest.mark.asyncio(loop_scope="function")
async def test_should_send_returns_true_on_db_error_and_logs(caplog):
    """P1-7: should_send 遇 DB 异常 → 返 True (fallback 发送) + logger.warning(exc_info=True)."""
    from app.services import drive_notification_dedup_service as dns

    db = MagicMock()
    db.execute = AsyncMock(side_effect=RuntimeError("simulated dedup DB failure"))

    with caplog.at_level(logging.WARNING, logger="microbubble.drive.notification_dedup"):
        result = await dns.should_send(db, user_id=1, comment_id=2, digest="abc")

    assert result is True, "DB 异常时 should_send 必须返 True (fallback 发送)"

    warning_records = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and r.name == "microbubble.drive.notification_dedup"
    ]
    assert warning_records, "缺少 logger.warning 记录"
    assert any(r.exc_info for r in warning_records), "WARNING 缺 exc_info"


@pytest.mark.asyncio(loop_scope="function")
async def test_should_send_returns_false_for_existing_dedup_row():
    """P1-7: 正常路径: dedup 命中 → 返 False (skip), regression test."""
    from app.services import drive_notification_dedup_service as dns

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=(123,))))

    result = await dns.should_send(db, user_id=1, comment_id=2, digest="abc")
    assert result is False


@pytest.mark.asyncio(loop_scope="function")
async def test_should_send_returns_true_when_no_row():
    """P1-7: 正常路径: dedup 未命中 → 返 True (允许发送), regression test."""
    from app.services import drive_notification_dedup_service as dns

    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(first=MagicMock(return_value=None)))

    result = await dns.should_send(db, user_id=1, comment_id=2, digest="abc")
    assert result is True
