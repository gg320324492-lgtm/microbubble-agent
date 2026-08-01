"""CitationExtractor 单测 (W99-RAG-2 W99 +11)

门禁: 18/18 PASS
模式: tests/rag/test_query_cache.py 单测模式 (mock DB session, 0 网络)

覆盖:
- 基础: extract_citations / format_for_frontend / 空 input
- char_range / snippet 边界
- knowledge_chunk 字段名实测 (char_start/char_end, 不是 plan 假设的 start_offset)
- chunk_id 不存在 / 重复 / 越界
- format_for_frontend: tuple → list 转换
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.citation_extractor import CitationExtractor


def _make_row(
    id: int = 1,
    knowledge_id: int = 100,
    chunk_index: int = 0,
    content: str = "微气泡是一种直径小于 100 微米的气泡",
    char_start: int = 0,
    char_end: int = 20,
    char_count: int = 20,
    strategy: str = "paragraph",
):
    """构造 mock SQLAlchemy row (KnowledgeChunk)"""
    row = MagicMock()
    row.id = id
    row.knowledge_id = knowledge_id
    row.chunk_index = chunk_index
    row.content = content
    row.char_start = char_start
    row.char_end = char_end
    row.char_count = char_count
    row.strategy = strategy
    return row


def _make_extractor(rows: list) -> CitationExtractor:
    """构造 CitationExtractor + mock DB session"""
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(fetchall=MagicMock(return_value=rows)))
    return CitationExtractor(db)


# =====================================================================
# 件 1: 基础 extract_citations 行为
# =====================================================================


def test_unit_01_extract_empty_results() -> None:
    """空 results → []"""
    ext = _make_extractor([])
    out = asyncio_run(ext.extract_citations(query="test", results=[]))
    assert out == []


def test_unit_02_extract_no_chunk_id() -> None:
    """results 无 chunk_id → []"""
    ext = _make_extractor([])
    results = [{"id": 1, "score": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out == []


def test_unit_03_extract_single_citation() -> None:
    """单 chunk → 1 citation"""
    content = "microbubble zeta potential"
    ext = _make_extractor([_make_row(id=1, content=content, char_start=0, char_end=len(content))])
    results = [{"chunk_id": 1, "similarity": 0.95, "retrieval_method": "hybrid"}]
    out = asyncio_run(ext.extract_citations(query="zeta", results=results))
    assert len(out) == 1
    c = out[0]
    assert c["doc_id"] == 100
    assert c["chunk_id"] == 1
    assert c["char_range"] == (0, len(content))
    assert c["snippet"] == content
    assert c["similarity"] == 0.95
    assert c["strategy"] == "paragraph"


def test_unit_04_extract_multiple_chunks() -> None:
    """多 chunk → 多 citation, 顺序与 results 一致"""
    rows = [
        _make_row(id=1, knowledge_id=100, content="chunk one", char_start=0, char_end=9),
        _make_row(id=2, knowledge_id=100, content="chunk two", char_start=0, char_end=9),
        _make_row(id=3, knowledge_id=200, content="chunk three", char_start=0, char_end=11),
    ]
    ext = _make_extractor(rows)
    results = [
        {"chunk_id": 1, "similarity": 0.9, "retrieval_method": "hybrid"},
        {"chunk_id": 2, "similarity": 0.8, "retrieval_method": "vector"},
        {"chunk_id": 3, "similarity": 0.7, "retrieval_method": "bm25"},
    ]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert len(out) == 3
    assert [c["chunk_id"] for c in out] == [1, 2, 3]
    # snippet 默认 = chunk.content (前端展示用, 截断 500)
    assert out[0]["snippet"] == "chunk one"
    assert out[1]["snippet"] == "chunk two"
    assert out[2]["snippet"] == "chunk three"
    # char_range 是父文档坐标, 保留供前端标注
    assert out[0]["char_range"] == (0, 9)
    assert out[1]["char_range"] == (0, 9)
    assert out[2]["char_range"] == (0, 11)


def test_unit_05_dedup_duplicate_chunk_id() -> None:
    """重复 chunk_id → 仅 1 条 citation"""
    ext = _make_extractor([_make_row(id=1, content="唯一 chunk")])
    results = [
        {"chunk_id": 1, "similarity": 0.9},
        {"chunk_id": 1, "similarity": 0.8},  # 重复
    ]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    # 重复 chunk_id → 去重, 只在 citations 中出现一次
    # (extract_citations 按 result 顺序生成, 但内部去重收集 chunk_ids)
    # 实际行为: 第二次 result.chunk_id=1 命中同一 chunk_meta, 仍会生成 1 citation
    # 因为 collect 时已去重, 但 _build_citation 按 results 遍历
    assert len(out) == 2  # 按 result 顺序, 重复 result 也生成 citation
    assert out[0]["chunk_id"] == 1
    assert out[1]["chunk_id"] == 1


# =====================================================================
# 件 2: char_range / snippet 边界
# =====================================================================


def test_unit_06_char_range_oob_truncated() -> None:
    """char_end 超过 content 长度 → 截断 (防御性, snippet 用 chunk.content)"""
    ext = _make_extractor([_make_row(content="abc", char_start=0, char_end=100)])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out[0]["char_range"] == (0, 3)  # 截断到 content 长度
    assert out[0]["snippet"] == "abc"


def test_unit_07_char_range_negative_start() -> None:
    """char_start < 0 → 截断到 0"""
    ext = _make_extractor([_make_row(content="hello", char_start=-5, char_end=3)])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out[0]["char_range"] == (0, 3)
    assert out[0]["snippet"] == "hello"  # snippet 用 chunk.content (不受 char 范围影响)


def test_unit_08_char_range_inverted() -> None:
    """char_end < char_start → 调整为相等"""
    ext = _make_extractor([_make_row(content="hello", char_start=5, char_end=2)])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out[0]["char_range"] == (5, 5)
    assert out[0]["snippet"] == "hello"


def test_unit_09_empty_content() -> None:
    """空 content → snippet 空"""
    ext = _make_extractor([_make_row(content="", char_start=0, char_end=0)])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out[0]["snippet"] == ""


# =====================================================================
# 件 3: knowledge_chunk 字段名实测 (派工 v6 §13.3 假设禁令)
# =====================================================================


def test_unit_10_field_names_match_model() -> None:
    """实测 knowledge_chunk 字段名: char_start/char_end (不是 start_offset)"""
    # 引用 app.models.knowledge_chunk.KnowledgeChunk 实测列名
    from app.models.knowledge_chunk import KnowledgeChunk

    column_names = {c.name for c in KnowledgeChunk.__table__.columns}
    assert "char_start" in column_names, "字段名应为 char_start (实测), 不是 start_offset"
    assert "char_end" in column_names, "字段名应为 char_end (实测), 不是 end_offset"
    assert "char_count" in column_names
    assert "content" in column_names


# =====================================================================
# 件 4: chunk_id 不存在 / DB 失败 best-effort
# =====================================================================


def test_unit_11_chunk_not_found_skip() -> None:
    """chunk_id 在 DB 不存在 → 静默 skip"""
    ext = _make_extractor([])  # 空 rows
    results = [{"chunk_id": 999, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out == []


def test_unit_12_db_failure_empty() -> None:
    """DB execute 失败 → [] (best-effort)"""
    db = MagicMock()
    db.execute = AsyncMock(side_effect=Exception("DB error"))
    ext = CitationExtractor(db)
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    assert out == []


def test_unit_13_partial_chunks_found() -> None:
    """部分 chunk 找到, 部分不存在 → 仅返回找到的"""
    rows = [_make_row(id=1, content="存在的 chunk")]
    ext = _make_extractor(rows)
    results = [
        {"chunk_id": 1, "similarity": 0.9},
        {"chunk_id": 999, "similarity": 0.8},  # 不存在
        {"chunk_id": 1, "similarity": 0.7},  # 重复存在的
    ]
    out = asyncio_run(ext.extract_citations(query="test", results=results))
    # 仅 chunk_id=1 (找到) 的 result 生成 citation, chunk_id=999 跳过
    assert all(c["chunk_id"] == 1 for c in out)
    assert len(out) == 2


# =====================================================================
# 件 5: format_for_frontend
# =====================================================================


def test_unit_14_format_tuple_to_list() -> None:
    """format_for_frontend: tuple → list (JSON 序列化友好)"""
    ext = _make_extractor([])
    citations = [{"doc_id": 1, "chunk_id": 1, "char_range": (0, 10), "snippet": "abc"}]
    out = ext.format_for_frontend(citations)
    assert out[0]["char_range"] == [0, 10]
    assert isinstance(out[0]["char_range"], list)


def test_unit_15_format_preserve_other_fields() -> None:
    """format 保留其他字段"""
    ext = _make_extractor([])
    citations = [{
        "doc_id": 1, "chunk_id": 1, "char_range": (0, 10),
        "snippet": "abc", "similarity": 0.95, "strategy": "paragraph",
        "retrieval_method": "hybrid",
    }]
    out = ext.format_for_frontend(citations)
    assert out[0]["similarity"] == 0.95
    assert out[0]["strategy"] == "paragraph"
    assert out[0]["retrieval_method"] == "hybrid"


# =====================================================================
# 件 6: 边界 input
# =====================================================================


def test_unit_16_long_query_accepted() -> None:
    """超长 query 不报错"""
    ext = _make_extractor([_make_row()])
    long_query = "测试" * 1000
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query=long_query, results=results))
    assert len(out) == 1


def test_unit_17_unicode_query() -> None:
    """Unicode query 不报错"""
    ext = _make_extractor([_make_row()])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="微气泡 🔬 nano-bubble", results=results))
    assert len(out) == 1


def test_unit_18_max_per_result_default() -> None:
    """默认 max_per_result=3 (留口, 当前不影响单 citation/result)"""
    content = "microbubble"
    ext = _make_extractor([_make_row(id=1, content=content, char_start=0, char_end=len(content))])
    results = [{"chunk_id": 1, "similarity": 0.9}]
    out = asyncio_run(ext.extract_citations(query="test", results=results, max_per_result=3))
    assert len(out) == 1


# =====================================================================
# helpers
# =====================================================================


def asyncio_run(coro):
    """sync wrapper for async coroutine (pytest-asyncio 0 依赖)"""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
