"""app/rag/agent_retriever 测试 — LangChain AgentExecutor 动态检索器选择

测试设计原则 (RAG-FW-02 conftest 同源):
1. 所有 LangChain import 在 conftest 中集中 mock, CI 不装框架依赖也能测
2. LLM 调用 mock 到 LLMClient.complete 层 (不 mock _route, 测真实解析逻辑)
3. 只测"我们的胶水代码逻辑", 不测框架行为
4. 单路检索器 (vector/bm25) mock 到 service 层, 不碰 DB

4 个场景:
1. route=vector → _vector_only 返回
2. route=bm25 → _bm25_only 返回
3. route 解析失败 (LLM 返回垃圾文本) → 回退 vector
4. AgentExecutor 异常 (工具抛异常) → 回退 hybrid 4 路并发
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import app.rag.agent_retriever as ar_module
from app.rag.agent_retriever import AgentRetriever


# ====================================================================
# 框架 mock fixtures — 与 RAG-FW-02 tests/rag_framework/conftest.py 同语义
# (RAG-FW-02 conftest 在其分支, 合入前本文件自带, 合入后本文件局部定义自动覆盖)
# ====================================================================

@pytest.fixture
def mock_langchain():
    """Mock 整个 langchain 家族 — CI 不装框架依赖也能测"""
    with patch.dict("sys.modules", {
        "langchain": MagicMock(),
        "langchain_core": MagicMock(),
        "langchain_community": MagicMock(),
        "langchain_anthropic": MagicMock(),
    }):
        yield


@pytest.fixture
def mock_all_frameworks(mock_langchain):
    """全框架 mock — 本测试只需 langchain 家族"""
    yield


class _FakeResp:
    """LLMClient.complete 返回的 Anthropic Message 形状最小 stub"""

    def __init__(self, text: str):
        class _Block:
            def __init__(self, text):
                self.text = text
                self.thinking = None

        self.content = [_Block(text)]


def _make_retriever(**kwargs) -> AgentRetriever:
    """构造被测实例 — 默认 llm=None (触发真实 LLMClient 懒初始化, 测试中 patch complete)"""
    return AgentRetriever(**kwargs)


# ====================================================================
# 场景 1: route=vector → _vector_only 返回
# ====================================================================

class TestRouteVector:
    async def test_vector_route_returns_vector_only(self, mock_all_frameworks, monkeypatch):
        """LLM 返回 'vector' → 走 _vector_only, 不碰 hybrid"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(
            return_value=[
                {"id": 1, "title": "微纳米气泡", "score": 0.9,
                 "retrieval_method": "vector", "normalized_score": 1.0},
            ]
        )
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp("vector"))

        results = await r.retrieve("什么是微纳米气泡的 zeta 电位", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 1
        assert results[0]["retrieval_method"] == "vector"
        fake_hybrid._vector_search.assert_awaited_once_with(
            "什么是微纳米气泡的 zeta 电位", 5, None
        )
        fake_hybrid.retrieve.assert_not_awaited()  # 未回退 hybrid


# ====================================================================
# 场景 2: route=bm25 → _bm25_only 返回
# ====================================================================

class TestRouteBm25:
    async def test_bm25_route_returns_bm25_only(self, mock_all_frameworks, monkeypatch):
        """LLM 返回 'bm25' → 走 _bm25_only (bm25_service.search), 不碰 hybrid"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        # bm25 service mock — _corpus_size > 0 跳过 DB 刷新分支
        fake_bm25 = MagicMock()
        fake_bm25._corpus_size = 1
        fake_bm25.search = MagicMock(
            return_value=[
                {"id": 7, "title": "PR9 查询改写", "score": 12.3,
                 "retrieval_method": "bm25"},
            ]
        )
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp("bm25"))

        with patch("app.services.bm25_service.get_bm25_service", return_value=fake_bm25):
            results = await r.retrieve("PR9-query-rewriter 函数签名", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 7
        assert results[0]["retrieval_method"] == "bm25"
        fake_bm25.search.assert_called_once_with("PR9-query-rewriter 函数签名", top_k=5)
        # 未创建 hybrid (bm25 路不触发 hybrid.retrieve)
        assert r._hybrid is None or not r._hybrid.retrieve.called


# ====================================================================
# 场景 3: route 解析失败 → 回退 vector
# ====================================================================

class TestRouteParseFailure:
    async def test_garbage_text_falls_back_vector(self, mock_all_frameworks, monkeypatch):
        """LLM 返回不可解析文本 ('hmm maybe a vector') → 回退 vector"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(
            return_value=[
                {"id": 2, "title": "默认路", "score": 0.8,
                 "retrieval_method": "vector", "normalized_score": 1.0},
            ]
        )
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp("hmm maybe a vector"))

        results = await r.retrieve("模糊问题", top_k=5)

        assert len(results) == 1
        assert results[0]["retrieval_method"] == "vector"
        fake_hybrid._vector_search.assert_awaited_once()

    async def test_empty_text_falls_back_vector(self, mock_all_frameworks, monkeypatch):
        """LLM 返回空文本 (无 text block) → 回退 vector"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(return_value=[{"id": 3, "title": "x"}])
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp(""))

        results = await r.retrieve("空文本问题", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 3
        fake_hybrid._vector_search.assert_awaited_once()

    async def test_llm_exception_falls_back_vector(self, mock_all_frameworks, monkeypatch):
        """LLM.complete 抛异常 → _route 内部回退 vector, 不炸"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(
            return_value=[{"id": 4, "title": "异常兜底", "retrieval_method": "vector"}]
        )
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(side_effect=TimeoutError("LLM timeout"))

        results = await r.retrieve("LLM 挂了的问题", top_k=5)

        assert len(results) == 1
        assert results[0]["retrieval_method"] == "vector"
        fake_hybrid._vector_search.assert_awaited_once()


