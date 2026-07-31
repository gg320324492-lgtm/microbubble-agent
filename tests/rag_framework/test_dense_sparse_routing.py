"""tests/rag_framework/test_dense_sparse_routing.py — Dense/Sparse/Hybrid 一层切换 e2e

4 个 mock 场景 (RAG-FW-08 派工 brief):
1. mode=dense  → 只走 LlamaIndex 向量路, 回退路不触发
2. mode=sparse → 只走 BM25Retriever 路
3. mode=hybrid → dense + sparse 并发融合去重
4. 异常回退    → 框架层异常 → 回退手写 hybrid_retriever.retrieve()

测试设计 (RAG-FW-02 conftest 哲学一致):
- 全部 mock llama_index / embedding_service, CI 不装框架依赖也能跑
- 只测我们的胶水代码逻辑 (路由/融合/回退), 不测框架行为
"""

import pytest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import app.services.bm25_service  # noqa: F401  — 预热 import (RAG-FW-14 W98 +0)
# 顺序污染修复: test_agent_retriever.py 的 bm25 测试在 patch.dict("sys.modules")
# 上下文内首次真实 import bm25_service, fixture 退出还原 sys.modules 后
# app.services.bm25_service 属性残留失效 → 本文件 TestRealInit 的
# patch("app.services.bm25_service.get_bm25_service") 解析失败
# (AttributeError: module 'app.services' has no attribute 'bm25_service').
# 模块级预热 import 保证 app.services.bm25_service 属性先于任何测试永久存在.

from app.rag import dense_sparse_routing
from app.rag.dense_sparse_routing import DenseSparseRouter


# ---------------------------------------------------------------------------
# 共享 fixture — mock 节点与单路实现
# ---------------------------------------------------------------------------

def _make_node(node_id, score, method):
    """构造 fake NodeWithScore — _node_to_dict 走属性访问, 用 SimpleNamespace"""
    return SimpleNamespace(
        node_id=node_id,
        text=f"标题 {node_id}\n内容 {node_id}",
        metadata={"title": f"标题 {node_id}", "category": "测试"},
        score=score,
    )


def _make_node_dict(node_id, score, method):
    """dict 形检索结果 (真实 _dense_only/_sparse_only 返回 dict)"""
    return {
        "id": node_id,
        "title": f"标题 {node_id}",
        "content": f"内容 {node_id}",
        "score": score,
        "retrieval_method": method,
    }


def _make_index_mock():
    """fake VectorStoreIndex — as_retriever 透传 similarity_top_k, aretrieve 截断"""
    index = MagicMock()
    retriever = MagicMock()

    def _as_retriever(*args, **kwargs):
        retriever.similarity_top_k = kwargs.get("similarity_top_k", 5)
        return retriever

    async def _aretrieve(query):
        k = getattr(retriever, "similarity_top_k", 5)
        nodes = [_make_node(1, 0.9, "dense"), _make_node(2, 0.8, "dense")]
        return nodes[:k]

    retriever.aretrieve = AsyncMock(side_effect=_aretrieve)
    index.as_retriever.side_effect = _as_retriever
    return index


@pytest.fixture
def router():
    return DenseSparseRouter(db=MagicMock())


# ---------------------------------------------------------------------------
# 场景 1: mode=dense — 只走向量路
# ---------------------------------------------------------------------------

class TestDenseMode:
    async def test_dense_only(self, router):
        """mode=dense → 向量检索, 每项 retrieval_method=dense_vector, top_k 截断"""
        with (
            patch.object(router, "_init_vector_index", new_callable=AsyncMock) as mock_init,
            patch.object(router, "_sparse_only", new_callable=AsyncMock) as mock_sparse,
            patch.object(router, "_fallback_hybrid", new_callable=AsyncMock) as mock_fb,
        ):
            mock_init.return_value = _make_index_mock()
            results = await router.retrieve("微气泡 zeta 电位", top_k=1, mode="dense")

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["retrieval_method"] == "dense_vector"
        mock_sparse.assert_not_awaited()
        mock_fb.assert_not_awaited()

    async def test_dense_default_mode_from_env(self, router):
        """env RAG_RETRIEVAL_MODE=dense → 未显式传 mode 也走向量路"""
        with (
            patch.object(dense_sparse_routing, "RETRIEVAL_MODE", "dense"),
            patch.object(router, "_init_vector_index", new_callable=AsyncMock) as mock_init,
            patch.object(router, "_sparse_only", new_callable=AsyncMock) as mock_sparse,
        ):
            mock_init.return_value = _make_index_mock()
            results = await router.retrieve("微气泡 zeta 电位", top_k=2)

        assert len(results) == 2
        mock_sparse.assert_not_awaited()


