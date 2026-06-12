"""测试 Day 1 重写的基础设施（不需要 DB）

覆盖：
- protocol.py: StreamEvent / RichBlock / ToolError 序列化
- tool_registry.py: @tool 装饰器 / dispatch_tool / Pydantic 校验 / 错误处理
- tracing.py: TraceCollector / tool_call 记录
- session_manager.py: 兼容接口（无 DB 时 skip）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_agent_v2_core.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import pytest
from pydantic import BaseModel, Field

from app.agent.protocol import (
    RichBlock,
    StreamEvent,
    ToolError,
    ToolInputError,
    ToolNotFoundError,
)
from app.agent.tool_registry import (
    TOOL_REGISTRY,
    ToolContext,
    dispatch_tool,
    get_all_tool_schemas,
    tool,
)
from app.agent.tracing import TraceCollector


# ============================================================================
# protocol 测试
# ============================================================================


class TestProtocol:
    def test_rich_block_basic(self):
        rb = RichBlock(type="meeting", data={"id": 84, "title": "例会"})
        assert rb.type == "meeting"
        assert rb.data == {"id": 84, "title": "例会"}
        assert rb.compact is False

    def test_stream_event_text_delta(self):
        evt = StreamEvent(type="text_delta", delta="你好")
        assert evt.delta == "你好"
        sse = evt.to_sse()
        assert sse.startswith("data: ")
        assert "text_delta" in sse
        assert "你好" in sse

    def test_stream_event_tool_use(self):
        evt = StreamEvent(
            type="tool_use",
            tool_name="query_meetings",
            tool_input={"date_from": "2026-06-01"},
            tool_use_id="call_123",
        )
        d = evt.model_dump()
        assert d["tool_name"] == "query_meetings"

    def test_stream_event_rich_block(self):
        evt = StreamEvent(
            type="rich_block",
            block=RichBlock(type="task_list", data={"tasks": []}),
        )
        d = evt.model_dump()
        assert d["block"]["type"] == "task_list"

    def test_stream_event_done(self):
        evt = StreamEvent(
            type="done",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            duration_ms=3200,
        )
        assert evt.usage["total_tokens"] == 150

    def test_tool_error_hierarchy(self):
        assert issubclass(ToolInputError, ToolError)
        assert issubclass(ToolNotFoundError, ToolError)


# ============================================================================
# tool_registry 测试
# ============================================================================


# 定义测试用工具
class AddInput(BaseModel):
    a: int
    b: int


class AddOutput(BaseModel):
    result: int


@tool(
    name="test_add",
    description="测试用加法",
    input_model=AddInput,
    output_model=AddOutput,
    requires_db=False,
)
async def mock_add(input: AddInput, ctx: ToolContext) -> dict:
    return {"result": input.a + input.b}


class GreetInput(BaseModel):
    name: str = Field(..., min_length=1)


class GreetOutput(BaseModel):
    greeting: str


@tool(
    name="test_greet",
    description="问候工具",
    input_model=GreetInput,
    output_model=GreetOutput,
    requires_db=False,
)
async def mock_greet(input: GreetInput, ctx: ToolContext) -> dict:
    return {"greeting": f"你好，{input.name}"}


class TestToolRegistry:
    def test_registry_contains_registered_tools(self):
        assert "test_add" in TOOL_REGISTRY
        assert "test_greet" in TOOL_REGISTRY

    def test_get_all_schemas(self):
        schemas = get_all_tool_schemas()
        names = [s["name"] for s in schemas]
        assert "test_add" in names
        assert "test_greet" in names
        # 验证 schema 格式符合 Anthropic 协议
        for s in schemas:
            assert "name" in s
            assert "description" in s
            assert "input_schema" in s
            assert s["input_schema"]["type"] == "object"

    @pytest.mark.asyncio
    async def test_dispatch_valid_input(self):
        ctx = ToolContext(db=None, user_id=None)
        result = await dispatch_tool("test_add", {"a": 1, "b": 2}, ctx)
        assert result == {"result": 3}

    @pytest.mark.asyncio
    async def test_dispatch_with_pydantic_validation_error(self):
        ctx = ToolContext(db=None, user_id=None)
        # b 字段类型错（传字符串）
        with pytest.raises(ToolInputError) as exc_info:
            await dispatch_tool("test_add", {"a": 1, "b": "wrong"}, ctx)
        assert exc_info.value.name == "test_add"
        assert exc_info.value.code == "TOOL_INPUT_INVALID"

    @pytest.mark.asyncio
    async def test_dispatch_missing_required_field(self):
        ctx = ToolContext(db=None, user_id=None)
        with pytest.raises(ToolInputError):
            await dispatch_tool("test_add", {"a": 1}, ctx)  # 缺 b

    @pytest.mark.asyncio
    async def test_dispatch_tool_not_found(self):
        ctx = ToolContext(db=None, user_id=None)
        with pytest.raises(ToolNotFoundError) as exc_info:
            await dispatch_tool("nonexistent_tool", {}, ctx)
        assert exc_info.value.code == "TOOL_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_dispatch_handler_exception_caught(self):
        """handler 抛异常时，返回 error dict 而不传播"""
        class BoomInput(BaseModel):
            x: int

        class BoomOutput(BaseModel):
            ok: bool

        @tool(
            name="test_boom",
            description="会爆的工具",
            input_model=BoomInput,
            output_model=BoomOutput,
            requires_db=False,
        )
        async def test_boom(input: BoomInput, ctx: ToolContext) -> dict:
            raise ValueError("故意爆炸")

        ctx = ToolContext(db=None, user_id=None)
        result = await dispatch_tool("test_boom", {"x": 1}, ctx)
        assert result["status"] == "error"
        assert "执行失败" in result["message"]
        assert "故意爆炸" in result["message"]


# ============================================================================
# tracing 测试
# ============================================================================


class TestTracing:
    def test_trace_basic(self):
        trace = TraceCollector(user_id=1, session_id="test", message="hello")
        trace.set_brief("简要")
        trace.set_detail("详细")
        trace.record_rich_block("meeting", title="5月例会")
        trace.record_tool_call(
            name="query_meetings",
            input={"date_from": "2026-06-01"},
            output={"count": 1, "meetings": []},
            duration_ms=120,
        )
        trace.set_usage(input_tokens=100, output_tokens=50)

        d = trace.to_dict()
        assert d["user_id"] == 1
        assert d["brief"] == "简要"
        assert d["detail"] == "详细"
        assert len(d["tool_calls"]) == 1
        assert d["tool_calls"][0]["name"] == "query_meetings"
        assert d["tool_calls"][0]["duration_ms"] == 120
        assert len(d["rich_blocks"]) == 1
        assert d["rich_blocks"][0]["type"] == "meeting"
        assert d["usage"]["total_tokens"] == 150

    def test_trace_with_block(self):
        with TraceCollector(user_id=2, session_id="s2", message="m") as trace:
            trace.set_brief("b")
            trace.record_tool_call("t1", {}, {"ok": True}, 50)
        assert trace.end_ts is not None
        assert trace.brief == "b"
        assert len(trace.tool_calls) == 1

    def test_trace_captures_exception(self):
        with pytest.raises(ValueError):
            with TraceCollector(user_id=3, session_id="s3", message="m") as trace:
                raise ValueError("boom")
        # 退出 with 时应捕获异常到 error
        assert trace.error is not None
        assert "ValueError" in trace.error
        assert "boom" in trace.error


# ============================================================================
# session_manager 接口测试（无 DB 时只测方法存在）
# ============================================================================


class TestSessionManagerInterface:
    def test_imports(self):
        from app.agent.session_manager import (
            SessionManager,
            session_manager,
            RedisSessionStoreCompat,
        )
        assert session_manager is not None
        assert isinstance(session_manager, SessionManager)
        assert hasattr(session_manager, "get_messages")
        assert hasattr(session_manager, "save_messages")
        assert hasattr(session_manager, "append_message")
        assert hasattr(session_manager, "delete")
        assert hasattr(session_manager, "mark_dirty")
        assert hasattr(session_manager, "is_dirty")
        assert hasattr(session_manager, "clear_dirty")

    def test_compat_layer(self):
        from app.agent.session_manager import RedisSessionStoreCompat
        compat = RedisSessionStoreCompat()
        assert hasattr(compat, "get_messages")
        assert hasattr(compat, "save_messages")
        assert hasattr(compat, "delete")
        assert hasattr(compat, "append_message")


# ============================================================================
# LLMClient 测试（不实际调用 API）
# ============================================================================


class TestLLMClient:
    def test_singleton(self):
        from app.core.llm import LLMClient
        c1 = LLMClient()
        c2 = LLMClient()
        assert c1 is c2

    def test_models_chain(self):
        from app.core.llm import llm_client
        assert len(llm_client.models) >= 1
        assert llm_client.models[0]  # 主模型非空

    def test_compat_functions_still_work(self):
        from app.core.llm import (
            get_anthropic_client,
            get_default_model,
            parse_llm_json,
            extract_text_from_response,
        )
        assert callable(get_anthropic_client)
        assert callable(get_default_model)
        assert callable(parse_llm_json)
        assert callable(extract_text_from_response)
        # parse_llm_json
        assert parse_llm_json('{"a": 1}') == {"a": 1}
        assert parse_llm_json('```json\n{"a": 1}\n```') == {"a": 1}
