"""分块器识别 [PAGE:N] 标记 — agent 9 号修复回归测试 (2026-10-09)

背景 (生产实测确认的 bug):
    file_parser_service 的 _parse_pdf / _parse_pptx 在每页前插入 [PAGE:N] 标记
    (file_parser_service.py:223 / :345, 注释写明"用于 inline 定位")。但
    `_chunk_paragraph` 只按 \\n\\n 切, 而 PPT/PDF 解析产物几乎不含 \\n\\n —— 实测
    一份 18 页 PPT 的解析结果 \\n\\n = 0 次 / [PAGE:N] = 18 次, 整份塌成 1 个
    chunk, 召回单元只有应有的 1/18。全库 594 个文件受影响 + 生产库
    knowledge_chunks 里 2017/2786 行含 [PAGE: 标记, 其中 2005 行无 \\n\\n (即塌陷受害者)。

修复: chunking_service 新增 `page` 策略 + paragraph 策略遇 [PAGE:N] 自动按页切。

测试纪律 (派工 v11 §7 + CLAUDE.md 类 20 教训):
- 夹具是**真实生产解析产物** (脱敏后落盘 tests/rag/fixtures/), 不是测试自造语句
  —— 自造语句的测试退回修复仍全绿 = 等于没写 (本项目踩过)。
- 变异测试: 把修复退回 (paragraph 不感知标记) 时 test_page_* 必须红。
- 回归锁: 无 [PAGE:N] 的旧文本行为**逐字节不变**。
"""
import re
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "pptx_17page_page_markers.txt"


def _load_fixture() -> str:
    return FIXTURE.read_text(encoding="utf-8")


# ============== 核心: 真实 PPT 夹具按页切 ==============

def test_page_01_fixture_is_real_multipage_pptx():
    """夹具自检: 真实解析产物含 18 个 [PAGE:N], 且几乎无 \\n\\n (塌陷前提)"""
    text = _load_fixture()
    assert text.count("[PAGE:") == 18, "夹具应含 18 个页标记"
    assert text.count("\n\n") == 0, (
        "PPT 解析产物不含 \\n\\n —— 这正是整份塌成 1 chunk 的根因"
    )


def test_page_02_paragraph_strategy_no_longer_collapses_to_one():
    """门禁 a: 18 页文本切出 18 块 (不再是 1 块) —— 修复的核心断言"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 18, (
        f"18 页应切 18 块, 实得 {len(chunks)} 块 "
        f"(退回修复 → 此断言红: 只有 1 块)"
    )


def test_page_03_page_strategy_explicit():
    """显式 strategy='page' 与 paragraph 自动感知结果一致"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    by_para = chunk_text(text, ChunkConfig(strategy="paragraph"))
    by_page = chunk_text(text, ChunkConfig(strategy="page"))
    assert len(by_page) == 18
    assert [(c.char_start, c.char_end) for c in by_para] == [
        (c.char_start, c.char_end) for c in by_page
    ]


def test_page_04_invariant_char_count_self_consistent():
    """门禁 b: 每块 char_count == char_end - char_start"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    for c in chunk_text(text, ChunkConfig(strategy="paragraph")):
        assert c.char_count == c.char_end - c.char_start
        assert c.char_start >= 0
        assert c.char_end > c.char_start


def test_page_05_invariant_content_zero_loss():
    """门禁 c: text[char_start:char_end] == content (无字符丢失)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    for c in chunk_text(text, ChunkConfig(strategy="paragraph")):
        assert text[c.char_start:c.char_end] == c.content, (
            f"DRIFT: text[{c.char_start}:{c.char_end}] != content"
        )


def test_page_06_full_reconstruction_no_gap_no_overlap():
    """门禁 d: 拼接所有 chunk 能还原原文 (无丢字, 无越界)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    rebuilt = "".join(text[c.char_start:c.char_end] for c in chunks)
    assert rebuilt == text, "chunk 拼接必须逐字节还原原文"


def test_page_07_page_markers_preserved_in_chunks():
    """标记保留 (不剥离) —— 前端 paperAdapter 依赖它做 inline 定位"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = _load_fixture()
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    # 所有 18 个标记仍存在于 chunk 集合里
    total_markers = sum(c.content.count("[PAGE:") for c in chunks)
    assert total_markers == 18
    # 每块以页标记起始 (inline 定位锚点)
    for c in chunks:
        assert c.content.lstrip().startswith("[PAGE:"), (
            f"块应以 [PAGE:N] 起始, 实际: {c.content[:30]!r}"
        )


