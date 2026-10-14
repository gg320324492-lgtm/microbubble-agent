"""PDF 版面清洗（Word 行号版式）单元测试 —— 类 20.223：文档说的必须被测到

设计取舍见 app/services/pdf_layout_cleaner.py 的模块 docstring：
保守策略 = **只删独占一行的纯数字行，不跨行接词、不删行内行号**。

三条「宁可漏改不可错改」的边界各有实测依据：
  ① 跨行接词不可靠：`shear\n314\n can`（两个完整词）与 `react\n34\nion`
     （一个词被劈开）**结构同构**，误接会粘连正常词、污染整个 BM25 索引。
  ② 行内行号不可靠：`shear 314 can` / `equations 12 and 14` /
     `300 K and 15 bar` 三者结构同构，实测误删率高于命中收益。
  ③ 只对「行号版式」PDF 施加，正常排版必须原样不动。
"""
import sys

sys.path.insert(0, "/app")
from app.services.pdf_layout_cleaner import clean_page, is_line_numbered_pdf


def test_removes_standalone_line_numbers():
    """独占一行的行号/页码必须删掉"""
    assert "28" not in clean_page(" \n28 \nr within MNBs generators")
    assert "18" not in clean_page("thods provide diff\n18 \nerent evidence")


def test_does_not_join_broken_words():
    """保守策略：**不**接词（接了会粘连正常词，污染索引）"""
    out = clean_page("turbulent shear\n314 \n can induce bubble collapse")
    assert out == "turbulent shear can induce bubble collapse"
    assert "shearcan" not in out


def test_preserves_normal_numbers():
    """正文数字/引用编号/量纲值必须原样保留"""
    keep = [
        "Fig. 5 shows the effect of 3 O2 molecules",
        "The mixture contained 2.5 g of catalyst",
        "reaction 3 is the dominant pathway",
        "See equations 12 and 14 for details",
        "at 300 K and 15 bar the rate is 21",
        "sample A1 and B2 were compared",
        "O2 and N2 are the main products",
        "In Fig. 7 the authors note 5 lines",
    ]
    for raw in keep:
        assert clean_page(raw) == raw, "被误改: %r -> %r" % (raw, clean_page(raw))


def test_never_produces_stuck_words():
    """跨行接合的历史踩坑产物：一个都不许出现"""
    out = clean_page("present in\n12 \nthe system" + " cavitation and\n13 \nturbulent flow")
    for bad in ("presentin", "cavitationand", "shearcan", "atomsmay"):
        assert bad not in out


def test_placeholders_survive():
    """[PAGE:N] / [FIGURE:N] 占位符（分块器依赖）不受清洗影响"""
    text = "Intro text\n[PAGE:5]\nBody\n5 \nmore\n[FIGURE:12]"
    out = clean_page(text)
    assert "[PAGE:5]" in out
    assert "[FIGURE:12]" in out


LINE_NUMBERED_PAGE = (
    "\n1 \nBeyond hydroxyl radicals in micro- and nanobubble\n2 \n"
    "systems: Formation, interconversion, and\n3 \n"
    "identification of reactive oxygen species\n4 \n"
    "Bing Wang, Xinyue Luo, Tianjie Zeng\n5 \n"
    "School of Chemistry, Southwest Petroleum\n6 \n"
    "Chengdu 610500, P.R. China\n7 \n"
    "Corresponding author: wangb@swpu.edu.cn\n8 \n"
    "a School of Chemistry and Chemical Engineering\n9 \n"
    "Southwest Petroleum University, Chengdu\n10 \n"
    "Manuscript Number: ER-26-18027\n11 \n"
    "Article Type: Review article\n12 \n"
    "Section/Category: Environmental Process\n13 \n"
    "Keywords: Micro- and nanobubbles\n14 \n"
    "Abstract: With favorable gas-transfer properties\n15 \n"
    "Review article submitted to Environmental Research"
)

NORMAL_PAGE = (
    "Abstract\nThis paper reviews the formation of reactive oxygen species in micro "
    "and nanobubble systems. We discuss gas transfer, interfacial effects, and "
    "bubble collapse in detail. The review covers EPR detection methods and "
    "their limitations for ROS identification in complex aqueous matrices. "
    "We further analyse the role of HTHP conditions. Finally we discuss the "
    "engineering implications for water treatment applications. The review is "
    "organised as follows. Section 2 covers fundamentals."
)


def test_detects_line_numbered_pdf():
    assert is_line_numbered_pdf(LINE_NUMBERED_PAGE) is True


def test_ignores_normal_pdf():
    assert is_line_numbered_pdf(NORMAL_PAGE) is False


def test_ignores_short_or_empty():
    assert is_line_numbered_pdf("") is False
    assert is_line_numbered_pdf("1\n2\n3") is False


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("  PASS %s" % name)
            except AssertionError as e:
                failures += 1
                print("  FAIL %s: %s" % (name, e))
    print()
    print("全部通过 ✓" if not failures else "%d 项失败 ✗" % failures)
    sys.exit(1 if failures else 0)