"""W100 +55a: pre-loop placeholder step 改名 `__plan_summary__`

覆盖:
- pre-loop 2 个 plan_step 事件 step 字段都是 `__plan_summary__` (前端按 __ 前缀隐藏整行)
- 老 `phase0_plan` 不再出现 (除了 3 个 per-tool done 的 fallback 兜底, 但本测试 case 不触发)
- plan_status 仍为 pending + running (与 W100 +53 协议一致)
- 后续 per-tool done 事件的 step 是 tool_name (W100 +53 协议不破)

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_w100_p55_plan_summary_placeholder.py -v
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
    resp.content = []
    return resp


class TestW100P55PlanSummaryPlaceholder:
    """W100 +55a: pre-loop 2 个 placeholder step 改名 __plan_summary__."""

    @pytest.mark.asyncio
    async def test_pre_loop_placeholder_renamed_to_plan_summary(self):
        """W100 +55a 修复: pre-loop pending + running 2 个 placeholder step 都是 __plan_summary__.

        根因: 老 step="phase0_plan" 走 useChatStream fallback 3 把后续 done 归并,
        导致前端 plan 数组前 1 行永远是 phase0_plan, 用户看到"3 行 phase0_plan".
        修法: 改用 __ 前缀, 前端按 startsWith('__') 隐藏整行.
        """
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
        ctx.llm.complete = AsyncMock(return_value=_empty_llm_response())
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

        # 抽取所有 plan_step 事件
        plan_events = [e for e in events if e.type == "plan_step"]

        # 前 2 个必须是 __plan_summary__ (pending + running)
        assert len(plan_events) >= 2, (
            f"期望至少 2 个 plan_step 事件 (pre-loop pending + running), 实测 {len(plan_events)}"
        )
        assert plan_events[0].step == "__plan_summary__", (
            f"第 1 个 plan_step step 应是 __plan_summary__, 实测 {plan_events[0].step!r}"
        )
        assert plan_events[0].plan_status == "pending", (
            f"第 1 个 plan_step 状态应是 pending, 实测 {plan_events[0].plan_status!r}"
        )
        assert plan_events[1].step == "__plan_summary__", (
            f"第 2 个 plan_step step 应是 __plan_summary__, 实测 {plan_events[1].step!r}"
        )
        assert plan_events[1].plan_status == "running", (
            f"第 2 个 plan_step 状态应是 running, 实测 {plan_events[1].plan_status!r}"
        )

        # 老 phase0_plan 不应再作为 pre-loop placeholder 出现
        # (后续 3 个 per-tool done 的 step 是 tool_name, 不在此断言范围)
        pre_loop_phase0 = [
            e for e in plan_events[:2] if e.step == "phase0_plan"
        ]
        assert len(pre_loop_phase0) == 0, (
            f"W100 +55a 修复: pre-loop 2 个 placeholder 不应再是 phase0_plan, "
            f"实测 {len(pre_loop_phase0)} 个"
        )

        # 后续 3 个 per-tool done step 仍是 tool_name (W100 +53 协议不破)
        per_tool_done = [e for e in plan_events[2:] if e.plan_status == "done"]
        assert len(per_tool_done) == 3, (
            f"W100 +53 协议: 3 个 per-tool done, 实测 {len(per_tool_done)}"
        )
        expected_tools = ["search_knowledge", "query_members", "list_projects"]
        for i, evt in enumerate(per_tool_done):
            assert evt.step == expected_tools[i], (
                f"第 {i} 个 done step 应是 {expected_tools[i]}, 实测 {evt.step!r}"
            )
