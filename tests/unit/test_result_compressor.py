"""测试 result_compressor.py（方案 C Stage 1）

跑法：SKIP_DB_SETUP=1 pytest tests/unit/test_result_compressor.py -v
"""

import os
os.environ.setdefault("SKIP_DB_SETUP", "1")

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.agent.intent_classifier import IntentCategory, IntentResult
from app.agent.result_compressor import (
    CompressionResult,
    _extract_items,
    compression_to_sse_event,
    compress_tool_result,
    inject_compressed_to_messages,
)


class TestExtractItems:
    """从工具结果中提取数据列表"""

    def test_extract_members(self):
        raw = {"status": "success", "count": 2, "members": [{"id": 1}, {"id": 2}]}
        items, key = _extract_items(raw)
        assert items == [{"id": 1}, {"id": 2}]
        assert key == "members"

    def test_extract_results(self):
        raw = {"status": "success", "count": 3, "results": [{"id": 1}, {"id": 2}, {"id": 3}]}
        items, key = _extract_items(raw)
        assert key == "results"
        assert len(items) == 3

    def test_extract_meetings(self):
        raw = {"meetings": [{"id": 1}], "count": 1}
        items, _ = _extract_items(raw)
        assert len(items) == 1

    def test_extract_tasks(self):
        raw = {"tasks": [{"id": 1}, {"id": 2}]}
        items, _ = _extract_items(raw)
        assert len(items) == 2

    def test_fallback_to_first_list(self):
        raw = {"unknown_key": [{"id": 1}], "status": "ok"}
        items, key = _extract_items(raw)
        assert key == "unknown_key"
        assert len(items) == 1

    def test_no_list_returns_empty(self):
        raw = {"status": "ok", "count": 0}
        items, _ = _extract_items(raw)
        assert items == []


class TestCompressToolResultMocked:
    """Mock LLM 测试 compress_tool_result"""

    @pytest.mark.asyncio
    async def test_no_compression_under_threshold(self):
        """少于阈值不压缩"""
        raw = {
            "status": "success",
            "count": 3,
            "members": [{"id": 1, "name": "张三"}, {"id": 2, "name": "李四"}, {"id": 3, "name": "王五"}],
        }
        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = MagicMock()

        result = await compress_tool_result("请教谁", intent, "query_members", raw, ctx)
        assert result is None  # 不压缩

    @pytest.mark.asyncio
    async def test_compression_over_threshold(self):
        """超过阈值时触发 Haiku 压缩"""
        members = [{"id": i, "name": f"成员{i}", "research_area": "饮用水"} for i in range(27)]
        raw = {"status": "success", "count": 27, "members": members}

        mock_response = MagicMock()
        mock_block = MagicMock()
        mock_block.text = json.dumps({
            "selected": [
                {"id": 1, "name": "杨慈", "research_area": "饮用水安全", "relevance": "直接研究饮用水灭菌"},
                {"id": 2, "name": "宋洋", "research_area": "饮用水处理", "relevance": "饮用水处理组"},
                {"id": 3, "name": "李锐远", "research_area": "管网水质", "relevance": "管网水质控制"},
            ],
            "reasoning": "按研究方向匹配饮用水，筛 top 3",
            "summary": "成员推荐 3 人（27→3）",
            "collapsed_by_default": True,
        }, ensure_ascii=False)
        mock_response.content = [mock_block]
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=mock_response)

        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = mock_llm

        result = await compress_tool_result("请教谁研究饮用水", intent, "query_members", raw, ctx)
        assert result is not None
        assert result.original_count == 27
        assert result.selected_count == 3
        assert "27→3" in result.summary
        assert result.collapsed_by_default is True

    @pytest.mark.asyncio
    async def test_compression_failure_returns_none(self):
        """压缩失败返回 None 不阻塞主流程"""
        raw = {"status": "success", "count": 10, "members": [{"id": i} for i in range(10)]}
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM 503"))

        intent = IntentResult(category=IntentCategory.RECOMMEND_PERSON, confidence=0.9)
        ctx = MagicMock()
        ctx.llm = mock_llm

        result = await compress_tool_result("请教谁", intent, "query_members", raw, ctx)
        assert result is None  # 失败不阻塞


class TestInjectCompressedToMessages:
    """验证压缩信息注入到 messages 末尾"""

    def test_inject_to_list_content(self):
        messages = [
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "..."},
            ]},
        ]
        comp = CompressionResult(
            selected=[{"id": 1, "name": "杨慈"}],
            reasoning="按研究匹配",
            original_count=27,
            selected_count=3,
            summary="3 人推荐",
        )
        inject_compressed_to_messages(messages, "query_members", "tu_1", comp)
        # 应该追加一个 text 类型的 <compressed> 块
        last = messages[-1]
        assert last["role"] == "user"
        assert len(last["content"]) == 2  # 原始 tool_result + 追加的 text
        text_block = last["content"][1]
        assert text_block["type"] == "text"
        assert "<compressed" in text_block["text"]
        assert "query_members" in text_block["text"]
        assert "27" in text_block["text"]


class TestCompressionToSseEvent:
    """CompressionResult → StreamEvent"""

    def test_sse_event_format(self):
        comp = CompressionResult(
            selected=[{"id": 1}],
            reasoning="筛选",
            original_count=27,
            selected_count=3,
            summary="3 人推荐",
        )
        evt = compression_to_sse_event("query_members", "tu_1", comp)
        assert evt.type == "tool_compressed"
        assert evt.tool_name == "query_members"
        assert evt.tool_use_id == "tu_1"
        assert evt.compression["original_count"] == 27
        assert "3 人推荐" in evt.label
