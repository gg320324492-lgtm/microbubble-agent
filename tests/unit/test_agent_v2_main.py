"""测试 v2 主类 MicroBubbleAgent + ChatEngine（不调 LLM / 不需 DB）

覆盖：
- MicroBubbleAgent 单例 + 三个公开方法签名
- _build_user_content 文本注入时间
- _build_user_content 多模态路径
- _is_meeting_transcript_query 检测
- ChatEngine 内部辅助函数 _extract_rich_block

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_agent_v2_main.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import asyncio
import pytest

from app.agent.chat_engine import ChatEngine, _extract_rich_block, _last_user_text
from app.agent.micro_bubble_agent import MicroBubbleAgent, agent as global_agent
from app.agent.prompts import (
    _is_meeting_transcript_query,
    get_meeting_analyzer_prompt,
)
from app.agent.protocol import RichBlock, StreamEvent


# ============================================================================
# Prompts 测试
# ============================================================================


class TestPrompts:
    def test_meeting_transcript_detection(self):
        assert _is_meeting_transcript_query("【张三】今天开什么会？") is True
        assert _is_meeting_transcript_query("这是会议记录：xxx") is True
        assert _is_meeting_transcript_query("请转录这段音频") is True
        assert _is_meeting_transcript_query("今天的发言内容") is True
        assert _is_meeting_transcript_query("张三发言：今天的重点") is True

    def test_normal_query_not_meeting(self):
        assert _is_meeting_transcript_query("我最近有什么任务？") is False
        assert _is_meeting_transcript_query("zeta 电位是什么？") is False
        assert _is_meeting_transcript_query("") is False
        assert _is_meeting_transcript_query(None) is False

    def test_get_meeting_analyzer_prompt(self):
        prompt = get_meeting_analyzer_prompt()
        assert "会议分析助手模式" in prompt
        assert "analyze_meeting_transcript" in prompt
        assert "query_members" in prompt


# ============================================================================
# MicroBubbleAgent v2 测试
# ============================================================================


class TestMicroBubbleAgentV2:
    def test_singleton(self):
        assert global_agent is not None
        assert isinstance(global_agent, MicroBubbleAgent)
        # 不应该是旧 core 的实例
        from app.agent.core import MicroBubbleAgent as LegacyAgent
        assert not isinstance(global_agent, LegacyAgent)

    def test_has_three_public_methods(self):
        assert hasattr(global_agent, "chat")
        assert hasattr(global_agent, "chat_stream")
        assert hasattr(global_agent, "clear_session")

    def test_chat_is_coroutine_function(self):
        import inspect
        assert inspect.iscoroutinefunction(global_agent.chat)

    def test_chat_stream_is_async_gen_function(self):
        import inspect
        assert inspect.isasyncgenfunction(global_agent.chat_stream)

    def test_clear_session_is_coroutine_function(self):
        import inspect
        assert inspect.iscoroutinefunction(global_agent.clear_session)

    def test_build_user_content_text(self):
        """纯文本消息应注入【当前时间】前缀"""
        content = global_agent._build_user_content(
            "我最近有什么任务？",
            image_data=None,
            image_media_type="image/png",
        )
        assert isinstance(content, str)
        assert "[当前时间:" in content
        assert "我最近有什么任务？" in content

    def test_build_user_content_with_image(self):
        """带图片应返回 list（多模态 content blocks）"""
        fake_image = b"\x89PNG_FAKE_BYTES"
        content = global_agent._build_user_content(
            "看看这张图",
            image_data=fake_image,
            image_media_type="image/png",
        )
        assert isinstance(content, list)
        assert content[0]["type"] == "image"
        assert content[0]["source"]["type"] == "base64"
        assert content[0]["source"]["media_type"] == "image/png"
        # 第二项是文本
        assert content[1]["type"] == "text"
        assert "看看这张图" in content[1]["text"]


# ============================================================================
# ChatEngine 测试
# ============================================================================


class TestChatEngine:
    def test_engine_singleton_via_agent(self):
        assert isinstance(global_agent.engine, ChatEngine)

    def test_engine_has_methods(self):
        engine = ChatEngine()
        # 2026-06-14 方案 C Stage 2：ChatEngine 重写为单阶段流式
        assert hasattr(engine, "chat_with_brief_and_detail"), "薄壳保留（旧 API 兼容）"
        assert hasattr(engine, "chat_stream"), "薄壳保留（旧 API 兼容）"
        assert hasattr(engine, "synthesize_stream"), "新主入口（方案 C 核心）"
        assert hasattr(engine, "_legacy_chat_stream"), "Kill switch 退回老实现（铁律 6）"
        # 删除的旧方法（_generate_with_tools / _append_detail_background 已迁到 agentic_loop.py）

    def test_last_user_text(self):
        msgs = [
            {"role": "system", "content": "你是助手"},
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！"},
            {"role": "user", "content": "我有什么任务？"},
        ]
        assert _last_user_text(msgs) == "我有什么任务？"

    def test_last_user_text_empty(self):
        assert _last_user_text([]) == ""
        assert _last_user_text([{"role": "assistant", "content": "x"}]) == ""

    def test_last_user_text_with_list_content(self):
        msgs = [
            {"role": "user", "content": [
                {"type": "image", "source": {"type": "base64"}},
                {"type": "text", "text": "看图"},
            ]}
        ]
        assert _last_user_text(msgs) == "看图"

    def test_extract_rich_block_with_hint(self):
        """工具结果里显式 rich_block_type 时应提取"""
        result = {
            "status": "success",
            "id": 84,
            "title": "例会",
            "key_points": ["要点1", "要点2"],
            "rich_block_type": "meeting",
        }
        rb = _extract_rich_block("custom_tool", result)
        assert rb is not None
        assert rb.type == "meeting"
        assert rb.data["id"] == 84
        assert "rich_block_type" not in rb.data  # 应被剥离

    def test_extract_rich_block_implicit_meetings(self):
        """query_meetings 隐式映射到 meeting"""
        result = {
            "status": "success",
            "count": 2,
            "meetings": [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}],
        }
        rb = _extract_rich_block("query_meetings", result)
        assert rb is not None
        assert rb.type == "meeting"
        assert "会议列表" in (rb.title or "")

    def test_extract_rich_block_implicit_tasks(self):
        result = {"status": "success", "count": 1, "tasks": []}
        rb = _extract_rich_block("query_tasks", result)
        assert rb is not None
        assert rb.type == "task_list"

    def test_extract_rich_block_implicit_knowledge(self):
        result = {"status": "success", "results": []}
        rb = _extract_rich_block("search_knowledge", result)
        assert rb is not None
        assert rb.type == "knowledge_ref"

    def test_extract_rich_block_error_no_block(self):
        """error 结果不产生 rich block"""
        result = {"status": "error", "message": "查询失败"}
        rb = _extract_rich_block("query_meetings", result)
        assert rb is None

    def test_extract_rich_block_unknown_tool_no_block(self):
        """未在隐式映射里的工具不产生 rich block"""
        result = {"status": "success", "ok": True}
        rb = _extract_rich_block("web_search", result)
        assert rb is None


# ============================================================================
# 兼容性测试：v2 不破坏旧 API
# ============================================================================


class TestBackwardCompat:
    def test_old_agent_still_importable(self):
        """旧 core.py 仍可导入（兼容性）"""
        from app.agent.core import agent as legacy_agent
        from app.agent.core import MicroBubbleAgent as LegacyAgent
        assert legacy_agent is not None
        assert isinstance(legacy_agent, LegacyAgent)
        # 旧 agent 仍可调用（虽然 v2 是新的）
        assert hasattr(legacy_agent, "chat")
        assert hasattr(legacy_agent, "chat_stream")
        assert hasattr(legacy_agent, "clear_session")

    def test_v2_and_legacy_coexist(self):
        """新旧两个 agent 单例共存"""
        from app.agent.core import agent as legacy
        assert legacy is not global_agent
        assert isinstance(legacy, MicroBubbleAgent) is False  # legacy 不是 v2
        assert isinstance(global_agent, MicroBubbleAgent) is True