# ====================================================================
# 场景 4: AgentExecutor 异常 → 回退 hybrid 4 路并发
# ====================================================================

class TestExecutorFailureFallback:
    async def test_tool_exception_falls_back_hybrid(self, mock_all_frameworks, monkeypatch):
        """单路工具抛异常 → retrieve 外层 catch → hybrid.retrieve 4 路并发"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(
            side_effect=RuntimeError("vector search crashed")
        )
        fake_hybrid.retrieve = AsyncMock(
            return_value=[
                {"id": 9, "title": "hybrid 回退", "score": 0.5,
                 "retrieval_method": "hybrid", "normalized_score": 0.7},
            ]
        )
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp("vector"))

        results = await r.retrieve("工具炸了的问题", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 9
        fake_hybrid.retrieve.assert_awaited_once_with("工具炸了的问题", top_k=5)

    async def test_route_exception_falls_back_hybrid(self, mock_all_frameworks, monkeypatch):
        """_route 意外抛异常 (非 LLM 路径) → 外层 catch → hybrid 回退"""
        monkeypatch.setattr(ar_module, "AGENT_ROUTER_ENABLED", True)

        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid.retrieve = AsyncMock(
            return_value=[{"id": 10, "title": "hybrid 回退 2", "score": 0.6}]
        )
        r._hybrid = fake_hybrid

        with patch.object(AgentRetriever, "_route", new=AsyncMock(side_effect=RuntimeError("boom"))):
            results = await r.retrieve("路由炸了的问题", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 10
        fake_hybrid.retrieve.assert_awaited_once()

    async def test_default_flag_on_runs_router(self, mock_all_frameworks):
        """默认配置 (AGENT_ROUTER_ENABLED=True, 激进模式 On by default) → 正常走路由

        开关关闭的 gate 短路语义由 RAG-FW-02 tests/rag_framework/test_gate_degradation.py
        (framework_gate feature_flag=False → fallback) 覆盖, 本测试不重复.
        """
        r = _make_retriever()
        fake_hybrid = AsyncMock()
        fake_hybrid._vector_search = AsyncMock(return_value=[{"id": 11, "title": "default on"}])
        r._hybrid = fake_hybrid
        r.llm = MagicMock()
        r.llm.complete = AsyncMock(return_value=_FakeResp("vector"))

        results = await r.retrieve("开关默认开", top_k=5)

        assert len(results) == 1
        assert results[0]["id"] == 11
        fake_hybrid._vector_search.assert_awaited_once()
