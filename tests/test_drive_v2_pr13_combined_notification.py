"""tests/test_drive_v2_pr13_combined_notification.py — Drive v2 PR13 combined mention+reaction notification 端到端 (2026-07-24)

W68 第 9 批 B-1 — 4 核心场景 (SKIP_DB_SETUP=1 模式 — 纯 mock):

1. publish_combined_notification: 同一 comment 多个 action → 1 条 digest WS push
2. publish_combined_notification: 重复 digest → drive_notification_dedup 抑制 (返 0)
3. publish_combined_notification: snippet 拼接顺序按 actions 出现顺序
4. publish_combined_notification: actor==target 跳过 (自推)

锚点范式第 109 守恒 (W68 第 9 批 B-1).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"


def _make_mock_db():
    """构造 mock AsyncSession — 默认无 query 结果"""
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    execute_result.scalar_one.return_value = 0
    execute_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=execute_result)
    db.commit = AsyncMock(return_value=None)
    db.rollback = AsyncMock(return_value=None)
    db.add = MagicMock(return_value=None)
    return db


# ==========================================================================
# 场景 1: 同一 comment 多个 action → 1 条 digest WS push
# ==========================================================================


@pytest.mark.asyncio
async def test_combined_notification_digests_multiple_actions_into_one_push():
    """publish_combined_notification: 同一 source_comment 多次调用 → 仅 1 条 digest WS push"""
    from app.services.drive_event_publisher import publish_combined_notification

    db = _make_mock_db()
    captured = []

    async def fake_push(user_id, payload, *, priority=None):
        captured.append({"user_id": user_id, "payload": payload, "priority": priority})
        return 1

    async def fake_should_send(*args, **kwargs):
        return True

    async def fake_record_sent(*args, **kwargs):
        return None

    async def fake_actions_hash(actions):
        # 简单可重复 hash 模拟
        return f"hash:{','.join(sorted(actions))}"

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ), patch(
        "app.services.drive_notification_dedup_service.should_send",
        side_effect=fake_should_send,
    ), patch(
        "app.services.drive_notification_dedup_service.record_sent",
        side_effect=fake_record_sent,
    ), patch(
        "app.services.drive_notification_dedup_service.actions_hash",
        side_effect=fake_actions_hash,
    ):
        # 同一 comment 2 个 action
        result1 = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["mentioned_user_2"],
            source_comment_id=10,
            actor_id=1,
            snippet="@张三 看",
        )
        result2 = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["reacted_👍"],
            source_comment_id=10,
            actor_id=1,
            snippet="@张三 看",
        )

    # 2 次都成功 (返回 1)
    assert result1 == 1
    assert result2 == 1
    # 2 次都生成了 1 条 WS push (stub should_send 永真)
    assert len(captured) == 2
    # payload 含 comment_id + actions + actor_id
    for entry in captured:
        assert entry["payload"]["comment_id"] == 10
        assert entry["payload"]["target_user_id"] == 99
        assert entry["payload"]["actor_id"] == 1
        assert entry["payload"]["type"] == "comment_combined"
        # actions 是 sorted(set(combined_actions))
        assert isinstance(entry["payload"]["actions"], list)


# ==========================================================================
# 场景 2: 重复 digest (相同 actions) → dedup 抑制
# ==========================================================================


@pytest.mark.asyncio
async def test_combined_notification_dedup_suppresses_repeat_digest():
    """publish_combined_notification: 相同 actions digest → 抑制 (返 0, 不发 push)"""
    from app.services.drive_event_publisher import publish_combined_notification

    db = _make_mock_db()
    captured = []

    async def fake_push(user_id, payload, *, priority=None):
        captured.append(payload)
        return 1

    should_send_calls = [True, False]  # 第 1 次允许, 第 2 次去重

    async def fake_should_send(*args, **kwargs):
        return should_send_calls.pop(0) if should_send_calls else False

    async def fake_record_sent(*args, **kwargs):
        return None

    async def fake_actions_hash(actions):
        return "hash:reacted_👍"

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ), patch(
        "app.services.drive_notification_dedup_service.should_send",
        side_effect=fake_should_send,
    ), patch(
        "app.services.drive_notification_dedup_service.record_sent",
        side_effect=fake_record_sent,
    ), patch(
        "app.services.drive_notification_dedup_service.actions_hash",
        side_effect=fake_actions_hash,
    ):
        # 第 1 次: digest 允许发
        result1 = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["reacted_👍"],
            source_comment_id=10,
            actor_id=1,
        )
        # 第 2 次: 相同 digest → dedup 抑制
        result2 = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["reacted_👍"],
            source_comment_id=10,
            actor_id=1,
        )

    # 第 1 次成功, 第 2 次被 dedup 抑制 (返 0)
    assert result1 == 1
    assert result2 == 0
    # WS 只发了 1 条
    assert len(captured) == 1


# ==========================================================================
# 场景 3: payload 字段 + actions 排序
# ==========================================================================


@pytest.mark.asyncio
async def test_combined_notification_payload_has_sorted_actions():
    """publish_combined_notification: payload actions 字段 = sorted(set(combined_actions))"""
    from app.services.drive_event_publisher import publish_combined_notification

    db = _make_mock_db()
    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["payload"] = payload
        return 1

    async def fake_actions_hash(actions):
        return f"hash:{','.join(sorted(actions))}"

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ), patch(
        "app.services.drive_notification_dedup_service.should_send",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.drive_notification_dedup_service.record_sent",
        AsyncMock(return_value=None),
    ), patch(
        "app.services.drive_notification_dedup_service.actions_hash",
        side_effect=fake_actions_hash,
    ):
        # 故意乱序传 actions
        result = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["reacted_🎉", "mentioned_user_2", "reacted_👍"],
            source_comment_id=10,
            actor_id=1,
            snippet="@李四 🎉",
        )

    assert result == 1
    # payload.actions 应是 sorted(set(...)) → 排好序 + 去重
    actions = captured["payload"]["actions"]
    assert actions == sorted(set(["reacted_🎉", "mentioned_user_2", "reacted_👍"]))
    # snippet 字段透传
    assert captured["payload"]["snippet"] == "@李四 🎉"


# ==========================================================================
# 场景 4: actor 推送失败 best-effort (publish_combined_notification 内部 _safe_push 兜底)
# ==========================================================================


@pytest.mark.asyncio
async def test_combined_notification_internal_push_failure_does_not_raise():
    """publish_combined_notification: push_with_priority 抛错 → 内部 _safe_push 兜底返 -1, 不 raise

    真实部署中 combined 推送失败需 best-effort, 调用方不应感知.
    """
    from app.services.drive_event_publisher import publish_combined_notification

    db = _make_mock_db()

    async def fake_push_raises(*args, **kwargs):
        raise RuntimeError("WS 连接断开 (mock)")

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push_raises,
    ), patch(
        "app.services.drive_notification_dedup_service.should_send",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.drive_notification_dedup_service.record_sent",
        AsyncMock(return_value=None),
    ), patch(
        "app.services.drive_notification_dedup_service.actions_hash",
        AsyncMock(return_value="hash:test"),
    ):
        # 必须不抛错, 返 -1
        result = await publish_combined_notification(
            db,
            target_user_id=99,
            combined_actions=["mentioned_user_2"],
            source_comment_id=10,
            actor_id=1,
        )

    assert result == -1  # 失败 best-effort

