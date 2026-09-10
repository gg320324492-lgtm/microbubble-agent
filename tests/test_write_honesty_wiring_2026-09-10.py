"""2026-09-10 chat_stream 入口接线集成测试 (fake redis + fake engine, 无 DB/无 ollama)

验证跨轮写事实的**两端接线**:
- 入: session meta last_turn.write_fact → _get_last_write_fact → engine.chat_stream(last_write_fact=…)
- 出: 本轮 tool_result(写成功) → done → _set_last_turn(tool_trace=…) → last_turn.write_fact 落 meta
- 结转: 本轮无新写但上轮有事实 → write_fact 结转 (连续核验不丢事实)
- 守恒: 无事实 / 无新写时不注入不虚增
"""
from __future__ import annotations

import json
from typing import Any, Optional

import pytest

import app.agent.micro_bubble_agent as mba
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import StreamEvent


class FakeSessionManager:
    """内存版 session meta (只实现被测代码用到的两个方法)。"""

    def __init__(self):
        self.meta: dict[str, dict[str, Any]] = {}

    async def get_session_meta(self, sid: str, field: str):
        raw = self.meta.get(sid, {}).get(field)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw

    async def set_session_meta(self, sid: str, field: str, value: Any) -> None:
        self.meta.setdefault(sid, {})[field] = json.dumps(value, ensure_ascii=False, default=str)


@pytest.fixture()
def fake_sm(monkeypatch):
    sm = FakeSessionManager()
    monkeypatch.setattr(mba, "session_manager", sm)
    return sm


# ============================================================================
# _get_last_write_fact / _build_last_turn / _set_last_turn 单元段
# ============================================================================


def test_build_last_turn_extracts_write_fact():
    trace = [
        {"type": "tool_result", "name": "query_tasks",
         "result": {"status": "success", "tasks": []}},
        {"type": "tool_result", "name": "update_task",
         "result": {"status": "success", "task_id": 77, "note_written": True,
                    "add_note_requested": True,
                    "description_tail": "[备注 2026-09-10] 本周组会汇报进度"}},
    ]
    turn = mba._build_last_turn(None, "加备注", "已添加", [], tool_trace=trace)
    assert turn["write_fact"]["tool"] == "update_task"
    assert turn["write_fact"]["task_id"] == 77


def test_build_last_turn_no_write_no_fact():
    trace = [{"type": "tool_result", "name": "query_tasks",
              "result": {"status": "success", "tasks": []}}]
    turn = mba._build_last_turn(None, "查任务", "共 17 项", [], tool_trace=trace)
    assert "write_fact" not in turn


def test_build_last_turn_failed_write_no_fact():
    """谎报防线数据面: update_task 返回 error → 不生成 write_fact。"""
    trace = [{"type": "tool_result", "name": "update_task",
              "result": {"status": "error", "message": "任务不存在"}}]
    turn = mba._build_last_turn(None, "改任务", "已完成", [], tool_trace=trace)
    assert "write_fact" not in turn


@pytest.mark.asyncio
async def test_get_last_write_fact_roundtrip(fake_sm):
    fake_sm.meta["s1"] = {"last_turn": json.dumps(
        {"intent": "execute_action", "write_fact": {"tool": "update_task", "task_id": 77}})}
    fact = await mba._get_last_write_fact("s1")
    assert fact is not None and fact["tool"] == "update_task"
    assert await mba._get_last_write_fact("s-none") is None


@pytest.mark.asyncio
async def test_set_last_turn_carries_over_prev_fact(fake_sm):
    """结转: 本轮无新写, 但上轮 last_turn 有 write_fact → 事实保留 (连续核验场景)。"""
    fake_sm.meta["s1"] = {"last_turn": json.dumps(
        {"intent": "execute_action", "write_fact": {"tool": "update_task", "task_id": 77}})}
    await mba._set_last_turn("s1", None, "真的写上了吗", "写上了", [],
                             tool_trace=[])  # 本轮 0 工具
    turn = json.loads(fake_sm.meta["s1"]["last_turn"])
    assert turn["write_fact"]["tool"] == "update_task"


@pytest.mark.asyncio
async def test_set_last_turn_new_write_overrides(fake_sm):
    fake_sm.meta["s1"] = {"last_turn": json.dumps(
        {"write_fact": {"tool": "update_task", "task_id": 77}})}
    trace = [{"type": "tool_result", "name": "create_task",
              "result": {"status": "success", "task_id": 200, "title": "新任务"}}]
    await mba._set_last_turn("s1", None, "建个任务", "已创建", [], tool_trace=trace)
    turn = json.loads(fake_sm.meta["s1"]["last_turn"])
    assert turn["write_fact"]["tool"] == "create_task"
    assert turn["write_fact"]["task_id"] == 200


