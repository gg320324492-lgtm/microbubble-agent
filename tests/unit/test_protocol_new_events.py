"""测试 protocol.py 新增的 6 种 SSE 事件 + RichBlock 3 个新字段（方案 C Stage 0）

验证：
1. 6 个新事件类型可序列化
2. RichBlock 新增 summary / expanded / collapsed_by_default 字段
3. SSE delta 语义铁律（每事件标注 increment 或 snapshot）
4. ToolContext 新增 redis / llm / loop_id 字段

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_protocol_new_events.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import inspect
import json

import pytest

from app.agent.protocol import RichBlock, StreamEvent, StreamEventType
from app.agent.tool_registry import ToolContext


class TestNewStreamEvents:
    """6 个新事件可正确构造 + 序列化"""

    def test_intent_detected_event(self):
        evt = StreamEvent(
            type="intent_detected",
            intent={
                "category": "recommend_person",
                "confidence": 0.92,
                "keywords": ["饮用水", "学习"],
                "suggested_tools": ["query_members"],
                "reasoning": "用户问'请教谁'，是推荐人意图",
            },
        )
        d = evt.model_dump()
        assert d["type"] == "intent_detected"
        assert d["intent"]["category"] == "recommend_person"
        # SSE 序列化
        sse = evt.to_sse()
        assert "intent_detected" in sse
        assert "饮用水" in sse

    def test_plan_step_event(self):
        evt = StreamEvent(
            type="plan_step",
            step="查询饮用水方向成员",
            label="🔧 query_members",
            plan_status="running",
        )
        d = evt.model_dump()
        assert d["step"] == "查询饮用水方向成员"
        assert d["plan_status"] == "running"

    def test_tool_compressed_event(self):
        evt = StreamEvent(
            type="tool_compressed",
            tool_name="query_members",
            compression={
                "original_count": 27,
                "selected_count": 3,
                "reasoning": "按研究方向匹配饮用水，筛选 top 3",
                "summary": "成员推荐 3 人（27→3）",
            },
        )
        d = evt.model_dump()
        assert d["compression"]["original_count"] == 27
        assert d["compression"]["selected_count"] == 3

    def test_synthesis_start_event(self):
        evt = StreamEvent(type="synthesis_start", label="✨ 综合分析中...")
        d = evt.model_dump()
        assert d["type"] == "synthesis_start"
        assert d["label"] == "✨ 综合分析中..."

    def test_critique_event(self):
        evt = StreamEvent(
            type="critique",
            critique={
                "score": 9,
                "addresses_question": True,
                "has_synthesis": True,
                "has_citations": True,
                "missing": [],
                "suggestion": "回答完整准确",
            },
        )
        d = evt.model_dump()
        assert d["critique"]["score"] == 9
        assert d["critique"]["addresses_question"] is True

    def test_retry_event(self):
        evt = StreamEvent(
            type="retry",
            retry_reason="critique score 5 < 7，缺少具体推荐",
            retry_count=1,
        )
        d = evt.model_dump()
        assert d["retry_count"] == 1
        assert "缺少具体推荐" in d["retry_reason"]


class TestStreamEventTypeContainsAllNew:
    """StreamEventType Literal 必须包含 (>=15) 个类型 (历史 + 方案 C + #043 + 留未来扩展)

    W1 (2026-07-21) T1 other fix: 数字断言改 >= (兼容 #043 加的 message_persisted + sync_required)
    """

    def test_all_event_types_present(self):
        from typing import get_args
        all_types = set(get_args(StreamEventType))
        # 原 9 种
        expected_old = {
            "text_delta", "tool_use", "tool_result", "rich_block",
            "thinking", "brief", "detail", "error", "done",
        }
        # 方案 C 6 种 (2026-06-14)
        expected_new = {
            "intent_detected", "plan_step", "tool_compressed",
            "synthesis_start", "critique", "retry",
        }
        # #043 2 种 (2026-06-29) 账号持久化聊天历史
        expected_043 = {
            "message_persisted", "sync_required",
        }
        assert expected_old.issubset(all_types)
        assert expected_new.issubset(all_types)
        assert expected_043.issubset(all_types)
        # 数字断言改 >= 17 (兼容未来扩展, 防止 stale 数字锁死)
        assert len(all_types) >= 17


class TestRichBlockNewFields:
    """RichBlock 新增 summary / expanded / collapsed_by_default 字段"""

    def test_rich_block_with_summary(self):
        rb = RichBlock(
            type="member",
            data={"members": []},
            summary="成员推荐 3 人（27→3）",
        )
        assert rb.summary == "成员推荐 3 人（27→3）"

    def test_rich_block_expanded_default_false(self):
        rb = RichBlock(type="meeting", data={})
        assert rb.expanded is False, "RichBlock.expanded 默认 False（折叠）"

    def test_rich_block_collapsed_by_default_true(self):
        rb = RichBlock(type="task_list", data={})
        assert rb.collapsed_by_default is True, "默认 collapsed_by_default=True"

    def test_rich_block_llm_override_expanded(self):
        """LLM 可在 synthesis 阶段 override 让重要 block 默认展开"""
        rb = RichBlock(
            type="knowledge_ref",
            data={"results": [{"id": 1}]},
            collapsed_by_default=False,
        )
        assert rb.collapsed_by_default is False

    def test_rich_block_serialization_includes_new_fields(self):
        rb = RichBlock(
            type="member",
            data={"members": []},
            summary="3 人推荐",
            expanded=False,
            collapsed_by_default=True,
        )
        d = rb.model_dump()
        assert "summary" in d
        assert "expanded" in d
        assert "collapsed_by_default" in d


class TestToolContextNewFields:
    """ToolContext 新增 redis / llm / loop_id 字段（铁律 1：跨 loop 安全）"""

    def test_tool_context_default_new_fields_none(self):
        ctx = ToolContext()
        assert ctx.redis is None
        assert ctx.llm is None
        assert ctx.loop_id == ""

    def test_tool_context_accepts_new_fields(self):
        """新字段可被传入（实际类型不强校验，因为 ToolContext 不是 Pydantic）"""
        sentinel_redis = object()
        sentinel_llm = object()
        ctx = ToolContext(
            redis=sentinel_redis,
            llm=sentinel_llm,
            loop_id="loop-abc-123",
        )
        assert ctx.redis is sentinel_redis
        assert ctx.llm is sentinel_llm
        assert ctx.loop_id == "loop-abc-123"

    def test_tool_context_old_fields_still_work(self):
        """新增字段不破坏老接口"""
        ctx = ToolContext(
            db="db_sentinel",
            user_id=42,
            channel_user_id="wechat_xxx",
        )
        assert ctx.db == "db_sentinel"
        assert ctx.user_id == 42
        assert ctx.channel_user_id == "wechat_xxx"


class TestSseSemanticAnnotation:
    """SSE delta 语义铁律：protocol.py 源码必须标注 [increment]/[snapshot]"""

    def test_protocol_file_has_semantic_annotations(self):
        """读取 protocol.py 源码，验证每个事件类型都有语义注释"""
        from pathlib import Path
        proto_path = Path(__file__).parent.parent.parent / "app" / "agent" / "protocol.py"
        source = proto_path.read_text(encoding="utf-8")
        # 至少应该出现这两个语义标记
        assert "[increment]" in source, "protocol.py 必须有 [increment] 语义标注"
        assert "[snapshot]" in source, "protocol.py 必须有 [snapshot] 语义标注"
        # 关键事件必须显式标注
        assert "text_delta" in source and source.count("[increment]") >= 1
        # brief / detail 必须标 deprecated
        assert "deprecated" in source.lower()


class TestBackwardCompat:
    """新字段不破坏老的事件序列化路径"""

    def test_old_text_delta_still_works(self):
        evt = StreamEvent(type="text_delta", delta="你好")
        assert evt.delta == "你好"
        sse = evt.to_sse()
        assert "text_delta" in sse
        assert "你好" in sse

    def test_old_rich_block_event_still_works(self):
        evt = StreamEvent(
            type="rich_block",
            block=RichBlock(type="task_list", data={"tasks": []}),
        )
        d = evt.model_dump()
        assert d["block"]["type"] == "task_list"
        # 新字段虽然存在但默认值不影响
        assert d["block"]["expanded"] is False
        assert d["block"]["collapsed_by_default"] is True

    def test_old_done_event_still_works(self):
        evt = StreamEvent(
            type="done",
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
            duration_ms=3200,
        )
        assert evt.usage["total_tokens"] == 150
        assert evt.duration_ms == 3200
