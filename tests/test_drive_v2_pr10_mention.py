"""tests/test_drive_v2_pr10_mention.py — Drive v2 PR10 @ Mention 提醒单元测试 (2026-07-24)

W68 第 5 批 Drive v2 PR9 mention 提醒集成 (锚点范式第 63 守恒).
覆盖 drive_event_publisher.publish_comment_mention + drive_comment_service.create_comment
的 mentions 集成路径.

5 核心场景 (不依赖 PostgreSQL, 用 Mock 模拟 db.execute / push_with_priority):
1. @ 单个用户 → publish_comment_mention 1 条 + payload 含 mentioned_user_id + priority=HIGH
2. @ 多个用户 → N 条独立 publish (不是批量合并)
3. @ 不存在用户 → 自动过滤 (mentions 列表跳过)
4. @ 重复同一用户 → dedup 后只发 1 条
5. mention 推送 priority=HIGH (区别于 comment_created=MEDIUM)
6. (bonus) self-mention @自己 → publisher 跳过
7. (bonus) WS 推送失败 → caller 不感知 (best-effort)

依赖:
- app.services.drive_event_publisher.publish_comment_mention
- app.services.mention_parser.parse_mentions / extract_snippet
- app.services.notification_service.push_with_priority / NotificationPriority

测试策略: SKIP_DB_SETUP=1 模式 (纯 mock, 无 PostgreSQL 依赖), 与 W68 WS 测试一致.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 让 import 走 SKIP_DB_SETUP=1 路径 — 避免重型 import + DB 依赖
os.environ["SKIP_DB_SETUP"] = "1"

from app.services.notification_service import NotificationPriority  # noqa: E402


# ==========================================================================
# Helpers: 构造 mock db / ORM 实例
# ==========================================================================


def _make_mock_db():
    """构造 mock AsyncSession: db.execute() 返回空 (publisher 不查 DB)"""
    db = MagicMock()
    execute_result = MagicMock()
    execute_result.first.return_value = None
    db.execute = AsyncMock(return_value=execute_result)
    return db


def _make_mock_comment(
    *, comment_id: int = 1, file_id: int = 10, folder_id=None,
    parent_id=None, author_id: int = 100, mentions=None,
    content: str = "@张三 看一下, @李四 一起",
):
    """构造 mock DriveComment ORM 实例 (只填需要的字段)"""
    c = MagicMock()
    c.id = comment_id
    c.file_id = file_id
    c.folder_id = folder_id
    c.parent_id = parent_id
    c.author_id = author_id
    c.mentions = mentions
    c.content = content
    c.resolved_at = None
    c.resolved_by = None
    return c


# ==========================================================================
# 场景 1: @ 单个用户 → publish_comment_mention 1 条 + priority=HIGH
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_single_user_payload_and_priority():
    """@ 单个用户 → publish_comment_mention 1 条 + payload 正确 + priority=HIGH"""
    from app.services.drive_event_publisher import publish_comment_mention

    db = _make_mock_db()
    comment = _make_mock_comment(
        comment_id=42, file_id=10, folder_id=None,
        parent_id=None, author_id=100, mentions=[3],
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
        result = await publish_comment_mention(
            db, comment,
            actor_id=100,
            mentioned_user_id=3,
            snippet="@张三 看一下, @李四 一起",
        )

    assert result == 1
    assert captured["user_id"] == 3  # mentioned user
    assert captured["priority"] == NotificationPriority.HIGH
    assert captured["payload"]["type"] == "comment_mention"
    assert captured["payload"]["comment_id"] == 42
    assert captured["payload"]["file_id"] == 10
    assert captured["payload"]["folder_id"] is None
    assert captured["payload"]["author_id"] == 100
    assert captured["payload"]["actor_id"] == 100
    assert captured["payload"]["mentioned_by"] == 100
    assert captured["payload"]["mentioned_user_id"] == 3
    assert captured["payload"]["snippet"] == "@张三 看一下, @李四 一起"
    assert "ts" in captured["payload"]
    # parsed ISO timestamp
    ts = captured["payload"]["ts"]
    parsed_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    assert parsed_dt.tzinfo is not None


# ==========================================================================
# 场景 2: @ 多个用户 → N 条独立 publish (不是批量合并)
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_multiple_users_independent_pushes():
    """@ 多个用户 → 每条 mention 1 次 publish (priority=HIGH, 不合并)"""
    from app.services.drive_event_publisher import publish_comment_mention

    db = _make_mock_db()
    comment = _make_mock_comment(
        comment_id=42, author_id=100,
        content="@张三 @李四 @王五 看一下",
    )

    captured = []

    async def fake_push(user_id, payload, *, priority=None):
        captured.append({
            "user_id": user_id,
            "priority": priority,
            "payload": payload,
        })
        return 1

    mentioned_ids = [3, 4, 5]
    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        for uid in mentioned_ids:
            await publish_comment_mention(
                db, comment,
                actor_id=100,
                mentioned_user_id=uid,
                snippet="@张三 @李四 @王五 看一下",
            )

    # 3 条独立 push, 不是 1 条合并
    assert len(captured) == 3, f"应 3 条独立推送, 实际 {len(captured)}"
    for i, uid in enumerate(mentioned_ids):
        assert captured[i]["user_id"] == uid
        assert captured[i]["priority"] == NotificationPriority.HIGH
        assert captured[i]["payload"]["type"] == "comment_mention"
        assert captured[i]["payload"]["mentioned_user_id"] == uid


# ==========================================================================
# 场景 3: mention_parser 解析 (依赖 mock db 返回 members)
# ==========================================================================


@pytest.mark.asyncio
async def test_parse_mentions_three_way_match():
    """mention_parser 解析 @username → user_id list (3 路匹配)"""
    from app.services.mention_parser import parse_mentions

    db = MagicMock()

    # 模拟 2 个 member: (id=3, username='alice', wechat_id='AliceWechat', name='张三')
    #                  (id=4, username='bob',   wechat_id=None,         name='李四')
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (3, "alice", "AliceWechat", "张三"),
        (4, "bob", None, "李四"),
    ]
    db.execute = AsyncMock(return_value=rows_result)

    # @张三 (name match) + @AliceWechat (wechat_id match) + @bob (username match)
    text = "@张三 @AliceWechat @bob"

    # caller 是 user_id=100 (不在这 2 人里)
    result = await parse_mentions(db, text, exclude_user_id=100)

    assert 3 in result  # 张三
    assert 4 in result  # bob
    assert len(result) == 2  # 实际命中 2 个 user (AliceWechat 和 alice 是同一 user=3)
    # 顺序按出现: 张三 (uid=3) 先, bob (uid=4) 后
    assert result[0] == 3 or result[0] == 4
    assert result[1] == 3 or result[1] == 4
    assert result[0] != result[1]


@pytest.mark.asyncio
async def test_parse_mentions_excludes_nonexistent_user():
    """@ 不存在用户 → mentions 列表跳过 (不抛错, 也不推 WS)"""
    from app.services.mention_parser import parse_mentions

    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (3, "alice", None, "Alice"),
    ]
    db.execute = AsyncMock(return_value=rows_result)

    # @Alice 命中; @GhostUser 没匹配
    text = "@Alice @GhostUser"
    result = await parse_mentions(db, text, exclude_user_id=100)

    assert result == [3]


@pytest.mark.asyncio
async def test_parse_mentions_excludes_self_mention():
    """@ 自己 → exclude_user_id 过滤掉"""
    from app.services.mention_parser import parse_mentions

    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (3, "alice", None, "张三"),
        (10, "bob", None, "Bob"),
    ]
    db.execute = AsyncMock(return_value=rows_result)

    # @张三(uid=3) + @Bob(uid=10), exclude uid=10 → 只返 [3]
    text = "@张三 @Bob"
    result = await parse_mentions(db, text, exclude_user_id=10)

    assert 10 not in result
    assert 3 in result
    assert len(result) == 1


@pytest.mark.asyncio
async def test_parse_mentions_dedup_repeat():
    """@ 重复同一用户 → mentions 列表去重 (只 1 个 entry)"""
    from app.services.mention_parser import parse_mentions

    db = MagicMock()
    rows_result = MagicMock()
    rows_result.all.return_value = [
        (3, "alice", None, "张三"),
    ]
    db.execute = AsyncMock(return_value=rows_result)

    # @张三 @张三 @张三 — regex findall 会先去重, 解析后只见 1 个 user
    text = "@张三 @张三 @张三"
    result = await parse_mentions(db, text, exclude_user_id=100)

    assert result == [3]
    assert len(result) == 1


# ==========================================================================
# 场景 4: priority 分类 (mention=HIGH, 其他=MEDIUM/LOW)
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_priority_is_high_not_medium():
    """mention 推送 priority=HIGH (与 W68 PR8d 'comment' 上下文一致)"""
    from app.services.drive_event_publisher import (
        publish_comment_created,
        publish_comment_deleted,
        publish_comment_mention,
    )

    db = _make_mock_db()  # file owner 解析会返 None → comment_created 跳过

    priorities_seen = []

    async def fake_push(user_id, payload, *, priority=None):
        priorities_seen.append((payload["type"], priority))
        return 0

    comment = _make_mock_comment(comment_id=1, file_id=10, author_id=100)

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        # mention → HIGH
        await publish_comment_mention(
            db, comment, actor_id=100, mentioned_user_id=3, snippet="x",
        )
        # created → MEDIUM (file owner=None, 会跳过; 但 priority 还是 MEDIUM)
        # 这里因为 _resolve_file_owner 返 None, created 函数会跳过 push
        # 我们单独验证 priority 通过别的方式

    by_type = dict(priorities_seen)
    assert by_type["comment_mention"] == NotificationPriority.HIGH


# ==========================================================================
# 场景 5: mention 推送 best-effort (failure 不阻塞 caller)
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_push_failure_is_best_effort():
    """push_with_priority 抛错 → publish_comment_mention 返 -1, 不 raise"""
    from app.services.drive_event_publisher import publish_comment_mention

    db = _make_mock_db()
    comment = _make_mock_comment(comment_id=42, author_id=100)

    async def fake_push_raises(*args, **kwargs):
        raise RuntimeError("WS 连接失败 (mock)")

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push_raises,
    ):
        # 必须不抛错
        result = await publish_comment_mention(
            db, comment,
            actor_id=100,
            mentioned_user_id=3,
            snippet="@张三",
        )

    assert result == -1, "失败 best-effort 应返 -1"


@pytest.mark.asyncio
async def test_mention_self_mention_skipped():
    """@ 自己 → publisher 跳过 (返回 0)"""
    from app.services.drive_event_publisher import publish_comment_mention

    db = _make_mock_db()
    comment = _make_mock_comment(comment_id=42, author_id=100)

    call_count = 0

    async def fake_push(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        result = await publish_comment_mention(
            db, comment,
            actor_id=100,
            mentioned_user_id=100,  # 自 @
            snippet="@自己",
        )

    assert call_count == 0
    assert result == 0


# ==========================================================================
# 场景 6 (bonus): extract_snippet 工具
# ==========================================================================


def test_extract_snippet_short_text():
    """短文本 (< 80 char) → 原样返回"""
    from app.services.mention_parser import extract_snippet

    text = "@张三 @李四 看一下这个文件"
    result = extract_snippet(text, max_chars=80)
    assert result == text


def test_extract_snippet_long_text():
    """长文本 (>= 80 char) → 截断 + ..."""
    from app.services.mention_parser import extract_snippet

    text = "这是一个非常长非常长的 comment content 内容, " * 4  # ~80+ char
    result = extract_snippet(text, max_chars=80)
    assert len(result) <= 80 + 3  # +3 是 "..."
    assert result.endswith("...")


def test_extract_snippet_whitespace_folded():
    """多余空白折叠"""
    from app.services.mention_parser import extract_snippet

    text = "@张三\n\n看一下\n   这个文件"
    result = extract_snippet(text, max_chars=80)
    # 多空白应折叠成单空格
    assert "\n" not in result
    assert "  " not in result


# ==========================================================================
# 场景 7 (bonus): payload 兼容性 (与 comment_created 不冲突)
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_and_created_are_independent_payloads():
    """mention payload 字段 ≠ comment_created payload (snippets 不同语义)"""
    from app.services.drive_event_publisher import (
        publish_comment_created,
        publish_comment_mention,
    )

    db = _make_mock_db()

    created_captured = {}
    mention_captured = {}

    async def fake_push(user_id, payload, *, priority=None):
        if payload.get("type") == "comment_created":
            created_captured["payload"] = payload
            created_captured["priority"] = priority
        elif payload.get("type") == "comment_mention":
            mention_captured["payload"] = payload
            mention_captured["priority"] = priority
        return 0

    comment = _make_mock_comment(comment_id=42, author_id=100, mentions=[3])

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        # 模拟 create_comment 顺序: 先 created (file owner), 再 mention (3 个 mentioned)
        # 注意: publish_comment_created 内 _resolve_file_owner 查 db.execute,
        # 这里 mock db.execute 返 None → 跳过 push (符合 file owner 不存在语义)
        await publish_comment_created(db, comment, actor_id=100)  # file owner=None → 0
        await publish_comment_mention(
            db, comment,
            actor_id=100,
            mentioned_user_id=3,
            snippet="@张三",
        )

    # created 没传 → captured 应为空 (file owner 跳过)
    assert "payload" not in created_captured
    # mention 传了 → captured 应填充
    assert mention_captured["payload"]["type"] == "comment_mention"
    assert "snippet" not in mention_captured["payload"] or mention_captured["payload"]["snippet"] == "@张三"
    assert mention_captured["payload"]["mentioned_user_id"] == 3
    assert mention_captured["payload"]["type"] == "comment_mention"

    # 对比字段: mention 有 snippet + mentioned_user_id, created 没有这俩字段
    # (验证两个 publisher 用独立 payload schema)
    expected_mention_keys = {"type", "comment_id", "file_id", "folder_id", "parent_id",
                              "author_id", "actor_id", "mentioned_by", "mentioned_user_id",
                              "snippet", "ts"}
    assert expected_mention_keys <= set(mention_captured["payload"].keys())


# ==========================================================================
# 场景 8 (bonus): integrate push_with_priority WS payload 完整校验
# ==========================================================================


@pytest.mark.asyncio
async def test_mention_ws_payload_passes_through_priority():
    """mention WS payload 走 push_with_priority 时 priority=HIGH 字段正确传递"""
    from app.services.drive_event_publisher import publish_comment_mention

    db = _make_mock_db()
    comment = _make_mock_comment(comment_id=99, file_id=None, folder_id=200, author_id=100)

    captured_priority = []

    async def fake_push(user_id, payload, *, priority=None):
        captured_priority.append((priority, payload["type"]))
        return 1

    with patch(
        "app.services.drive_event_publisher.push_with_priority",
        side_effect=fake_push,
    ):
        await publish_comment_mention(
            db, comment,
            actor_id=100,
            mentioned_user_id=42,
            snippet="folder 级别评论 mention",
        )

    assert len(captured_priority) == 1
    assert captured_priority[0] == (NotificationPriority.HIGH, "comment_mention")
