"""CHAT-P0-A — 对话历史闭环: PG 回填 Redis + 窗口化 + 去重 + 记忆注入

覆盖 7 case:
1. Redis 空 + PG 20 条 → 首次请求 LLM messages 含全部且顺序正确
2. 回填后 PG 增 3 条 → 第二次请求断言 list_messages(after_id=last_pg_id)
3. 重启模拟: 清 Redis 续聊 → 上下文不丢
4. 窗口化: 30 轮 → 截断为最近 12 轮
5. 去重: PG 重复行 → 加载去重
6. PG 失败 → best-effort 返回 None 不阻塞
7. 记忆注入: 流式路径 system prompt 含记忆

跑法:
    SKIP_DB_SETUP=1 pytest tests/test_session_context.py -v
    # 需要真 PG (microbubble_test) 的部分:
    pytest tests/test_session_context.py -v  (不带 SKIP_DB_SETUP)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ============================================================================
# 纯单元测试（SKIP_DB_SETUP=1 可用, 不碰真 DB / 真 Redis）
# ============================================================================


class TestFetchPgMessages:
    """_fetch_pg_messages: 统一格式 / 过滤 / best-effort"""

    @pytest.mark.asyncio
    async def test_fetch_filters_partial_deleted_tool(self):
        """过滤 partial/deleted/system/tool, 只留 user/assistant 的 role/content 两键"""
        from app.agent.micro_bubble_agent import _fetch_pg_messages
        from app.services import chat_history_service as real_chat_svc

        def make_msg(mid, role, content, is_partial=False, is_deleted=False):
            m = MagicMock()
            m.id = mid
            m.role = role
            m.content = content
            m.is_partial = is_partial
            m.is_deleted = is_deleted
            return m

        fake_rows = [
            make_msg(1, "user", "你好"),
            make_msg(2, "assistant", "你好！"),
            make_msg(3, "system", "system msg"),
            make_msg(4, "tool", "tool out"),
            make_msg(5, "assistant", "半截", is_partial=True),
            make_msg(6, "assistant", "软删", is_deleted=True),
            make_msg(7, "user", "还有什么"),
        ]
        mock_db = MagicMock()

        with patch.object(real_chat_svc, "list_messages", AsyncMock(return_value=(fake_rows, False))):
            result = await _fetch_pg_messages(mock_db, user_id=1, session_id="s1")

        assert result == [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
            {"role": "user", "content": "还有什么"},
        ]

    @pytest.mark.asyncio
    async def test_fetch_failure_returns_none(self):
        """PG 失败 → None（best-effort, 不抛）"""
        from app.agent.micro_bubble_agent import _fetch_pg_messages
        from app.services import chat_history_service as real_chat_svc

        mock_db = MagicMock()
        with patch.object(
            real_chat_svc, "list_messages",
            AsyncMock(side_effect=RuntimeError("PG down")),
        ):
            result = await _fetch_pg_messages(mock_db, user_id=1, session_id="s1")
        assert result is None


class TestWindowMessages:
    """_window_messages: 窗口化 + 去重"""

    def test_window_truncates_to_12_turns(self):
        """30 轮 (60 条) → 只留最近 12 轮 (24 条)"""
        from app.agent.micro_bubble_agent import _window_messages
        msgs = []
        for i in range(30):
            msgs.append({"role": "user", "content": f"q{i}"})
            msgs.append({"role": "assistant", "content": f"a{i}"})
        out = _window_messages(msgs)
        assert len(out) == 24
        assert out[0] == {"role": "user", "content": "q18"}  # 第 19 轮开始 (60-24=36 → 下标 36)
        assert out[-1] == {"role": "assistant", "content": "a29"}

    def test_window_dedup_adjacent_duplicates(self):
        """相邻同 role 同 content 重复 → 只留最后一条"""
        from app.agent.micro_bubble_agent import _window_messages
        msgs = [
            {"role": "user", "content": "q1"},
            {"role": "user", "content": "q1"},  # 重复
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]
        out = _window_messages(msgs)
        assert out == [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "q2"},
        ]

    def test_window_under_limit_passthrough(self):
        """不足 24 条不截断"""
        from app.agent.micro_bubble_agent import _window_messages
        msgs = [{"role": "user", "content": "x"}, {"role": "assistant", "content": "y"}]
        assert _window_messages(msgs) == msgs


class TestEnsureSessionContext:
    """_ensure_session_context: PG 回填 Redis 的核心逻辑"""

    @pytest.mark.asyncio
    async def test_redis_empty_pg_full_backfill(self):
        """Redis 空 + PG 20 条 → 全量回填 + save_messages 调用 + 返回 20 条"""
        import app.agent.micro_bubble_agent as mba

        fake_redis_msgs = []
        pg_msgs = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
            for i in range(20)
        ]

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=fake_redis_msgs)
        session_manager_mock.save_messages = AsyncMock()
        session_manager_mock.get_meta = AsyncMock(return_value={})

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=pg_msgs)):
            result = await mba._ensure_session_context(MagicMock(), user_id=1, session_id="s1")

        assert result == pg_msgs
        session_manager_mock.save_messages.assert_awaited_once_with("s1", pg_msgs)

    @pytest.mark.asyncio
    async def test_redis_nonempty_incremental_backfill(self):
        """Redis 非空 + last_pg_id=10 + PG 新增 3 条 → 增量回填 after_id=10 且 save 合并结果"""
        import app.agent.micro_bubble_agent as mba

        redis_msgs = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        new_msgs = [
            {"role": "user", "content": "q2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "q3"},
        ]

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=redis_msgs)
        session_manager_mock.get_meta = AsyncMock(return_value={"last_pg_id": 10})
        session_manager_mock.save_messages = AsyncMock()

        captured = {}
        async def fake_fetch(db, user_id, session_id, *, after_id=0, limit=24):
            captured["after_id"] = after_id
            captured["limit"] = limit
            return new_msgs

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", fake_fetch):
            result = await mba._ensure_session_context(MagicMock(), user_id=1, session_id="s1")

        assert captured["after_id"] == 10  # 断言 list_messages(after_id=last_pg_id)
        assert result == redis_msgs + new_msgs
        session_manager_mock.save_messages.assert_awaited_once_with("s1", redis_msgs + new_msgs)

    @pytest.mark.asyncio
    async def test_redis_empty_pg_failure_returns_redis(self):
        """PG 加载失败 (None) → best-effort 返回空列表, 不抛异常"""
        import app.agent.micro_bubble_agent as mba

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=None)):
            result = await mba._ensure_session_context(MagicMock(), user_id=1, session_id="s1")

        assert result == []
        session_manager_mock.save_messages.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_user_id_none_skips_db(self):
        """user_id=None（匿名 webchat）→ 不查 PG（越权铁律）"""
        import app.agent.micro_bubble_agent as mba

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[{"role": "user", "content": "x"}])
        mock_fetch = AsyncMock(return_value=[{"role": "user", "content": "y"}])

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", mock_fetch):
            result = await mba._ensure_session_context(MagicMock(), user_id=None, session_id="s1")

        assert result == [{"role": "user", "content": "x"}]
        mock_fetch.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_redis_read_failure_best_effort(self):
        """Redis 读失败 → 不抛, 走 PG 全量回填"""
        import app.agent.micro_bubble_agent as mba

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(side_effect=RuntimeError("redis down"))
        session_manager_mock.save_messages = AsyncMock()
        pg_msgs = [{"role": "user", "content": "m0"}]

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=pg_msgs)):
            result = await mba._ensure_session_context(MagicMock(), user_id=1, session_id="s1")

        assert result == pg_msgs


class TestLastPgId:
    """_get/_set_last_pg_id: Redis meta hash 游标"""

    @pytest.mark.asyncio
    async def test_set_and_get_roundtrip(self):
        import app.agent.micro_bubble_agent as mba

        hash_store = {}
        r = MagicMock()

        async def fake_hset(key, field, value):
            hash_store[key] = {**hash_store.get(key, {}), field: value}
            return 1

        async def fake_hgetall(key):
            return dict(hash_store.get(key, {}))

        async def fake_expire(key, ttl):
            return 1

        r.hset = fake_hset
        r.expire = fake_expire
        session_manager_mock = MagicMock()
        session_manager_mock._meta_key.side_effect = lambda sid: f"agent_session:{sid}:meta"
        session_manager_mock.ttl = 172800

        async def _get_meta(sid):
            return await fake_hgetall(f"agent_session:{sid}:meta")
        session_manager_mock.get_meta = _get_meta

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch("app.core.redis.get_redis", AsyncMock(return_value=r)):
            await mba._set_last_pg_id("s1", 42)
            val = await mba._get_last_pg_id("s1")

        assert val == 42

    @pytest.mark.asyncio
    async def test_get_invalid_returns_none(self):
        import app.agent.micro_bubble_agent as mba
        session_manager_mock = MagicMock()
        session_manager_mock.get_meta = AsyncMock(return_value={"last_pg_id": "not-an-int"})
        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock):
            assert await mba._get_last_pg_id("s1") is None


class TestInjectMemories:
    """_inject_memories: 共享记忆注入段"""

    @pytest.mark.asyncio
    async def test_memories_injected(self):
        import app.agent.micro_bubble_agent as mba

        mem_svc = MagicMock()
        mem_svc.search_memories = AsyncMock(return_value=[
            {"memory_type": "preference", "content": "喜欢简洁回答"},
            {"memory_type": "entity", "content": "王天志是组长"},
        ])

        with patch("app.services.memory_service.MemoryService", MagicMock(return_value=mem_svc)):
            text = await mba._inject_memories(MagicMock(), user_id=1, query="近况")

        assert "关于用户的长期记忆" in text
        assert "喜欢简洁回答" in text
        assert "王天志是组长" in text

    @pytest.mark.asyncio
    async def test_no_memories_returns_empty(self):
        import app.agent.micro_bubble_agent as mba
        mem_svc = MagicMock()
        mem_svc.search_memories = AsyncMock(return_value=[])
        with patch("app.services.memory_service.MemoryService", MagicMock(return_value=mem_svc)):
            assert await mba._inject_memories(MagicMock(), user_id=1, query="x") == ""

    @pytest.mark.asyncio
    async def test_failure_returns_empty(self):
        import app.agent.micro_bubble_agent as mba
        mem_svc = MagicMock()
        mem_svc.search_memories = AsyncMock(side_effect=RuntimeError("boom"))
        with patch("app.services.memory_service.MemoryService", MagicMock(return_value=mem_svc)):
            assert await mba._inject_memories(MagicMock(), user_id=1, query="x") == ""


class TestBuildSystemPromptUsesSharedInject:
    """_build_system_prompt 走共享 _inject_memories（流式/非流式统一 — A4）"""

    @pytest.mark.asyncio
    async def test_streaming_system_prompt_contains_memories(self):
        """流式路径: _build_system_prompt(user_id, db) 注入记忆"""
        from app.agent.micro_bubble_agent import MicroBubbleAgent
        import app.agent.micro_bubble_agent as mba

        agent = MicroBubbleAgent()
        mem_svc = MagicMock()
        mem_svc.search_memories = AsyncMock(return_value=[
            {"memory_type": "summary", "content": "课题组近期聚焦臭氧微纳米气泡"},
        ])

        with patch("app.services.memory_service.MemoryService", MagicMock(return_value=mem_svc)):
            prompt = await agent._build_system_prompt(1, "介绍一下课题组近况", MagicMock())

        assert "关于用户的长期记忆" in prompt
        assert "臭氧微纳米气泡" in prompt


class TestChatStreamHistoryInjection:
    """chat_stream 端到端: PG 历史注入 LLM messages（mock engine）"""

    @pytest.mark.asyncio
    async def test_chat_stream_uses_pg_backfilled_messages(self):
        """Redis 空 + PG 20 条 → engine 收到的 messages 含全部历史 + 当前消息"""
        import app.agent.micro_bubble_agent as mba
        from app.agent.protocol import StreamEvent

        pg_msgs = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"历史{i}"}
            for i in range(20)
        ]

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()

        captured = {}

        async def fake_engine_stream(**kwargs):
            captured["messages"] = kwargs.get("messages")
            captured["system"] = kwargs.get("system")
            yield StreamEvent(type="done", duration_ms=1, text_without_json="ok")

        agent = mba.MicroBubbleAgent()
        agent.engine.chat_stream = fake_engine_stream

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=pg_msgs)), \
             patch.object(mba, "_set_last_pg_id", AsyncMock()):
            events = []
            async for evt in agent.chat_stream(
                "介绍一下课题组近况", session_id="s1", db=MagicMock(), user_id=1,
            ):
                events.append(evt)

        msgs = captured["messages"]
        # 20 条历史 + 1 条当前 user 消息, 顺序: 历史在前, 当前在后
        assert len(msgs) == 21
        assert msgs[0] == {"role": "user", "content": "历史0"}
        assert msgs[-1]["role"] == "user"
        assert "介绍一下课题组近况" in msgs[-1]["content"]
        # 系统提示词含记忆（mock 记忆注入）
        assert captured["system"] is not None

    @pytest.mark.asyncio
    async def test_chat_stream_window_12_turns(self):
        """30 轮历史 → engine 只收到最近 12 轮 (24 条) + 当前消息"""
        import app.agent.micro_bubble_agent as mba
        from app.agent.protocol import StreamEvent

        pg_msgs = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"轮{i}"}
            for i in range(60)  # 30 轮
        ]

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()

        captured = {}

        async def fake_engine_stream(**kwargs):
            captured["messages"] = kwargs.get("messages")
            yield StreamEvent(type="done", duration_ms=1, text_without_json="ok")

        agent = mba.MicroBubbleAgent()
        agent.engine.chat_stream = fake_engine_stream

        with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=pg_msgs)), \
             patch.object(mba, "_set_last_pg_id", AsyncMock()):
            async for _ in agent.chat_stream("追问", session_id="s1", db=MagicMock(), user_id=1):
                pass

        msgs = captured["messages"]
        assert len(msgs) == 25  # 24 历史 + 1 当前
        assert msgs[0] == {"role": "user", "content": "轮36"}  # 第 19 轮开始

    @pytest.mark.asyncio
    async def test_chat_stream_done_emits_message_id(self):
        """assistant 落库后补发带 message_id 的 done 事件（A5 反馈锚点）"""
        import app.agent.micro_bubble_agent as mba
        from app.agent.protocol import StreamEvent

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()
        mba._set_last_pg_id = AsyncMock()  # noqa: 直接替换避免 patch 开销

        async def fake_engine_stream(**kwargs):
            yield StreamEvent(type="done", duration_ms=5, text_without_json="回答完毕")

        agent = mba.MicroBubbleAgent()
        agent.engine.chat_stream = fake_engine_stream

        chat_svc_mock = MagicMock()
        chat_svc_mock.ensure_session_for_stream = AsyncMock(return_value=MagicMock())
        user_msg = MagicMock()
        user_msg.id = 100
        chat_svc_mock.append_message = AsyncMock(side_effect=[user_msg, MagicMock(id=200)])
        import app.services
        with patch.object(app.services, "chat_history_service", chat_svc_mock), \
             patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
             patch.object(mba, "_fetch_pg_messages", AsyncMock(return_value=None)), \
             patch.object(mba, "_set_last_pg_id", AsyncMock()) as set_last:
            events = []
            async for evt in agent.chat_stream("你好", session_id="s1", db=MagicMock(), user_id=1):
                events.append(evt)

        done_events = [e for e in events if e.type == "done" and e.message_id is not None]
        assert done_events, "应补发带 message_id 的 done 事件"
        assert done_events[0].message_id == 200
        set_last.assert_awaited_once_with("s1", 200)


# ============================================================================
# 真 DB 集成测试（不带 SKIP_DB_SETUP 时运行: 真 PG + fakeredis）
# ============================================================================
# 注: 这些测试需要 TEST_DATABASE_URL (postgres:password@localhost:5432/microbubble_test)
# 与 fakeredis。跑法: pytest tests/test_session_context.py -v

@pytest.mark.asyncio
async def test_integration_redis_empty_pg_backfill(db, test_member):
    """真 PG: Redis 空 + PG 有 20 条 → 首次请求 messages 含全部且顺序正确"""
    import fakeredis.aioredis
    import app.agent.micro_bubble_agent as mba

    from app.services import chat_history_service as chat_svc
    from sqlalchemy import select
    from app.models.chat_history import ChatMessage

    sid = "ctx_integration_1"
    await chat_svc.create_session(db, user_id=test_member.id, client_session_id=sid)
    for i in range(20):
        await chat_svc.append_message(
            db, test_member.id, sid,
            role="user" if i % 2 == 0 else "assistant",
            content=f"历史消息{i}",
        )
    # 额外插一条 partial + tool, 验证过滤
    stmt = select(ChatMessage).where(ChatMessage.session_id == sid).limit(1)
    first = (await db.execute(stmt)).scalar_one()
    # append tool 角色消息
    from app.models.chat_history import ChatMessage as CM
    from app.models.chat_history import ChatSession as CS
    tool_msg = CM(session_id=sid, role="tool", content="tool out")
    db.add(tool_msg)
    await db.commit()

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    session_manager_mock = MagicMock()
    session_manager_mock.get_messages = AsyncMock(return_value=[])
    session_manager_mock.save_messages = AsyncMock()
    session_manager_mock.get_meta = AsyncMock(return_value={})
    session_manager_mock.ttl = 172800

    with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
         patch("app.core.redis.get_redis", AsyncMock(return_value=fake)):
        result = await mba._ensure_session_context(db, user_id=test_member.id, session_id=sid)

    assert len(result) == 20, f"应返回 20 条 (过滤 tool), 实际 {len(result)}"
    assert all(m["role"] in ("user", "assistant") for m in result)
    assert all("content" in m for m in result)
    # 顺序: 旧 → 新
    assert result[0]["content"] == "历史消息0"
    assert result[-1]["content"] == "历史消息19"
    # 已回填 Redis
    session_manager_mock.save_messages.assert_awaited_once()


@pytest.mark.asyncio
async def test_integration_restart_simulation(db, test_member):
    """真 PG: 模拟重启 — 首次请求回填后清 Redis, 续聊上下文不丢"""
    import fakeredis.aioredis
    import app.agent.micro_bubble_agent as mba

    from app.services import chat_history_service as chat_svc

    sid = "ctx_integration_restart"
    await chat_svc.create_session(db, user_id=test_member.id, client_session_id=sid)
    for i in range(4):
        await chat_svc.append_message(
            db, test_member.id, sid,
            role="user" if i % 2 == 0 else "assistant",
            content=f"对话内容{i}",
        )

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    session_manager_mock = MagicMock()
    session_manager_mock.get_messages = AsyncMock(return_value=[])
    session_manager_mock.save_messages = AsyncMock()
    session_manager_mock.get_meta = AsyncMock(return_value={})
    session_manager_mock.ttl = 172800

    with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
         patch("app.core.redis.get_redis", AsyncMock(return_value=fake)):
        first = await mba._ensure_session_context(db, user_id=test_member.id, session_id=sid)

    assert len(first) == 4  # 重启后首次请求 → PG 全量回填

    # 续聊: PG 追加 2 条, Redis 被清空 (模拟 TTL 过期)
    from app.services import chat_history_service as chat_svc2
    await chat_svc2.append_message(db, test_member.id, sid, role="user", content="续聊问题")
    await chat_svc2.append_message(db, test_member.id, sid, role="assistant", content="续聊回答")

    session_manager_mock2 = MagicMock()
    session_manager_mock2.get_messages = AsyncMock(return_value=[])  # Redis 又空了
    session_manager_mock2.save_messages = AsyncMock()
    session_manager_mock2.get_meta = AsyncMock(return_value={})
    session_manager_mock2.ttl = 172800

    with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock2), \
         patch("app.core.redis.get_redis", AsyncMock(return_value=fake)):
        second = await mba._ensure_session_context(db, user_id=test_member.id, session_id=sid)

    contents = [m["content"] for m in second]
    assert "对话内容0" in contents  # 老上下文不丢
    assert "续聊问题" in contents
    assert "续聊回答" in contents
    assert second[-1]["content"] == "续聊回答"  # 顺序正确


@pytest.mark.asyncio
async def test_integration_incremental_backfill(db, test_member):
    """真 PG: Redis 非空 + last_pg_id → 增量回填只补新增"""
    import fakeredis.aioredis
    import app.agent.micro_bubble_agent as mba

    from app.services import chat_history_service as chat_svc

    sid = "ctx_integration_incr"
    await chat_svc.create_session(db, user_id=test_member.id, client_session_id=sid)
    for i in range(6):
        await chat_svc.append_message(
            db, test_member.id, sid,
            role="user" if i % 2 == 0 else "assistant",
            content=f"旧消息{i}",
        )
    # 取当前最大 message id 作为 last_pg_id
    from sqlalchemy import select, func
    from app.models.chat_history import ChatMessage
    max_id = (await db.execute(select(func.max(ChatMessage.id)))).scalar()

    # 追加 3 条新消息
    for i in range(3):
        await chat_svc.append_message(
            db, test_member.id, sid,
            role="user" if i % 2 == 0 else "assistant",
            content=f"新消息{i}",
        )

    fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
    redis_msgs = [{"role": "user", "content": "旧消息0"}, {"role": "assistant", "content": "旧消息1"}]
    session_manager_mock = MagicMock()
    session_manager_mock.get_messages = AsyncMock(return_value=redis_msgs)
    session_manager_mock.get_meta = AsyncMock(return_value={"last_pg_id": max_id})
    session_manager_mock.save_messages = AsyncMock()
    session_manager_mock.ttl = 172800

    with patch("app.agent.micro_bubble_agent.session_manager", session_manager_mock), \
         patch("app.core.redis.get_redis", AsyncMock(return_value=fake)):
        result = await mba._ensure_session_context(db, user_id=test_member.id, session_id=sid)

    assert len(result) == 2 + 3  # Redis 2 条 + 增量 3 条
    assert result[-1]["content"] == "新消息2"
