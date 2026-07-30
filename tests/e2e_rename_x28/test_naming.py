"""
W89-X-28 e2e: vitest spec 命名规范化边界

约定:
- vitest 运行 spec 候选: *.test.js / *.spec.js
- 项目约定统一用 *.test.js (unit/components/ 沿用 + e2e/ 全规范)
- playwright 专属 spec.mjs 不在此约束 (它们有 testMatch 显式控制)

实测状态 (2026-07-30 main HEAD a000d0bf2):
- tests/unit/components/ 目录 W89-P-10 还未合入 main, 不存在
- tests/e2e/ 现存 15 vitest spec, 本任务重命名为 *.test.js
- tests/router/ 1 vitest spec 重命名
- 跨 e2e + router 共 16 *.test.js
- src/__tests__ 仍有 5 个 *.spec.js (W89-P-10 范围外, 留 W89+ 后续处理)
"""
from pathlib import Path

# 工区根 (worktree 根目录)
WORKTREE_ROOT = Path(__file__).resolve().parents[2]
WEB_TESTS = WORKTREE_ROOT / "web" / "tests"

# vitest 期望命名: *.test.js (.spec.js 是历史遗留, 应改)
E2E_DIR = WEB_TESTS / "e2e"
ROUTER_DIR = WEB_TESTS / "router"
UNIT_DIR = WEB_TESTS / "unit"


def _is_vitest_spec(path: Path) -> bool:
    """判断是否是 vitest spec (排除 playwright spec.py 与 spec.mjs)"""
    if path.suffix != ".js":
        return False
    if not (path.name.endswith(".test.js") or path.name.endswith(".spec.js")):
        return False
    # 排除 playwright (require playwright test)
    text = path.read_text(encoding="utf-8", errors="ignore")[:500]
    return "vitest" in text or path.name.endswith(".test.js")


def test_no_spec_js_in_e2e_dir():
    """tests/e2e/ 中不应再有 *.spec.js (除非是 playwright 专属)

    Playwright 在 e2e/ 下保留 3 个 spec.js:
    - mobile_push_notification.spec.js
    - mobile_swipe_gesture.spec.js
    - mobile_voice_input.spec.js
    它们 require('@playwright/test'), 不属于 vitest.
    """
    playwright_specs = {
        "mobile_push_notification.spec.js",
        "mobile_swipe_gesture.spec.js",
        "mobile_voice_input.spec.js",
    }
    actual_specs = sorted(p.name for p in E2E_DIR.glob("*.spec.js"))
    leftover = [s for s in actual_specs if s not in playwright_specs]
    assert not leftover, (
        f"tests/e2e/ 残留 vitest *.spec.js (应统一为 *.test.js): {leftover}"
    )


def test_e2e_dir_has_test_js_for_vitest():
    """tests/e2e/ 应有 15+ vitest *.test.js (15 vitest + 0 playwright 重复)"""
    test_files = [p.name for p in E2E_DIR.glob("*.test.js")]
    assert len(test_files) >= 15, (
        f"期望 ≥ 15 .test.js, 实际 {len(test_files)}: {test_files}"
    )


def test_router_has_resolveMobile_test_js():
    """tests/router/resolveMobile.test.js 必存在"""
    assert (ROUTER_DIR / "resolveMobile.test.js").exists(), (
        "tests/router/resolveMobile.test.js 应存在 (本次重命名产物)"
    )
    assert not (ROUTER_DIR / "resolveMobile.spec.js").exists(), (
        "tests/router/resolveMobile.spec.js 不应残留"
    )


def test_unit_dir_intact():
    """tests/unit/ 既有 *.test.js (mobile-fab / pwa-update-toast) 不被改动

    派工 brief 提及 tests/unit/components/ 但 W89-P-10 还未合入 main,
    本任务不动 tests/unit/ 任何文件 (0 production code 改动铁律守恒).
    """
    test_files = sorted(p.name for p in UNIT_DIR.glob("*.test.js"))
    assert "mobile-fab.test.js" in test_files
    assert "pwa-update-toast.test.js" in test_files
