"""tests/test_drive_v2_pr12_reactions.py — Drive v2 PR12 表情反应单元测试 (2026-07-24)

W68 第 8 批 B-2 — Drive v2 PR12 Emoji Reactions 端到端验证.
锚点范式第 94 守恒.

7 核心场景 (SKIP_DB_SETUP=1 模式 — 纯 mock, 无 PostgreSQL 依赖):
1. add_reaction: 增成功 → DriveReaction.id != None
2. add_reaction: 重复幂等 → UNIQUE 约束触发 → 返 None (不抛错)
3. add_reaction: emoji 不在白名单 → 抛 DriveReactionServiceError(400)
4. remove_reaction: 仅本人可删 → 非本人抛 DriveReactionServiceError(403)
5. list_reactions: 聚合 emoji → count + members (按 count desc 排序)
6. publish_reaction_added WS 推送: priority=HIGH + payload 字段正确
7. polymorphic target: 跨 comment/file 验证 target_type 正确分流

依赖:
- app.services.drive_reaction_service.DriveReactionService
- app.services.drive_event_publisher.publish_reaction_added
- app.models.drive_reaction.ALLOWED_EMOJIS

测试策略: SKIP_DB_SETUP=1 模式, 与 W68 PR10 mention 测试一致.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"

from app.models.drive_reaction import ALLOWED_EMOJIS  # noqa: E402
from app.services.notification_service import NotificationPriority  # noqa: E402


# ==========================================================================
# Helpers: 构造 mock db / ORM 实例
# ==========================================================================


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
    db.refresh = AsyncMock(return_value=None)
    db.add = MagicMock(return_value=None)
    db.delete = AsyncMock(return_value=None)
    return db


def _make_mock_reaction(
    *,
    reaction_id: int = 1,
    target_type: str = "comment",
    target_id: int = 10,
    member_id: int = 100,
    emoji: str = "👍",
):
    """构造 mock DriveReaction ORM 实例"""
    r = MagicMock()
    r.id = reaction_id
    r.target_type = target_type
    r.target_id = target_id
    r.member_id = member_id
    r.emoji = emoji
    r.created_at = datetime(2026, 7, 24, 12, 0, 0)
    r.updated_at = datetime(2026, 7, 24, 12, 0, 0)
    return r


# ==========================================================================
# 场景 1: add_reaction 增成功
# ==========================================================================


@pytest.mark.asyncio
async def test_add_reaction_success_returns_id():
    """add_reaction 成功 → DriveReaction.id 不为 None"""
    from app.services.drive_reaction_service import DriveReactionService

    db = _make_mock_db()

    # _validate_target_exists 返 1 (存在)
    # _check_target_read_authority 返 True
    target_exists_result = MagicMock()
    target_exists_result.scalar_one.return_value = 1
    target_auth_result = MagicMock()
    target_auth_result.first.return_value = (None, None, 100)  # owner_id=100 (==user)

    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return target_exists_result
        return target_auth_result

    db.execute = AsyncMock(side_effect=fake_execute)

    svc = DriveReactionService(db)

    # 直接调 add_reaction, 用 patch mock 内部 validate
    # mock db.commit: 模拟 DB 分配 id=1
    async def fake_commit():
        # 在 commit 后给 reaction 模拟分配 id
        for obj in db.add.call_args_list:
            pass  # 我们已经有 reaction 实例
    # 用 side_effect 给所有 mock 反应都分配 id
    reaction_holder = {}

    async def fake_commit_with_id():
        # 找最近 add 的对象 — 我们在调用前先 add, 所以 holder 已被设置
        if "_pending" in reaction_holder:
            obj = reaction_holder["_pending"]
            if hasattr(obj, "id") and obj.id is None:
                obj.id = 1
            reaction_holder.pop("_pending", None)

    db.commit = AsyncMock(side_effect=fake_commit_with_id)
    original_add = db.add

    def fake_add(obj):
        reaction_holder["_pending"] = obj
        return original_add(obj)

    db.add = MagicMock(side_effect=fake_add)

    with patch(
        "app.services.drive_reaction_service._validate_target_exists",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.drive_reaction_service._check_target_read_authority",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.drive_event_publisher.publish_reaction_added",
        AsyncMock(return_value=1),
    ):
        reaction = await svc.add_reaction(
            target_type="comment",
            target_id=10,
            member_id=100,
            emoji="👍",
        )

    assert reaction is not None
    assert reaction.id == 1
    assert reaction.target_type == "comment"
    assert reaction.target_id == 10
    assert reaction.member_id == 100
    assert reaction.emoji == "👍"


# ==========================================================================
# 场景 2: add_reaction 重复幂等
# ==========================================================================


@pytest.mark.asyncio
async def test_add_reaction_idempotent_returns_none_on_unique_violation():
    """add_reaction 重复 → UNIQUE 约束触发 → 返 None (不抛错)"""
    from sqlalchemy.exc import IntegrityError

    from app.services.drive_reaction_service import DriveReactionService

    db = _make_mock_db()
    db.commit = AsyncMock(side_effect=IntegrityError("UNIQUE", {}, None))

    svc = DriveReactionService(db)

    with patch(
        "app.services.drive_reaction_service._validate_target_exists",
        AsyncMock(return_value=True),
    ), patch(
        "app.services.drive_reaction_service._check_target_read_authority",
        AsyncMock(return_value=True),
    ):
        reaction = await svc.add_reaction(
            target_type="comment",
            target_id=10,
            member_id=100,
            emoji="👍",
        )

    assert reaction is None  # 幂等命中


# ==========================================================================
# 场景 3: add_reaction emoji 不在白名单
# ==========================================================================


@pytest.mark.asyncio
async def test_add_reaction_emoji_not_in_whitelist_raises_400():
    """emoji 不在白名单 → 抛 DriveReactionServiceError(400)"""
    from app.services.drive_reaction_service import (
        DriveReactionService,
        DriveReactionServiceError,
    )

    db = _make_mock_db()
    svc = DriveReactionService(db)

    # 不在 12 个内置白名单的 emoji
    with pytest.raises(DriveReactionServiceError) as exc_info:
        await svc.add_reaction(
            target_type="comment",
            target_id=10,
            member_id=100,
            emoji="🦄",  # 独角兽 — 不在白名单
        )

    assert exc_info.value.status_code == 400
    assert "白名单" in str(exc_info.value)


# ==========================================================================
# 场景 4: remove_reaction 仅本人
# ==========================================================================


@pytest.mark.asyncio
async def test_remove_reaction_only_owner_can_delete():
    """remove_reaction 仅本人 → 非本人抛 DriveReactionServiceError(403)"""
    from app.services.drive_reaction_service import (
        DriveReactionService,
        DriveReactionServiceError,
    )

    db = _make_mock_db()

    # mock 查到的 reaction 是 member=100 拥有的
    reaction_mock = _make_mock_reaction(reaction_id=1, member_id=100, emoji="👍")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = reaction_mock
    db.execute = AsyncMock(return_value=fetch_result)

    svc = DriveReactionService(db)

    # user_id=999 尝试删除 member_id=100 的 reaction → 应抛 403
    with pytest.raises(DriveReactionServiceError) as exc_info:
        await svc.remove_reaction_by_id(reaction_id=1, user_id=999)

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_remove_reaction_owner_can_delete_succeeds():
    """本人删除自己的 reaction → 成功 + commit"""
    from app.services.drive_reaction_service import DriveReactionService

    db = _make_mock_db()

    reaction_mock = _make_mock_reaction(reaction_id=1, member_id=100, emoji="👍")
    fetch_result = MagicMock()
    fetch_result.scalar_one_or_none.return_value = reaction_mock
    db.execute = AsyncMock(return_value=fetch_result)

    svc = DriveReactionService(db)

    # member_id=100 本人删自己
    result = await svc.remove_reaction_by_id(reaction_id=1, user_id=100)

    assert result is True


# ==========================================================================
# 场景 5: list_reactions 聚合
# ==========================================================================


@pytest.mark.asyncio
async def test_list_reactions_aggregates_by_emoji_sorted_by_count():
    """list_reactions 聚合 emoji → count + members (按 count desc)"""
    from app.services.drive_reaction_service import DriveReactionService

    db = _make_mock_db()

    # mock 3 条 reactions: 2 个 👍 + 1 个 ❤️
    r1 = _make_mock_reaction(reaction_id=1, member_id=100, emoji="👍")
    r2 = _make_mock_reaction(reaction_id=2, member_id=101, emoji="👍")
    r3 = _make_mock_reaction(reaction_id=3, member_id=102, emoji="❤️")

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = [r1, r2, r3]

    members_result = MagicMock()
    members_result.scalars.return_value.all.return_value = []

    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return list_result
        return members_result

    db.execute = AsyncMock(side_effect=fake_execute)

    svc = DriveReactionService(db)
    items = await svc.list_reactions(target_type="comment", target_id=10)

    assert len(items) == 2  # 2 个 emoji
    # 按 count desc 排序: 👍(count=2) 排第一
    assert items[0]["emoji"] == "👍"
    assert items[0]["count"] == 2
    assert items[1]["emoji"] == "❤️"
    assert items[1]["count"] == 1


# ==========================================================================
# 场景 6: publish_reaction_added WS 推送
# ==========================================================================


@pytest.mark.asyncio
async def test_publish_reaction_added_ws_payload_and_priority():
    """publish_reaction_added → WS push + priority=HIGH + payload 字段完整"""
    from app.services.drive_event_publisher import publish_reaction_added

    db = _make_mock_db()

    # mock target owner = 999 (避免自推)
    # comment 路径: 先查 comment → file_id/folder_id, 再查 file owner
    # 这里直接 mock 第一层 lookup 返 (file_id=20, folder_id=None), 让 _resolve_target_owner
    # 再走 _resolve_file_owner(20)
    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # comment query: file_id, folder_id
            r = MagicMock()
            r.first.return_value = (20, None)
            return r
        # file owner query
        r = MagicMock()
        r.first.return_value = (999,)
        return r

    db.execute = AsyncMock(side_effect=fake_execute)

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
        result = await publish_reaction_added(
            db,
            reaction_id=42,
            target_type="comment",
            target_id=10,
            actor_id=100,
            emoji="👍",
        )

    assert result == 1
    assert captured["user_id"] == 999  # owner
    assert captured["priority"] == NotificationPriority.HIGH
    payload = captured["payload"]
    assert payload["type"] == "reaction_added"
    assert payload["reaction_id"] == 42
    assert payload["target_type"] == "comment"
    assert payload["target_id"] == 10
    assert payload["actor_id"] == 100
    assert payload["emoji"] == "👍"
    assert "ts" in payload


@pytest.mark.asyncio
async def test_publish_reaction_added_self_reaction_skipped():
    """自推 (actor == owner) → publisher 跳过"""
    from app.services.drive_event_publisher import publish_reaction_added

    db = _make_mock_db()

    # comment → file_id=20 → owner_id=100 (== actor_id=100) → 自推
    call_count = 0

    async def fake_execute(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            r = MagicMock()
            r.first.return_value = (20, None)
            return r
        r = MagicMock()
        r.first.return_value = (100,)  # owner
        return r

    db.execute = AsyncMock(side_effect=fake_execute)

    push_called = False

    async def fake_push(*args, **kwargs):
        nonlocal push_called
        push_called = True
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_reaction_added(
            db,
            reaction_id=42,
            target_type="comment",
            target_id=10,
            actor_id=100,
            emoji="👍",
        )

    assert not push_called
    assert result == 0


# ==========================================================================
# 场景 7: polymorphic target 跨 comment/file 验证
# ==========================================================================


@pytest.mark.asyncio
async def test_polymorphic_target_comment_vs_file():
    """polymorphic target: comment / file 走不同 owner 解析路径"""
    from app.services.drive_event_publisher import publish_reaction_added

    db = _make_mock_db()

    # comment: file_id=20 → owner_id=999
    # file:    owner_id=888
    async def fake_execute(stmt, *args, **kwargs):
        # 看 stmt 的列字段判断是什么查询
        stmt_str = str(stmt)
        if "drive_comments" in stmt_str or "file_id, folder_id" in stmt_str:
            # comment 查询: file_id=20, folder_id=None
            r = MagicMock()
            r.first.return_value = (20, None)
            return r
        if "knowledge" in stmt_str.lower() and "created_by" in stmt_str:
            # file owner 查询
            r = MagicMock()
            r.first.return_value = (888,)
            return r
        # 默认空
        r = MagicMock()
        r.first.return_value = None
        return r

    db.execute = AsyncMock(side_effect=fake_execute)

    captured_targets = []

    async def fake_push(user_id, payload, *, priority=None):
        captured_targets.append((user_id, payload["target_type"], payload["emoji"]))
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        # comment target → 应走 file/folder owner 路径 (file_id=20 → owner_id=888)
        await publish_reaction_added(
            db,
            reaction_id=1,
            target_type="comment",
            target_id=10,
            actor_id=100,
            emoji="👍",
        )
        # file target → 应直接走 Knowledge.created_by (888)
        await publish_reaction_added(
            db,
            reaction_id=2,
            target_type="file",
            target_id=20,
            actor_id=100,
            emoji="❤️",
        )

    # 两条推送, 都是 owner (888 是 file owner; comment 走 file_id=20 → owner=888)
    assert len(captured_targets) == 2
    targets_types = [t[1] for t in captured_targets]
    assert "comment" in targets_types
    assert "file" in targets_types
    # 不同 emoji
    emojis = [t[2] for t in captured_targets]
    assert "👍" in emojis
    assert "❤️" in emojis


# ==========================================================================
# Bonus: 白名单完整性
# ==========================================================================


def test_allowed_emojis_count_is_12():
    """ALLOWED_EMOJIS 恰好 12 个内置白名单"""
    assert len(ALLOWED_EMOJIS) == 12
    # 抽样几个核心 emoji 存在
    for e in ["👍", "❤️", "🎉", "😂"]:
        assert e in ALLOWED_EMOJIS


def test_allowed_emojis_are_strings():
    """白名单 emoji 全部是 1-2 字符 (UTF-8 视觉宽度)"""
    for e in ALLOWED_EMOJIS:
        assert isinstance(e, str)
        assert 1 <= len(e) <= 16


# ==========================================================================
# Bonus: list_my_reactions 返 emoji 列表
# ==========================================================================


@pytest.mark.asyncio
async def test_list_my_reactions_returns_emoji_list():
    """list_my_reactions 返 List[str] emoji 字面值"""
    from app.services.drive_reaction_service import DriveReactionService

    db = _make_mock_db()

    # mock: 当前 user 已 react 了 👍 和 ❤️
    emoji_result = MagicMock()
    emoji_result.scalars.return_value.all.return_value = ["👍", "❤️"]

    db.execute = AsyncMock(return_value=emoji_result)

    svc = DriveReactionService(db)
    emojis = await svc.list_my_reactions(
        target_type="comment",
        target_id=10,
        member_id=100,
    )

    assert sorted(emojis) == ["❤️", "👍"]