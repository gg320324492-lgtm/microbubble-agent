"""file_parser_service._parse_pptx 组合形状 (p:grpSp) 递归回归测试

背景 (2026-10-09 agent38): 修复前 `_parse_pptx` 只遍历 `slide.shapes` 顶层,
组合形状里的文本被静默丢弃。生产实测 (295 个 pptx / 5185 页): 含 group 的页
559 (10.8%), 净损失 22,397 字符, 134 页单页损失 >20 字符; knowledge.id=1118 /
973 / 1042 三个 pptx 各有**整页**抽出 0 字符。

不依赖 DB / MinIO / Celery, fixture 用 python-pptx 现场生成:
    python -m pytest tests/test_file_parser_pptx_group_shapes.py -v
"""
import io

import pytest
from pptx import Presentation
from pptx.util import Emu

from app.services.file_parser_service import (
    _PPTX_GROUP_MAX_DEPTH,
    file_parser_service as fps,
)


def _tb(shapes, text, left=0, top=0):
    """在给定 shape 集合上放一个带单段文本的文本框"""
    box = shapes.add_textbox(Emu(left), Emu(top), Emu(2_000_000), Emu(500_000))
    box.text_frame.text = text
    return box


def _build(build_slide):
    """建一个单页 pptx, build_slide(slide) 负责摆 shape"""
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank, 无占位符
    build_slide(slide)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_group_shape_text_is_extracted():
    """核心回归: 组内 3 个有字 shape 必须被抽出 (修复前全丢)"""

    def build(slide):
        group = slide.shapes.add_group_shape()
        _tb(group.shapes, "组内甲", 0, 0)
        _tb(group.shapes, "组内乙", 0, 600_000)
        _tb(group.shapes, "组内丙", 0, 1_200_000)

    text = await fps._parse_pptx(_build(build))
    for expected in ("组内甲", "组内乙", "组内丙"):
        assert expected in text, f"组内文本 {expected} 被丢弃"


@pytest.mark.asyncio
async def test_group_order_is_document_order_in_place():
    """顺序稳定性: 组内文本插在 group 原本所处的文档序位置, 前后顶层文本相对次序不变"""

    def build(slide):
        _tb(slide.shapes, "顶层一", 0, 0)
        group = slide.shapes.add_group_shape()
        _tb(group.shapes, "组内甲", 0, 0)
        _tb(group.shapes, "组内乙", 0, 600_000)
        _tb(slide.shapes, "顶层二", 0, 0)

    text = await fps._parse_pptx(_build(build))
    order = [line for line in text.splitlines() if line and not line.startswith(("[PAGE:", "--- "))]
    assert order == ["顶层一", "组内甲", "组内乙", "顶层二"]


@pytest.mark.asyncio
async def test_nested_group_is_recursed():
    """group 嵌 group (OOXML 合法) 也要抽到"""

    def build(slide):
        outer = slide.shapes.add_group_shape()
        _tb(outer.shapes, "外层甲", 0, 0)
        inner = outer.shapes.add_group_shape()
        _tb(inner.shapes, "内层乙", 0, 0)

    text = await fps._parse_pptx(_build(build))
    assert "外层甲" in text and "内层乙" in text


@pytest.mark.asyncio
async def test_table_inside_group_is_extracted():
    """组内表格走 has_table 分支 (与顶层一致)

    python-pptx 的 GroupShapes 没有 add_table (只有 _SlideShapeTree 有), 所以先在
    幻灯片层建表, 再把 graphicFrame 元素 reparent 进 group —— 这正是真实 PPT 里
    `p:grpSp > p:graphicFrame > a:tbl` 的结构。
    """

    def build(slide):
        frame = slide.shapes.add_table(
            2, 2, Emu(0), Emu(0), Emu(2_000_000), Emu(1_000_000)
        )
        frame.table.cell(0, 0).text = "单元格A"
        frame.table.cell(0, 1).text = "单元格B"
        frame.table.cell(1, 0).text = "单元格C"
        group = slide.shapes.add_group_shape()
        group._element.append(frame._element)  # 从 slide spTree 挪进 group spTree

    text = await fps._parse_pptx(_build(build))
    assert "单元格A 单元格B" in text
    assert "单元格C" in text


@pytest.mark.asyncio
async def test_page_marker_stays_first_line_of_each_page():
    """[PAGE:N] 必须在页首 —— chunking_service 按它切页, 位置不能动"""

    def build_p1(slide):
        group = slide.shapes.add_group_shape()
        _tb(group.shapes, "第一页组内", 0, 0)
        _tb(slide.shapes, "第一页顶层", 0, 0)

    def build_p2(slide):
        _tb(slide.shapes, "第二页顶层", 0, 0)

    prs = Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[6])
    build_p1(s1)
    s2 = prs.slides.add_slide(prs.slide_layouts[6])
    build_p2(s2)
    buf = io.BytesIO()
    prs.save(buf)

    lines = (await fps._parse_pptx(buf.getvalue())).splitlines()
    assert lines[0] == "[PAGE:1]"
    assert "[PAGE:2]" in lines
    assert lines.index("[PAGE:2]") < lines.index("第二页顶层")
    # 有文本的页才有 "--- 第N页 ---" 分隔行
    assert lines.index("[PAGE:2]") < lines.index("--- 第2页 ---") < lines.index("第二页顶层")


@pytest.mark.asyncio
async def test_group_without_text_yields_no_placeholder_text():
    """空组 (只有无字图片形状) 不应产生空行/噪声 —— 保持既有 'if text' 过滤语义"""

    def build(slide):
        slide.shapes.add_picture(io.BytesIO(_PNG_1PX), Emu(0), Emu(0), Emu(100_000), Emu(100_000))

    text = await fps._parse_pptx(_build(build))
    # 无任何文本 → 只有 [PAGE:1], 不应有 "--- 第1页 ---"
    assert text.strip() == "[PAGE:1]"


@pytest.mark.asyncio
async def test_deep_nesting_beyond_limit_does_not_recurse_or_crash():
    """防御: 超过深度上限的嵌套 group 被截断, 不爆栈"""

    def build(slide):
        cur = slide.shapes
        for _ in range(_PPTX_GROUP_MAX_DEPTH + 3):
            cur = cur.add_group_shape().shapes
        _tb(cur, "深层文本")

    text = await fps._parse_pptx(_build(build))
    # 截断后深层文本取不到, 但解析必须正常返回而不是 RecursionError
    assert "[PAGE:1]" in text


# 1x1 透明 PNG —— 给 add_picture 造一个"组内无字形状"
_PNG_1PX = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)