"""KB 迁移脚本 — 纯函数单测 (无 DB / 无 async fixture 依赖, 任意环境可跑)

跑法:
    docker exec microbubble-agent-app-1 bash -c "cd /app && python -m pytest tests/test_migrate_kb_tags.py -v"

覆盖:
- normalize_tags 严格相等归并 (5 case)
- normalize_tags 幂等性
- normalize_tags 保序去重
- should_delete 多种 title 子串 case
"""

import sys
from pathlib import Path

# 让脚本可独立导入 (本地或容器)
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from migrate_kb_tags import (  # noqa: E402
    EXPANSION_TAGS,
    NORMALIZED_TAG,
    TITLE_DELETE_KEYWORDS,
    normalize_tags,
    should_delete,
)


# ── normalize_tags: 严格相等归并 ─────────────────────────────────
def test_normalize_basic_rename():
    """['拓展', 'intent:foo'] → ['自动拓展', 'intent:foo']"""
    new, changed = normalize_tags(["拓展", "intent:foo"])
    assert new == [NORMALIZED_TAG, "intent:foo"]
    assert changed is True


def test_normalize_dedup_all_variants():
    """['拓展', '自动拓展', '拓展测试'] → ['自动拓展'] (去重)"""
    new, changed = normalize_tags(list(EXPANSION_TAGS))
    assert new == [NORMALIZED_TAG]
    assert changed is True


def test_normalize_preserves_others():
    """['case-study', 'method', '拓展'] → ['case-study', 'method', '自动拓展']"""
    new, changed = normalize_tags(["case-study", "method", "拓展"])
    assert new == ["case-study", "method", NORMALIZED_TAG]
    assert changed is True


def test_normalize_strict_no_false_hit():
    """['foo拓展bar', 'case'] 不变 (严格相等不匹配子串)"""
    new, changed = normalize_tags(["foo拓展bar", "case"])
    assert new == ["foo拓展bar", "case"]
    assert changed is False


def test_normalize_idempotent():
    """已归一的 ['自动拓展'] 再次调用 → 不变 + changed=False"""
    new1, c1 = normalize_tags(["case", NORMALIZED_TAG])
    assert c1 is False
    new2, c2 = normalize_tags(new1)
    assert new2 == new1
    assert c2 is False


def test_normalize_preserves_order_and_dedups():
    """保序去重: 输入 ['z','拓展','a','自动拓展','a'] → ['z','自动拓展','a']"""
    new, changed = normalize_tags(["z", "拓展", "a", "自动拓展", "a"])
    assert new == ["z", NORMALIZED_TAG, "a"]
    assert changed is True


def test_normalize_empty_and_none():
    """None 和 [] 透传, changed=False"""
    new1, c1 = normalize_tags(None)
    assert new1 == []
    assert c1 is False
    new2, c2 = normalize_tags([])
    assert new2 == []
    assert c2 is False


def test_normalize_intent_scoped_tags_preserved():
    """自动拓展特有的 intent:X / scope:Y 这种 key:value tag 不被误改"""
    new, changed = normalize_tags(
        ["拓展", "intent:explain_concept", "scope:core", "case"]
    )
    assert new == ["自动拓展", "intent:explain_concept", "scope:core", "case"]
    assert changed is True


# ── should_delete: 子串匹配 ─────────────────────────────────────
def test_should_delete_true_cases():
    """含中文'测试'子串的都删 ('test' 英文不应中文字符串匹配命中)"""
    for title in ["测试用例", "压力测试仪", "alpha 测试协议", "性能测试报告", "这是一个测试"]:
        assert should_delete(title) is True, f"应当被删: {title!r}"


def test_should_delete_english_test_not_matched():
    """英文 'test' (全小写) 不匹配 'TEST' (大写, 测试样板用大写)"""
    for title in ["test", "Test ran yesterday"]:
        assert should_delete(title) is False, f"不应当被删: {title!r}"


def test_should_delete_uppercase_TEST_matched():
    """英文 'TEST01'/'TEST02' 大写样板 → 删 (覆盖自动拓展测试样板 [自动拓展-S-TEST##])"""
    for title in ["TEST01", "S-TEST02", "[自动拓展-S-TEST01] 什么是 zeta 电位?"]:
        assert should_delete(title) is True, f"应当被删: {title!r}"


def test_should_delete_false_cases():
    """不含 '测试' 子串的不删"""
    for title in ["臭氧氧化", "微纳米气泡", "DLVO理论", "alpha", "zeta 电位"]:
        assert should_delete(title) is False, f"不应当被删: {title!r}"


def test_should_delete_empty_none():
    """None / 空字符串 → False"""
    assert should_delete(None) is False
    assert should_delete("") is False


# ── 规则常量 sanity ───────────────────────────────────────────────
def test_constants_consistent():
    """NORMALIZED_TAG 必须在 EXPANSION_TAGS 内 (否则改名为空操作)"""
    assert NORMALIZED_TAG in EXPANSION_TAGS
    assert "测试" in TITLE_DELETE_KEYWORDS
    assert "TEST" in TITLE_DELETE_KEYWORDS
