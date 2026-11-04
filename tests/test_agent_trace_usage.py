"""agent trace token 观测接链（2026-11-04 A 档）

背景: `TraceCollector.set_usage()` 自 2026-06-14 定义后**全仓零调用** ⇒
`agent_traces.input_tokens` 2623 行全 NULL, 前端 AgentTracesView /
MobileMessageBubble 早就在渲染 total_tokens 却永远拿不到数据。

本文件锁住新接的三件事:
① add_usage 的累计语义 (含 usage 初值为 None 的情况)
② contextvar 只在 `async with trace` 作用域内生效, 退出即解绑 (不污染后续请求)
③ LLMClient._report_usage 对缺 usage 的响应必须静默安全 (观测不得炸主链路)
"""
from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.agent.tracing import TraceCollector, add_usage_to_current_trace, _current_trace
from app.core.llm import LLMClient


def _mk():
    return TraceCollector(user_id=1, session_id="s-test", message="hi")


@contextmanager
def _no_persist():
    """阻断 trace 落库。

    ⚠️ 两个入口都必须堵：`_schedule_persist`（Celery 退路）与
    `_persist_now`（2026-09-11 起的**进程内直写**，正常/abort/error 三条路径
    都走它）。只 patch 前者会让测试真的写进生产 agent_traces ——
    2026-11-04 实测踩过：库里多出一条 session_id='s-test' 的假记录，
    且同类老测试已在生产表里留下 30 条 session_id='s1' / message='hi' 的残留。
    """
    with patch.object(TraceCollector, "_schedule_persist", lambda self: None), \
         patch.object(TraceCollector, "_persist_now", AsyncMock(return_value=None)):
        yield


# ---------- ① 累计语义 ----------


def test_add_usage_accumulates_across_calls():
    c = _mk()
    c.add_usage(100, 20)
    assert c.usage == {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
    c.add_usage(50, 10)
    assert c.usage["input_tokens"] == 150
    assert c.usage["output_tokens"] == 30
    assert c.usage["total_tokens"] == 180


def test_add_usage_survives_none_usage():
    """老数据/未初始化路径: usage 为 None 时也要能累计。"""
    c = _mk()
    c.usage = None
    c.add_usage(7, 3)
    assert c.usage["input_tokens"] == 7
    assert c.usage["total_tokens"] == 10


def test_add_usage_zero_is_safe():
    c = _mk()
    c.add_usage(0, 0)
    assert c.usage["total_tokens"] == 0


# ---------- ② contextvar 作用域 ----------


def test_helper_is_noop_without_collector():
    """不在 `async with trace` 内 (如意图分类早于 trace 创建) ⇒ 静默跳过, 不抛。"""
    assert _current_trace.get() is None
    add_usage_to_current_trace(10, 5)
    assert _current_trace.get() is None


@pytest.mark.asyncio
async def test_collector_bound_only_inside_async_with():
    c = _mk()
    with _no_persist():
        async with c:
            assert _current_trace.get() is c
            add_usage_to_current_trace(1000, 50)
            assert c.usage["input_tokens"] == 1000
        # 退出后必须解绑, 且不得再写入已完成的 collector
        assert _current_trace.get() is None
        add_usage_to_current_trace(999, 1)
        assert c.usage["input_tokens"] == 1000


# ---------- ③ 上报入口的健壮性 ----------


def test_report_usage_tolerates_missing_usage():
    """观测函数绝不能把对话主链路带崩: None / 无 usage / 非整型都要静默。"""
    client = LLMClient.__new__(LLMClient)
    client._report_usage(None)
    client._report_usage(object())

    class _Bad:
        class usage:  # noqa: N801 - 故意造一个取不到整数的 usage
            input_tokens = "abc"
            output_tokens = None

    client._report_usage(_Bad())


def test_report_usage_writes_into_collector():
    c = _mk()

    class _U:
        input_tokens = 4321
        output_tokens = 87

    class _Resp:
        usage = _U()

    with _no_persist():
        token = _current_trace.set(c)
        try:
            LLMClient.__new__(LLMClient)._report_usage(_Resp())
        finally:
            _current_trace.reset(token)
    assert c.usage["input_tokens"] == 4321
    assert c.usage["output_tokens"] == 87
