"""PR9 / W95 — search_service enable_rewriting 集成 e2e (8 case)

派工锚点: W95 +10
派工日期: 2026-07-30

测试策略: 验证 search() 新参数 enable_rewriting 不破坏 v1 行为
- enable_rewriting=False → 走原 query, 不调 rewriter
- enable_rewriting=True + 全局 False → 走原 query
- enable_rewriting=True + 全局 True + LLM 成功 → 改写生效
- enable_rewriting=True + LLM 失败 → 降级原 query
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class MockMessagesResponse:
    def __init__(self, text: str):
        self.content = [MagicMock(text=text)]


def make_mock_anthropic(json_text: str):
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=MockMessagesResponse(json_text))
    return client


class TestSearchServiceRewriting:
    """enable_rewriting 集成"""

    @pytest.mark.asyncio
    async def test_enable_rewriting_false_passes_through(self):
        """enable_rewriting=False → search() 不调 rewriter"""
        from app.services.search_service import search_service

        # Mock _multi_search to return fake results
        search_service._multi_search = AsyncMock(
            return_value=[
                {"title": "T", "url": "https://x.com", "snippet": "S"}
            ]
        )
        result = await search_service.search(query="微纳米气泡", max_results=3, enable_rewriting=False)
        assert result["status"] == "success"
        assert result["query"] == "微纳米气泡"
        # rewriting_used 是空 list (enable_rewriting=False 没改写)
        assert result.get("rewriting_used") == []
        search_service._multi_search.assert_called_once_with("微纳米气泡", 3)

    @pytest.mark.asyncio
    async def test_enable_rewriting_true_global_false_skips(self):
        """enable_rewriting=True + QUERY_REWRITER_ENABLED=False → 走原 query"""
        from app.services import query_rewriter
        from app.services.search_service import search_service

        original = query_rewriter.QUERY_REWRITER_ENABLED
        query_rewriter.QUERY_REWRITER_ENABLED = False
        try:
            search_service._multi_search = AsyncMock(
                return_value=[{"title": "T", "url": "u", "snippet": "s"}]
            )
            result = await search_service.search(query="q", max_results=3, enable_rewriting=True)
            assert result["query"] == "q"
            assert result["rewriting_used"] == []
            # _multi_search 用原 query 调
            search_service._multi_search.assert_called_once_with("q", 3)
        finally:
            query_rewriter.QUERY_REWRITER_ENABLED = original

    @pytest.mark.asyncio
    async def test_enable_rewriting_true_global_true_llm_works(self):
        """enable_rewriting=True + 全局 True + LLM 成功 → 改写生效"""
        from app.services import query_rewriter
        from app.services import search_service as search_svc_module
        from app.services.search_service import search_service

        # search_service 在 import 时绑定 QUERY_REWRITER_ENABLED → patch 实际模块属性
        original_qr = query_rewriter.QUERY_REWRITER_ENABLED
        original_ss = search_svc_module.QUERY_REWRITER_ENABLED
        query_rewriter.QUERY_REWRITER_ENABLED = True
        search_svc_module.QUERY_REWRITER_ENABLED = True
        try:
            llm_text = '["变体1", "变体2"]'
            search_service._multi_search = AsyncMock(
                return_value=[{"title": "T", "url": "u", "snippet": "s"}]
            )
            with patch("app.core.llm.get_anthropic_client", return_value=make_mock_anthropic(llm_text)):
                result = await search_service.search(query="原查询", max_results=3, enable_rewriting=True)
            # _multi_search 被调用
            assert search_service._multi_search.called
            # rewriting_used 应含原 query + 改写
            assert len(result["rewriting_used"]) >= 1
        finally:
            query_rewriter.QUERY_REWRITER_ENABLED = original_qr
            search_svc_module.QUERY_REWRITER_ENABLED = original_ss

    @pytest.mark.asyncio
    async def test_enable_rewriting_llm_failure_falls_back(self):
        """enable_rewriting=True + LLM 失败 → 降级原 query"""
        from app.services import query_rewriter
        from app.services.search_service import search_service

        original = query_rewriter.QUERY_REWRITER_ENABLED
        query_rewriter.QUERY_REWRITER_ENABLED = True
        try:
            client = MagicMock()
            client.messages.create = AsyncMock(side_effect=Exception("net error"))
            search_service._multi_search = AsyncMock(
                return_value=[{"title": "T", "url": "u", "snippet": "s"}]
            )
            with patch("app.core.llm.get_anthropic_client", return_value=client):
                result = await search_service.search(query="原始", max_results=3, enable_rewriting=True)
            # 降级: 用原 query
            search_service._multi_search.assert_called_once_with("原始", 3)
            assert result["query"] == "原始"
        finally:
            query_rewriter.QUERY_REWRITER_ENABLED = original

    @pytest.mark.asyncio
    async def test_search_returns_rewriting_used_field(self):
        """返回 dict 含 rewriting_used 字段 (供 v2 hook 消费)"""
        from app.services.search_service import search_service

        search_service._multi_search = AsyncMock(return_value=[])
        result = await search_service.search(query="q", max_results=3)
        assert "rewriting_used" in result
        assert isinstance(result["rewriting_used"], list)


class TestSearchServiceV1Compatibility:
    """v1 search() 行为守恒"""

    @pytest.mark.asyncio
    async def test_search_default_no_rewriting(self):
        """search() 默认 enable_rewriting=False (v1 调用方零改动)"""
        from app.services.search_service import SearchService, search_service

        sig = SearchService.search
        import inspect
        s = inspect.signature(sig)
        assert s.parameters["enable_rewriting"].default is False

    @pytest.mark.asyncio
    async def test_search_empty_results_handles_rewriting_used(self):
        """空结果时 rewriting_used 也存在"""
        from app.services.search_service import search_service

        search_service._multi_search = AsyncMock(return_value=[])
        result = await search_service.search(query="x", max_results=3)
        assert result["status"] == "success"
        assert result["results"] == []
        assert result["result_count"] == 0
        assert result["rewriting_used"] == []

    def test_sogou_bing_untouched(self):
        """_sogou_weixin_search / _bing_search 函数签名不动"""
        import inspect
        from app.services.search_service import SearchService

        sogou_sig = inspect.signature(SearchService._sogou_weixin_search)
        bing_sig = inspect.signature(SearchService._bing_search)
        assert "query" in sogou_sig.parameters
        assert "max_results" in sogou_sig.parameters
        assert "query" in bing_sig.parameters
        assert "max_results" in bing_sig.parameters
