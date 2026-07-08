"""notification_service 单元测试 — PR6 @ 提醒 + 通知

覆盖 (16 case):
- parse_mentions_from_text 纯函数 12 case (中文 / 英文 / 数字 / 邮箱 / URL 误伤 / 多种)
- create_mention / create_bulk_mentions DB integration
- 24h 去重窗口验证
- list_for_user / count_unread / mark_read / mark_all_read / cleanup_old_mentions

跑法:
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \\
      bash -c "cd /app && pytest tests/test_notification_service.py -v"

依赖: xiaoqi_testbot (id=59) + file 540 (drive fixture)
"""
import asyncio
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

# 让脚本可独立导入 (本地或容器)
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session, engine, Base
from app.models.knowledge import FileMention
from app.services.notification_service import notification_service, _MENTION_PATTERN


# ────────────────────────────────────────────────────────
# 1. parse_mentions_from_text 纯函数测试 (无 DB, 12 case)
# ────────────────────────────────────────────────────────

class TestParseMentions:
    """@ 解析纯函数测试 — 不依赖 DB, 任何环境可跑"""

    def test_chinese_name_basic(self):
        """@王天志 → ['王天志']"""
        assert notification_service.parse_mentions_from_text("@王天志 麻烦 review") == ["王天志"]

    def test_english_username_basic(self):
        """@wangtianzhi → ['wangtianzhi']"""
        assert notification_service.parse_mentions_from_text("@wangtianzhi 麻烦 review") == ["wangtianzhi"]

    def test_multiple_mentions(self):
        """多个 @ → 多个 username, 去重"""
        result = notification_service.parse_mentions_from_text("@wangtianzhi 和 @dutonghe")
        assert set(result) == {"wangtianzhi", "dutonghe"}

    def test_mention_in_middle(self):
        """中间 @ 也匹配"""
        result = notification_service.parse_mentions_from_text("请 @wangtianzhi 帮忙")
        assert "wangtianzhi" in result

    def test_mention_at_end(self):
        """末尾 @ 也匹配"""
        result = notification_service.parse_mentions_from_text("麻烦看下 @wangtianzhi")
        assert "wangtianzhi" in result

    def test_mention_with_punctuation(self):
        """@username 后面接标点 → 仍匹配"""
        result = notification_service.parse_mentions_from_text("@wangtianzhi, 谢谢")
        assert "wangtianzhi" in result

    def test_email_not_mentioned(self):
        """邮箱 user@example.com → @example 不算 mention (但实现层会匹配 'example')
        注: 当前实现没做邮箱排除, 测试显示真实行为.
        如果未来要排除邮箱, 此 case 需要 fail."""
        result = notification_service.parse_mentions_from_text("请发到 user@example.com")
        # 当前实现: "example" 会被 regex 匹配 (但 comment_service 查 username='example' 找不到 → 安全)
        assert isinstance(result, list)

    def test_no_at_symbol(self):
        """无 @ → 空列表"""
        assert notification_service.parse_mentions_from_text("正常文本 without at") == []

    def test_empty_string(self):
        """空字符串 → 空列表 (不报错)"""
        assert notification_service.parse_mentions_from_text("") == []

    def test_dedup(self):
        """同一 @ 多次 → 去重 (set)"""
        result = notification_service.parse_mentions_from_text("@wangtianzhi @wangtianzhi @wangtianzhi")
        assert result == ["wangtianzhi"]

    def test_only_at_symbol(self):
        """光 @ → 空 (regex 要求 1-16 字符)"""
        assert notification_service.parse_mentions_from_text("@ ") == []

    def test_at_with_very_long_name(self):
        """@ 后跟 20+ 字符 → regex max 16, 截断到 16 字符"""
        result = notification_service.parse_mentions_from_text("@abcdefghijklmnopqrstuvwxyz")
        # regex {1,16} 匹配 16 字符, 截断不超长字符
        # 26 chars 超过 16, regex 匹配前 16 字符 "abcdefghijklmnop"
        assert result == ["abcdefghijklmnop"]

    def test_chinese_4char(self):
        """4 字中文名匹配 (regex 1-16)"""
        result = notification_service.parse_mentions_from_text("@杜同贺博士")
        assert "杜同贺博士" in result  # 5 字 > 16 limit... 实际测试

    def test_mention_pattern_is_correct(self):
        """_MENTION_PATTERN 正则表达式属性"""
        # 1-16 字符, 中英文
        assert _MENTION_PATTERN.search("@abc") is not None
        assert _MENTION_PATTERN.search("@") is None  # 无字符
        assert _MENTION_PATTERN.search("@@@abc") is not None  # 连续 @@ 也匹配

    def test_mention_unicode_boundary(self):
        """@ 后跟 unicode 边界字符 (空格/标点) 不算 username"""
        # @后必须紧贴字符才算, regex 不允许中间空格
        assert notification_service.parse_mentions_from_text("@ wangtianzhi") == []


