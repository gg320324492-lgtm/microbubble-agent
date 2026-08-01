"""CHAT-P1-B — 闲聊 fast path + last_turn 续讲路由（7 case）。"""

from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest

from app.agent.chat_engine import ChatEngine
from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.micro_bubble_agent import (
    MicroBubbleAgent,
    _build_follow_up_context,
    _build_last_turn,
)
from app.agent.protocol import StreamEvent
from app.agent.session_manager import SessionManager
from app.agent.thinking_config import resolve_thinking_config


def _intent(category: IntentCategory) -> IntentResult:
    return IntentResult(category=category, confidence=0.99)


async def _run_micro_stream(
    intent: IntentResult,
    message: str,
    *,
    thinking_mode: str = "balanced",
    follow_up_context: str = "",
):
    """在 micro_bubble_agent 入口跑一轮，engine/Redis/PG 全 mock。"""
    agent = MicroBubbleAgent()
    captured = {}

    async def fake_engine_stream(**kwargs):
        captured.update(kwargs)
        yield StreamEvent(
            type="done",
            mode=kwargs.get("thinking_mode") or "balanced",
            text_without_json="回答完成",
        )

    agent.engine.chat_stream = fake_engine_stream
    classify = AsyncMock(return_value=intent)
    follow_up = AsyncMock(return_value=follow_up_context)
    save_last_turn = AsyncMock()
    with patch(
        "app.agent.micro_bubble_agent._ensure_session_context",
        AsyncMock(return_value=[]),
    ), patch(
        "app.agent.micro_bubble_agent.classify_intent", classify,
    ), patch(
        "app.agent.micro_bubble_agent._build_follow_up_context", follow_up,
    ), patch(
        "app.agent.micro_bubble_agent._set_last_turn", save_last_turn,
    ):
        events = [
            event
            async for event in agent.chat_stream(
                message,
                session_id="s1",
                thinking_mode=thinking_mode,
            )
        ]
    return captured, events, classify, follow_up, save_last_turn


@pytest.mark.asyncio
async def test_casual_chat_forces_fast_config():
    """B1: casual_chat 自动覆盖 balanced，engine 复用预分类且真拿 fast 配置。"""
    captured, events, classify, _, _ = await _run_micro_stream(
        _intent(IntentCategory.CASUAL_CHAT), "你好",
    )

    classify.assert_awaited_once_with(question="你好", ctx=classify.await_args.kwargs["ctx"])
    assert captured["thinking_mode"] == "fast"
    assert captured["preclassified_intent"].category is IntentCategory.CASUAL_CHAT
    assert "闲聊风格" in captured["system"]
    assert any(event.type == "done" for event in events)

    # engine 消费同一预分类结果时不得再次调分类器，ToolContext 必须是真 fast。
    engine = ChatEngine()
    loop = MagicMock()
    engine_capture = {}

    async def run(**kwargs):
        engine_capture.update(kwargs)
        yield StreamEvent(type="done", mode="fast", text_without_json="回答完成")

    loop.run = run
    with patch("app.agent.chat_engine.classify_intent", AsyncMock()) as engine_classify, patch(
        "app.agent.chat_engine.AgenticLoop", return_value=loop,
    ), patch(
        "app.agent.chat_engine.TraceCollector", MagicMock(return_value=_AsyncTrace()),
    ):
        _ = [
            event
            async for event in engine.synthesize_stream(
                messages=captured["messages"],
                system=captured["system"],
                thinking_mode=captured["thinking_mode"],
                preclassified_intent=captured["preclassified_intent"],
            )
        ]
    engine_classify.assert_not_awaited()
    config = engine_capture["ctx"].thinking_config
    assert config.mode == "fast"
    assert config.max_tool_rounds == 0
    assert config.skip_plan_step is True
    assert config.skip_critique is True


@pytest.mark.asyncio
async def test_follow_up_forces_fast_and_injects_context():
    """B1+B2: follow_up 自动 fast，并把上一轮主题块注入 system。"""
    captured, _, _, follow_up, _ = await _run_micro_stream(
        _intent(IntentCategory.FOLLOW_UP),
        "继续",
        follow_up_context="上一轮主题：臭氧传质",
    )

    assert captured["thinking_mode"] == "fast"
    assert captured["preclassified_intent"].category is IntentCategory.FOLLOW_UP
    assert "闲聊风格" in captured["system"]
    assert "上一轮主题：臭氧传质" in captured["system"]
    follow_up.assert_awaited_once_with(None, "s1", "继续")


