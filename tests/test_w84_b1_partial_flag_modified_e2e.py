"""W84 第 1 批 B-1 P1-2 — mark_message_partial 必须 flag_modified + commit (CLAUDE.md 2026-06-28 教训)."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


@pytest.mark.asyncio(loop_scope="function")
async def test_mark_message_partial_by_message_id_calls_flag_modified(monkeypatch):
    """P1-2: 走 message_id 分支必须 flag_modified(msg, 'is_partial') + commit."""
    from app.services import chat_history_service as chs

    db = MagicMock()
    msg = MagicMock()
    msg.session_id = "sid_001"
    db.get = AsyncMockSingle(return_value=msg)

    flag_modified_calls: list = []

    def fake_flag_modified(obj, name):
        flag_modified_calls.append(name)

    captured = {}

    async def fake_get_session(*args, **kwargs):
        captured["get_session_called"] = True
        return MagicMock()

    async def fake_commit():
        captured["commit_called"] = True

    db.commit = fake_commit

    monkeypatch.setattr(chs, "flag_modified", fake_flag_modified)
    monkeypatch.setattr(chs, "get_session", fake_get_session)

    result = await chs.mark_message_partial(
        db, user_id=1, session_id="sid_001", message_id=123,
    )

    assert result is msg
    assert flag_modified_calls == ["is_partial"], flag_modified_calls
    assert captured.get("commit_called") is True, captured
    assert captured.get("get_session_called") is True, captured


@pytest.mark.asyncio(loop_scope="function")
async def test_mark_message_partial_by_client_msg_id_calls_flag_modified(monkeypatch):
    """P1-2: 走 client_msg_id 分支也必须 flag_modified + commit."""
    from sqlalchemy import select
    from app.services import chat_history_service as chs

    db = MagicMock()
    msg = MagicMock()
    msg.session_id = "sid_002"

    async def fake_execute(stmt):
        return MagicMock(scalar_one_or_none=MagicMock(return_value=msg))

    db.execute = fake_execute

    flag_modified_calls: list = []

    def fake_flag_modified(obj, name):
        flag_modified_calls.append(name)

    captured = {}

    async def fake_get_session(*args, **kwargs):
        captured["get_session_called"] = True
        return MagicMock()

    async def fake_commit():
        captured["commit_called"] = True

    db.commit = fake_commit

    monkeypatch.setattr(chs, "flag_modified", fake_flag_modified)
    monkeypatch.setattr(chs, "get_session", fake_get_session)

    result = await chs.mark_message_partial(
        db, user_id=1, session_id="sid_002", client_msg_id="cmid_xyz",
    )

    assert result is msg
    assert flag_modified_calls == ["is_partial"]
    assert captured.get("commit_called") is True
    assert captured.get("get_session_called") is True


class AsyncMockSingle:
    """AsyncMock 单值工厂, 避免 unittest.mock.AsyncMock 在 sync context 报 issues."""

    def __init__(self, return_value=None):
        self.return_value = return_value

    async def __call__(self, *args, **kwargs):
        return self.return_value
