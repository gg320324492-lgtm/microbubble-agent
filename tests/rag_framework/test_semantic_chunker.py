"""Semantic Chunker 语义分块测试 — mock 场景 4 个

设计原则 (RAG-FW-02 conftest):
- CI 不装 langchain_experimental, 通过 sys.modules 注入 fake 框架
- 只测我们的胶水代码逻辑 (开关 / 回退 / 偏移 / semantic_score), 不测框架行为
- 场景: enabled+成功 / enabled+ImportError 回退规则 / enabled+运行时异常回退 / disabled 直接回退
"""

import sys
import types
from unittest.mock import patch

import pytest

from app.rag.semantic_chunker import SENTENCE_SPLIT_REGEX, semantic_chunk

SENT1 = "微气泡发生器工艺参数直接影响粒径分布。"
SENT2 = "设备选型决定整机能耗水平与运行稳定性。"
TEXT = SENT1 + SENT2


def _embedding_mock(text: str):
    """固定 2 维向量, 所有句子同向量 → 余弦相似度 = 1.0"""
    return [0.1, 0.2]


class FakeSemanticChunker:
    """新版本签名 fake — 记录构造参数 + 固定 split_text 输出"""

    last_instance = None  # 测试用: 记录最后一次构造的实例

    def __init__(
        self,
        embeddings,
        breakpoint_threshold_type="percentile",
        breakpoint_threshold_amount=95,
        min_chunk_size=200,
        sentence_split_regex=None,
    ):
        type(self).last_instance = self
        self.kwargs = {
            "embeddings": embeddings,
            "breakpoint_threshold_type": breakpoint_threshold_type,
            "breakpoint_threshold_amount": breakpoint_threshold_amount,
            "min_chunk_size": min_chunk_size,
            "sentence_split_regex": sentence_split_regex,
        }
        self.split_calls = []

    def split_text(self, text: str):
        self.split_calls.append(text)
        return [SENT1, SENT2]


class FailingSemanticChunker(FakeSemanticChunker):
    """split_text 抛运行时异常的 fake — 模拟 embedding 服务故障"""

    def split_text(self, text: str):
        raise RuntimeError("embedding service down")


def _framework_fakes() -> dict:
    """构建 langchain_core + langchain_experimental fake 模块 dict"""
    fake_core = types.ModuleType("langchain_core")
    fake_core.__path__ = []
    fake_embeddings = types.ModuleType("langchain_core.embeddings")
    fake_embeddings.Embeddings = type("Embeddings", (), {})

    fake_exp = types.ModuleType("langchain_experimental")
    fake_exp.__path__ = []
    fake_splitter = types.ModuleType("langchain_experimental.text_splitter")

    return {
        "langchain_core": fake_core,
        "langchain_core.embeddings": fake_embeddings,
        "langchain_experimental": fake_exp,
        "langchain_experimental.text_splitter": fake_splitter,
    }


@pytest.fixture
def fake_framework():
    """langchain 家族 fake 注入 sys.modules"""
    with patch.dict("sys.modules", _framework_fakes()):
        yield


@pytest.fixture
def framework_blocked():
    """langchain 家族置 None → import 必抛 ImportError"""
    with patch.dict(
        "sys.modules",
        {
            "langchain_core": None,
            "langchain_core.embeddings": None,
            "langchain_experimental": None,
            "langchain_experimental.text_splitter": None,
        },
    ):
        yield


class TestSemanticChunker:
    """Semantic Chunker — 4 场景"""

    def test_enabled_success(
        self, fake_framework, monkeypatch
    ):
        """场景 1: 开关开启 + 框架可用 → SemanticChunker 分块成功"""
        # 用真实 fake 类 (FakeSemanticChunker) 替换 sys.modules 里的占位
        fake_splitter = sys.modules["langchain_experimental.text_splitter"]
        fake_splitter.SemanticChunker = FakeSemanticChunker

        from langchain_experimental.text_splitter import SemanticChunker

        chunks = semantic_chunk(TEXT, embedding_fn=_embedding_mock)

        assert len(chunks) == 2
        # 构造参数透传
        assert isinstance(chunks, list)
        # 偏移严格指回原文
        assert chunks[0] == {
            "content": SENT1,
            "char_start": 0,
            "char_end": len(SENT1),
            "semantic_score": 1.0,
        }
        assert chunks[1]["content"] == SENT2
        assert chunks[1]["char_start"] == len(SENT1)
        assert chunks[1]["char_end"] == len(TEXT)

        # SemanticChunker 构造参数: percentile + 95 + min_chunk_size + 中文句读 regex
        splitter = FakeSemanticChunker.last_instance.kwargs
        assert splitter["breakpoint_threshold_type"] == "percentile"
        assert splitter["breakpoint_threshold_amount"] == 95
        assert splitter["min_chunk_size"] == 200
        assert splitter["sentence_split_regex"] == SENTENCE_SPLIT_REGEX
        # 注入的 embedding 函数被 adapter 包装
        assert splitter["embeddings"]._fn is _embedding_mock

    def test_enabled_import_error_falls_back(
        self, framework_blocked
    ):
        """场景 2: 开关开启 + 框架未安装 (ImportError) → 回退规则分块"""
        chunks = semantic_chunk(TEXT, embedding_fn=_embedding_mock)

        # 回退到 chunking_service paragraph 策略 (无空行 → 1 chunk)
        assert len(chunks) == 1
        assert chunks[0]["content"] == TEXT
        assert chunks[0]["char_start"] == 0
        assert chunks[0]["char_end"] == len(TEXT)
        assert chunks[0]["semantic_score"] == 0.0

    def test_enabled_runtime_error_falls_back(
        self, fake_framework
    ):
        """场景 3: 开关开启 + 运行时异常 (embedding 故障) → 回退规则分块"""
        fake_splitter = sys.modules["langchain_experimental.text_splitter"]
        fake_splitter.SemanticChunker = FailingSemanticChunker

        chunks = semantic_chunk(TEXT, embedding_fn=_embedding_mock)

        assert len(chunks) == 1
        assert chunks[0]["content"] == TEXT
        assert chunks[0]["semantic_score"] == 0.0

    def test_disabled_direct_fallback(
        self, monkeypatch
    ):
        """场景 4: 开关关闭 → 直接回退规则分块 (不触碰框架)"""
        monkeypatch.setattr(
            "app.rag.semantic_chunker.SEMANTIC_CHUNKER_ENABLED", False
        )

        chunks = semantic_chunk(TEXT, embedding_fn=_embedding_mock)

        assert len(chunks) == 1
        assert chunks[0]["content"] == TEXT
        assert chunks[0]["char_start"] == 0
        assert chunks[0]["char_end"] == len(TEXT)
        assert chunks[0]["semantic_score"] == 0.0
