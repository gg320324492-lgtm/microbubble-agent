"""2026-09-10 写操作诚实性修复 — 编排接线 e2e (脚本化 LLM, 确定性)

与 tests/test_write_honesty_guards_2026-09-10.py 分工: 那个文件测纯函数;
本文件用假 LLM 驱动**真实 AgenticLoop.run 全链路**, 断言三处接线在 synthesis
的 system prompt 里真的生效 (单测改源码字符串会红, 但接线断了没人知道):

1. guard: execute_action + 0 工具 → system 含 "修改操作未能执行" 硬声明 (Fix 2)
2. fact-anchor: follow_up 核验问句 + ctx.last_write_fact → system 含 "[系统确定性事实]" (Fix 1)
3. critic grounding: 同场景 critic prompt 含 "跨轮确定性事实" (Fix 4)

不依赖 ollama / DB (ctx.db=None, 场景内无任何 dispatch)。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.agent.agentic_loop import AgenticLoop
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.tool_registry import ToolContext


class _Delta:
    def __init__(self, text):
        self.type = "text_delta"
        self.text = text


class _Event:
    def __init__(self, text):
        self.type = "content_block_delta"
        self.delta = _Delta(text)


class _StreamCM:
    def __init__(self, events):
        self._events = events

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    def __aiter__(self):
        async def _gen():
            for e in self._events:
                yield e
        return _gen()


class ScriptedLLM:
    """假 LLM: complete 按 prompt 特征应答 (critique JSON), stream 吐固定文本。

    捕获每次调用的 system, 供断言注入是否真的进了 prompt。
    """

    def __init__(self, synthesis_text: str):
        self.synthesis_text = synthesis_text
        self.complete_prompts: list[str] = []
        self.stream_systems: list[str] = []

    async def complete(self, messages, **kwargs):
        self.complete_prompts.append(str(messages))
        return SimpleNamespace(content=[SimpleNamespace(text=json.dumps({
            "score": 8, "addresses_question": True, "has_synthesis": True,
            "has_citations": False, "grounded_in_tools": 9,
            "missing": [], "suggestion": "",
        }))])

    def stream(self, **kwargs):
        self.stream_systems.append(kwargs.get("system", ""))

        async def _outer():
            yield _StreamCM([_Event(self.synthesis_text)])
        return _outer()


def _ctx(llm: ScriptedLLM, last_write_fact=None) -> ToolContext:
    return ToolContext(db=None, user_id=1, llm=llm, last_write_fact=last_write_fact)


async def _drain(loop: AgenticLoop, messages, system, intent, ctx) -> str:
    text = ""
    async for evt in loop.run(messages=messages, system=system, intent=intent, ctx=ctx):
        if evt.type == "text_delta":
            text += evt.delta or ""
    return text


@pytest.mark.asyncio
async def test_guard_injects_no_write_declaration_for_execute_action():
    """Fix 2 接线: execute_action 轮全程 0 工具 → synthesis system 必须含写未执行硬声明。"""
    llm = ScriptedLLM("本轮未能执行该修改操作。")
    ctx = _ctx(llm)
    intent = IntentResult(category=IntentCategory.EXECUTE_ACTION, confidence=0.95,
                          suggested_tools=[])
    # 首轮模型直接文本作答 (无 tool_use); suggested_tools 空 → nudge 退回文本指令;
    # 二轮仍无 tool_use → break。无论走哪条, guard 都必须命中"有读无写/无写"分支。
    await _drain(AgenticLoop(),
                 [{"role": "user", "content": "帮我给韩重阳的任务加一条备注：测试"}],
                 "BASE-SYSTEM", intent, ctx)
    synth_system = llm.stream_systems[-1]
    assert "BASE-SYSTEM" in synth_system
    assert "本轮工具执行状态告知" in synth_system, "guard 未注入 synthesis system"
    assert "修改操作未能执行" in synth_system or "写操作**工具执行成功" in synth_system
    assert "严禁输出'已完成/已添加/已更新'" in synth_system or "严禁输出'已添加/已更新/已删除/已保存'" in synth_system


@pytest.mark.asyncio
async def test_fact_anchor_injected_on_verification_follow_up():
    """Fix 1 接线: 核验问句 + 上轮写事实 → synthesis system 含确定性事实与反假否认指令。"""
    fact = {"tool": "update_task", "task_id": 77, "note_written": True,
            "description_tail": "[备注 2026-09-10 04:10] 本周组会汇报进度",
            "ts": "2026-09-10T12:00:00+00:00"}
    llm = ScriptedLLM("写上了。")
    ctx = _ctx(llm, last_write_fact=fact)
    intent = IntentResult(category=IntentCategory.FOLLOW_UP, confidence=0.92)
    await _drain(AgenticLoop(),
                 [{"role": "user", "content": "刚才那条备注写上了吗？原话是什么？"}],
                 "BASE-SYSTEM", intent, ctx)
    synth_system = llm.stream_systems[-1]
    assert "[系统确定性事实]" in synth_system, "上轮写事实未注入 synthesis system"
    assert "本周组会汇报进度" in synth_system
    assert "假否认" in synth_system


@pytest.mark.asyncio
async def test_critic_receives_cross_turn_fact_grounding():
    """Fix 4 接线: 同场景 critic prompt 必须拿到跨轮事实 (不再'（无工具返回）'盲区)。"""
    fact = {"tool": "update_task", "task_id": 77,
            "description_tail": "[备注 2026-09-10 04:10] 本周组会汇报进度"}
    llm = ScriptedLLM("写上了。")
    ctx = _ctx(llm, last_write_fact=fact)
    intent = IntentResult(category=IntentCategory.FOLLOW_UP, confidence=0.92)
    await _drain(AgenticLoop(),
                 [{"role": "user", "content": "刚才那条备注写上了吗？"}],
                 "BASE-SYSTEM", intent, ctx)
    critic_prompts = [p for p in llm.complete_prompts if "质量评审" in p or "score" in p.lower()]
    assert critic_prompts, "critic 未被调用"
    assert any("跨轮确定性事实" in p for p in critic_prompts), \
        "critic prompt 缺跨轮事实 grounding"


@pytest.mark.asyncio
async def test_no_fact_no_injection_untouched_path():
    """守恒: 无 last_write_fact 的普通轮, system 不得混入事实注入 (0 副作用)。"""
    llm = ScriptedLLM("你好。")
    ctx = _ctx(llm)
    intent = IntentResult(category=IntentCategory.CASUAL_CHAT, confidence=0.9)
    await _drain(AgenticLoop(), [{"role": "user", "content": "你好"}],
                 "BASE-SYSTEM", intent, ctx)
    synth_system = llm.stream_systems[-1]
    assert "[系统确定性事实]" not in synth_system
    # casual_chat 不在 guard 意图集合, 也不该出现写声明
    assert "本轮工具执行状态告知" not in synth_system
