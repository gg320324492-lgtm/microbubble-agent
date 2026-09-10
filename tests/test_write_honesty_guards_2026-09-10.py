"""2026-09-10 写操作诚实性 4 项修复回归 (实测第 4 组对话质量事故)

对应 4 个真 bug:
1. **反假否认 (trace 5697)**: "刚才那条备注写上了吗" 被答"还没写上", 与 DB 事实相反。
   修 = 上轮写成功事实存 last_turn → 本轮核验问句命中时工程注入确定性事实。
2. **写谎报 guard (trace 5696)**: execute_action 轮 nudge 只补只读 query_tasks,
   模型见"查到任务"便称"已添加备注", 实际没写库。老 guard 条件 `not tool_calls`
   不成立完全不触发。修 = guard 口径改为"有无成功的写工具调用"。
3. **轨迹事实源**: write 成败以 tool_calls 里的成功写记录为准 (registry 单一事实源)。
4. **critic 盲区 (trace 5697 自评 9/10 漏判)**: follow_up 轮工具证据恒"（无工具返回）",
   critic 无从核验假否认。修 = 无本轮写但有上轮写事实时把事实喂给 critic。

单测覆盖纯函数 + critic prompt 注入; guard 分支与 fact 注入接线用源码结构断言
(与 tests/test_w83_b1_agentic_loop_silent_except_e2e.py 同 idiom, 防回归改回)。
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


# ============================================================================
# Fix 3: registry 单一事实源 — 写工具判定纯函数
# ============================================================================


class TestWriteToolFacts:
    def test_write_tools_are_registered(self):
        from app.agent.tool_registry import WRITE_TOOL_NAMES, is_write_tool
        # 核心写工具必须在白名单 (新写工具不登记 = guard 失明, 见 registry 注释)
        for t in ("create_task", "update_task", "save_memory", "save_conversation_knowledge"):
            assert t in WRITE_TOOL_NAMES
            assert is_write_tool(t)
        # 只读工具不得进白名单 (否则谎报 guard 会被读操作误判为已写)
        for t in ("query_tasks", "query_members", "get_task_stats", "search_knowledge"):
            assert not is_write_tool(t)

    def test_write_tool_succeeded_only_true_status(self):
        from app.agent.tool_registry import write_tool_succeeded
        assert write_tool_succeeded({"status": "success", "task_id": 77})
        assert not write_tool_succeeded({"status": "error", "message": "x"})
        assert not write_tool_succeeded({"status": "rejected"})
        assert not write_tool_succeeded({"status": "skipped"})
        assert not write_tool_succeeded(None)
        assert not write_tool_succeeded("not a dict")

    def test_save_memory_success_states(self):
        """save_memory 特例契约: created/merged/updated 都算改库成功。"""
        from app.agent.tool_registry import write_tool_succeeded
        for st in ("created", "merged", "updated"):
            assert write_tool_succeeded({"status": st, "memory_id": 1})
        assert not write_tool_succeeded({"status": "blocked"})

    def test_add_note_requested_but_not_written_is_failure(self):
        """update_task 关键陷阱: add_note 请求了但 note_written=False → 不算成功写。"""
        from app.agent.tool_registry import write_tool_succeeded
        assert write_tool_succeeded(
            {"status": "success", "add_note_requested": True, "note_written": True})
        assert not write_tool_succeeded(
            {"status": "success", "add_note_requested": True, "note_written": False})
        # 纯改状态 (未请求 add_note) 正常成功
        assert write_tool_succeeded(
            {"status": "success", "add_note_requested": False, "note_written": False})

    def test_has_successful_write_reads_both_call_shapes(self):
        """tool_calls (output 键) 与 tool_trace (result 键) 两种形态都要认。"""
        from app.agent.tool_registry import has_successful_write
        assert has_successful_write([
            {"name": "query_tasks", "output": {"status": "success", "tasks": []}},
            {"name": "update_task", "output": {"status": "success", "task_id": 77}},
        ])
        assert has_successful_write([
            {"name": "update_task", "result": {"status": "success", "task_id": 77}},
        ])
        # 有读无写 → False (trace 5696 事故形态)
        assert not has_successful_write([
            {"name": "query_tasks", "output": {"status": "success", "tasks": [1, 2, 3]}},
        ])
        # 写了但失败 → False
        assert not has_successful_write([
            {"name": "update_task", "output": {"status": "error", "message": "not found"}},
        ])
        assert not has_successful_write([])
        assert not has_successful_write(None)

    def test_extract_write_fact_last_success_compact(self):
        from app.agent.tool_registry import extract_write_fact
        fact = extract_write_fact([
            {"name": "query_tasks", "output": {"status": "success", "tasks": []}},
            {"name": "update_task", "output": {
                "status": "success", "task_id": 77, "note_written": True,
                "new_status": "in_progress",
                "description_tail": "[备注 2026-09-10 04:10] 本周组会汇报进度",
                "add_note_requested": True}},
        ])
        assert fact is not None
        assert fact["tool"] == "update_task"
        assert fact["task_id"] == 77
        assert "本周组会汇报进度" in fact["description_tail"]
        # 无成功写 → None
        assert extract_write_fact([
            {"name": "query_tasks", "output": {"status": "success"}},
        ]) is None
        # 只保留标量, 不带大列表 (防 Redis 膨胀)
        assert "tasks" not in fact


# ============================================================================
# Fix 1: 反假否认 — 核验问句识别 + 事实注入文本
# ============================================================================


class TestWriteFactAnchor:
    def test_verification_questions_match(self):
        from app.agent.agentic_loop import _looks_like_verification
        for q in (
            "刚才那条备注写上了吗？原话是什么？",
            "刚刚那个改好了没有",
            "之前加的任务成功了吗",
            "上一条备注写上了吗",
            "那条改了没",
            "刚才那个删除成功了吗",
            "备注的原话是什么",
        ):
            assert _looks_like_verification(q), f"应识别为核验问句: {q}"

    def test_non_verification_questions_do_not_match(self):
        from app.agent.agentic_loop import _looks_like_verification
        for q in (
            "现在有哪些进行中的任务？",
            "他手上还有其他任务吗？",
            "什么是微纳米气泡",
            "帮我给这个任务加一条备注：测试",  # 新指令, 非核验
            "详细介绍本课题组",
        ):
            assert not _looks_like_verification(q), f"不应识别为核验问句: {q}"

    def _ctx(self, fact):
        from app.agent.tool_registry import ToolContext
        ctx = ToolContext.__new__(ToolContext)  # 绕开 __init__ 依赖, 只塞用到的属性
        ctx.last_write_fact = fact
        return ctx

    def test_fact_note_injected_on_verification(self):
        from app.agent.agentic_loop import _last_write_fact_note
        fact = {"tool": "update_task", "task_id": 77, "title": None,
                "description_tail": "[备注 2026-09-10 04:10] 本周组会汇报进度",
                "note_written": True}
        msgs = [{"role": "user", "content": "刚才那条备注写上了吗？原话是什么？"}]
        note = _last_write_fact_note(self._ctx(fact), msgs)
        assert note
        assert "update_task" in note
        assert "本周组会汇报进度" in note
        assert "严禁" in note and "假否认" in note

    def test_no_note_without_fact(self):
        from app.agent.agentic_loop import _last_write_fact_note
        msgs = [{"role": "user", "content": "刚才那条备注写上了吗？"}]
        assert _last_write_fact_note(self._ctx(None), msgs) == ""

    def test_no_note_on_non_verification_turn(self):
        from app.agent.agentic_loop import _last_write_fact_note
        fact = {"tool": "update_task", "task_id": 77}
        msgs = [{"role": "user", "content": "现在有哪些进行中的任务？"}]
        assert _last_write_fact_note(self._ctx(fact), msgs) == ""


# ============================================================================
# Fix 4: critic 跨轮 grounding 注入
# ============================================================================


class _CapturingLLM:
    def __init__(self, resp_text):
        self._resp_text = resp_text
        self.captured_prompt = None

    async def complete(self, messages, **kwargs):
        self.captured_prompt = messages[0]["content"]
        return SimpleNamespace(content=[SimpleNamespace(text=self._resp_text)])


class TestCriticGrounding:
    async def _run(self, monkeypatch, extra_grounding):
        from app.agent import critic as critic_mod
        from app.agent.intent_classifier import IntentCategory, IntentResult
        monkeypatch.setattr(critic_mod.settings, "LLM_BACKEND", "anthropic", raising=False)
        llm = _CapturingLLM(json.dumps({
            "score": 5, "addresses_question": True, "has_synthesis": True,
            "has_citations": False, "grounded_in_tools": 8, "missing": [], "suggestion": ""}))
        ctx = SimpleNamespace(llm=llm)
        intent = IntentResult(category=IntentCategory.FOLLOW_UP, confidence=0.9)
        result = await critic_mod.critique_response(
            user_question="刚才那条备注写上了吗？",
            intent=intent,
            response_text="还没写上——",
            rich_blocks=[],
            tool_calls=[],  # 本轮无工具 → 老逻辑 critic 拿到"（无工具返回）"
            ctx=ctx,
            extra_grounding=extra_grounding,
        )
        return llm, result

    async def test_extra_grounding_flows_into_prompt(self, monkeypatch):
        fact = "上一轮 update_task 已成功, description_tail=[备注] 本周组会汇报进度"
        llm, result = await self._run(monkeypatch, fact)
        assert "跨轮确定性事实" in llm.captured_prompt
        assert "本周组会汇报进度" in llm.captured_prompt
        assert result.score == 5  # 正常解析未破坏

    async def test_empty_grounding_keeps_old_contract(self, monkeypatch):
        llm, _ = await self._run(monkeypatch, "")
        assert "跨轮确定性事实" not in llm.captured_prompt


# ============================================================================
# Fix 2 + 接线: 源码结构断言 (guard 分支 / fact 注入 / tool_calls 累积)
# ============================================================================


def _src():
    import pathlib
    return (pathlib.Path(__file__).resolve().parent.parent
            / "app/agent/agentic_loop.py").read_text(encoding="utf-8")


class TestGuardWiring:
    def test_guard_triggers_on_read_without_write(self):
        """核心修复: guard 触发条件必须含 (_needs_write and not _write_done)。"""
        src = _src()
        assert "_needs_write and not _write_done" in src, \
            "guard 需按'有无成功写'判定, 不能只在 not tool_calls 时触发"
        assert "has_successful_write(tool_calls)" in src

    def test_write_fact_note_wired_into_system(self):
        src = _src()
        assert "_last_write_fact_note(ctx, messages)" in src, \
            "_run_legacy 必须在指代锚定之后注入上轮写事实"

    def test_critic_receives_fact_grounding(self):
        src = _src()
        assert "extra_grounding=_critic_grounding" in src, \
            "Phase 3 critique 必须接收跨轮写事实 (否则 follow_up 轮 critic 盲区复发)"
