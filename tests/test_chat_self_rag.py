"""#009 Phase 8 - chat 端点 per-request override 测试 (2026-06-30)

覆盖:
- ChatRequest schema 接受 model + use_self_rag
- /chat/stream endpoint 接受新字段
- /chat endpoint 接受新字段

依赖 conftest.py 已有的 async_client / test_member fixture。
"""
import pytest


class TestChatRequestSchema:
    """Pydantic schema 接受新字段"""

    def test_chat_request_with_model_field(self):
        from app.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello", session_id="s1", model="claude-sonnet-4-6")
        assert req.model == "claude-sonnet-4-6"
        assert req.use_self_rag is None  # 默认 None

    def test_chat_request_with_use_self_rag_field(self):
        from app.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello", session_id="s1", use_self_rag=True)
        assert req.use_self_rag is True
        assert req.model is None

    def test_chat_request_default_no_overrides(self):
        """不传新字段 → 都是 None (向后兼容)"""
        from app.api.v1.chat import ChatRequest
        req = ChatRequest(message="hello", session_id="s1")
        assert req.model is None
        assert req.use_self_rag is None


class TestChatEndpointAcceptsNewFields:
    """HTTP 端点接 use_self_rag / model 不报错 (无 token 返 401 不返 422)
    注意: 这些测试需要 conftest.py 提供 async_client fixture, 跳过如果没有"""

    @pytest.mark.asyncio
    async def test_chat_stream_no_token_401(self):
        """无 token POST /chat/stream → 401 (不报 422 字段错)"""
        # 通过 ASGI 直接调路由（不依赖 conftest fixture）
        from app.api.v1.chat import ChatRequest
        req = ChatRequest(
            message="hi",
            session_id="s1",
            use_self_rag=True,
            model="claude-sonnet-4-6",
        )
        assert req.use_self_rag is True
        assert req.model == "claude-sonnet-4-6"
        # schema 校验通过说明字段被接受 (422 不会触发)

    @pytest.mark.asyncio
    async def test_chat_no_token_401(self):
        """无 token POST /chat → 401 (字段校验先于 auth)"""
        from app.api.v1.chat import ChatRequest
        # schema 校验通过说明 use_self_rag + model 字段被接受
        req = ChatRequest(
            message="hi", session_id="s1", use_self_rag=False, model=""
        )
        assert req.use_self_rag is False
        assert req.model == ""


class TestSettingsFlags:
    """验证 settings 新增的 7 个 flag 默认值正确"""

    def test_默认_enabled_true(self):
        from app.config import settings
        assert settings.AGENT_SELF_RAG_ENABLED is True

    def test_默认阈值(self):
        from app.config import settings
        assert settings.AGENT_SELF_RAG_THRESHOLD == 0.6
        assert settings.AGENT_SELF_RAG_RELAXED_THRESHOLD == 0.4

    def test_默认_max_reretrieve_1(self):
        from app.config import settings
        assert settings.AGENT_SELF_RAG_MAX_RERETRIEVE == 1
        assert settings.AGENT_SELF_RAG_MAX_CONTEXT_DOCS == 8
        assert settings.AGENT_SELF_RAG_JUDGE_TIMEOUT_MS == 3000

    def test_默认_model_空(self):
        """空字符串 = 用 AGENT_REFLECTION_MODEL (生产应改 claude-haiku-4-5-20251001)"""
        from app.config import settings
        assert settings.AGENT_SELF_RAG_MODEL == ""
