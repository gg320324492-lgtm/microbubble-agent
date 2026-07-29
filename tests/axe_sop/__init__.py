"""
tests/axe_sop/test_doc_exists.py — W89-P-12 axe-rules.md 沉淀硬门禁.

类 20.60 沉淀: axe SOP doc 必含 ≥ 5 规则 + 修法 + CI 集成段.

用法:
    pytest tests/axe_sop/ -v
"""

from pathlib import Path


def _axe_doc_path() -> Path:
    """定位 docs/axe-rules.md."""
    return Path(__file__).resolve().parents[2] / "docs" / "axe-rules.md"


def test_axe_rules_doc_exists():
    """axe-rules.md 必存在."""
    doc = _axe_doc_path()
    assert doc.exists(), f"missing SOP doc: {doc}"


def test_axe_rules_doc_has_5_rules():
    """5 个 axe 规则 SOP 必出现 (类 20.60)."""
    doc = _axe_doc_path().read_text(encoding="utf-8")
    required_rules = [
        "color-contrast",
        "html-has-lang",
        "aria-command-name",
        "scrollable-region-focusable",
        "link-name",
    ]
    missing = [r for r in required_rules if r not in doc]
    assert not missing, f"missing SOP for rules: {missing}"


def test_axe_rules_doc_has_ci_section():
    """CI 集成段必存在."""
    doc = _axe_doc_path().read_text(encoding="utf-8")
    # 类 20.60 第 3 段: 修法 + 验证 + CI 集成
    assert "## CI" in doc or "build:a11y" in doc, "missing CI integration section"