# ---------------------------------------------------------------------------
# 场景 2: mode=sparse — 只走 BM25 路
# ---------------------------------------------------------------------------

class TestSparseMode:
    async def test_sparse_only(self, router):
        """mode=sparse → BM25Retriever 检索, retrieval_method=bm25"""
        fake_retriever = MagicMock()
        fake_retriever.aretrieve = AsyncMock(
            return_value=[
                _make_node(10, 12.34, "bm25"),
                _make_node(11, 9.87, "bm25"),
            ]
        )
        with (
            patch.object(router, "_init_bm25_retriever", new_callable=AsyncMock) as mock_init,
            patch.object(router, "_dense_only", new_callable=AsyncMock) as mock_dense,
            patch.object(router, "_fallback_hybrid", new_callable=AsyncMock) as mock_fb,
        ):
            mock_init.return_value = fake_retriever
            results = await router.retrieve("气泡 尺寸 分布", top_k=5, mode="sparse")

        assert len(results) == 2
        assert results[0]["id"] == 10
        assert results[0]["score"] == 12.34
        assert all(r["retrieval_method"] == "bm25" for r in results)
        assert fake_retriever.similarity_top_k == 5  # top_k 动态覆盖
        mock_dense.assert_not_awaited()
        mock_fb.assert_not_awaited()

    async def test_sparse_empty_corpus_returns_empty(self, router):
        """语料为空 → sparse-only 返回空列表 (不抛错)"""
        with patch.object(router, "_init_bm25_retriever", new_callable=AsyncMock) as mock_init:
            mock_init.return_value = None
            results = await router.retrieve("气泡", top_k=5, mode="sparse")

        assert results == []


# ---------------------------------------------------------------------------
# 场景 3: mode=hybrid — dense + sparse 并发融合去重
# ---------------------------------------------------------------------------

class TestHybridMode:
    async def test_hybrid_merges_and_dedupes(self, router):
        """hybrid → 两路并发 + 同 id 保留最高分 + top_k 截断"""
        dense_nodes = [
            _make_node_dict(1, 0.9, "dense"),
            _make_node_dict(2, 0.8, "dense"),
            _make_node_dict(3, 0.7, "dense"),
        ]
        sparse_nodes = [
            _make_node_dict(1, 0.5, "bm25"),   # 与 dense id=1 重复, dense 分高保留
            _make_node_dict(4, 0.6, "bm25"),
        ]
        with (
            patch.object(router, "_dense_only", new_callable=AsyncMock) as mock_dense,
            patch.object(router, "_sparse_only", new_callable=AsyncMock) as mock_sparse,
            patch.object(router, "_fallback_hybrid", new_callable=AsyncMock) as mock_fb,
        ):
            mock_dense.return_value = dense_nodes
            mock_sparse.return_value = sparse_nodes
            results = await router.retrieve("微气泡 制备", top_k=3, mode="hybrid")

        ids = [r["id"] for r in results]
        assert ids == [1, 2, 3]  # 去重后 4 条 → top_k=3
        assert results[0]["score"] == 0.9  # id=1 保留 dense 最高分
        mock_dense.assert_awaited_once()
        mock_sparse.assert_awaited_once()
        mock_fb.assert_not_awaited()

    async def test_hybrid_tolerates_single_leg_failure(self, router):
        """hybrid 单路失败 → 容忍并返回另一路结果"""
        with (
            patch.object(router, "_dense_only", new_callable=AsyncMock) as mock_dense,
            patch.object(router, "_sparse_only", new_callable=AsyncMock) as mock_sparse,
            patch.object(router, "_fallback_hybrid", new_callable=AsyncMock) as mock_fb,
        ):
            mock_dense.side_effect = RuntimeError("pgvector 不可用")
            mock_sparse.return_value = [_make_node_dict(4, 0.6, "bm25")]
            results = await router.retrieve("微气泡", top_k=5, mode="hybrid")

        assert len(results) == 1
        assert results[0]["id"] == 4
        mock_fb.assert_not_awaited()

    async def test_hybrid_all_legs_fail_falls_back(self, router):
        """hybrid 两路全失败 → 抛异常 → retrieve() 回退手写"""
        with (
            patch.object(router, "_dense_only", new_callable=AsyncMock) as mock_dense,
            patch.object(router, "_sparse_only", new_callable=AsyncMock) as mock_sparse,
            patch.object(router, "_fallback_hybrid", new_callable=AsyncMock) as mock_fb,
        ):
            mock_dense.side_effect = RuntimeError("pgvector 不可用")
            mock_sparse.side_effect = RuntimeError("bm25 语料空")
            mock_fb.return_value = [{"id": 99, "retrieval_method": "handwritten"}]
            results = await router.retrieve("微气泡", top_k=5, mode="hybrid")

        assert results == [{"id": 99, "retrieval_method": "handwritten"}]
        mock_fb.assert_awaited_once()


