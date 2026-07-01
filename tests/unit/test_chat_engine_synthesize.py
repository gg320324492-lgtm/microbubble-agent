"""测试 ChatEngine Stage 2 重构（方案 C）

验证：
1. ChatEngine 新方法签名（synthesize_stream 主入口 + 2 个薄壳 + kill switch fallback）
2. 死常量 MAX_CONTINUES / _append_detail_background 已删除
3. TraceCollector async context manager 异常路径同步落库
4. ChatResponse 加 intent / critique 字段

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_chat_engine_synthesize.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.chat_engine import ChatEngine, _extract_rich_block
from app.agent.protocol import RichBlock, StreamEvent
from app.agent.tracing import TraceCollector, TraceStatus


class TestChatEngineNewArchitecture:
    """Stage 2 ChatEngine 架构验证"""

    def test_engine_has_synthesize_stream(self):
        """新主入口 synthesize_stream 必须存在"""
        engine = ChatEngine()
        assert hasattr(engine, "synthesize_stream")
        # 是 async generator
        import inspect
        assert inspect.isasyncgenfunction(engine.synthesize_stream)

    def test_max_continues_removed(self):
        """死常量 MAX_CONTINUES 已被删除（agentic_loop.py 不再用）"""
        from pathlib import Path
        engine_path = Path(__file__).parent.parent.parent / "app" / "agent" / "chat_engine.py"
        content = engine_path.read_text(encoding="utf-8")
        assert "MAX_CONTINUES" not in content, "死常量 MAX_CONTINUES 残留！"

    def test_append_detail_background_removed(self):
        """_append_detail_background 已被删除（取消 brief/detail 双层）"""
        from pathlib import Path
        engine_path = Path(__file__).parent.parent.parent / "app" / "agent" / "chat_engine.py"
        content = engine_path.read_text(encoding="utf-8")
        assert "_append_detail_background" not in content, "detail 后台任务应已删除！"

    # 2026-06-29 已删除（chat_engine_legacy.py + 3 flag 30 天承诺提前收官, commit 817f1ffa）:
    # - test_engine_has_kill_switch_fallback (断言 hasattr _legacy_chat_stream)
    # - test_legacy_chat_engine_file_exists (断言 chat_engine_legacy.py 存在)
    # - test_kill_switch_respects_settings (断言 settings.AGENT_NEW_ARCHITECTURE_ENABLED is True)


class TestExtractRichBlockBackwardCompat:
    """_extract_rich_block 与原实现兼容"""

    def test_explicit_rich_block_type(self):
        result = {
            "status": "success",
            "rich_block_type": "meeting",
            "id": 1,
            "title": "测试会议",
        }
        rb = _extract_rich_block("query_meetings", result)
        assert rb is not None
        assert rb.type == "meeting"
        assert rb.title == "测试会议"
        assert "rich_block_type" not in rb.data  # 应被剥离

    def test_implicit_query_meetings(self):
        result = {"status": "success", "count": 1, "meetings": []}
        rb = _extract_rich_block("query_meetings", result)
        assert rb is not None
        assert rb.type == "meeting"

    def test_implicit_query_members(self):
        result = {"status": "success", "count": 27, "members": []}
        rb = _extract_rich_block("query_members", result)
        assert rb is not None
        assert rb.type == "member"

    def test_error_result_no_block(self):
        result = {"status": "error", "message": "查询失败"}
        rb = _extract_rich_block("query_meetings", result)
        assert rb is None  # error 不出 block

    def test_unknown_tool_no_block(self):
        result = {"status": "success", "ok": True}
        rb = _extract_rich_block("web_search", result)
        assert rb is None

    def test_none_rich_block_type_skipped(self):
        """17 个 tool 默认 rich_block_type=None，应跳过（CLAUDE.md 2026-06-12 hotfix）"""
        result = {"status": "success", "rich_block_type": None, "data": []}
        rb = _extract_rich_block("query_meetings", result)
        # 显式 None 跳过，但隐式映射命中 query_meetings 仍出 block
        assert rb is not None
        assert rb.type == "meeting"


class TestTraceCollectorAsyncContext:
    """TraceCollector async context manager（铁律 4）"""

    @pytest.mark.asyncio
    async def test_normal_exit_status_completed(self):
        """正常退出 → status=COMPLETED，Celery 异步持久化"""
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        async with trace:
            trace.record_tool_call("query_members", {}, {"members": []}, 100)
        assert trace.status == TraceStatus.COMPLETED
        assert trace.end_ts is not None

    @pytest.mark.asyncio
    async def test_cancelled_error_status_aborted(self):
        """CancelledError → status=ABORTED，create_task 异步落库（铁律 4 收尾增强）"""
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        persist_called = []

        async def mock_persist():
            persist_called.append(trace.status)
            return None
        trace._persist_now = mock_persist

        # 2026-06-14 Stage 5 收尾：__aexit__ 用 create_task fire-and-forget 而非 await
        # 测试需要等待 task 完成（否则 mock 还没被调）
        with pytest.raises(asyncio.CancelledError):
            async with trace:
                trace.record_tool_call("query_members", {}, {}, 50)
                raise asyncio.CancelledError()

        # 给 create_task 时间跑完
        await asyncio.sleep(0.05)

        assert trace.status == TraceStatus.ABORTED
        assert len(persist_called) == 1
        assert persist_called[0] == TraceStatus.ABORTED

    @pytest.mark.asyncio
    async def test_other_exception_status_error(self):
        """非 CancelledError 异常 → status=ERROR，create_task 异步落库"""
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        persist_called = []

        async def mock_persist():
            persist_called.append(trace.status)
            return None
        trace._persist_now = mock_persist

        with pytest.raises(RuntimeError):
            async with trace:
                trace.record_tool_call("query_members", {}, {}, 30)
                raise RuntimeError("LLM boom")

        await asyncio.sleep(0.05)

        assert trace.status == TraceStatus.ERROR
        assert trace.error is not None
        assert "RuntimeError" in trace.error
        assert len(persist_called) == 1
        assert persist_called[0] == TraceStatus.ERROR

    @pytest.mark.asyncio
    async def test_normal_exit_uses_celery_not_sync(self):
        """正常退出走 Celery 异步（不调 _persist_now）"""
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        sync_called = []

        async def mock_persist():
            sync_called.append(True)
            return None
        trace._persist_now = mock_persist

        # Mock Celery schedule
        schedule_called = []
        original_schedule = trace._schedule_persist
        trace._schedule_persist = lambda: schedule_called.append(True)

        async with trace:
            pass

        assert len(sync_called) == 0, "正常路径不该调同步落库"
        assert len(schedule_called) == 1, "正常路径该调 Celery schedule"


class TestTraceCollectorNewFields:
    """TraceCollector Stage 2 新增字段"""

    def test_status_field_default(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        assert trace.status == TraceStatus.IN_PROGRESS

    def test_intent_fields(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        trace.set_intent("recommend_person", 0.92)
        assert trace.intent_category == "recommend_person"
        assert trace.intent_confidence == 0.92

    def test_critique_fields(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        trace.set_critique(score=9, retry_count=0)
        assert trace.critique_score == 9
        assert trace.retry_count == 0

    def test_synthesis_text_setter(self):
        """set_synthesis() 取代 set_brief/set_detail"""
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        trace.set_synthesis("推荐杨慈、宋洋、李锐远")
        assert trace.synthesis_text == "推荐杨慈、宋洋、李锐远"
        assert trace.brief == "推荐杨慈、宋洋、李锐远"  # 兼容老 API

    def test_to_dict_includes_status(self):
        trace = TraceCollector(user_id=1, session_id="s1", message="hi")
        trace.set_synthesis("test")
        d = trace.to_dict()
        assert "status" in d
        assert d["status"] == TraceStatus.IN_PROGRESS


class TestChatResponseIntentCritique:
    """ChatResponse 加 intent / critique 字段"""

    def test_chat_response_has_new_fields(self):
        from app.api.v1.chat import ChatResponse
        # 字段存在于 BaseModel 注解
        fields = ChatResponse.model_fields
        assert "intent" in fields
        assert "critique" in fields
        # intent 是 Optional
        assert fields["intent"].default is None
        assert fields["critique"].default is None

    def test_chat_response_legacy_fields_preserved(self):
        """10 字段 schema 不破坏"""
        from app.api.v1.chat import ChatResponse
        fields = ChatResponse.model_fields
        for old_field in ["content", "session_id", "is_brief", "rich_blocks", "tool_trace", "usage", "duration_ms"]:
            assert old_field in fields, f"老字段 {old_field} 缺失"

    def test_chat_response_construct_with_new_fields(self):
        from app.api.v1.chat import ChatResponse
        resp = ChatResponse(
            content="推荐杨慈",
            session_id="s1",
            intent={"category": "recommend_person", "confidence": 0.92},
            critique={"score": 9, "addresses_question": True, "has_synthesis": True, "has_citations": True},
        )
        assert resp.intent["category"] == "recommend_person"
        assert resp.critique["score"] == 9