# ============================================================================
# chat_stream 入口贯通: fact 读→传 engine; done→写回 fact
# ============================================================================


class CapturingEngine:
    """假 engine: 捕获 chat_stream kwargs, yield 一轮 写成功 + done。"""

    def __init__(self, synth_text="已完成"):
        self.captured: dict[str, Any] = {}
        self.synth_text = synth_text

    async def chat_stream(self, **kwargs):
        self.captured = kwargs
        yield StreamEvent(type="intent_detected", intent={
            "category": "execute_action", "confidence": 0.95})
        yield StreamEvent(type="tool_use", tool_name="update_task",
                          tool_input={"task_id": 77, "add_note": "测试"},
                          tool_use_id="x1")
        yield StreamEvent(type="tool_result", tool_name="update_task",
                          tool_output={"status": "success", "task_id": 77,
                                       "note_written": True, "add_note_requested": True},
                          tool_use_id="x1")
        yield StreamEvent(type="text_delta", delta=self.synth_text)
        yield StreamEvent(type="done", duration_ms=100, session_id=kwargs.get("session_id"),
                          text_without_json=self.synth_text)


@pytest.mark.asyncio
async def test_chat_stream_passes_fact_to_engine_and_persists_write(fake_sm, monkeypatch):
    """贯通两端: 入 (meta→last_write_fact→engine) + 出 (tool_result→last_turn.write_fact)。"""
    fake_sm.meta["verify_s1"] = {"last_turn": json.dumps(
        {"write_fact": {"tool": "update_task", "task_id": 77,
                        "description_tail": "[备注] 旧事实"}})}

    async def fake_ensure_ctx(db, user_id, session_id):
        return []
    async def fake_classify(question, ctx):
        return IntentResult(category=IntentCategory.DATA_QUERY, confidence=0.9)

    monkeypatch.setattr(mba, "_ensure_session_context", fake_ensure_ctx)
    monkeypatch.setattr(mba, "classify_intent", fake_classify)

    agent = mba.MicroBubbleAgent.__new__(mba.MicroBubbleAgent)
    engine = CapturingEngine()
    agent.engine = engine

    events = [e async for e in agent.chat_stream(
        "刚才那条备注写上了吗？", session_id="verify_s1", db=None, user_id=None)]
    assert any(e.type == "done" for e in events)

    # 入口读 → 透传
    assert engine.captured.get("last_write_fact") is not None
    assert engine.captured["last_write_fact"]["tool"] == "update_task"
    # done 写回 → 本轮 create/update 成功事实覆盖旧事实
    turn = json.loads(fake_sm.meta["verify_s1"]["last_turn"])
    assert turn["write_fact"]["tool"] == "update_task"
    assert turn["write_fact"]["task_id"] == 77


@pytest.mark.asyncio
async def test_chat_stream_no_prev_fact_passes_none(fake_sm, monkeypatch):
    """守恒: 新会话无 meta → engine 收到 last_write_fact=None (行为与修复前一致)。"""
    async def fake_ensure_ctx(db, user_id, session_id):
        return []
    async def fake_classify(question, ctx):
        return IntentResult(category=IntentCategory.CASUAL_CHAT, confidence=0.9)
    monkeypatch.setattr(mba, "_ensure_session_context", fake_ensure_ctx)
    monkeypatch.setattr(mba, "classify_intent", fake_classify)

    agent = mba.MicroBubbleAgent.__new__(mba.MicroBubbleAgent)
    engine = CapturingEngine(synth_text="你好")
    engine_read = CapturingEngine  # noqa: F841
    agent.engine = engine

    # 无写工具的 engine (复用 CapturingEngine 会写回 fact, 这里只验证入参)
    async def pure_engine(**kwargs):
        engine.captured = kwargs
        yield StreamEvent(type="done", duration_ms=1, session_id=kwargs.get("session_id"),
                          text_without_json="你好")
    engine.chat_stream = pure_engine  # type: ignore[method-assign]

    _ = [e async for e in agent.chat_stream("你好", session_id="fresh_s", db=None, user_id=None)]
    assert engine.captured.get("last_write_fact") is None
    turn = json.loads(fake_sm.meta["fresh_s"]["last_turn"])
    assert "write_fact" not in turn
