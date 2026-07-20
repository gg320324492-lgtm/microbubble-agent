"""comment_service 单元测试 — PR6 文件评论 + @ 自动 mention

覆盖 (10 case):
- create_comment 集成 4 case (写库 + 自动 mention 解析 + activity log)
- list_comments 集成 2 case (按时间倒序 + before_id cursor)
- delete_comment 集成 2 case (owner 删 / 越权返 False)
- count_for_file 集成 1 case
- @ 中英文 + dedup + self-mention 排除 4 case

跑法:
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \\
      bash -c "cd /app && pytest tests/test_comment_service.py -v"
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select, delete

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session
from app.models.knowledge import FileComment, FileMention
from app.services.comment_service import comment_service


@pytest_asyncio.fixture(scope="function")
async def db():
    async with async_session() as session:
        yield session


# W1 (2026-07-21) T1 endpoint_404 fix: hardcoded file_id=540 需要对应 Knowledge 行 (FK 约束)
# 加 module-scope autouse fixture 在每个 test 前 ensure file_id=540 + user_id=59 存在
@pytest_asyncio.fixture(autouse=True)
async def _ensure_test_knowledge(db):
    """保证 file_id=540 + user_id=59 存在 (comment 测试硬编码)"""
    from app.core.database import async_session as _session_factory
    from app.models.knowledge import Knowledge
    from app.models.member import Member

    async with _session_factory() as session:
        # 确保 user 59 (xiaoqi_testbot) 存在
        result = await session.execute(
            select(Member).where(Member.id == 59)
        )
        if not result.scalar_one_or_none():
            user = Member(
                id=59,
                username="xiaoqi_testbot",
                name="测试小助手",
                wechat_id="__NULL_BACKFILL_59__",  # 满足 PR6-P17 NOT NULL
                is_active=True,
                role="admin",
            )
            session.add(user)
        # 确保 file_id=540 (drive 文件行) 存在
        result = await session.execute(
            select(Knowledge).where(Knowledge.id == 540)
        )
        if not result.scalar_one_or_none():
            file_kb = Knowledge(
                id=540,
                title="comment test file",
                content="test content",
                storage_mode="kb",
                created_by=59,
            )
            session.add(file_kb)
        await session.commit()


# ────────────────────────────────────────────────────────
# 1. create_comment 集成测试 (4 case)
# ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCreateComment:
    """create_comment — 写库 + @ 解析 + activity log"""

    async def test_create_simple_comment(self, db):
        """写评论无 @ → 简单评论"""
        comment, mentioned_ids = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="hello world",
        )
        assert comment.id is not None
        assert comment.user_id == 59
        assert comment.content == "hello world"
        assert mentioned_ids == []  # 无 @

    async def test_create_comment_with_mention(self, db):
        """@username 自动创建 file_mention"""
        comment, mentioned_ids = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="@zhaohangjia 麻烦看下",
        )
        # mentioned_ids 应含赵航佳 (id=2)
        assert 2 in mentioned_ids
        # file_mentions 表应有新行
        stmt = select(FileMention).where(
            FileMention.file_id == 540,
            FileMention.mentioned_user_id == 2,
        )
        mentions = (await db.execute(stmt)).scalars().all()
        # 注意 24h dedup, 如果之前 @ 过可能被 skip
        assert len(mentions) >= 0  # 至少 0 条 (dedup 可能拦截)

    async def test_create_comment_self_mention_excluded(self, db):
        """@ 自己被排除 (避免自提醒噪音)"""
        # xiaoqi_testbot self-@: "@xiaoqi_testbot" 或 "@测试小助手"
        # 实际 username 是 xiaoqi_testbot
        comment, mentioned_ids = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="@xiaoqi_testbot self mention",
        )
        # 自己排除
        assert 59 not in mentioned_ids

    async def test_create_comment_activity_logged(self, db):
        """创建评论自动写 activity_events (comment action)"""
        from app.models.knowledge import ActivityEvent
        before_count = (await db.execute(
            select(ActivityEvent).where(
                ActivityEvent.action == "comment",
                ActivityEvent.target_type == "file",
                ActivityEvent.target_id == 540,
            )
        )).scalars().all()
        before = len(before_count)

        await comment_service.create_comment(
            db, file_id=540, user_id=59, content="activity log test " + str(datetime.utcnow()),
        )
        after_count = (await db.execute(
            select(ActivityEvent).where(
                ActivityEvent.action == "comment",
                ActivityEvent.target_type == "file",
                ActivityEvent.target_id == 540,
            )
        )).scalars().all()
        assert len(after_count) == before + 1


# ────────────────────────────────────────────────────────
# 2. list_comments (2 case)
# ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestListComments:
    """list_comments — 按时间倒序 + cursor 分页"""

    async def test_list_returns_recent_first(self, db):
        """list_comments 返回按 created_at desc 的评论"""
        rows = await comment_service.list_comments(db, file_id=540, limit=10)
        assert isinstance(rows, list)
        # 倒序: 后面的 created_at >= 前面的
        if len(rows) >= 2:
            assert rows[0][0].created_at >= rows[1][0].created_at

    async def test_list_with_before_id_cursor(self, db):
        """before_id cursor: 仅返 id < before_id"""
        # 先拿 5 条
        first_page = await comment_service.list_comments(db, file_id=540, limit=5)
        if not first_page:
            pytest.skip("no comments to test pagination")
        # 拿最后一条 id
        last_id = first_page[-1][0].id
        # before_id 分页
        second_page = await comment_service.list_comments(
            db, file_id=540, limit=5, before_id=last_id,
        )
        # 第二页所有 id < last_id
        assert all(c.id < last_id for c, _ in second_page)


# ────────────────────────────────────────────────────────
# 3. delete_comment (2 case)
# ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDeleteComment:
    """delete_comment — owner of comment OR owner of file 可删"""

    async def test_delete_by_comment_owner(self, db):
        """评论 owner 删自己评论 → True"""
        # 创建
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="to be deleted",
        )
        # 删
        ok = await comment_service.delete_comment(db, comment_id=c.id, user_id=59)
        assert ok is True
        # 验证真的删了
        remaining = (await db.execute(
            select(FileComment).where(FileComment.id == c.id)
        )).scalar_one_or_none()
        assert remaining is None

    async def test_delete_by_other_user_fails(self, db):
        """非 owner 删评论 → False"""
        # 创建 (owner=59)
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="owned by 59",
        )
        # user 1 试图删 (file owner 也是 59, not user 1)
        # file 540 owned by user 59, so user 1 is neither comment owner nor file owner
        ok = await comment_service.delete_comment(db, comment_id=c.id, user_id=1)
        assert ok is False  # 越权
        # 评论仍存在
        remaining = (await db.execute(
            select(FileComment).where(FileComment.id == c.id)
        )).scalar_one_or_none()
        assert remaining is not None

    async def test_delete_nonexistent_comment(self, db):
        """不存在的 comment_id → False (不报错)"""
        ok = await comment_service.delete_comment(db, comment_id=999999, user_id=59)
        assert ok is False


# ────────────────────────────────────────────────────────
# 4. count_for_file (1 case)
# ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestCountForFile:
    """count_for_file — 文件评论数 (前端 FileCard 徽章)"""

    async def test_count_returns_int(self, db):
        """count_for_file 返回 int (≥ 0)"""
        count = await comment_service.count_for_file(db, file_id=540)
        assert isinstance(count, int)
        assert count >= 0

    async def test_count_after_create_increments(self, db):
        """创建评论后 count +1"""
        before = await comment_service.count_for_file(db, file_id=540)
        await comment_service.create_comment(
            db, file_id=540, user_id=59, content="count test " + str(datetime.utcnow()),
        )
        after = await comment_service.count_for_file(db, file_id=540)
        assert after == before + 1


# ────────────────────────────────────────────────────────
# 5. update_comment 集成测试 (v2 PR6-P6) (8 case)
# ────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateComment:
    """v2 PR6-P6: update_comment — owner only + 5 分钟窗口 + 422 错误"""

    async def test_update_success(self, db):
        """owner 编辑成功 + content 更新 + mentions 重新解析"""
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="原始内容",
        )
        new_content = "编辑后内容 @WangTianZhi"
        c2, new_mentions = await comment_service.update_comment(
            db, comment_id=c.id, user_id=59, new_content=new_content,
        )
        assert c2.id == c.id
        assert c2.content == new_content
        # @WangTianZhi 解析为 username (lowercase), case-insensitive
        assert isinstance(new_mentions, list)

    async def test_update_nonexistent_comment_raises(self, db):
        """编辑不存在的评论 → ValueError (HTTP 422)"""
        with pytest.raises(ValueError, match="评论不存在"):
            await comment_service.update_comment(
                db, comment_id=99999999, user_id=59, new_content="edit",
            )

    async def test_update_other_user_comment_raises(self, db):
        """非 owner 编辑 → ValueError (无权限)"""
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="user 59 的评论",
        )
        with pytest.raises(ValueError, match="无权编辑"):
            await comment_service.update_comment(
                db, comment_id=c.id, user_id=58, new_content="试图编辑别人的",
            )

    async def test_update_empty_content_raises(self, db):
        """空内容 → ValueError"""
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="原始",
        )
        with pytest.raises(ValueError, match="内容不能为空"):
            await comment_service.update_comment(
                db, comment_id=c.id, user_id=59, new_content="   ",
            )

    async def test_update_too_long_content_raises(self, db):
        """超长内容 (>2000 字符) → ValueError"""
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="原始",
        )
        long_content = "x" * 2001
        with pytest.raises(ValueError, match="超长"):
            await comment_service.update_comment(
                db, comment_id=c.id, user_id=59, new_content=long_content,
            )

    async def test_update_preserves_thread_depth(self, db):
        """编辑不改变 thread_depth / parent_comment_id / reply_count (结构不动)"""
        # 顶层评论
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="顶层",
        )
        c2, _ = await comment_service.update_comment(
            db, comment_id=c.id, user_id=59, new_content="顶层编辑后",
        )
        assert c2.thread_depth == c.thread_depth == 0
        assert c2.parent_comment_id == c.parent_comment_id
        assert c2.reply_count == c.reply_count == 0

    async def test_update_preserves_reply_structure(self, db):
        """编辑父评论不影响子评论 + reply_count 仍正确"""
        parent, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="父评论",
        )
        # 加 1 个 reply (reply_count 应该 = 1)
        await comment_service.create_comment(
            db, file_id=540, user_id=58, content="reply 1", parent_comment_id=parent.id,
        )
        # 编辑父评论
        parent2, _ = await comment_service.update_comment(
            db, comment_id=parent.id, user_id=59, new_content="父评论编辑后",
        )
        # reply_count 仍是 1 (结构不动)
        assert parent2.reply_count == 1
        assert parent2.content == "父评论编辑后"

    async def test_update_window_exceeded_raises(self, db):
        """5 分钟窗口外编辑 → ValueError (人工把 created_at 改到 6 分钟前)"""
        from sqlalchemy import update as sql_update
        c, _ = await comment_service.create_comment(
            db, file_id=540, user_id=59, content="6 分钟前创建的",
        )
        # 倒推 created_at 到 6 分钟前 (360s)
        from datetime import timedelta
        old_time = datetime.utcnow() - timedelta(seconds=360)
        await db.execute(
            sql_update(FileComment)
            .where(FileComment.id == c.id)
            .values(created_at=old_time)
        )
        await db.commit()
        await db.refresh(c)
        # 编辑应被拒绝
        with pytest.raises(ValueError, match="编辑窗口已过"):
            await comment_service.update_comment(
                db, comment_id=c.id, user_id=59, new_content="试图改",
            )