@pytest.mark.asyncio
async def test_search_info_keeps_requested_mode():
    """非闲聊不误套 fast，也不读取 follow_up meta。"""
    captured, _, _, follow_up, _ = await _run_micro_stream(
        _intent(IntentCategory.SEARCH_INFO), "找臭氧资料",
    )

    assert captured["thinking_mode"] == "balanced"
    assert captured["preclassified_intent"].category is IntentCategory.SEARCH_INFO
    follow_up.assert_not_awaited()


@pytest.mark.asyncio
async def test_session_meta_json_roundtrip():
    """B2: last_turn 以 JSON 写入 agent_session:{sid}:meta 并原样读回。"""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    manager = SessionManager(ttl=3600)
    payload = {"intent": "search_info", "chunk_ids": [1, 2], "topics": ["臭氧"]}
    with patch("app.agent.session_manager.get_redis", AsyncMock(return_value=redis)):
        await manager.set_session_meta("s1", "last_turn", payload)
        assert await manager.get_session_meta("s1", "last_turn") == payload
        assert await redis.ttl("agent_session:s1:meta") > 0


def test_last_turn_built_from_real_search_results():
    """B2: done 后待写对象严格含真实 ids/title/回答摘要六字段。"""
    meta = _build_last_turn(
        _intent(IntentCategory.SEARCH_INFO),
        "臭氧传质",
        "核心回答",
        [{"id": 7, "title": "臭氧传质", "content": "正文"}],
    )
    assert set(meta) == {
        "intent", "query", "chunk_ids", "answer_summary", "topics", "timestamp",
    }
    assert meta["intent"] == "search_info"
    assert meta["chunk_ids"] == [7]
    assert meta["topics"] == ["臭氧传质"]
    assert meta["answer_summary"] == "核心回答"


@pytest.mark.asyncio
async def test_follow_up_reuses_ids_and_appends_retrieval():
    """B2: 复用上轮 ID 结果集，并用上轮主题追加检索后去重注入。"""
    manager = MagicMock()
    manager.get_session_meta = AsyncMock(return_value={
        "intent": "search_info",
        "query": "臭氧怎么传质",
        "answer_summary": "上一轮讲了臭氧传质",
        "topics": ["臭氧传质"],
        "chunk_ids": [7],
    })
    retriever = MagicMock()
    retriever.retrieve = AsyncMock(return_value=[
        {"id": 7, "title": "重复", "content": "重复"},
        {"id": 8, "title": "新资料", "content": "新正文"},
    ])
    with patch("app.agent.micro_bubble_agent.session_manager", manager), patch(
        "app.agent.micro_bubble_agent._load_knowledge_by_ids",
        AsyncMock(return_value=[
            {"id": 7, "title": "旧资料", "content": "旧正文"},
        ]),
    ), patch(
        "app.services.hybrid_retriever.get_hybrid_retriever", return_value=retriever,
    ):
        block = await _build_follow_up_context(MagicMock(), "s1", "继续")

    assert "上一轮讲了臭氧传质" in block
    assert "旧资料" in block
    assert "新资料" in block
    assert block.count("[7]") == 1
    retrieval_query = retriever.retrieve.await_args.kwargs["query"]
    assert "臭氧怎么传质" in retrieval_query
    assert "臭氧传质" in retrieval_query
    assert "继续" in retrieval_query


def test_casual_prompt_persona_and_banned_templates():
    """B3: 人格块包含 80 字/自然引导，并明确禁止模板句。"""
    from app.agent.prompts import _CASUAL_GUIDELINES, get_intent_aware_guidelines

    assert get_intent_aware_guidelines("follow_up") == _CASUAL_GUIDELINES
    assert "80 字内" in _CASUAL_GUIDELINES
    assert "需要展开 XX 吗" in _CASUAL_GUIDELINES
    assert "禁止模板句" in _CASUAL_GUIDELINES
    assert resolve_thinking_config("fast").model == "qwen3:8b"


class _AsyncTrace:
    def set_intent(self, *args, **kwargs):
        pass

    def record_rich_block(self, *args, **kwargs):
        pass

    def set_critique(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False
