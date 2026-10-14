"""chunking min_chars 过滤的回归测试

## 背景（2026-10-14）

Word 稿件 PDF 的版面把化学式排成一行一个符号（``O3`` / ``914`` / ``1213``），
按 ``\\n\\n`` 切段会产出大量碎片。实测 `ER-26-18027`：

    总 chunk 338，其中 char_count<50 的有 164 个（48.5%）
    样本: ``O3`` / ``12`` / ``914`` / ``1213`` / ``106`` / ``335``

这些碎片是**检索噪声**：纯数字串会匹配任何含数字的查询，把无关 chunk 顶上来。

`min_chars` 默认 0（**不改变既有行为**），只在重切时启用。
"""
import sys

sys.path.insert(0, "/app")
from app.services.chunking_service import ChunkConfig, chunk_text


PAGE_TEXT = (
    "[PAGE:1]\nO3\n\n12\n\n914\n\n1213\n\n"
    "This is a real paragraph with actual English content that should survive "
    "the filter because it is long enough to be useful for retrieval.\n\n"
    "[PAGE:2]\nReaction mechanisms in micro and nanobubble systems were "
    "reviewed comprehensively across gas transfer and interfacial effects."
)


def test_default_keeps_everything():
    """默认 min_chars=0 ⇒ 行为与改动前完全一致（向后兼容）"""
    out = chunk_text(PAGE_TEXT)
    assert len(out) > 5, "默认应不过滤，实际 %d 个" % len(out)
    assert any(c.char_count < 10 for c in out), "默认应保留碎片"


def test_min_chars_filters_fragments():
    """启用 min_chars ⇒ 碎片被丢弃"""
    out = chunk_text(PAGE_TEXT, ChunkConfig(strategy="paragraph", min_chars=50))
    assert all(c.char_count >= 50 for c in out), "仍有碎片: %s" % [
        c.char_count for c in out if c.char_count < 50]
    assert len(out) < 10, "过滤后应显著减少，实际 %d" % len(out)


def test_content_not_lost_from_real_paragraphs():
    """过滤只丢碎片，**真实段落内容不能丢**"""
    out = chunk_text(PAGE_TEXT, ChunkConfig(strategy="paragraph", min_chars=50))
    joined = " ".join(c.content for c in out)
    assert "Reaction mechanisms" in joined
    assert "real paragraph with actual English content" in joined


def test_char_offsets_stay_consistent():
    """不变量: content == text[char_start:char_end]（过滤不得破坏偏移一致性）"""
    out = chunk_text(PAGE_TEXT, ChunkConfig(strategy="paragraph", min_chars=50))
    for c in out:
        assert PAGE_TEXT[c.char_start:c.char_end] == c.content
        assert c.char_count == c.char_end - c.char_start


def test_page_strategy_also_honours_min_chars():
    """走 page 策略（带 [PAGE:N] 标记时自动路由过去）也要过滤"""
    out = chunk_text(PAGE_TEXT, ChunkConfig(strategy="page", min_chars=50))
    for c in out:
        # page 策略保留整页（不按段落细分），过滤只作用于页内 paragraph 子块
        if c.strategy == "paragraph":
            assert c.char_count >= 50


def test_min_chars_zero_is_noop():
    """min_chars=0 与不传参结果完全一致"""
    a = chunk_text(PAGE_TEXT, ChunkConfig(strategy="paragraph"))
    b = chunk_text(PAGE_TEXT, ChunkConfig(strategy="paragraph", min_chars=0))
    assert len(a) == len(b)
    assert [c.content for c in a] == [c.content for c in b]


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