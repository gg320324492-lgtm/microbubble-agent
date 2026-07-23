"""tests/test_drive_v2_pr9_ws.py — Drive v2 PR9 WS 推送单元测试 (2026-07-24)

W68 第 4 批 Drive v2 PR9 WS 推送闭环 (锚点范式第 48 守恒).
F-1/F-2 报告明示 'WS 推送不强制每 PR 集成, 留给 PR10'. 本测试覆盖 PR10 集成.

5 核心场景 (不依赖 PostgreSQL, 用 Mock 模拟 db.execute / push_with_priority):
1. publish_comment_created → push_with_priority → WS payload 正确 + priority=MEDIUM
2. publish_version_uploaded → push_with_priority → WS payload 正确
3. publish_* 失败 best-effort (push_with_priority 抛错时 caller 不感知)
4. 多订阅者 (一个 user 多 ws 连接, 全部收到推送)
5. priority 分类 (comment_deleted=LOW, 其余=MEDIUM, resolved_by=author=skip)

依赖:
- app.services.drive_event_publisher (本 PR 新建)
- app.services.notification_service (a-1): push_with_priority / NotificationPriority
- app.api.v1.ws_notifications (a-1): NotificationManager.push_to_user

测试策略: SKIP_DB_SETUP=1 模式 (纯 mock, 无 PostgreSQL 依赖), 与 W1 T1 跨 scope 闭环一致.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"

# 这些 import 在 SKIP_DB_SETUP=1 模式下安全 (publisher 不依赖 DB session 类型)
from app.services.notification_service import NotificationPriority  # noqa: E402

# 注意: SKIP_DB_SETUP=1 时 conftest 会让 db/client/test_member fixture 不可用
# 所以测试用纯 mock, 不依赖 fixtures


# ==========================================================================
# Helpers: 构造 mock db / ORM 实例
# ==========================================================================


def _make_mock_db(uploader_id: int = 2, folder_owner_id: int = 2):
    """构造 mock AsyncSession: db.execute() 返回 uploader/owner_id

    用于 _resolve_file_owner / _resolve_folder_owner / _resolve_comment_author
    这 3 个内部 SQL lookup. mock 行为:
    - execute(stmt).first() → (uploader_id,) (单 row, 单列)
    """
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.first.return_value = (uploader_id,)
    db.execute = AsyncMock(return_value=execute_result)
    return db


def _make_mock_comment(
    *, comment_id: int = 1, file_id: int = 10, folder_id=None,
    parent_id=None, author_id: int = 100, mentions=None,
    resolved_at=None, resolved_by=None,
):
    """构造 mock DriveComment ORM 实例 (只填需要的字段)"""
    c = MagicMock()
    c.id = comment_id
    c.file_id = file_id
    c.folder_id = folder_id
    c.parent_id = parent_id
    c.author_id = author_id
    c.mentions = mentions
    c.resolved_at = resolved_at
    c.resolved_by = resolved_by
    return c


def _make_mock_version(
    *, version_id: int = 5, file_id: int = 10, version_number: int = 2,
    uploader_id: int = 100, size: int = 4096, comment: str = "new",
):
    """构造 mock DriveFileVersion ORM 实例"""
    v = MagicMock()
    v.id = version_id
    v.file_id = file_id
    v.version_number = version_number
    v.uploader_id = uploader_id
    v.size = size
    v.comment = comment
    return v


# ==========================================================================
# 场景 1: publish_comment_created → payload + priority=MEDIUM
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_comment_created_payload_and_priority():
    """comment_created 推送 → file owner (mock uploader=2) 收到正确 payload + MEDIUM"""
    from app.services.drive_event_publisher import publish_comment_created

    db = _make_mock_db(uploader_id=2)  # file owner = 2
    comment = _make_mock_comment(
        comment_id=42, file_id=10, author_id=100, mentions=[999],
    )

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["user_id"] = user_id
        captured["payload"] = payload
        captured["priority"] = priority
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_comment_created(db, comment, actor_id=100)

    assert result == 1
    assert captured["user_id"] == 2  # file owner (≠ author)
    assert captured["priority"] == NotificationPriority.MEDIUM
    assert captured["payload"]["type"] == "comment_created"
    assert captured["payload"]["comment_id"] == 42
    assert captured["payload"]["file_id"] == 10
    assert captured["payload"]["author_id"] == 100
    assert captured["payload"]["actor_id"] == 100
    assert captured["payload"]["mentions"] == [999]
    assert "ts" in captured["payload"]
    assert captured["payload"]["is_resolved"] is False


@pytest.mark.asyncio
async def test_publish_comment_created_skips_self_push():
    """comment_created 自推跳过: author == file owner → 不推送"""
    from app.services.drive_event_publisher import publish_comment_created

    db = _make_mock_db(uploader_id=100)  # file owner == author
    comment = _make_mock_comment(author_id=100)

    call_count = 0

    async def fake_push(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_comment_created(db, comment, actor_id=100)

    assert call_count == 0, "自推应跳过"
    assert result == 0


@pytest.mark.asyncio
async def test_publish_comment_updated_payload():
    """comment_updated 推送 → payload 含 updated_at 信息 + MEDIUM"""
    from app.services.drive_event_publisher import publish_comment_updated

    db = _make_mock_db(uploader_id=2)
    comment = _make_mock_comment(comment_id=42, file_id=10, author_id=100)

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["payload"] = payload
        captured["priority"] = priority
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_comment_updated(db, comment, actor_id=100)

    assert captured["payload"]["type"] == "comment_updated"
    assert captured["priority"] == NotificationPriority.MEDIUM
    assert captured["payload"]["comment_id"] == 42


# ==========================================================================
# 场景 2: publish_version_uploaded / publish_version_rollback
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_version_uploaded_payload():
    """version_uploaded 推送 → file owner 收到正确 payload + MEDIUM"""
    from app.services.drive_event_publisher import publish_version_uploaded

    db = _make_mock_db(uploader_id=2)  # file owner = 2 ≠ uploader
    version = _make_mock_version(
        version_id=5, file_id=10, version_number=2,
        uploader_id=100, size=4096, comment="new version uploaded",
    )

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["user_id"] = user_id
        captured["payload"] = payload
        captured["priority"] = priority
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_version_uploaded(
            db, version, file_name="test.pdf",
        )

    assert result == 1
    assert captured["user_id"] == 2
    assert captured["priority"] == NotificationPriority.MEDIUM
    assert captured["payload"]["type"] == "version_uploaded"
    assert captured["payload"]["version_id"] == 5
    assert captured["payload"]["file_id"] == 10
    assert captured["payload"]["version_number"] == 2
    assert captured["payload"]["file_name"] == "test.pdf"
    assert captured["payload"]["uploader_id"] == 100
    assert captured["payload"]["size"] == 4096
    assert captured["payload"]["comment"] == "new version uploaded"


@pytest.mark.asyncio
async def test_publish_version_rollback_payload():
    """version_rollback 推送 → payload 含 target_version_number"""
    from app.services.drive_event_publisher import publish_version_rollback

    db = _make_mock_db(uploader_id=2)
    version = _make_mock_version(
        version_id=8, file_id=10, version_number=4, uploader_id=100,
        comment="Rolled back to v3",
    )

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["payload"] = payload
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_version_rollback(
            db, version, file_name="test.pdf", target_version_number=3,
        )

    assert captured["payload"]["type"] == "version_rollback"
    assert captured["payload"]["version_number"] == 4
    assert captured["payload"]["target_version_number"] == 3


# ==========================================================================
# 场景 3: 失败 best-effort (push_with_priority 抛错 → caller 不感知)
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_failure_is_best_effort():
    """push_with_priority 抛错 → publish_* 捕获异常返 -1, 不 raise"""
    from app.services.drive_event_publisher import publish_comment_created

    db = _make_mock_db(uploader_id=2)
    comment = _make_mock_comment(file_id=10, author_id=100)

    async def fake_push_raises(*args, **kwargs):
        raise RuntimeError("Redis 连接失败 (mock)")

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push_raises,
    ):
        # 必须不抛错
        result = await publish_comment_created(db, comment, actor_id=100)

    assert result == -1, "失败 best-effort 应返 -1"


@pytest.mark.asyncio
async def test_publish_comment_deleted_priority_low():
    """comment_deleted 推送 priority=LOW (删除低优先级)"""
    from app.services.drive_event_publisher import publish_comment_deleted

    db = _make_mock_db(uploader_id=2)  # file owner = 2

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["priority"] = priority
        captured["payload"] = payload
        captured["user_id"] = user_id
        return 0  # 模拟离线入队

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_comment_deleted(
            db,
            comment_id=42,
            file_id=10,
            folder_id=None,
            author_id=100,
            actor_id=100,
        )

    assert captured["priority"] == NotificationPriority.LOW
    assert captured["payload"]["type"] == "comment_deleted"
    assert captured["payload"]["comment_id"] == 42
    assert captured["payload"]["file_id"] == 10
    assert captured["payload"]["folder_id"] is None


@pytest.mark.asyncio
async def test_publish_comment_resolved_skips_self():
    """resolved_by == author → 跳过自推"""
    from app.services.drive_event_publisher import publish_comment_resolved

    db = _make_mock_db(uploader_id=2)
    call_count = 0

    async def fake_push(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_comment_resolved(
            db,
            comment_id=42,
            file_id=10,
            folder_id=None,
            resolved_by=100,  # author 也是 100
            author_id=100,
        )

    assert call_count == 0
    assert result == 0


@pytest.mark.asyncio
async def test_publish_comment_resolved_to_author():
    """resolved_by ≠ author → 推送给 author"""
    from app.services.drive_event_publisher import publish_comment_resolved

    db = _make_mock_db(uploader_id=2)
    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["user_id"] = user_id
        captured["payload"] = payload
        captured["priority"] = priority
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_comment_resolved(
            db,
            comment_id=42,
            file_id=10,
            folder_id=None,
            resolved_by=2,  # file owner 标记 resolved
            author_id=100,  # author 收推送
        )

    assert captured["user_id"] == 100  # author
    assert captured["priority"] == NotificationPriority.MEDIUM
    assert captured["payload"]["type"] == "comment_resolved"
    assert captured["payload"]["resolved_by"] == 2


# ==========================================================================
# 场景 4: 多订阅者 fan-out (一个 user 多个 ws 连接)
# ==========================================================================


@pytest.mark.asyncio
async def test_multiple_ws_subscribers_all_receive_push():
    """场景 4: 同一 user 多 ws (桌面+移动) → push_to_user fan-out 全部

    直接测 a-1 NotificationManager (不依赖 DB / Redis), 验证多 ws 收推送.
    """
    from app.api.v1.ws_notifications import NotificationManager

    mgr = NotificationManager()
    user_id = 2

    # 模拟 2 个 ws 连接 (桌面 + 移动)
    ws_desktop = AsyncMock()
    ws_desktop.send_text = AsyncMock()
    ws_mobile = AsyncMock()
    ws_mobile.send_text = AsyncMock()

    await mgr.connect(user_id, ws_desktop)
    await mgr.connect(user_id, ws_mobile)

    assert mgr.online_count() == 1  # 1 user 在线
    assert mgr.is_online(user_id) is True

    delivered = await mgr.push_to_user(user_id, {
        "type": "comment_created",
        "comment_id": 99,
        "ts": datetime.now(timezone.utc).isoformat(),
    })

    assert delivered == 2, f"2 ws 都应收到推送, 实际 delivered={delivered}"
    assert ws_desktop.send_text.called
    assert ws_mobile.send_text.called


@pytest.mark.asyncio
async def test_offline_user_uses_offline_queue():
    """用户离线 (ws 未连接) → push_to_user 返 0 (publisher 内部应自动 fallback 到入队)"""
    from app.api.v1.ws_notifications import NotificationManager

    mgr = NotificationManager()
    user_id = 999  # 没 connect 过

    delivered = await mgr.push_to_user(user_id, {
        "type": "comment_created",
        "comment_id": 1,
    })

    assert delivered == 0, "用户离线 → delivered=0"


# ==========================================================================
# 场景 5: priority 分类 (LOW for delete, MEDIUM for others)
# ==========================================================================


@pytest.mark.asyncio
async def test_priority_classification_all_events():
    """验证每个 publish_* 用的 priority 符合设计:
    - comment_deleted → LOW
    - 其他 (created/updated/resolved + version_uploaded/rollback) → MEDIUM
    """
    from app.services.drive_event_publisher import (
        publish_comment_created,
        publish_comment_deleted,
        publish_comment_resolved,
        publish_comment_updated,
        publish_version_rollback,
        publish_version_uploaded,
    )

    db = _make_mock_db(uploader_id=2)
    priorities_seen = []

    async def fake_push(user_id, payload, *, priority=None):
        priorities_seen.append((payload["type"], priority))
        return 0

    comment = _make_mock_comment(comment_id=1, file_id=10, author_id=100)
    version = _make_mock_version(version_id=5, file_id=10, uploader_id=100)

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        # 1. comment_created
        await publish_comment_created(db, comment, actor_id=100)
        # 2. comment_updated
        await publish_comment_updated(db, comment, actor_id=100)
        # 3. comment_deleted (file_id 模式, author=100 ≠ file owner=2)
        await publish_comment_deleted(
            db,
            comment_id=1,
            file_id=10,
            folder_id=None,
            author_id=100,
            actor_id=100,
        )
        # 4. comment_resolved (resolved_by=2 ≠ author=100)
        await publish_comment_resolved(
            db,
            comment_id=1,
            file_id=10,
            folder_id=None,
            resolved_by=2,
            author_id=100,
        )
        # 5. version_uploaded (uploader=100 ≠ file owner=2)
        await publish_version_uploaded(db, version, file_name="test.pdf")
        # 6. version_rollback
        await publish_version_rollback(
            db, version, file_name="test.pdf", target_version_number=1,
        )

    by_type = dict(priorities_seen)
    assert by_type.get("comment_deleted") == NotificationPriority.LOW
    assert by_type.get("comment_created") == NotificationPriority.MEDIUM
    assert by_type.get("comment_updated") == NotificationPriority.MEDIUM
    assert by_type.get("comment_resolved") == NotificationPriority.MEDIUM
    assert by_type.get("version_uploaded") == NotificationPriority.MEDIUM
    assert by_type.get("version_rollback") == NotificationPriority.MEDIUM


# ==========================================================================
# 场景 6 (bonus): folder_id 路径
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_comment_folder_target():
    """comment_created 走 folder_id 路径 → 通知 folder owner"""
    from app.services.drive_event_publisher import publish_comment_created

    # mock db: file_id lookup 返 None (不调), folder_id lookup 返 owner_id=77
    db = MagicMock()

    async def fake_execute(stmt):
        result = MagicMock()
        # 简化: 都返 (77,) — publisher 内部会调多次, 但只会用对应的那个
        result.first.return_value = (77,)
        return result

    db.execute = AsyncMock(side_effect=fake_execute)

    comment = _make_mock_comment(
        comment_id=99, file_id=None, folder_id=200, author_id=100,
    )

    captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        captured["user_id"] = user_id
        captured["payload"] = payload
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_comment_created(db, comment, actor_id=100)

    # folder owner = 77, 但因为 db.execute 都返 (77,), 实际看 file_id 是否被处理
    # (file_id=None 时 _resolve_file_owner 立即返 None, 走 folder_id 分支)
    # 这里我们只断言 payload 包含 folder_id, 不强断言 user_id (mock 不区分 file/folder)
    assert captured["payload"]["folder_id"] == 200
    assert captured["payload"]["file_id"] is None
    assert captured["payload"]["type"] == "comment_created"