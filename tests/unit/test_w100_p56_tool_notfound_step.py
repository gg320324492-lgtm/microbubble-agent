"""W100 +56: ToolNotFoundError 错误事件 step 改名 `__plan_summary__`

根因: W100 +55a 只改了 pre-loop 2 个 placeholder (line 942 pending / line 949 running),
漏了 line 978 ToolNotFoundError 分支 — 该分支仍 emit step="phase0_plan",
前端 PlanSteps template 只按 startsWith('__') 隐藏, 于是用户看到 1 行 "phase0_plan"
(看不出是哪个 tool 不存在, 也看不出这是个警告).

修法: 该分支 step 也改 `__plan_summary__`, 前端整行隐藏; 后端 logger.warning 保留可调试.

覆盖:
- dispatch_tool 抛 ToolNotFoundError 时, plan_step 事件 step == "__plan_summary__"
- label 仍含 tool_name (后端可读 + 前端若将来显示也有信息)
- plan_status 仍 running (协议不破)
- 全流程 0 个 plan_step 事件 step == "phase0_plan"

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_w100_p56_tool_notfound_step.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.agentic_loop import AgenticLoop
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import StreamEvent
from app.agent.tool_registry import ToolNotFoundError


def _empty_llm_response() -> MagicMock:
    """构造一个空 LLM 响应 (phase1 走自然 break → 进入 synthesis)"""
    resp = MagicMock()
    resp.content = []
    return resp


class TestW100P56ToolNotFoundStep:
    """W100 +56: ToolNotFoundError 分支 step 改名 __plan_summary__."""

    @pytest.mark.asyncio
    async def test_tool_not_found_step_is_plan_summary(self):
        """dispatch_tool 抛 ToolNotFoundError → plan_step step 必须是 __plan_summary__."""
        loop = AgenticLoop()
        messages = [{"role": "user", "content": "查询微纳米气泡基础"}]
        intent = IntentResult(
            category=IntentCategory.SEARCH_INFO,
            suggested_tools=["search_knowledge", "no_such_tool"],
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
            if name == "no_such_tool":
                raise ToolNotFoundError(f"tool {name} not found")
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

        plan_events = [e for e in events if e.type == "plan_step"]

        # ToolNotFound 事件: label 含 tool 名 + "不存在"
        notfound = [
            e for e in plan_events
            if e.label and "no_such_tool" in e.label and "不存在" in e.label
        ]
        assert len(notfound) == 1, (
            f"期望 1 个 ToolNotFound plan_step 事件, 实测 {len(notfound)} "
            f"(全部 plan_step: {[(e.step, e.plan_status, e.label) for e in plan_events]})"
        )

        # W100 +56 核心断言: step 是 __plan_summary__ 而非 phase0_plan
        assert notfound[0].step == "__plan_summary__", (
            f"W100 +56 修复: ToolNotFound 事件 step 应是 __plan_summary__, "
            f"实测 {notfound[0].step!r}"
        )
        assert notfound[0].plan_status == "running", (
            f"plan_status 协议不破, 应是 running, 实测 {notfound[0].plan_status!r}"
        )

        # 全流程 0 个 phase0_plan (W100 +55a pre-loop 2 处 + W100 +56 本处全收口)
        leftover = [e for e in plan_events if e.step == "phase0_plan"]
        assert len(leftover) == 0, (
            f"W100 +55a/+56 收口后不应再有 phase0_plan step, 实测 {len(leftover)} 个"
        )
