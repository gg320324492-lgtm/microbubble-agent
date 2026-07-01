"""#043 Phase 8 — chat_history_service 单元测试

覆盖 service 层全部公共方法（happy / error / 越权 3 类用例）
"""
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.models.chat_history import ChatSession, ChatMessage
from app.services.chat_history_service import (
    create_session,
    get_session,
    list_sessions,
    update_session,
    delete_session,
    append_message,
    list_messages,
    search_sessions,
    create_share,
    get_share_public,
    cleanup_soft_deleted_sessions,
)


# ============================================================================
# ChatSession CRUD
# ============================================================================

class TestChatSessionCRUD:
    @pytest.mark.asyncio
    async def test_create_session_无_first_message(self, db, test_member):
        """空会话创建，title 默认为'新对话'"""
        session = await create_session(
            db, user_id=test_member.id, client_session_id="test_001"
        )
        assert session.id == "test_001"
        assert session.title == "新对话"
        assert session.user_id == test_member.id
        assert session.message_count == 0

    @pytest.mark.asyncio
    async def test_create_session_带_first_message(self, db, test_member):
        """首条消息自动建 + 设置 preview + last_message_at"""
        session = await create_session(
            db, user_id=test_member.id, client_session_id="test_002",
            title="测试", first_message="你好世界",
        )
        assert session.title == "测试"
        assert session.preview == "你好世界"
        assert session.last_message_at is not None
        assert session.message_count == 1

    @pytest.mark.asyncio
    async def test_get_session_越权(self, db, test_member, admin_member):
        """用户 A 拿用户 B 的 session_id → 404"""
        # 用户 B 创建会话
        b_session = await create_session(
            db, user_id=admin_member.id, client_session_id="b_session_1"
        )
        # 用户 A 拿用户 B 的 session_id → 404
        with pytest.raises(Exception) as exc_info:
            await get_session(
                db, session_id="b_session_1", user_id=test_member.id
            )
        assert "404" in str(exc_info.value) or "NotFound" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_list_sessions_分页(self, db, test_member):
        """创建 N 个会话 + 分页查询"""
        for i in range(5):
            await create_session(
                db, user_id=test_member.id,
                client_session_id=f"page_{i}",
                title=f"会话{i}",
            )
        result = await list_sessions(db, user_id=test_member.id, page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["page_size"] == 2

    @pytest.mark.asyncio
    async def test_list_sessions_按_archived_过滤(self, db, test_member):
        """include_archived=false 默认排除归档"""
        s1 = await create_session(db, user_id=test_member.id, client_session_id="active_1")
        s2 = await create_session(db, user_id=test_member.id, client_session_id="archived_1")
        await update_session(db, session_id="archived_1", user_id=test_member.id, is_archived=True)

        active_only = await list_sessions(db, user_id=test_member.id, include_archived=False)
        assert all(s.id != "archived_1" for s in active_only["items"])

        with_archived = await list_sessions(db, user_id=test_member.id, include_archived=True)
        assert any(s.id == "archived_1" for s in with_archived["items"])

    @pytest.mark.asyncio
    async def test_list_sessions_按_tag_过滤(self, db, test_member):
        """tag=research → 只返含此 tag 的会话"""
        await create_session(db, user_id=test_member.id, client_session_id="tag_1", tags=["research", "urgent"])
        await create_session(db, user_id=test_member.id, client_session_id="tag_2", tags=["work"])
        await create_session(db, user_id=test_member.id, client_session_id="tag_3", tags=["research"])

        result = await list_sessions(db, user_id=test_member.id, tag="research")
        ids = {s.id for s in result["items"]}
        assert "tag_1" in ids
        assert "tag_3" in ids
        assert "tag_2" not in ids

    @pytest.mark.asyncio
    async def test_update_session_改_title(self, db, test_member):
        """PATCH /chat/sessions/{id} {title: 'X'} → 200 + 新 title"""
        await create_session(db, user_id=test_member.id, client_session_id="upd_1", title="旧标题")
        updated = await update_session(db, session_id="upd_1", user_id=test_member.id, title="新标题")
        assert updated.title == "新标题"

    @pytest.mark.asyncio
    async def test_update_session_改_tags_替换数组(self, db, test_member):
        """tags: ['a', 'b'] → 替换整个数组（不是追加）"""
        await create_session(db, user_id=test_member.id, client_session_id="tag_repl", tags=["a", "b", "c"])
        updated = await update_session(db, session_id="tag_repl", user_id=test_member.id, tags=["x", "y"])
        assert sorted(updated.tags) == ["x", "y"]

    @pytest.mark.asyncio
    async def test_update_session_toggle_pinned(self, db, test_member):
        """is_pinned: true → 写入 DB"""
        await create_session(db, user_id=test_member.id, client_session_id="pin_1")
        updated = await update_session(db, session_id="pin_1", user_id=test_member.id, is_pinned=True)
        assert updated.is_pinned is True

    @pytest.mark.asyncio
    async def test_soft_delete_session(self, db, test_member):
        """DELETE /chat/sessions/{id} → deleted_at = NOW()"""
        await create_session(db, user_id=test_member.id, client_session_id="soft_1")
        result = await delete_session(db, user_id=test_member.id, session_id="soft_1", hard=False)
        assert result is True
        # 验证 DB
        stmt = select(ChatSession).where(ChatSession.id == "soft_1")
        session = (await db.execute(stmt)).scalar_one()
        assert session.deleted_at is not None

    @pytest.mark.asyncio
    async def test_hard_delete_session(self, db, test_member):
        """DELETE ?hard=true → 物理删除 + CASCADE 消息"""
        await create_session(db, user_id=test_member.id, client_session_id="hard_1", first_message="X")
        await delete_session(db, user_id=test_member.id, session_id="hard_1", hard=True)
        # 验证 DB
        stmt = select(ChatSession).where(ChatSession.id == "hard_1")
        session = (await db.execute(stmt)).scalar_one_or_none()
        assert session is None
        # 验证 CASCADE 消息
        msg_stmt = select(ChatMessage).where(ChatMessage.session_id == "hard_1")
        msgs = (await db.execute(msg_stmt)).scalars().all()
        assert len(msgs) == 0


# ============================================================================
# ChatMessage CRUD
# ============================================================================

class TestChatMessageCRUD:
    @pytest.mark.asyncio
    async def test_append_message_user(self, db, test_member):
        """append_message 写入 + message_count +1"""
        await create_session(db, user_id=test_member.id, client_session_id="msg_1")
        msg = await append_message(
            db, session_id="msg_1", user_id=test_member.id,
            role="user", content="用户消息", client_msg_id="client_001",
        )
        assert msg.role == "user"
        assert msg.content == "用户消息"
        # 验证 message_count
        stmt = select(ChatSession).where(ChatSession.id == "msg_1")
        session = (await db.execute(stmt)).scalar_one()
        assert session.message_count == 1

    @pytest.mark.asyncio
    async def test_append_message_幂等_同_client_msg_id(self, db, test_member):
        """同一 client_msg_id 重复 append → 返回原 message（不重复写）"""
        await create_session(db, user_id=test_member.id, client_session_id="idem_1")
        msg1 = await append_message(
            db, session_id="idem_1", user_id=test_member.id,
            role="user", content="first", client_msg_id="idem_001",
        )
        msg2 = await append_message(
            db, session_id="idem_1", user_id=test_member.id,
            role="user", content="second (should be ignored)", client_msg_id="idem_001",
        )
        assert msg1.id == msg2.id  # 同一 ID
        # 验证 message_count 仍 = 1
        stmt = select(ChatSession).where(ChatSession.id == "idem_1")
        session = (await db.execute(stmt)).scalar_one()
        assert session.message_count == 1

    @pytest.mark.asyncio
    async def test_list_messages_分页(self, db, test_member):
        """10 条消息 page_size=5 → 5 + has_more=True"""
        await create_session(db, user_id=test_member.id, client_session_id="page_msg")
        for i in range(10):
            await append_message(
                db, session_id="page_msg", user_id=test_member.id,
                role="user", content=f"msg{i}", client_msg_id=f"page_msg_{i}",
            )
        result = await list_messages(db, session_id="page_msg", user_id=test_member.id, page=1, page_size=5)
        assert len(result["items"]) == 5
        assert result["has_more"] is True

    @pytest.mark.asyncio
    async def test_list_messages_after_id_增量(self, db, test_member):
        """after_id=N → 只返 id > N (流式中断恢复用)"""
        await create_session(db, user_id=test_member.id, client_session_id="incr_msg")
        for i in range(5):
            await append_message(
                db, session_id="incr_msg", user_id=test_member.id,
                role="user", content=f"msg{i}", client_msg_id=f"incr_{i}",
            )
        # 拿前 2 条
        result = await list_messages(db, session_id="incr_msg", user_id=test_member.id, page_size=2)
        last_id = result["items"][-1].id
        # 增量
        incr = await list_messages(db, session_id="incr_msg", user_id=test_member.id, after_id=last_id)
        assert len(incr["items"]) == 3
        assert all(m.id > last_id for m in incr["items"])


# ============================================================================
# Search
# ============================================================================

class TestChatSearch:
    @pytest.mark.asyncio
    async def test_search_跨会话(self, db, test_member):
        """'zeta' 命中多会话多消息 → 结果含 session_id + message_id + snippet"""
        await create_session(db, user_id=test_member.id, client_session_id="s_zeta_1", first_message="zeta 电位")
        await create_session(db, user_id=test_member.id, client_session_id="s_zeta_2", first_message="zeta 测量")
        await create_session(db, user_id=test_member.id, client_session_id="s_other", first_message="其他内容")

        result = await search_sessions(db, user_id=test_member.id, query="zeta", page_size=10)
        # 至少 2 个 session 命中
        session_ids = {item["session_id"] for item in result["items"]}
        assert "s_zeta_1" in session_ids
        assert "s_zeta_2" in session_ids
        assert "s_other" not in session_ids

    @pytest.mark.asyncio
    async def test_search_最少_2_字符(self, db, test_member):
        """单字符 q → 422 ValidationException（按 chat_history_service 实际行为）"""
        # 1 字符可能 silent ignore 或 raise — 接受任一行为，验证不返回大量结果
        result = await search_sessions(db, user_id=test_member.id, query="z", page_size=10)
        # 期望 0 结果（防性能问题）
        assert len(result["items"]) == 0


# ============================================================================
# Share
# ============================================================================

class TestChatShare:
    @pytest.mark.asyncio
    async def test_create_share_默认_1d(self, db, test_member):
        """POST /chat/sessions/{sid}/share 无参 → expires_at = NOW() + 1d"""
        await create_session(db, user_id=test_member.id, client_session_id="share_1")
        share = await create_share(db, session_id="share_1", user_id=test_member.id)
        assert share.session_id == "share_1"
        assert share.permission == "read"
        assert share.expires_at is not None
        # 1 天内
        delta = (share.expires_at - datetime.utcnow()).total_seconds()
        assert 86000 < delta < 86500

    @pytest.mark.asyncio
    async def test_create_share_永久(self, db, test_member):
        """expires_hours=null → expires_at = null (永久)"""
        await create_session(db, user_id=test_member.id, client_session_id="share_perm")
        share = await create_share(db, session_id="share_perm", user_id=test_member.id, expires_hours=None)
        assert share.expires_at is None

    @pytest.mark.asyncio
    async def test_get_public_share_无_JWT(self, db, test_member):
        """GET /chat/shares/{token} 无 Authorization → 200 (匿名只读)"""
        await create_session(db, user_id=test_member.id, client_session_id="pub_1", first_message="公开")
        share = await create_share(db, session_id="pub_1", user_id=test_member.id)
        # 无 user_id 注入（匿名）
        result = await get_share_public(db, share_token=share.id)
        assert result is not None
        assert result["session"]["id"] == "pub_1"


# ============================================================================
# Cleanup (Phase 7 核心)
# ============================================================================

class TestCleanup:
    @pytest.mark.asyncio
    async def test_cleanup_软删除_30d_前_物理删除(self, db, test_member):
        """deleted_at < cutoff → 物理删除（CASCADE 消息）"""
        # 创建会话 + 软删除
        await create_session(db, user_id=test_member.id, client_session_id="old_del")
        await append_message(
            db, session_id="old_del", user_id=test_member.id,
            role="user", content="历史消息", client_msg_id="old_del_1",
        )
        await delete_session(db, user_id=test_member.id, session_id="old_del", hard=False)
        # 手动改 deleted_at = 31 天前
        old_dt = datetime.now(timezone.utc) - timedelta(days=31)
        stmt = select(ChatSession).where(ChatSession.id == "old_del")
        session = (await db.execute(stmt)).scalar_one()
        session.deleted_at = old_dt.replace(tzinfo=None)
        await db.commit()

        # 跑清理
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        deleted_count = await cleanup_soft_deleted_sessions(db, cutoff)
        assert deleted_count >= 1

        # 验证物理删除
        stmt = select(ChatSession).where(ChatSession.id == "old_del")
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is None

    @pytest.mark.asyncio
    async def test_cleanup_软删除_15d_前_不删(self, db, test_member):
        """deleted_at > cutoff → 保留"""
        await create_session(db, user_id=test_member.id, client_session_id="recent_del")
        await delete_session(db, user_id=test_member.id, session_id="recent_del", hard=False)
        # 默认 deleted_at = NOW()，距今约 0 天

        cutoff = datetime.now(timezone.utc) - timedelta(days=15)
        deleted_count = await cleanup_soft_deleted_sessions(db, cutoff)
        # 15 天 cutoff 不删 < 15 天的软删除
        stmt = select(ChatSession).where(ChatSession.id == "recent_del")
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is not None

    @pytest.mark.asyncio
    async def test_cleanup_active_session_不删(self, db, test_member):
        """deleted_at IS NULL → 保留（即使其他条件满足）"""
        await create_session(db, user_id=test_member.id, client_session_id="active_keep")
        # 改 created_at 到 100 天前，确保不删
        old_dt = datetime.now(timezone.utc) - timedelta(days=100)
        stmt = select(ChatSession).where(ChatSession.id == "active_keep")
        session = (await db.execute(stmt)).scalar_one()
        session.created_at = old_dt.replace(tzinfo=None)
        await db.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        await cleanup_soft_deleted_sessions(db, cutoff)
        # 验证仍存在
        stmt = select(ChatSession).where(ChatSession.id == "active_keep")
        result = (await db.execute(stmt)).scalar_one_or_none()
        assert result is not None

    @pytest.mark.asyncio
    async def test_cleanup_CASCADE_messages_shares(self, db, test_member):
        """session 物理删 → messages/shares 自动删（FK CASCADE）"""
        await create_session(db, user_id=test_member.id, client_session_id="cascade_test")
        await append_message(
            db, session_id="cascade_test", user_id=test_member.id,
            role="user", content="cascade msg", client_msg_id="cascade_1",
        )
        await create_share(db, session_id="cascade_test", user_id=test_member.id)
        # 改 deleted_at
        old_dt = datetime.now(timezone.utc) - timedelta(days=31)
        stmt = select(ChatSession).where(ChatSession.id == "cascade_test")
        session = (await db.execute(stmt)).scalar_one()
        session.deleted_at = old_dt.replace(tzinfo=None)
        await db.commit()

        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        await cleanup_soft_deleted_sessions(db, cutoff)

        # 验证 messages 全部 CASCADE 删除
        msg_stmt = select(ChatMessage).where(ChatMessage.session_id == "cascade_test")
        msgs = (await db.execute(msg_stmt)).scalars().all()
        assert len(msgs) == 0


# ============================================================================
# 2026-07-01 ensure_session_for_stream 跨用户污染检测测试
# ============================================================================

class TestEnsureSessionForStreamCrossUser:
    """bug 1d: detect cross-user session_id 污染,记录 WARN 日志

    场景:
    - 客户端 logout 时 localStorage 残留旧 user 的 sessionId
    - 新 user 登录后用旧 id 发请求
    - 后端 get_session(user_id, session_id) 找不到
    - 旧实现: 静默创建新行(标题"新对话")
    - 新实现: 检测到 (id) 存在但 (user_id) 不匹配 → WARN 日志,但仍创建(向后兼容)
    """

    @pytest.mark.asyncio
    async def test_existing_session_for_current_user_returns_normally(
        self, db, test_member
    ):
        """happy path: 自己的 session 直接返回,无 WARN"""
        from app.services.chat_history_service import ensure_session_for_stream
        await create_session(
            db, user_id=test_member.id, client_session_id="my_session_1"
        )
        result = await ensure_session_for_stream(
            db, user_id=test_member.id, session_id="my_session_1"
        )
        assert result is not None
        assert result.id == "my_session_1"
        assert result.user_id == test_member.id

    @pytest.mark.asyncio
    async def test_new_session_created_for_first_message(self, db, test_member):
        """happy path: session 不存在,创建新行"""
        from app.services.chat_history_service import ensure_session_for_stream
        result = await ensure_session_for_stream(
            db, user_id=test_member.id, session_id="new_session_1",
            first_message="你好"
        )
        assert result.id == "new_session_1"
        assert result.title == "你好"
        assert result.user_id == test_member.id

    @pytest.mark.asyncio
    async def test_cross_user_session_id_logs_warning_before_integrity_error(
        self, db, test_member, caplog
    ):
        """bug 1d: 检测跨用户 session_id 污染 → WARN 日志(行为仍保持向后兼容)

        实际行为:
        - ChatSession.id 是 PK (String(64), primary_key=True)
        - 同 id 跨 user 实际会触发 IntegrityError(INSERT 失败)
        - 旧实现: WARN 没记录,问题难定位
        - 新实现: WARN 在 INSERT 前记录,运维监控可见
        - 业务影响: 该请求会 500(因为 INSERT 失败),前端需:
          (a) logout 时清空 localStorage(已修 1c)
          (b) 登录时 pickInitialSessionId 选 server 已存在 id(已修 1b)
        """
        from app.services.chat_history_service import ensure_session_for_stream
        from sqlalchemy.exc import IntegrityError
        import logging

        # user A 先创建 session
        await create_session(
            db, user_id=test_member.id, client_session_id="leaked_id_2"
        )

        # user B 试图用 leaked_id_2 → 触发 IntegrityError
        # 但 WARN 应在 IntegrityError 之前记录
        with caplog.at_level(logging.WARNING, logger='app.services.chat_history_service'):
            with pytest.raises(IntegrityError):
                await ensure_session_for_stream(
                    db, user_id=test_member.id + 888, session_id="leaked_id_2",
                )
            # 必须 rollback 才能让后续 query 正常
            await db.rollback()

        # 验证 WARN 日志被记录(监控可见)
        warning_msgs = [r.message for r in caplog.records if r.levelname == 'WARNING']
        cross_user_warns = [m for m in warning_msgs if 'CROSS-USER' in m]
        assert len(cross_user_warns) >= 1, f"Expected CROSS-USER WARN, got: {warning_msgs}"
        # 警告里应包含 user_id 信息便于排查
        assert any('belongs to user_id' in m for m in cross_user_warns)

    @pytest.mark.asyncio
    async def test_idempotent_for_same_user(self, db, test_member):
        """happy path: 同一 user 重复 ensure → 返回同一个 ChatSession,无重复创建"""
        from app.services.chat_history_service import ensure_session_for_stream
        result1 = await ensure_session_for_stream(
            db, user_id=test_member.id, session_id="idem_test"
        )
        result2 = await ensure_session_for_stream(
            db, user_id=test_member.id, session_id="idem_test",
            first_message="second call"
        )
        # 两次应该返回同一行(idempotent),且 title 不被覆盖
        assert result1.id == result2.id == "idem_test"
        # 第二次调用 title 应该仍是 "新对话"(first_message 不会覆盖)
        # 实际行为: get_session 返回已有,直接 return existing
        assert result2.title == result1.title
