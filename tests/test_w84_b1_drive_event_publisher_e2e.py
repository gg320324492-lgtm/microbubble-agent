"""W84 第 1 批 B-1 P1-1 — drive_event_publisher 发布 reaction + combined notification fallback.

派工前提铁律 12 (派工 v4 铁律 3 真验证): 改前改后 e2e 都必须 pass.
SKIP_DB_SETUP=1 模式 + mock publish / dedup, 验证:

1. combined notification dedup DB 异常时, 应 fallback 到 dedup_fallback=True
   payload 直接推 (不静默吞).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock

os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
import pytest_asyncio


@pytest.mark.asyncio(loop_scope="function")
async def test_combined_notification_dedup_error_falls_back_to_send(monkeypatch):
    """P1-1: publish_combined_notification 遇 dedup DB 异常 → fallback 推 (非 -1 静默).

    旧实现 except: log + return -1 → caller 误以为推送成功, UI 无反馈.
    新实现: except: log + 直接调 _safe_push 走 fallback 路径.
    """
    from app.services import drive_event_publisher as dep

    db = MagicMock()

    async def fake_should_send(*args, **kwargs):
        raise RuntimeError("simulated dedup lookup failure")

    async def fake_record_sent(*args, **kwargs):
        return None

    captured = []

    async def fake_safe_push(user_id, payload, *, priority=None):
        captured.append((user_id, payload.get("type"), payload.get("dedup_fallback")))
        return 1

    # drive_event_publisher 在 publish_combined_notification 内 import 成员
    monkeypatch.setattr(
        "app.services.drive_notification_dedup_service.should_send", fake_should_send
    )
    monkeypatch.setattr(
        "app.services.drive_notification_dedup_service.record_sent", fake_record_sent
    )
    monkeypatch.setattr(dep, "_safe_push", fake_safe_push)

    result = await dep.publish_combined_notification(
        db,
        target_user_id=42,
        combined_actions=["reacted_👍", "mentioned"],
        source_comment_id=7,
        actor_id=99,
        snippet="hello",
    )

    assert result == 1, f"expected fallback push to return 1, got {result}"
    assert captured == [(42, "comment_combined", True)], captured


@pytest.mark.asyncio(loop_scope="function")
async def test_combined_notification_dedup_skip_returns_zero(monkeypatch):
    """正常 dedup 命中 → 仍然 return 0 (不推), regression test."""
    from app.services import drive_event_publisher as dep

    db = MagicMock()

    async def fake_should_send(*args, **kwargs):
        return False  # 已发送, skip

    async def fake_record_sent(*args, **kwargs):
        raise AssertionError("should not record_sent when should_send=False")

    async def fake_safe_push(user_id, payload, *, priority=None):
        raise AssertionError("should not push when should_send=False")

    monkeypatch.setattr(
        "app.services.drive_notification_dedup_service.should_send", fake_should_send
    )
    monkeypatch.setattr(
        "app.services.drive_notification_dedup_service.record_sent", fake_record_sent
    )
    monkeypatch.setattr(dep, "_safe_push", fake_safe_push)

    result = await dep.publish_combined_notification(
        db,
        target_user_id=42,
        combined_actions=["mentioned"],
        source_comment_id=7,
        actor_id=99,
    )
    assert result == 0
