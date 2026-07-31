"""tests/rag_framework/test_multi_hop_engine.py — MultiHopEngine 4 场景 mock 测试

场景:
1. engine 初始化成功 → SubQuestionQueryEngine 返回 → 组装结果 (used_framework=True)
2. ImportError (框架依赖缺失) → framework_gate 降级 → 单轮 (used_framework=False)
3. 运行时异常 (engine 内部抛错) → 降级单轮 (used_framework=False)
4. MULTI_HOP_ENABLED=False → 直接降级单轮, 不初始化 engine

依赖 conftest.py 的 mock_langchain / mock_llama_index / mock_langfuse fixtures
(CI 不装框架依赖也能测, 测试只测胶水代码逻辑)。
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.rag.multi_hop_engine import MultiHopEngine


@pytest.fixture
def mock_all_frameworks():
    """Mock 整个框架家族 — 与 rag_framework/conftest.py 同名同义 (本分支自包含)

    CI 不装 llama_index / langchain 依赖也能测, 测试只测胶水代码逻辑。
    """
    with patch.dict('sys.modules', {
        'langchain': MagicMock(),
        'langchain_core': MagicMock(),
        'langchain_community': MagicMock(),
        'langchain_anthropic': MagicMock(),
        'llama_index': MagicMock(),
        'llama_index.core': MagicMock(),
        'llama_index.core.query_engine': MagicMock(),
        'llama_index.core.retrievers': MagicMock(),
        'llama_index.core.tools': MagicMock(),
        'llama_index.vector_stores': MagicMock(),
        'llama_index.vector_stores.pgvector': MagicMock(),
        'llama_index.embeddings.langchain': MagicMock(),
        'llama_index.readers': MagicMock(),
        'llama_index.readers.file': MagicMock(),
        'langfuse': MagicMock(),
        'langfuse.callback': MagicMock(),
        'langfuse.callback.langfuse_callback_handler': MagicMock(),
    }):
        yield


class _FakeSubQuery:
    def __init__(self, text):
        self.sub_query = text


class _FakeSourceNode:
    def __init__(self, sub_query, node):
        self.sub_query = sub_query
        self.node = node

    def dict(self):
        return {"node": self.node.dict()}


@pytest.fixture
def engine(mock_all_frameworks):
    """所有框架 mock + db 伪对象"""
    db = MagicMock()
    db.bind.url = "postgresql+asyncpg://postgres:password@localhost:5432/microbubble"
    return MultiHopEngine(db=db, llm=MagicMock())


class TestMultiHopEngine:
    """MultiHopEngine — 4 场景"""

    async def test_engine_success(self, engine):
        """场景 1: 初始化成功 + 查询成功 → used_framework=True"""
        fake_response = MagicMock()
        fake_response.response = "综合答案: 方案 A 功效类似方案 B"
        fake_response.source_nodes = [
            _FakeSourceNode(_FakeSubQuery("方案 A 的关键指标?"), MagicMock(dict=lambda: {"id": 1})),
            _FakeSourceNode(_FakeSubQuery("功效类似的方案?"), MagicMock(dict=lambda: {"id": 2})),
        ]

        engine._engine = MagicMock()  # 跳过真实框架初始化
        engine._engine.aquery = AsyncMock(return_value=fake_response)

        result = await engine.query("写出一个跟方案 A 功效类似的替代")

        assert result["used_framework"] is True
        assert "综合答案" in result["answer"]
        assert result["sub_questions"] == ["方案 A 的关键指标?", "功效类似的方案?"]
        assert len(result["source_nodes"]) == 2
        assert result["confidence"] == "high"

    async def test_import_error_falls_back_single_hop(self, engine):
        """场景 2: 框架依赖缺失 (ImportError) → framework_gate 捕获 → 降级单轮"""
        with patch.object(
            engine,
            "_init_engine",
            side_effect=ImportError("No module named 'llama_index'"),
        ), patch(
            "app.services.knowledge_qa_service.KnowledgeQAService",
        ) as mock_svc:
            mock_svc.return_value.answer_question = AsyncMock(
                return_value={"answer": "单轮答案", "sources": [{"id": 9, "title": "KB 条目"}]}
            )
            result = await engine.query("写出一个跟方案 A 功效类似的替代")

        assert result["used_framework"] is False
        assert result["answer"] == "单轮答案"
        assert result["source_nodes"] == [{"id": 9, "title": "KB 条目"}]
        assert result["confidence"] == "medium"
        assert result["sub_questions"] == []
        mock_svc.return_value.answer_question.assert_awaited_once_with(
            "写出一个跟方案 A 功效类似的替代", top_k=6, auto_research=False
        )

    async def test_runtime_error_falls_back_single_hop(self, engine):
        """场景 3: 运行时异常 (engine 内部抛错) → 降级单轮"""
        with patch.object(
            engine,
            "_init_engine",
            side_effect=TimeoutError("LLM timeout"),
        ), patch(
            "app.services.knowledge_qa_service.KnowledgeQAService",
        ) as mock_svc:
            mock_svc.return_value.answer_question = AsyncMock(
                return_value={"answer": "降级答案", "sources": []}
            )
            result = await engine.query("写出一个跟方案 A 功效类似的替代")

        assert result["used_framework"] is False
        assert result["answer"] == "降级答案"
        assert result["confidence"] == "medium"

    async def test_flag_off_direct_fallback(self, engine):
        """场景 4: MULTI_HOP_ENABLED=False → framework_gate 直接降级, 不初始化 engine"""
        # 装饰器闭包读 module globals, 必须 patch query.__globals__ 生效
        with patch.dict(
            MultiHopEngine.query.__globals__,
            {"MULTI_HOP_ENABLED": False},
        ), patch(
            "app.services.knowledge_qa_service.KnowledgeQAService",
        ) as mock_svc:
            mock_svc.return_value.answer_question = AsyncMock(
                return_value={"answer": "单轮答案", "sources": [{"id": 3}]}
            )
            result = await engine.query("写出一个跟方案 A 功效类似的替代")

        assert result["used_framework"] is False
        assert result["answer"] == "单轮答案"
        assert result["confidence"] == "medium"
        assert result["sub_questions"] == []
        # 开关关闭时不初始化 engine
        assert engine._engine is None
