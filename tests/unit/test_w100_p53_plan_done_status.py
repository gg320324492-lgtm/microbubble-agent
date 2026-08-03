"""测试 W100 +53 plan_step done status emit — 每个 tool_result 后 yield plan_status='done'

覆盖：
- 6 个 planned tool → 每个完成后 yield plan_step done 带 tool_use_id
- 每个 done 事件的 tool_use_id 与对应 tool_use 一致 (前端 dedup 依赖)
- 老 phase0_plan done 事件不再发 (避免孤儿 step)
- plan_step 完成后不再 yield done, 改 yield thinking (避免污染 plan 数组)

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_w100_p53_plan_done_status.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.agentic_loop import AgenticLoop
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import StreamEvent


def _empty_llm_response() -> MagicMock:
    """构造一个空 LLM 响应 (phase1 走自然 break → 进入 synthesis)"""
    resp = MagicMock()
    resp.content = []  # _extract_tool_uses 返空 → phase1 break
    return resp


class TestW100P53PlanDoneStatus:
    """W100 +53: 每个 tool_result 后 yield plan_status='done' 原地更新."""

    @pytest.mark.asyncio
    async def test_each_tool_result_yields_plan_status_done_with_tool_use_id(self):
        """每个 tool 完成 → yield 1 个 plan_step done, 带对应 tool_use_id."""
        loop = AgenticLoop()
        messages = [{"role": "user", "content": "查询微纳米气泡基础"}]
        intent = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            suggested_tools=["search_knowledge", "query_members", "list_projects"],
            confidence=0.95,
        )

        ctx = MagicMock()
        ctx.redis = None
        ctx.trace = None
        ctx.llm = MagicMock()
        # LLM 返空响应 → phase1 自然 break → 进入 synthesis (不会触发 UnboundLocalError)
        ctx.llm.complete = AsyncMock(return_value=_empty_llm_response())
        # Mock synthesize_stream 让 synthesis 跳过 (避免 model 调用)
        ctx.thinking_config = MagicMock()
        ctx.thinking_config.skip_critique = True
        ctx.thinking_config.skip_plan_step = False

        from app.agent import agentic_loop as loop_mod
        async def fake_dispatch(name, payload, ctx):
            return {"status": "success", "name": name, "result": "ok"}
        async def fake_synthesize_stream(*args, **kwargs):
            if False:
                yield None
            return
            yield  # noqa - 让函数成为 async generator
        original_dispatch = loop_mod.dispatch_tool
        original_synthesize = loop_mod.AgenticLoop._synthesize_stream
        loop_mod.dispatch_tool = fake_dispatch
        loop_mod.AgenticLoop._synthesize_stream = fake_synthesize_stream
        try:
            events: list[StreamEvent] = []
            async for evt in loop.run(messages, "system", intent, ctx, max_rounds=2):
                events.append(evt)
        finally:
            loop_mod.dispatch_tool = original_dispatch
            loop_mod.AgenticLoop._synthesize_stream = original_synthesize

        # 抽取所有 plan_step done 事件
        plan_done = [e for e in events if e.type == "plan_step" and e.plan_status == "done"]
        # 应该有 3 个 (3 个 tool 各 1 个 done), 不再是 1 个 phase0_plan done
        assert len(plan_done) == 3, (
            f"期望 3 个 done 事件 (每 tool 一个), 实测 {len(plan_done)}: "
            f"{[(e.step, e.tool_use_id) for e in plan_done]}"
        )
        # 每个 done 带 tool_use_id, 且与 tool_name 匹配
        expected_tools = ["search_knowledge", "query_members", "list_projects"]
        for i, evt in enumerate(plan_done):
            assert evt.tool_use_id, f"第 {i} 个 done 事件缺 tool_use_id"
            assert evt.tool_name == expected_tools[i], (
                f"第 {i} 个 done tool_name={evt.tool_name}, 期望 {expected_tools[i]}"
            )
            assert expected_tools[i] in evt.tool_use_id, (
                f"tool_use_id={evt.tool_use_id} 应包含 tool_name={expected_tools[i]}"
            )
            assert evt.plan_status == "done"

    @pytest.mark.asyncio
    async def test_post_loop_done_no_longer_yielded_as_plan_step(self):
        """W100 +53 修复: 不再 yield post-loop 'phase0_plan done' (避免孤儿 step)."""
        loop = AgenticLoop()
        messages = [{"role": "user", "content": "查询"}]
        intent = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            suggested_tools=["search_knowledge"],
            confidence=0.95,
        )

        ctx = MagicMock()
        ctx.redis = None
        ctx.trace = None
        ctx.llm = MagicMock()
        ctx.llm.complete = AsyncMock(return_value=_empty_llm_response())
        ctx.thinking_config = MagicMock()
        ctx.thinking_config.skip_critique = True

        from app.agent import agentic_loop as loop_mod
        async def fake_dispatch(name, payload, ctx):
            return {"status": "success"}
        async def fake_synthesize_stream(self, **kwargs):
            return
            yield  # noqa
        original_dispatch = loop_mod.dispatch_tool
        original_synthesize = loop_mod.AgenticLoop._synthesize_stream
        loop_mod.dispatch_tool = fake_dispatch
        loop_mod.AgenticLoop._synthesize_stream = fake_synthesize_stream
        try:
            events: list[StreamEvent] = []
            async for evt in loop.run(messages, "system", intent, ctx, max_rounds=2):
                events.append(evt)
        finally:
            loop_mod.dispatch_tool = original_dispatch
            loop_mod.AgenticLoop._synthesize_stream = original_synthesize

        # 不应再有 'phase0_plan' 结尾的 plan_step done (那是 W100 +53 之前的孤儿)
        phase0_done = [
            e for e in events
            if e.type == "plan_step" and e.plan_status == "done" and e.step == "phase0_plan"
        ]
        assert len(phase0_done) == 0, (
            f"W100 +53 已修复: phase0_plan done 不应再 yield, 实测仍有 {len(phase0_done)}"
        )
        # 但 '计划完成' summary 应改走 thinking 事件
        thinking = [e for e in events if e.type == "thinking" and "计划完成" in (e.label or "")]
        assert len(thinking) >= 1, (
            "计划完成 summary 应走 thinking 事件, 让前端 toolTrace 显示而不污染 plan 数组"
        )

    @pytest.mark.asyncio
    async def test_done_event_tool_use_id_unique_per_tool(self):
        """6 个 tool → 6 个不同的 tool_use_id (前端 dedup key)."""
        loop = AgenticLoop()
        messages = [{"role": "user", "content": "查询"}]
        intent = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            suggested_tools=["search_knowledge", "query_members", "list_projects",
                            "get_meeting_transcript", "get_task", "list_formulas"],
            confidence=0.95,
        )

        ctx = MagicMock()
        ctx.redis = None
        ctx.trace = None
        ctx.llm = MagicMock()
        ctx.llm.complete = AsyncMock(return_value=_empty_llm_response())
        ctx.thinking_config = MagicMock()
        ctx.thinking_config.skip_critique = True

        from app.agent import agentic_loop as loop_mod
        async def fake_dispatch(name, payload, ctx):
            return {"status": "success"}
        async def fake_synthesize_stream(self, **kwargs):
            return
            yield  # noqa
        original_dispatch = loop_mod.dispatch_tool
        original_synthesize = loop_mod.AgenticLoop._synthesize_stream
        loop_mod.dispatch_tool = fake_dispatch
        loop_mod.AgenticLoop._synthesize_stream = fake_synthesize_stream
        try:
            events: list[StreamEvent] = []
            async for evt in loop.run(messages, "system", intent, ctx, max_rounds=2):
                events.append(evt)
        finally:
            loop_mod.dispatch_tool = original_dispatch
            loop_mod.AgenticLoop._synthesize_stream = original_synthesize

        plan_done = [e for e in events if e.type == "plan_step" and e.plan_status == "done"]
        # AGENT_PLAN_STEP_MAX=5 默认截断 → 6 tool 被截到 5 个 → 5 个 done
        assert len(plan_done) == 5, (
            f"期望 5 个 done 事件 (默认截断到 AGENT_PLAN_STEP_MAX=5), 实测 {len(plan_done)}"
        )
        # 每个 tool_use_id 唯一
        ids = [e.tool_use_id for e in plan_done]
        assert len(set(ids)) == len(ids), f"tool_use_id 应唯一, 实测: {ids}"