# ---------------------------------------------------------------------------
# 场景 4: 异常回退手写 — 单路异常 / 初始化异常 / 开关关闭
# ---------------------------------------------------------------------------

class TestFallback:
    async def test_leg_exception_falls_back_to_handwritten(self, router):
        """mode=dense 向量路抛异常 → 回退手写 hybrid_retriever.retrieve"""
        fallback = AsyncMock(
            return_value=[{"id": 7, "title": "手写结果", "retrieval_method": "vector"}]
        )
        with (
            patch.object(router, "_init_vector_index", new_callable=AsyncMock) as mock_init,
            patch.object(router, "_fallback_hybrid", fallback),
        ):
            mock_init.side_effect = RuntimeError("llama_index 未安装")
            results = await router.retrieve("zeta 电位", top_k=5, mode="dense")

        assert results[0]["id"] == 7
        fallback.assert_awaited_once_with("zeta 电位", 5)

    async def test_init_exception_falls_back_to_handwritten(self, router):
        """_init_vector_index 抛异常 → 回退手写"""
        fallback = AsyncMock(return_value=[{"id": 8}])
        with (
            patch.object(router, "_init_vector_index", new_callable=AsyncMock, side_effect=RuntimeError("boom")),
            patch.object(router, "_fallback_hybrid", fallback),
        ):
            results = await router.retrieve("微气泡", top_k=3, mode="dense")

        assert results == [{"id": 8}]
        fallback.assert_awaited_once_with("微气泡", 3)

    async def test_retrieve_is_gate_decorated(self, router):
        """retrieve 被 framework_gate 包裹 — 开关关闭语义由 gate 保证 (FW-02 已测)"""
        # functools.wraps 保留 __wrapped__ 引用 → 证明 @framework_gate 已应用
        wrapped = getattr(router.retrieve, "__wrapped__", None)
        assert wrapped is not None
        assert wrapped.__name__ == "retrieve"
        # gate 关闭场景 (feature_flag=False → None) 由 FW-02 test_gate_degradation.py 覆盖,
        # 本文件不重复测 gate 本身

    async def test_fallback_hybrid_calls_handwritten_service(self):
        """_fallback_hybrid → HybridRetriever.retrieve(query, top_k=top_k) 真实委托"""
        svc_mock = MagicMock()
        svc_mock.retrieve = AsyncMock(return_value=[{"id": 42, "retrieval_method": "bm25"}])
        with patch("app.services.hybrid_retriever.HybridRetriever", return_value=svc_mock):
            router = DenseSparseRouter(db="fake_db")
            results = await router._fallback_hybrid("微气泡 zeta", top_k=5)

        assert results == [{"id": 42, "retrieval_method": "bm25"}]
        svc_mock.retrieve.assert_awaited_once_with("微气泡 zeta", top_k=5)


