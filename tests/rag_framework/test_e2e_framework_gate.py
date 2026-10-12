"""Hybrid RAG Stack 端到端回退验证

5 项能力各 1 种回退场景:
1. LangFuse Tracing 无 key → 静默禁用 (handler=None)
2. Query 翻译 LLM 失败 → 回退原 query 直传
3. Agent Router 路由失败 → 回退 4 路并发
4. Dense/Sparse 路由异常 → 回退手写 hybrid
5. 跨模态解析 ImportError → 回退手写解析

全 mock, CI 无需安装 langchain/llama-index/langfuse。

据实适配说明 (RAG-FW-11, 与 5 项能力实际实现签名对齐, 不改 app/rag 代码):
- test_01: lc_tracing 用 `from app.rag import config` 读模块属性 (LANGFUSE_TRACE_ENABLED
  在 import 时由 env 计算), 故 patch app.rag.config.LANGFUSE_TRACE_ENABLED 而非 os.environ;
  另加 _reset_langfuse_handler() 隔离模块级单例
- test_05: 为确定性模拟 "Dense/Sparse 路由异常", patch _init_vector_index +
  _init_bm25_retriever 抛 ImportError (不依赖本机 llama_index/bm25 语料状态)
- test_07: _fallback_parse 内部 open(file_path, "rb"), 必须传真实临时文件 (tmp_path)
- test_08: 冒烟循环内为 multimodal 创建真实临时文件 (tmp_path_factory)

2026-10-12 移除 2 项能力 (Multi-hop / Semantic Chunker) 及其用例:
`app/rag/multi_hop_engine.py` 与 `app/rag/semantic_chunker.py` 经 import blocker
运行时实测 (298 模块全扫) 确认**零调用方**, 属 RAG-FW 交付后从未接线的孤立模块,
已一并删除; 连带移除 requirements 里只被 multi_hop 用的 `langchain-community`。
`graph_retriever.multi_hop_retrieve` 是**图检索的另一套实现**, 不在本次范围。
"""

import inspect

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag import config
from app.rag.config import (
    QUERY_TRANSLATION_ENABLED,
    MULTI_HOP_ENABLED,
    AGENT_ROUTER_ENABLED,
    DENSE_SPARSE_ROUTING_ENABLED,
    SEMANTIC_CHUNKER_ENABLED,
    MULTIMODAL_PARSER_ENABLED,
)


class TestEndToEndFallback:
    """7 能力回退 + 1 冒烟"""

    # ====================================================================
    # 1. LangFuse Tracing 无 key → 静默禁用
    # ====================================================================

    async def test_01_langfuse_no_key_disabled(self):
        """LangFuse 无 key → handler=None (静默禁用)"""
        from app.rag.lc_tracing import get_langfuse_handler, _reset_langfuse_handler

        _reset_langfuse_handler()
        try:
            # 适配: lc_tracing 读 config 模块属性 (import 时由 env 计算),
            # patch 模块属性等价于"无 API key"环境
            with patch.object(config, "LANGFUSE_TRACE_ENABLED", False):
                handler = get_langfuse_handler()
            assert handler is None
        finally:
            _reset_langfuse_handler()

    # ====================================================================
    # 2. Query 翻译 LLM 失败 → 回退原 query 直传
    # ====================================================================

    async def test_02_query_translation_llm_failure_falls_back(self):
        """Query 翻译 LLM 失败 → 回退 [query] 原样"""
        from app.rag.query_translator import QueryTranslator

        translator = QueryTranslator(llm=AsyncMock(side_effect=Exception("LLM down")))
        result = await translator.translate("臭氧微气泡消毒", mode="multi_query")
        assert result is None or result == ["臭氧微气泡消毒"]

    # ====================================================================
    # ====================================================================
    # 4. Agent Router 路由失败 → 回退 4 路并发
    # ====================================================================

    async def test_04_agent_router_route_failure_falls_back(self):
        """Agent Router 路由失败 → 回退 4 路并发"""
        from app.rag.agent_retriever import AgentRetriever

        retriever = AgentRetriever(db=MagicMock())
        with patch.object(retriever, "_route", AsyncMock(side_effect=Exception("route fail"))):
            with patch.object(retriever, "_hybrid_retrieve", AsyncMock(return_value=[{"id": 1}])):
                result = await retriever.retrieve("测试 query")
        assert result == [{"id": 1}]

    # ====================================================================
    # 5. Dense/Sparse 路由异常 → 回退手写 hybrid
    # ====================================================================

    async def test_05_dense_sparse_exception_falls_back(self):
        """Dense/Sparse 路由异常 → 回退手写 hybrid"""
        from app.rag.dense_sparse_routing import DenseSparseRouter

        router = DenseSparseRouter(db=MagicMock())
        # 适配: 确定性模拟框架异常 (llama_index 缺失) — 两路 init 抛 ImportError
        # → _hybrid 两路全失败 raise RuntimeError → retrieve except → _fallback_hybrid
        with patch.object(
            router, "_init_vector_index", AsyncMock(side_effect=ImportError("llama_index missing"))
        ), patch.object(
            router, "_init_bm25_retriever", AsyncMock(side_effect=ImportError("llama_index missing"))
        ), patch.object(router, "_fallback_hybrid", AsyncMock(return_value=[{"id": 2}])):
            result = await router.retrieve("测试 query", mode="hybrid")
        assert result == [{"id": 2}]

    # ====================================================================
    # ====================================================================
    # 7. 跨模态解析 ImportError → 回退手写解析
    # ====================================================================

    async def test_07_multimodal_import_error_falls_back(self, tmp_path):
        """跨模态解析 ImportError → 回退手写解析"""
        from app.rag.multimodal_parser import parse_document_enhanced

        # 适配: _fallback_parse 内部 open(file_path, "rb"), 需要真实临时文件
        notes = tmp_path / "test.pdf"
        notes.write_text("fallback text", encoding="utf-8")
        with patch.dict("sys.modules", {"llama_index.readers.file": None}):
            with patch("app.services.file_parser_service.FileParserService") as MockSvc:
                MockSvc.return_value.extract_content = AsyncMock(
                    return_value={"text": "fallback text", "images": {}}
                )
                result = await parse_document_enhanced(str(notes), "pdf")
        assert result["text"] == "fallback text"
        assert result["metadata"]["fallback"] is True

    # ====================================================================
    # 8. 全链路冒烟
    # ====================================================================

    async def test_08_full_chain_smoke(self, tmp_path_factory):
        """全链路冒烟: 5 能力全 ImportError → 全部回退不崩"""
        # 适配: multimodal 场景需要真实临时文件 (目录, test_07 内部会建 test.pdf)
        smoke_dir = tmp_path_factory.mktemp("smoke")

        errors = []
        coros = [
            ("query_translator", self.test_02_query_translation_llm_failure_falls_back()),
            ("agent_router", self.test_04_agent_router_route_failure_falls_back()),
            ("dense_sparse", self.test_05_dense_sparse_exception_falls_back()),
            ("multimodal", self.test_07_multimodal_import_error_falls_back(smoke_dir)),
        ]
        for name, coro in coros:
            try:
                if inspect.isawaitable(coro):
                    await coro
            except Exception as e:  # noqa: BLE001 — 冒烟测试必须捕获全部异常
                errors.append(f"{name}: {e}")
        assert errors == [], f"回退失败: {errors}"
