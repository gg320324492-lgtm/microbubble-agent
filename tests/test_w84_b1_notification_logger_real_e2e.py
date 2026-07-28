"""W84 第 1 批 B-1 P1-3 (real) — notification_service logger.error 真验证 (async)."""
from __future__ import annotations

import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


@pytest.mark.asyncio(loop_scope="function")
async def test_create_mention_ws_push_failure_logs_error(caplog):
    """P1-3: WS push 失败 → logger.error(..., exc_info=True).

    drive_event_publisher / notification_service 在函数内 import
    `app.api.v1.ws_notifications.notification_manager.push_to_user`,
    必须 patch 该字符串路径, 不能用 ns.notification_manager (模块级不存在).
    """
    from app.services import notification_service as ns

    db = MagicMock()
    db.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()

    with caplog.at_level(logging.ERROR, logger="app.services.notification_service"):
        with patch.object(
            ns.NotificationService, "_lookup_actor_name", new=AsyncMock(return_value="actor")
        ), patch.object(
            ns.NotificationService, "_lookup_rich_metadata", new=AsyncMock(return_value={})
        ), patch(
            "app.api.v1.ws_notifications.notification_manager.push_to_user",
            new=AsyncMock(side_effect=RuntimeError("ws boom")),
        ):
            await ns.NotificationService.create_mention(
                db, file_id=1, mentioned_user_id=2, mentioned_by=1, context="comment"
            )

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and r.name == "app.services.notification_service"
    ]
    assert error_records, "expected at least one ERROR record, got none"
    assert any("ws boom" in r.getMessage() or "WS push" in r.getMessage() for r in error_records)
    assert any(r.exc_info for r in error_records), "expected exc_info attached to ERROR records"


@pytest.mark.asyncio(loop_scope="function")
async def test_push_to_browser_failure_logs_error(caplog):
    """P1-3: _push_to_browser 失败 → logger.error(..., exc_info=True).

    _push_to_browser 内部 `from app.services.push_service import push_to_user`,
    同样必须 patch 字符串路径.
    """
    from app.services import notification_service as ns

    with caplog.at_level(logging.ERROR, logger="app.services.notification_service"):
        with patch(
            "app.services.push_service.push_to_user",
            new=AsyncMock(side_effect=RuntimeError("push boom")),
        ):
            await ns._push_to_browser(
                1, {"type": "mention", "title": "t", "body": "b"}, db=MagicMock()
            )

    error_records = [
        r for r in caplog.records
        if r.levelno >= logging.ERROR and r.name == "app.services.notification_service"
    ]
    assert error_records
    assert any(r.exc_info for r in error_records)
