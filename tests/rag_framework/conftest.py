"""tests/rag_framework conftest — Mock LangChain/LlamaIndex for CI

测试设计原则：
1. 所有 import 框架的模块在 conftest 中集中 mock，不实际导入框架包
2. 使用 unittest.mock.patch 或 pytest-monkeypatch 在测试中注入 mock
3. 单元测试只测"我们的胶水代码逻辑"，不测框架行为
4. 集成测试在标记为 @pytest.mark.rag_integration 中可选执行（需安装框架依赖）
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


@pytest.fixture
def mock_langchain():
    """Mock 整个 langchain 家族 — CI 不装框架依赖也能测"""
    with patch.dict('sys.modules', {
        'langchain': MagicMock(),
        'langchain_core': MagicMock(),
        'langchain_community': MagicMock(),
        'langchain_anthropic': MagicMock(),
    }):
        yield


@pytest.fixture
def mock_llama_index():
    """Mock 整个 llama-index 家族"""
    with patch.dict('sys.modules', {
        'llama_index': MagicMock(),
        'llama_index.core': MagicMock(),
        'llama_index.core.query_engine': MagicMock(),
        'llama_index.core.retrievers': MagicMock(),
        'llama_index.vector_stores': MagicMock(),
        'llama_index.vector_stores.pgvector': MagicMock(),
        'llama_index.readers': MagicMock(),
        'llama_index.readers.file': MagicMock(),
    }):
        yield


@pytest.fixture
def mock_langfuse():
    """Mock LangFuse SDK"""
    with patch.dict('sys.modules', {
        'langfuse': MagicMock(),
        'langfuse.callback': MagicMock(),
        'langfuse.callback.langfuse_callback_handler': MagicMock(),
    }):
        yield


@pytest.fixture
def mock_all_frameworks(mock_langchain, mock_llama_index, mock_langfuse):
    """全框架 mock — 默认测试环境"""
    yield