# ============== 回归锁: 无标记文本行为完全不变 ==============

def test_page_08_regression_no_marker_paragraph_unchanged():
    """无 [PAGE:N] 文本走原 \\n\\n 路径, 逐字节不变 (回归锁)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = "Para one here.\n\nPara two follows.\n\nPara three."
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 3
    assert all(c.strategy == "paragraph" for c in chunks)
    # 既有行为: 分隔符归属下一块 (boundary = 分隔符起始), 故 2/3 块带前导 \n\n
    assert chunks[0].content == "Para one here."
    assert chunks[1].content == "\n\nPara two follows."
    assert chunks[2].content == "\n\nPara three."
    # 与无标记时逐字节一致: 拼接还原原文
    assert "".join(text[c.char_start:c.char_end] for c in chunks) == text


def test_page_09_regression_single_paragraph_no_separator():
    """无分隔符无标记 → 1 chunk (既有行为)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = "just one paragraph without any blank line"
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 1
    assert chunks[0].char_count == len(text)


def test_page_10_regression_heading_unaffected_by_marker():
    """heading 策略不受标记影响 (调用方显式选择, 不自动切换)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    # 含标记 + markdown heading 的混合文本
    text = "[PAGE:1]\n# Title\nBody.\n\n## Sub\nMore."
    chunks = chunk_text(text, ChunkConfig(strategy="heading"))
    titles = [c.chunk_metadata["section_title"] for c in chunks]
    assert titles == ["Title", "Sub"]


def test_page_11_regression_empty_and_whitespace():
    """空串 / 纯空白 → [] (既有行为)"""
    from app.services.chunking_service import chunk_text

    assert chunk_text("") == []
    assert chunk_text("   ") == []


# ============== 边界: 页内仍含 \n\n 时两级切分 (PDF 场景) ==============

def test_page_12_pdf_style_page_with_inner_paragraphs():
    """PDF 风格: 页标记之间还有 \\n\\n → 页内再切 (page-first, para-within-page)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = (
        "[PAGE:1]\nIntro para.\n\nSecond para of page 1.\n"
        "[PAGE:2]\nNext page content.\n\nAnother para.\n"
    )
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    # 页 1 → 2 段, 页 2 → 2 段 = 4 块
    assert len(chunks) == 4
    # 拼接还原
    assert "".join(text[c.char_start:c.char_end] for c in chunks) == text
    # 首块保留 [PAGE:1] 标记
    assert chunks[0].content.startswith("[PAGE:1]")


def test_page_13_single_page_marker_yields_one_chunk():
    """只有 1 个页标记 → 1 块 (不虚增)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = "[PAGE:1]\nOnly one page here."
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 1
    assert chunks[0].strategy == "page"


def test_page_14_leading_text_before_first_marker_kept():
    """首个标记前的文本作为前导段保留 (不丢)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = "frontmatter text before markers\n[PAGE:1]\nBody."
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph"))
    assert len(chunks) == 2
    assert "frontmatter" in chunks[0].content
    assert "".join(text[c.char_start:c.char_end] for c in chunks) == text


def test_page_15_oversized_page_falls_back_to_window():
    """单页超 max_chars → 走 window 兜底 (不产巨块)"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    text = "[PAGE:1]\n" + "x" * 7000
    chunks = chunk_text(text, ChunkConfig(strategy="paragraph", max_chars=6000))
    assert all(c.char_count <= 6000 for c in chunks)
    assert all(c.strategy == "window" for c in chunks)
    # window 兜底带 100 字符 overlap (既有行为), 故非连续拼接; 但每块偏移仍自洽
    for c in chunks:
        assert c.char_count == c.char_end - c.char_start
        assert text[c.char_start:c.char_end] == c.content
    # 覆盖全文: 首块起点 0, 末块终点 == len(text)
    assert chunks[0].char_start == 0
    assert chunks[-1].char_end == len(text)


def test_page_16_invalid_strategy_still_raises():
    """未知 strategy 仍抛 ValueError"""
    from app.services.chunking_service import chunk_text, ChunkConfig

    with pytest.raises(ValueError, match="Unknown chunk strategy"):
        chunk_text("test", ChunkConfig(strategy="unknown"))
