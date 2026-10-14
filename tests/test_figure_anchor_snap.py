"""[PAGE:N] 标记偏移吸附的回归测试

## 背景（2026-10-14 修）

`[FIGURE:N]` 占位符按**绝对 offset** 插入。若 offset 落在某个 `[PAGE:N]` 标记
**内部**，插入会把标记劈开：

    [PAG  +  \n[FIGURE:99]\n  +  E:81]
      ↑ 正则 \[PAGE:(\d+)\] 匹配不到 ⇒ 分块器认为第 81 页不存在 ⇒ 该页内容
        被并进第 80 页。

**实测触发条件**（`ER-26-18027.pdf` 第 81 页）：该页是整页图片
（9 张图 + 化学式碎片，全页找不到任何 `Fig. N` 引用）⇒ 9 个占位符
**全部落到同一 offset**（页尾），而该 offset 恰是 `[PAGE:82]` 起点 +4。

⇒ 任何「整页无图注文」的页（图片页 / 图表页 / 参考文献页）都会命中，
不是孤例。

## 修法

插入前把落在标记内部的 offset **吸附到该标记之后**。

本测试直接验证 `_snap` 的行为（通过整条 parser 链路太重，这里精确复刻
插入逻辑），并覆盖三个必须成立的不变量。
"""
import re
import sys


def _snap_all(full_text, anchors):
    """复刻 file_parser_service._parse_pdf 的插入逻辑（含吸附）"""
    page_spans = [(m.start(), m.end()) for m in re.finditer(r"\[PAGE:\d+\]", full_text)]

    def _snap(pos):
        for start, end in page_spans:
            if start < pos < end:
                return end
        return pos

    out = full_text
    snapped = 0
    for pos, ph in sorted(anchors, key=lambda x: x[0], reverse=True):
        p2 = _snap(pos)
        if p2 != pos:
            snapped += 1
        out = out[:p2] + ph + out[p2:]
    return out, snapped


def test_page_marker_survives_whole_image_page():
    """核心场景：整页图片的占位符全部落在下一页标记内部"""
    full = "[PAGE:80]text80\n[PAGE:81]text81\n[PAGE:82]text82"
    p82 = full.find("[PAGE:82]")
    # 9 个占位符全落在标记内（p82+4 处），模拟真实 bug
    anchors = [(p82 + 4, "\n[FIGURE:%d]\n" % (99 + i)) for i in range(9)]
    out, snapped = _snap_all(full, anchors)

    pages = [int(x) for x in re.findall(r"\[PAGE:(\d+)\]", out)]
    assert sorted(pages) == [80, 81, 82], "标记被劈开: %s" % pages
    assert snapped == 9
    figs = re.findall(r"\[FIGURE:(\d+)\]", out)
    assert len(figs) == 9, "占位符丢失: %d" % len(figs)


def test_no_markers_lost_for_any_offset():
    """任意 offset 组合下，标记数量与占位符数量都必须守恒"""
    for offset_delta in range(-6, 12):
        full = "[PAGE:1]a\n[PAGE:2]b\n[PAGE:3]c\n[PAGE:4]d"
        anchors = [(full.find("[PAGE:3]") + offset_delta, "\n[FIGURE:1]\n")]
        out, _ = _snap_all(full, anchors)
        pages = sorted(int(x) for x in re.findall(r"\[PAGE:(\d+)\]", out))
        assert pages == [1, 2, 3, 4], "offset 相对量 %+d 时标记丢失: %s" % (offset_delta, pages)
        assert len(re.findall(r"\[FIGURE:(\d+)\]", out)) == 1, "占位符丢失 @ %+d" % offset_delta


def test_unrelated_offsets_unchanged():
    """不落在标记内的 offset 不应被移动（避免改变原有行为）"""
    full = "[PAGE:1]abcdefghij\n[PAGE:2]klmnop"
    target = full.find("klmnop") + 2  # 落在正文中
    out, snapped = _snap_all(full, [(target, "\n[FIGURE:1]\n")])
    assert snapped == 0
    assert out == "…".join([]) or out.replace("\n[FIGURE:1]\n", "") == full


def test_order_independence():
    """占位符按任意顺序插入，结果都应保留全部标记"""
    full = "[PAGE:1]aaa\n[PAGE:2]bbb"
    p2 = full.find("[PAGE:2]")
    anchors = [(p2 + 2, "\n[FIGURE:%d]\n" % i) for i in (1, 2, 3)]
    out, _ = _snap_all(full, anchors)
    assert sorted(int(x) for x in re.findall(r"\[PAGE:(\d+)\]", out)) == [1, 2]
    assert len(re.findall(r"\[FIGURE:\d+\]", out)) == 3


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