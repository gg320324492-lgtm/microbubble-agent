"""
src_tests_x5.test_naming - src/__tests__/ vitest spec 命名门禁 (W90-X-5)

派工前提铁律类 20.83:
- vitest spec 命名必统一 .test.js
- src/__tests__/ 必无 .spec.js 后缀 (派工 brief W89-X-28 留口)
- 与 playwright visual/.spec.mjs 不冲突 (后者 .mjs 扩展名)
"""

from pathlib import Path

WEB_SRC = Path(__file__).resolve().parents[2] / "web" / "src"
SRC_TESTS = WEB_SRC / "__tests__"


def test_no_spec_js_in_src_tests():
    """src/__tests__/ 必无 .spec.js 后缀 (W89-X-28 留口 W90-X-5 整改)"""
    specs = list(WEB_SRC.rglob("*.spec.js"))
    assert not specs, f".spec.js 残留: {[s.relative_to(WEB_SRC.parent.parent) for s in specs]}"


def test_src_tests_has_test_js():
    """src/__tests__/ 必含 .test.js 后缀 (≥ 5 个, 含嵌套子目录)"""
    tests = list(WEB_SRC.rglob("*.test.js"))
    assert len(tests) >= 5, f"期望 ≥ 5 .test.js, 实际 {len(tests)}: {[t.name for t in tests]}"
