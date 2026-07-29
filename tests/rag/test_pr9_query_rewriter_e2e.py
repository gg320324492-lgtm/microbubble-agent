"""PR9 / W95 — QueryRewriter 专项 e2e 测试 (8 case)

派工锚点: W95 +8
派工日期: 2026-07-30

测试策略: mock PR4 synonym_dict (未建场景 + 已建场景) + mock LLM 兜底
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockMessagesResponse:
    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


def make_mock_anthropic(json_text: str):
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MockMessagesResponse(json_text))
    return client


class TestQueryRewriterLayer1:
    """Layer 1: synonym_dict (PR4) 测试"""

    def test_no_synonym_dict_returns_original(self):
        """PR4 synonym_dict 未建 → 仅原 query"""
        from app.services.query_rewriter import QueryRewriter

        rw = QueryRewriter(max_variants=5, enable_llm=False)
        result = rw.rewrite_sync("微纳米气泡")
        assert result == ["微纳米气泡"]

    def test_with_synonym_dict_top_level(self):
        """PR4 synonym_dict 顶层实例 + expand() 返回列表"""
        from app.services.query_rewriter import QueryRewriter

        # mock 模块
        fake_sd_module = MagicMock()
        fake_sd_module.synonym_dict = MagicMock()
        fake_sd_module.synonym_dict.expand = MagicMock(return_value=["纳米气泡", "微泡"])

        rw = QueryRewriter(max_variants=5, enable_llm=False)
        with patch.dict(sys.modules, {"app.services.synonym_dict": fake_sd_module}):
            result = rw.rewrite_sync("微纳米气泡")
        assert result[0] == "微纳米气泡"  # 原 query 在第 1 位
        assert "纳米气泡" in result
        assert "微泡" in result

    def test_with_synonym_dict_factory(self):
        """PR4 synonym_dict 工厂函数模式"""
        from app.services.query_rewriter import QueryRewriter

        fake_sd_module = MagicMock()
        fake_sd_instance = MagicMock()
        fake_sd_instance.expand = MagicMock(return_value=["气泡"])
        fake_sd_module.get_synonym_dict = MagicMock(return_value=fake_sd_instance)
        # 顶层 synonym_dict 没有 → 让 pattern 1 raise AttributeError
        # 这样会落到 pattern 2 工厂调用
        del fake_sd_module.synonym_dict  # 删除属性 → pattern 1 raise

        rw = QueryRewriter(max_variants=5, enable_llm=False)
        with patch.dict(sys.modules, {"app.services.synonym_dict": fake_sd_module}):
            result = rw.rewrite_sync("微泡")
        assert "气泡" in result

    def test_synonym_dict_returns_empty_list(self):
        """synonym_dict.expand() 返回 [] → 走 LLM 兜底"""
        from app.services.query_rewriter import QueryRewriter

        fake_sd_module = MagicMock()
        fake_sd_module.synonym_dict = MagicMock()
        fake_sd_module.synonym_dict.expand = MagicMock(return_value=[])

        rw = QueryRewriter(max_variants=5, enable_llm=False)  # LLM 关闭
        with patch.dict(sys.modules, {"app.services.synonym_dict": fake_sd_module}):
            result = rw.rewrite_sync("test")
        # LLM 关闭, synonym_dict 返回 [], 结果只有原 query
        assert result == ["test"]


class TestQueryRewriterAsync:
    """异步版 + LLM 兜底"""

    @pytest.mark.asyncio
    async def test_async_rewrite_no_synonym_dict_llm_disabled(self):
        from app.services.query_rewriter import QueryRewriter

        rw = QueryRewriter(max_variants=5, enable_llm=False)
        result = await rw.rewrite("微纳米气泡水处理")
        assert result == ["微纳米气泡水处理"]

    @pytest.mark.asyncio
    async def test_async_rewrite_with_llm_fallback(self):
        """synonym_dict 缺, LLM 兜底启用"""
        from app.services.query_rewriter import QueryRewriter

        rw = QueryRewriter(max_variants=5, enable_llm=True)
        llm_json = '["纳米气泡污水处理", "microbubble water treatment", "微泡水处理"]'
        # get_anthropic_client 在 _llm_rewrite 函数体内懒导入 → patch 源模块
        with patch("app.core.llm.get_anthropic_client", return_value=make_mock_anthropic(llm_json)):
            result = await rw.rewrite("微纳米气泡水处理")
        assert result[0] == "微纳米气泡水处理"
        assert "纳米气泡污水处理" in result
        assert "microbubble water treatment" in result

    @pytest.mark.asyncio
    async def test_async_rewrite_llm_codeblock(self):
        """LLM 返回 markdown 代码块包裹的 JSON 数组"""
        from app.services.query_rewriter import QueryRewriter

        rw = QueryRewriter(max_variants=5, enable_llm=True)
        llm_text = '```json\n["变体A", "变体B"]\n```'
        with patch("app.core.llm.get_anthropic_client", return_value=make_mock_anthropic(llm_text)):
            result = await rw.rewrite("test")
        assert "变体A" in result
        assert "变体B" in result


class TestQueryRewriterEdgeCases:
    """边界"""

    @pytest.mark.asyncio
    async def test_max_variants_limit(self):
        """max_variants 限制生效"""
        from app.services.query_rewriter import QueryRewriter

        fake_sd_module = MagicMock()
        fake_sd_module.synonym_dict = MagicMock()
        fake_sd_module.synonym_dict.expand = MagicMock(return_value=["a", "b", "c", "d", "e", "f"])

        rw = QueryRewriter(max_variants=3, enable_llm=False)
        with patch.dict(sys.modules, {"app.services.synonym_dict": fake_sd_module}):
            result = rw.rewrite_sync("test")
        # max=3, 含原 query, 总长 ≤ 3
        assert len(result) <= 3
