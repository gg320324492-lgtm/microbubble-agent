"""RAG-FW-10 跨模态解析器测试 — 3 场景 (mock, 不装框架依赖)

场景:
1. pdf 成功 — LlamaIndex PDFReader 结构化提取 (layout + 表格 + 图表)
2. ImportError — 框架未装 → 回退 file_parser_service 手写解析
3. disabled — MULTIMODAL_PARSER_ENABLED=False → 直接回退, 不 import 框架

与 tests/rag_framework/conftest.py (rag-fw-02) 的 mock 风格一致:
用 patch.dict('sys.modules') 注入框架 mock, CI 不装框架依赖也能测。
"""

import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.rag import multimodal_parser as mp


def _doc(text: str, page: int = None):
    """构造 LlamaIndex Document 等价物 (text + metadata)"""
    md = {"page": page} if page is not None else {}
    return SimpleNamespace(text=text, metadata=md)


async def test_pdf_success_structured_extraction(tmp_path):
    """场景 1: pdf 成功 — layout + 表格 + 图表结构化提取"""
    fake_docs = [
        _doc("Table 1: 气泡参数对比\n直径 粒径\nFig. 1: 尺寸分布", page=1),
        _doc("Fig. 2: 浓度变化曲线", page=2),
    ]
    reader_cls = MagicMock()
    reader_cls.return_value.load_data.return_value = fake_docs

    with patch.dict(
        "sys.modules",
        {"llama_index.readers.file": SimpleNamespace(PDFReader=reader_cls)},
    ):
        result = await mp.parse_document_enhanced(str(tmp_path / "paper.pdf"), "pdf")

    # PDFReader 被调用 (传入文件路径)
    reader_cls.assert_called_once()
    reader_cls.return_value.load_data.assert_called_once()
    assert reader_cls.return_value.load_data.call_args.args[0] == str(tmp_path / "paper.pdf")

    # metadata: parser + page_count
    assert result["metadata"]["parser"] == "llamaindex_pdf_reader"
    assert result["metadata"]["page_count"] == 2
    assert result["metadata"]["source"] == "paper.pdf"

    # text: 全量拼接
    assert "Table 1: 气泡参数对比" in result["text"]
    assert "Fig. 2: 浓度变化曲线" in result["text"]

    # tables: "Table 1" 结构化提取
    assert len(result["tables"]) == 1
    assert result["tables"][0]["table_id"] == "1"
    assert result["tables"][0]["caption"].startswith("Table 1")

    # images: "Fig. 1" + "Fig. 2" 图表描述提取
    assert [img["figure_id"] for img in result["images"]] == ["1", "2"]


async def test_import_error_falls_back(tmp_path):
    """场景 2: 框架未装 (ImportError) → 回退 file_parser_service"""
    notes = tmp_path / "notes.txt"
    notes.write_text("hello from fallback", encoding="utf-8")

    # sys.modules 中 entry=None → `from llama_index.readers.file import PDFReader` 抛 ImportError
    with patch.dict("sys.modules", {"llama_index.readers.file": None}):
        result = await mp.parse_document_enhanced(str(notes), "pdf")

    assert result["metadata"] == {"fallback": True}
    assert result["text"] == "hello from fallback"
    assert result["tables"] == []
    # file_parser_service 的 images 结构原样透传
    assert result["images"] == {}


async def test_disabled_returns_fallback(tmp_path):
    """场景 3: MULTIMODAL_PARSER_ENABLED=False → 直接回退, 不触碰框架"""
    notes = tmp_path / "notes.txt"
    notes.write_text("disabled mode", encoding="utf-8")

    with patch.object(mp, "MULTIMODAL_PARSER_ENABLED", False):
        result = await mp.parse_document_enhanced(str(notes), "pdf")

    assert result["metadata"] == {"fallback": True}
    assert result["text"] == "disabled mode"
    assert result["tables"] == []
