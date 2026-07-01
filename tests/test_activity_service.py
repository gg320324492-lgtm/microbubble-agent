"""activity_service 单元测试 — PR6 活动动态流

覆盖 (10 case):
- to_dict 纯函数 4 case (含 meta JSON 解析 + actor_name 注入)
- log DB 集成 4 case (合法 action / 非法 action / target_name 冗余 / metadata 持久化)
- feed 集成 2 case (cursor 分页 + actor_ids 过滤)

跑法:
    docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 \\
      bash -c "cd /app && pytest tests/test_activity_service.py -v"
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import async_session
from app.models.knowledge import ActivityEvent
from app.services.activity_service import (
    activity_service,
    VALID_ACTIONS,
    VALID_TARGET_TYPES,
)


# ────────────────────────────────────────────────────────
# 1. to_dict 纯函数测试 (无 DB, 4 case)
# ────────────────────────────────────────────────────────

class TestToDict:
    """to_dict 纯函数 — 不依赖 DB"""

    def _make_event(self, action="upload", target_type="file", meta=None):
        """构造 ActivityEvent (绕过 ORM __init__ 限制)"""
        evt = ActivityEvent()
        evt.id = 1
        evt.actor_id = 59
        evt.action = action
        evt.target_type = target_type
        evt.target_id = 540
        evt.target_name = "test.txt"
        evt.meta_data = meta or {"content_preview": "test"}
        evt.created_at = datetime(2026, 7, 1, 14, 0, 0)
        return evt

    def test_to_dict_basic(self):
        """to_dict 基础转换"""
        evt = self._make_event()
        d = activity_service.to_dict(evt, actor_name="测试小助手")
        assert d["id"] == 1
        assert d["action"] == "upload"
        assert d["target_type"] == "file"
        assert d["actor_name"] == "测试小助手"
        assert d["target_name"] == "test.txt"
        assert d["metadata"]["content_preview"] == "test"

    def test_to_dict_isoformat(self):
        """created_at 转 ISO 字符串"""
        evt = self._make_event()
        d = activity_service.to_dict(evt)
        assert d["created_at"] == "2026-07-01T14:00:00"

    def test_to_dict_meta_string_json(self):
        """metadata 是字符串时自动 JSON 解析 (容错)"""
        evt = self._make_event(meta='{"comment_id": 5}')
        d = activity_service.to_dict(evt)
        assert d["metadata"]["comment_id"] == 5

    def test_to_dict_meta_string_invalid(self):
        """metadata 字符串无法 JSON 解析 → 返空 dict"""
        evt = self._make_event(meta="not-valid-json{")
        d = activity_service.to_dict(evt)
        assert d["metadata"] == {}

    def test_to_dict_actor_name_none(self):
        """actor_name=None 时不报错"""
        evt = self._make_event()
        d = activity_service.to_dict(evt, actor_name=None)
        assert d["actor_name"] is None


# ────────────────────────────────────────────────────────
# 2. constants 测试
# ────────────────────────────────────────────────────────

class TestConstants:
    """VALID_ACTIONS / VALID_TARGET_TYPES 稳定性"""

    def test_valid_actions_complete(self):
        """所有 11 个 action 都在白名单"""
        assert "upload" in VALID_ACTIONS
        assert "rename" in VALID_ACTIONS
        assert "move" in VALID_ACTIONS
        assert "delete" in VALID_ACTIONS
        assert "restore" in VALID_ACTIONS
        assert "share" in VALID_ACTIONS
        assert "version_restore" in VALID_ACTIONS
        assert "comment" in VALID_ACTIONS
        assert "mention" in VALID_ACTIONS
        assert "star" in VALID_ACTIONS
        assert "unstar" in VALID_ACTIONS

    def test_valid_target_types(self):
        """3 个 target_type 合法"""
        assert VALID_TARGET_TYPES == frozenset({"file", "folder", "comment"})


# ────────────────────────────────────────────────────────
# 3. DB 集成测试 (cursor 分页 + actor 过滤)
# ────────────────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def db():
    async with async_session() as session:
        yield session


@pytest.mark.asyncio
class TestFeedDB:
    """feed cursor 分页 + actor_ids 过滤 — 集成测试"""

    async def test_feed_with_actor_ids_filter(self, db):
        """feed(actor_ids=[59]) 仅返 testbot 触发的活动"""
        events = await activity_service.feed(
            db,
            actor_ids=[59],  # xiaoqi_testbot
            limit=50,
        )
        # 全部是 actor_id=59
        assert all(e.actor_id == 59 for e in events)

    async def test_feed_cursor_pagination(self, db):
        """feed(before_id=X) 仅返 id < X 的事件 (cursor 分页)"""
        # 拿前 5 条
        first_page = await activity_service.feed(db, limit=5)
        assert len(first_page) >= 1
        # 用最后一条 id 当 cursor
        last_id = first_page[-1].id
        # 拿 before_id=last_id 的下一页
        second_page = await activity_service.feed(db, limit=5, before_id=last_id)
        # 第二页所有 id < last_id
        assert all(e.id < last_id for e in second_page)

    async def test_feed_all_no_filter(self, db):
        """feed() 默认返所有活动"""
        events = await activity_service.feed(db, limit=100)
        assert isinstance(events, list)

    async def test_feed_limit_respected(self, db):
        """feed(limit=N) 最多返 N 条"""
        events = await activity_service.feed(db, limit=3)
        assert len(events) <= 3


@pytest.mark.asyncio
class TestLogDB:
    """log DB 集成测试"""

    async def test_log_valid_action(self, db):
        """合法 action 写入并返 ActivityEvent"""
        evt = await activity_service.log(
            db,
            actor_id=59,
            action="upload",
            target_type="file",
            target_id=540,
            target_name="test.txt",
            metadata={"size": 1024},
        )
        await db.commit()
        assert evt is not None
        assert evt.id is not None
        assert evt.action == "upload"

    async def test_log_invalid_action_returns_none(self, db):
        """非法 action (白名单外) → 返 None, 不写库"""
        evt = await activity_service.log(
            db,
            actor_id=59,
            action="hacker_destroy",  # 不在 VALID_ACTIONS
            target_type="file",
            target_id=540,
        )
        await db.commit()
        assert evt is None  # logger.warning + 返 None

    async def test_log_invalid_target_type(self, db):
        """非法 target_type → 返 None"""
        evt = await activity_service.log(
            db,
            actor_id=59,
            action="upload",
            target_type="random_type",  # 不在白名单
        )
        await db.commit()
        assert evt is None

    async def test_log_target_name_persisted(self, db):
        """target_name 冗余存储 (目标删后仍能展示)"""
        evt = await activity_service.log(
            db,
            actor_id=59,
            action="rename",
            target_type="file",
            target_id=540,
            target_name="old_name.pdf",
            metadata={"old_name": "old", "new_name": "new"},
        )
        await db.commit()
        # refresh from DB
        await db.refresh(evt)
        assert evt.target_name == "old_name.pdf"

    async def test_log_metadata_persisted(self, db):
        """metadata JSONB 正确存储"""
        meta = {"comment_id": 5, "mention_count": 2, "preview": "test"}
        evt = await activity_service.log(
            db,
            actor_id=59,
            action="comment",
            target_type="file",
            target_id=540,
            target_name="x.txt",
            metadata=meta,
        )
        await db.commit()
        await db.refresh(evt)
        # JSONB → dict
        assert evt.meta_data["comment_id"] == 5
        assert evt.meta_data["mention_count"] == 2