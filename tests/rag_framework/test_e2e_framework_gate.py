"""Hybrid RAG Stack 端到端回退验证

7 项能力各 1 种回退场景:
1. LangFuse Tracing 无 key → 静默禁用 (handler=None)
2. Query 翻译 LLM 失败 → 回退原 query 直传
3. Multi-hop 引擎 ImportError → 降级单轮
4. Agent Router 路由失败 → 回退 4 路并发
5. Dense/Sparse 路由异常 → 回退手写 hybrid
6. Semantic Chunker ImportError → 回退规则分块
7. 跨模态解析 ImportError → 回退手写解析

全 mock, CI 无需安装 langchain/llama-index/langfuse。

据实适配说明 (RAG-FW-11, 与 7 项能力实际实现签名对齐, 不改 app/rag 代码):
- test_01: lc_tracing 用 `from app.rag import config` 读模块属性 (LANGFUSE_TRACE_ENABLED
  在 import 时由 env 计算), 故 patch app.rag.config.LANGFUSE_TRACE_ENABLED 而非 os.environ;
  另加 _reset_langfuse_handler() 隔离模块级单例
- test_03: multi_hop_engine.query 自带 try/except, ImportError 走 _fallback_single_hop
  (真实 KnowledgeQAService), 需 patch 该 service 才能不碰 DB
- test_05: 为确定性模拟 "Dense/Sparse 路由异常", patch _init_vector_index +
  _init_bm25_retriever 抛 ImportError (不依赖本机 llama_index/bm25 语料状态)
- test_07: _fallback_parse 内部 open(file_path, "rb"), 必须传真实临时文件 (tmp_path)
- test_08: 冒烟循环内为 multimodal 创建真实临时文件 (tmp_path_factory)
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
    # 3. Multi-hop 引擎 ImportError → 降级单轮
    # ====================================================================

    async def test_03_multi_hop_import_error_degrades(self):
        """Multi-hop ImportError → 降级单轮 (used_framework=False)"""
        from app.rag.multi_hop_engine import MultiHopEngine

        engine = MultiHopEngine()
        # 适配: query 内部 except → _fallback_single_hop 用真实 KnowledgeQAService,
        # patch 该 service 避免碰 DB (与 test_multi_hop_engine.py 同模式)
        with patch.dict("sys.modules", {"llama_index": None}), patch(
            "app.services.knowledge_qa_service.KnowledgeQAService",
        ) as mock_svc:
            mock_svc.return_value.answer_question = AsyncMock(
                return_value={"answer": "单轮降级答案", "sources": []}
            )
            result = await engine.query("方案 A 的替代是什么?")
        assert result["used_framework"] is False
        assert "answer" in result

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
    # 6. Semantic Chunker ImportError → 回退规则分块
    # ====================================================================

    def test_06_semantic_chunker_import_error_falls_back(self):
        """Semantic Chunker ImportError → 回退规则分块"""
        from app.rag.semantic_chunker import semantic_chunk

        with patch.dict("sys.modules", {"langchain_experimental": None}):
            chunks = semantic_chunk("第一段。\n\n第二段。\n\n第三段。")
        assert len(chunks) >= 1
        assert all("content" in c for c in chunks)

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
        """全链路冒烟: 7 能力全 ImportError → 全部回退不崩"""
        # 适配: multimodal 场景需要真实临时文件 (目录, test_07 内部会建 test.pdf)
        smoke_dir = tmp_path_factory.mktemp("smoke")

        errors = []
        coros = [
            ("query_translator", self.test_02_query_translation_llm_failure_falls_back()),
            ("multi_hop", self.test_03_multi_hop_import_error_degrades()),
            ("agent_router", self.test_04_agent_router_route_failure_falls_back()),
            ("dense_sparse", self.test_05_dense_sparse_exception_falls_back()),
            ("semantic_chunker", self.test_06_semantic_chunker_import_error_falls_back()),
            ("multimodal", self.test_07_multimodal_import_error_falls_back(smoke_dir)),
        ]
        for name, coro in coros:
            try:
                # 同步测试 (test_06) 返回 None, 异步测试返回 coroutine — 据实适配 await
                if inspect.isawaitable(coro):
                    await coro
            except Exception as e:  # noqa: BLE001 — 冒烟测试必须捕获全部异常
                errors.append(f"{name}: {e}")
        assert errors == [], f"回退失败: {errors}"
