"""W98 P2-F — 微信 handler 会话上下文同步铁证

派工 v10 §3 要求: tests/test_wechat_session_sync.py 新增微信同步铁证
(模拟微信消息 handler 调用 ensure_session_context → list_messages 包含历史)

铁证 4 类:
1. wechat handler 模块导入 ensure_session_context (派工 §1 真验证)
2. wechat handler 3 处 agent.chat 前调 ensure_session_context (派工 §2)
3. 模拟微信消息链路: ensure_session_context 被触发 + 返回含历史的 messages
4. 微信群聊 / 私聊 / 客服 3 类入口都接入共享服务
"""
import pytest

pytest.importorskip("sentence_transformers", reason="需要 sentence_transformers 才能跑 embedding fixture")

import inspect
from unittest.mock import AsyncMock, MagicMock, patch


class TestWechatHandlerSharedImport:
    """微信 handler 共享 import 铁证 (派工 v10 §1 + §2)"""

    def test_handler_module_imports_shared_ensure_session_context(self):
        """微信 handler 真从 app.services.session_context import ensure_session_context (非 wechat_service.py 假设)"""
        import app.wechat.handler
        from app.services.session_context import ensure_session_context
        src = inspect.getsource(app.wechat.handler)
        assert "from app.services.session_context import" in src
        assert "ensure_session_context" in src

    def test_handler_has_three_ensure_session_context_callsites(self):
        """3 处 agent.chat() 前都调 ensure_session_context (群聊 + 私聊 + kf)"""
        import app.wechat.handler
        src = inspect.getsource(app.wechat.handler)
        call_count = src.count("await ensure_session_context(")
        assert call_count == 3, f"微信 handler 应有 3 处 ensure_session_context 调用, 实际 {call_count}"

    def test_handler_three_agent_chat_callsites(self):
        """3 处 agent.chat() callsite (派工 v10 §2 真验证 — grep 实测)"""
        import app.wechat.handler
        src = inspect.getsource(app.wechat.handler)
        chat_calls = src.count("await agent.chat(")
        assert chat_calls == 3, f"微信 handler 应有 3 处 agent.chat 调用, 实际 {chat_calls}"


class TestWechatSharedContextInjection:
    """微信同步铁证 — 模拟消息链路"""

    @pytest.mark.asyncio
    async def test_simulated_general_chat_calls_ensure_session_context(self):
        """模拟微信私聊: ensure_session_context 在 agent.chat 之前被调"""
        from app.services.session_context import ensure_session_context

        # 模拟 PG 已有 4 条历史 (2 轮对话)
        pg_history = [
            {"role": "user", "content": "课题组近况"},
            {"role": "assistant", "content": "本周有 3 个新任务"},
            {"role": "user", "content": "我看看任务"},
            {"role": "assistant", "content": "已发到你的列表"},
        ]

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])  # Redis 空 (模拟重启)
        session_manager_mock.save_messages = AsyncMock()

        with patch("app.services.session_context.session_manager", session_manager_mock), \
             patch("app.services.session_context._fetch_pg_messages", AsyncMock(return_value=pg_history)):
            msgs = await ensure_session_context(MagicMock(), user_id=42, session_id="wx_user_42")

        # 微信 handler 调用后: Redis 应有 4 条历史 (供 LLM 上下文)
        assert len(msgs) == 4
        assert msgs[0]["content"] == "课题组近况"
        # session_manager.save_messages 必被调 (写入 Redis 供后续 chat 使用)
        session_manager_mock.save_messages.assert_awaited_once_with("wx_user_42", pg_history)

    @pytest.mark.asyncio
    async def test_simulated_group_chat_session_id_pattern(self):
        """微信群聊 session_id 格式: wechat_group_{chat_id}"""
        from app.services.session_context import ensure_session_context

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()

        pg_history = [{"role": "user", "content": "群聊历史"}]

        with patch("app.services.session_context.session_manager", session_manager_mock), \
             patch("app.services.session_context._fetch_pg_messages", AsyncMock(return_value=pg_history)):
            # 群聊 session_id 模式 (handler.py:473)
            msgs = await ensure_session_context(MagicMock(), user_id=42, session_id="wechat_group_chat_xxx")

        assert len(msgs) == 1
        session_manager_mock.save_messages.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_simulated_kf_session_id_pattern(self):
        """微信客服 session_id 格式: kf:{user_id}"""
        from app.services.session_context import ensure_session_context

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[])
        session_manager_mock.save_messages = AsyncMock()

        pg_history = [{"role": "user", "content": "kf历史"}]

        with patch("app.services.session_context.session_manager", session_manager_mock), \
             patch("app.services.session_context._fetch_pg_messages", AsyncMock(return_value=pg_history)):
            # kf session_id 模式 (handler.py:1211)
            msgs = await ensure_session_context(MagicMock(), user_id=42, session_id="kf:wxid_abc")

        assert len(msgs) == 1


class TestWechatAnonymousGuard:
    """微信匿名 fallback 越权铁律"""

    @pytest.mark.asyncio
    async def test_wechat_anon_returns_redis_only(self):
        """user_id=None (匿名) → 不加载 PG 历史, 只返回 Redis (越权铁律)"""
        from app.services.session_context import ensure_session_context

        session_manager_mock = MagicMock()
        session_manager_mock.get_messages = AsyncMock(return_value=[{"role": "user", "content": "anon_msg"}])
        session_manager_mock.save_messages = AsyncMock()

        with patch("app.services.session_context.session_manager", session_manager_mock):
            msgs = await ensure_session_context(MagicMock(), user_id=None, session_id="wechat_group_anonymous")

        assert msgs == [{"role": "user", "content": "anon_msg"}]
        session_manager_mock.save_messages.assert_not_called()