# ---------------------------------------------------------------------------
# 真实胶水实现 — mock 框架层 (不装 llama_index)
# ---------------------------------------------------------------------------

class TestRealInit:
    async def test_bm25_retriever_uses_bm25_service_corpus(self):
        """_init_bm25_retriever 从 bm25_service 语料构建节点 (mock llama_index)"""
        fake_bm25 = MagicMock()
        fake_bm25._documents = [
            {"id": 1, "title": "气泡制备", "content": "微纳米气泡 制备方法", "category": "制备"},
            {"id": 2, "title": "zeta 电位", "content": "表面电荷测量", "category": "表征"},
        ]
        fake_retriever = MagicMock()
        fake_retriever.aretrieve = AsyncMock(
            return_value=[_make_node(1, 5.0, "bm25")]
        )

        with (
            patch("app.services.bm25_service.get_bm25_service", return_value=fake_bm25),
            patch.dict(
                "sys.modules",
                {
                    "llama_index": MagicMock(),
                    "llama_index.core": MagicMock(),
                    "llama_index.core.retrievers": MagicMock(),
                    "llama_index.core.schema": MagicMock(),
                },
            ),
            patch("llama_index.core.retrievers.BM25Retriever.from_defaults", return_value=fake_retriever),
            patch("llama_index.core.schema.TextNode", side_effect=lambda **kw: kw) as mock_text_node,
        ):
            router = DenseSparseRouter(db=None)
            retriever = await router._init_bm25_retriever()

        assert retriever is fake_retriever
        # 语料 2 条 → TextNode 调 2 次, 元数据不含 id/title/content
        text_args = mock_text_node.call_args_list
        assert len(text_args) == 2
        assert text_args[0].kwargs["id_"] == "1"
        assert text_args[0].kwargs["metadata"] == {"category": "制备"}
        assert text_args[0].kwargs["text"] == "气泡制备\n微纳米气泡 制备方法"

    async def test_sparse_only_with_real_bm25_retriever(self):
        """sparse-only 端到端: 真实 _init_bm25_retriever + aretrieve"""
        fake_bm25 = MagicMock()
        fake_bm25._documents = [{"id": 1, "title": "气泡制备", "content": "微纳米气泡 制备方法"}]
        fake_retriever = MagicMock()
        fake_retriever.aretrieve = AsyncMock(
            return_value=[_make_node(1, 5.0, "bm25")]
        )

        with (
            patch("app.services.bm25_service.get_bm25_service", return_value=fake_bm25),
            patch.dict(
                "sys.modules",
                {
                    "llama_index": MagicMock(),
                    "llama_index.core": MagicMock(),
                    "llama_index.core.retrievers": MagicMock(),
                    "llama_index.core.schema": MagicMock(),
                },
            ),
            patch("llama_index.core.retrievers.BM25Retriever.from_defaults", return_value=fake_retriever),
            patch("llama_index.core.schema.TextNode", side_effect=lambda **kw: kw),
        ):
            router = DenseSparseRouter(db=None)
            results = await router.retrieve("气泡制备", top_k=5, mode="sparse")

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["retrieval_method"] == "bm25"
        assert fake_retriever.similarity_top_k == 5

    async def test_dense_only_with_real_init_flow(self, router):
        """dense-only 真实初始化流 (mock PGVectorStore/VectorStoreIndex 工厂)"""
        index = _make_index_mock()
        with (
            patch.dict(
                "sys.modules",
                {
                    "llama_index": MagicMock(),
                    "llama_index.core": MagicMock(),
                    "llama_index.vector_stores": MagicMock(),
                    "llama_index.vector_stores.postgres": MagicMock(),
                },
            ),
            patch("llama_index.core.VectorStoreIndex.from_vector_store", return_value=index),
            patch("llama_index.vector_stores.postgres.PGVectorStore") as mock_pg,
        ):
            results = await router.retrieve("微气泡 zeta 电位", top_k=5, mode="dense")

        assert len(results) == 2
        # 只读: perform_setup=False (不建表/不建索引)
        setup_kwargs = mock_pg.call_args.kwargs
        assert setup_kwargs["perform_setup"] is False
        assert setup_kwargs["table_name"] == "knowledge"