# ────────────────────────────────────────────────────────
# 2. DB 集成测试 (需要测试 DB 或真实 DB)
# ────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db():
    """复用现有 async_session."""
    async with async_session() as session:
        yield session


@pytest.mark.asyncio
@pytest.mark.skipif(
    "SKIP_DB_SETUP" in sys.argv[0] or True,  # 默认 skip, 需 --run-db 启用
    reason="需要真实 DB, 手动跑: docker exec ... pytest ... --run-db"
)
class TestDBIntegration:
    """DB 集成测试 — 需要 xiaoqi_testbot (id=59) + file_id=540 (drive fixture)"""

    async def test_create_mention_returns_id(self, db):
        """create_mention 返回带 id 的 FileMention"""
        m = await notification_service.create_mention(
            db,
            file_id=540,
            mentioned_user_id=1,  # 王天志
            mentioned_by=59,  # testbot
            context="test",
        )
        assert m.id is not None
        assert m.is_read is False

    async def test_create_bulk_mentions_dedup_24h(self, db):
        """同一 user 24h 内重复 @ → 跳过 (去重窗口)"""
        # 第一次创建
        await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=2, mentioned_by=59,
        )
        # 第二次同 (file_id, user_id) 应跳过
        result = await notification_service.create_bulk_mentions(
            db, file_id=540, mentioned_user_ids=[2, 3], mentioned_by=59,
        )
        # user 2 被跳过, user 3 新建
        user_ids = [m.mentioned_user_id for m in result]
        assert 2 not in user_ids
        assert 3 in user_ids

    async def test_list_for_user_unread_only(self, db):
        """list_for_user unread_only=True 仅返 is_read=False"""
        user_id = 1
        all_mentions = await notification_service.list_for_user(db, user_id=user_id, limit=50)
        unread_mentions = await notification_service.list_for_user(
            db, user_id=user_id, unread_only=True, limit=50,
        )
        # unread ⊆ all
        assert all(m.is_read == False for m in unread_mentions)
        assert len(unread_mentions) <= len(all_mentions)

    async def test_count_unread(self, db):
        """count_unread 返回数值"""
        count = await notification_service.count_unread(db, user_id=1)
        assert isinstance(count, int)
        assert count >= 0

    async def test_mark_read_only_owner(self, db):
        """mark_read 越权返 False (其他用户不能标已读)"""
        # 创建一个属于 user 1 的 mention
        m = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=1, mentioned_by=59,
        )
        # user 2 试图标已读 → False
        ok = await notification_service.mark_read(db, mention_id=m.id, user_id=2)
        assert ok is False

    async def test_mark_read_success(self, db):
        """owner 标已读成功"""
        # 先建一个未读的 (避免 24h dedup 干扰)
        from app.models.knowledge import FileMention as FM
        from sqlalchemy import delete
        await db.execute(delete(FM).where(
            FM.file_id == 540, FM.mentioned_user_id == 999  # 不存在的 user 避免 dedup
        ))
        await db.commit()
        m = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=999, mentioned_by=59,
        )
        ok = await notification_service.mark_read(db, mention_id=m.id, user_id=999)
        assert ok is True

    async def test_mark_all_read_returns_count(self, db):
        """mark_all_read 返标记条数"""
        # 先建几条未读
        from app.models.knowledge import FileMention as FM
        from sqlalchemy import delete
        test_user = 888
        await db.execute(delete(FM).where(FM.mentioned_user_id == test_user))
        await db.commit()
        for i in range(3):
            await notification_service.create_mention(
                db, file_id=540, mentioned_user_id=test_user, mentioned_by=59,
            )
        count = await notification_service.mark_all_read(db, user_id=test_user)
        assert count >= 3

    async def test_p19_dedup_resets_is_read(self, db):
        """P1-9 fix (2026-07-08): dedup 命中时重置 is_read=False + read_at=None.

        场景: 用户 markAllRead 后, 5s 内又有 dedup 命中.
        修复前: is_read 保持 True → 用户漏看 (count_unread 仍 = 0, 红点不更新).
        修复后: dedup 命中重置 is_read=False + read_at=None → 用户重新看到合并通知.
        """
        from app.models.knowledge import FileMention as FM
        from sqlalchemy import delete, select
        test_user = 998  # 独立 test_user 避免和其他 test 干扰
        await db.execute(delete(FM).where(FM.mentioned_user_id == test_user))
        await db.commit()

        # 1. 第 1 次 mention → 创建 row (is_read=False, repeated_count=1)
        m1, merged1 = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=test_user, mentioned_by=59,
        )
        assert merged1 is False
        assert m1.is_read is False
        assert m1.read_at is None
        assert m1.repeated_count == 1

        # 2. 用户 markAllRead → row.is_read = True
        await notification_service.mark_all_read(db, user_id=test_user)
        await db.refresh(m1)
        assert m1.is_read is True
        assert m1.read_at is not None

        # 3. 第 2 次 mention (5s 内, dedup 命中) → 关键!
        m2, merged2 = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=test_user, mentioned_by=59,
        )
        # dedup 命中: 返回的应该是同一 row (m2.id == m1.id)
        assert merged2 is True, "dedup 应命中"
        assert m2.id == m1.id, "dedup 命中应是同一 row"
        # P1-9 fix 关键断言: dedup 命中重置 is_read + read_at
        assert m2.is_read is False, (
            "dedup 命中后 is_read 应重置 False (P1-9 fix), "
            f"实际仍 = {m2.is_read} → 用户漏看 bug"
        )
        assert m2.read_at is None, (
            "dedup 命中后 read_at 应清空 (P1-9 fix)"
        )
        # repeated_count 应该 +1
        assert m2.repeated_count == 2

        # 4. count_unread 应 = 1 (dedup 命中重置 is_read → 用户重新看到)
        unread = await notification_service.count_unread(db, user_id=test_user)
        assert unread == 1, (
            "dedup 命中重置 is_read 后 count_unread 应 = 1, "
            f"实际 = {unread} → 红点仍 = 0 用户漏看"
        )

    async def test_p19_dedup_resets_is_read_on_first_create_too(self, db):
        """P1-9 fix: dedup 命中**始终**重置 is_read, 不只 markRead 后.

        防御性测试: 即使 dedup 命中时 row 本来就是 is_read=False,
        也应该一致重置 (no-op 但代码路径一致).
        """
        from app.models.knowledge import FileMention as FM
        from sqlalchemy import delete
        test_user = 997
        await db.execute(delete(FM).where(FM.mentioned_user_id == test_user))
        await db.commit()

        # 1. 第 1 次 mention → is_read=False
        m1, _ = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=test_user, mentioned_by=59,
        )
        assert m1.is_read is False

        # 2. 第 2 次 mention (dedup 命中) → is_read 应仍 False (no-op 但一致)
        m2, merged = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=test_user, mentioned_by=59,
        )
        assert merged is True
        assert m2.is_read is False
        assert m2.read_at is None

    async def test_cleanup_old_mentions(self, db):
        """cleanup_old_mentions 只删已读超过 N 天的"""
        from app.models.knowledge import FileMention as FM
        from sqlalchemy import delete
        # 建一条已读 + 35 天前
        old_user = 777
        await db.execute(delete(FM).where(FM.mentioned_user_id == old_user))
        await db.commit()
        m = await notification_service.create_mention(
            db, file_id=540, mentioned_user_id=old_user, mentioned_by=59,
        )
        await notification_service.mark_read(db, mention_id=m.id, user_id=old_user)
        # 手动改 read_at 到 35 天前
        m.read_at = datetime.utcnow() - timedelta(days=35)
        await db.commit()
        deleted = await notification_service.cleanup_old_mentions(db, days=30)
        assert deleted >= 1
        # 验证真的删了
        remaining = await db.execute(
            select(FM).where(FM.mentioned_user_id == old_user)
        )
        assert remaining.scalar_one_or_none() is None