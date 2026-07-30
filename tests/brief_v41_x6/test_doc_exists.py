from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "dispatch-template-v4.1.md"
CLAUDE = Path(__file__).resolve().parents[2] / "CLAUDE.md"


def test_v41_doc_exists():
    assert DOC.exists()


def test_v41_doc_has_6_mandatory_sections():
    """v4.1 必含 6 必读段 (类 20.46 / 47 / 97 / 98 / 108 / 109)"""
    content = DOC.read_text(encoding="utf-8")
    for class_id in ["20.46", "20.47", "20.97", "20.98", "20.108", "20.109"]:
        assert class_id in content, f"Missing class {class_id}"


def test_claude_md_has_v41_refs():
    """CLAUDE.md 必含 v4.1 引用。"""
    content = CLAUDE.read_text(encoding="utf-8")
    assert "dispatch-template-v4.1" in content
