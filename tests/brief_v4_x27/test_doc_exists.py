"""W89-X-27 派工 brief v4 升级 e2e 加固测试.

W89 第 1+2 批沉淀 9 新铁律 (类 20.60-68):
- axe SOP / 集成真验证 / visual baseline / 硬门禁 / CI 触发
- vitest 调研 / swipe 拦截 / networkidle / 真环境 v2

CLAUDE.md 永久纪律 + 类 20.82 "派工 brief v4 升级必含 ≥ 9 铁律 + 实战举例".
"""
from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "dispatch-template-v4.md"


def test_v4_doc_exists():
    """v4 文档必须存在."""
    assert DOC.exists(), f"Missing dispatch template v4 at {DOC}"


def test_v4_doc_has_9_new_classes():
    """v4 必含类 20.60-68 共 9 类."""
    content = DOC.read_text(encoding="utf-8")
    for c in ["20.60", "20.61", "20.62", "20.63", "20.64", "20.65", "20.66", "20.67", "20.68"]:
        assert c in content, f"Missing class {c}"


def test_v4_doc_has_class_82():
    """v4 必含类 20.82 派工 brief v4 升级必含规则."""
    content = DOC.read_text(encoding="utf-8")
    assert "20.82" in content, "Missing class 20.82 (派工 brief v4 升级规则)"


def test_v4_doc_has_9_new_section_headers():
    """v4 必含 9 段标题 (类 20.60-68 每类 1 段)."""
    content = DOC.read_text(encoding="utf-8")
    expected_headers = [
        "类 20.60",
        "类 20.61",
        "类 20.62",
        "类 20.63",
        "类 20.64",
        "类 20.65",
        "类 20.66",
        "类 20.67",
        "类 20.68",
    ]
    for h in expected_headers:
        assert h in content, f"Missing section header for {h}"
