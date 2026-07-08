"""测试 agentic_loop.py（方案 C Stage 1）

覆盖：
- _sanitize_pending_tool_uses 防御（铁律 4）
- 事件流顺序 [increment]/[snapshot] 标注
- CancelledError 路径
- 不通过 ctx.redis/llm 注入的代码全部走 fallback

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_agentic_loop.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.agentic_loop import (
    AgenticLoop,
    _block_dump,
    _expand_concept_to_four_domain,
    _last_user_text,
    _sanitize_pending_tool_uses,
    CONCEPT_DOMAIN_TOOLS,
)
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.protocol import StreamEvent, StreamEventType
from app.agent.tool_registry import ToolContext


class TestExpandConceptToFourDomain:
    """P2-3 fix (2026-07-08): 4 域 fan-out 截断时优先保留 4 域工具.

    bug: 之前实现 simple slice [:MAX], 当 LLM planned 6 个工具时按原顺序
    砍第 6 个, 可能砍掉 query_members (4 域) 而保留 LLM 最后选的 get_meeting_transcript.
    fix: 4 域工具移到前部, LLM planned 的非 4 域保留尾部, 截断时优先砍非 4 域.
    """

    def test_single_4domain_tool_appended_to_length_4(self):
        """planned=['search_knowledge'] → 补齐 4 域 = 4 个."""
        result = _expand_concept_to_four_domain(['search_knowledge'])
        assert len(result) == 4
        # 4 域 tool 全在结果里
        for tool in CONCEPT_DOMAIN_TOOLS:
            assert tool in result
        assert 'search_knowledge' in result

    def test_4domain_first_others_last_for_truncation(self):
        """planned 含 4 域 + 非 4 域 → 4 域在前, 非 4 域在后 (截断安全)."""
        result = _expand_concept_to_four_domain(
            ['search_knowledge', 'get_meeting_transcript']
        )
        # 4 域 tool 应在结果前半部
        four_domain_indices = [i for i, t in enumerate(result) if t in CONCEPT_DOMAIN_TOOLS]
        other_indices = [i for i, t in enumerate(result) if t not in CONCEPT_DOMAIN_TOOLS]
        # 所有 4 域 index < 所有非 4 域 index (4 域在前)
        assert max(four_domain_indices) < min(other_indices), \
            f"4 域必须在前部 (用于截断时优先保留), 实际 indices: {[(i, t) for i, t in enumerate(result)]}"
        # 4 域全保
        for tool in CONCEPT_DOMAIN_TOOLS:
            assert tool in result

    def test_six_non_4domain_truncated_keeps_all_4domain(self):
        """P2-3 核心 bug 场景: planned 6 个非 4 域 → MAX=5 → 4 域全保 + 1 个非 4 域.

        修复前: 简单 slice [:5] 砍掉第 6 个, 但 4 域补全后追加在末尾,
                砍掉的是 query_members 等 4 域工具.
        修复后: 4 域移到前部, 砍掉的是 LLM planned 的非 4 域尾部.
        """
        planned = ['a', 'b', 'c', 'd', 'e', 'f']  # 6 个非 4 域
        result = _expand_concept_to_four_domain(planned)
        # MAX=5 (默认 settings.AGENT_PLAN_STEP_MAX), 所以结果长度 = 5
        assert len(result) == 5
        # 4 域工具**全部**保留 (不被砍)
        for tool in CONCEPT_DOMAIN_TOOLS:
            assert tool in result, f"4 域 tool {tool} 应被保留"
        # 非 4 域只有 1 个 (砍掉 5 个), 必须是 'a' (LLM 原顺序第一个)
        others = [t for t in result if t not in CONCEPT_DOMAIN_TOOLS]
        assert others == ['a']

    def test_four_domain_dedup_when_llm_planned_partial(self):
        """LLM 已 planned 部分 4 域 → 只补缺失的."""
        result = _expand_concept_to_four_domain(
            ['search_knowledge', 'list_formulas', 'query_members']
        )
        # 4 域中 list_hypotheses 缺失 → 自动补
        assert 'list_hypotheses' in result
        # 没有重复 (4 域去重)
        assert len(result) == len(set(result))
        # search_knowledge 仍在结果 (LLM 原 planned)
        assert 'search_knowledge' in result


class TestSanitizePendingToolUses:
    """悬空 tool_use 防御（铁律 4）"""

    def test_no_pending_no_change(self):
        messages = [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_1", "name": "x", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "ok"},
            ]},
        ]
        n = _sanitize_pending_tool_uses(messages, reason="test")
        assert n == 0
        # 不应追加哨兵
        assert len(messages) == 3

    def test_one_pending_gets_sentinel(self):
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_1", "name": "x", "input": {}},
                {"type": "tool_use", "id": "tu_2", "name": "y", "input": {}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "ok"},
            ]},
        ]
        n = _sanitize_pending_tool_uses(messages, reason="max_rounds_reached")
        assert n == 1
        # 应该追加一条 user 消息，含 tu_2 的哨兵
        assert len(messages) == 3
        last_msg = messages[-1]
        assert last_msg["role"] == "user"
        assert isinstance(last_msg["content"], list)
        sentinel = last_msg["content"][0]
        assert sentinel["type"] == "tool_result"
        assert sentinel["tool_use_id"] == "tu_2"
        assert "strange close" in sentinel["content"]
        assert "max_rounds_reached" in sentinel["content"]

    def test_multiple_pending_each_gets_sentinel(self):
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_1"},
                {"type": "tool_use", "id": "tu_2"},
                {"type": "tool_use", "id": "tu_3"},
            ]},
            # 全部没 close
        ]
        n = _sanitize_pending_tool_uses(messages, reason="cancelled")
        assert n == 3
        last = messages[-1]
        assert len(last["content"]) == 3


class TestLastUserText:
    """从 messages 提取最后 user 文本"""

    def test_string_content(self):
        messages = [{"role": "user", "content": "你好"}]
        assert _last_user_text(messages) == "你好"

    def test_list_content_with_text_block(self):
        messages = [{"role": "user", "content": [
            {"type": "text", "text": "请教谁"},
            {"type": "image", "source": {}},
        ]}]
        assert _last_user_text(messages) == "请教谁"

    def test_empty_messages(self):
        assert _last_user_text([]) == ""

    def test_only_assistant_messages(self):
        messages = [{"role": "assistant", "content": "hi"}]
        assert _last_user_text(messages) == ""


class TestBlockDump:
    """content block → dict 转换"""

    def test_dict_passthrough(self):
        d = {"type": "text", "text": "hi"}
        assert _block_dump(d) == d

    def test_unknown_object(self):
        class FakeBlock:
            type = "text"
            text = "hi"
        result = _block_dump(FakeBlock())
        assert result["type"] == "text"
        assert result["text"] == "hi"


class TestEventStreamSemantics:
    """事件流 [increment]/[snapshot] 标注 — 通过源码静态分析验证"""

    def test_agentic_loop_documents_event_order(self):
        """agentic_loop.py 源码 docstring 必须列出事件顺序"""
        from pathlib import Path
        loop_path = Path(__file__).parent.parent.parent / "app" / "agent" / "agentic_loop.py"
        source = loop_path.read_text(encoding="utf-8")
        # 关键事件必须标 increment/snapshot
        assert "[increment]" in source, "agentic_loop.py 必须标注 increment 事件"
        assert "[snapshot]" in source, "agentic_loop.py 必须标注 snapshot 事件"
        # 必须列出关键事件
        for evt in ["text_delta", "tool_use", "tool_result", "synthesis_start", "critique", "retry"]:
            assert evt in source, f"事件 {evt} 必须在 agentic_loop.py 出现"


class TestCancelledErrorPath:
    """CancelledError 时 sanitize + re-raise（铁律 4）"""

    @pytest.mark.asyncio
    async def test_cancelled_sanitizes_messages(self):
        """CancelledError 后 messages 应该被 sanitize"""
        loop = AgenticLoop()
        messages = [
            {"role": "assistant", "content": [
                {"type": "tool_use", "id": "tu_1", "name": "x", "input": {}},
            ]},
        ]
        intent = IntentResult(category=IntentCategory.SEARCH_INFO)

        # Mock LLM 第一次调就抛 CancelledError
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=asyncio.CancelledError())

        ctx = MagicMock()
        ctx.llm = mock_llm
        ctx.redis = None
        ctx.trace = None

        with pytest.raises(asyncio.CancelledError):
            async for evt in loop.run(messages, "system", intent, ctx, max_rounds=2):
                pass

        # 验证：messages 应该被 sanitize 追加哨兵
        assert len(messages) >= 2
        last = messages[-1]
        assert last["role"] == "user"
        assert isinstance(last["content"], list)
        assert last["content"][0]["tool_use_id"] == "tu_1"
        assert "cancelled" in last["content"][0]["content"]


class TestAbortVsNormal:
    """正常流 vs 异常流：异常时仍有 done 事件吗？"""

    @pytest.mark.asyncio
    async def test_llm_error_yields_error_event(self):
        """非 CancelledError 异常时 yield error 事件"""
        loop = AgenticLoop()
        messages = [{"role": "user", "content": "hi"}]
        intent = IntentResult(category=IntentCategory.SEARCH_INFO)

        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM boom"))
        # 2026-06-14 Stage 5：synthesize_stream 用 `async for stream in llm.stream(...)`，
        # 需要一个 async generator 抛错（不是 AsyncMock，AsyncMock 是 awaitable）
        async def boom_stream(**kwargs):
            if False:
                yield None  # 变成 async generator
            raise RuntimeError("stream LLM boom")
        mock_llm.stream = boom_stream
        ctx = MagicMock()
        ctx.llm = mock_llm
        ctx.redis = None
        ctx.trace = None

        events = []
        with pytest.raises(RuntimeError):
            async for evt in loop.run(messages, "system", intent, ctx, max_rounds=1):
                events.append(evt)

        # 应该有 error 事件
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) >= 1
        assert "AGENTIC_LOOP_ERROR" in error_events[0].code
