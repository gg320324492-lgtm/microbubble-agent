"""
build:a11y + prebuild + health-check.spec 守恒 (W89-P-5 沉淀).

CLAUDE.md 永久纪律强化: 'npm run build' 唯一合法, build 后必跑 a11y
health-check (类 20.52). 本测试三大门禁:

1. test_build_a11y_script_exists — web/package.json scripts.build:a11y 必存在
2. test_health_check_spec_exists — health-check.spec.mjs 必存在 + critical+serious 硬断言代码可见
3. test_prebuild_hook_safe — prebuild hook 必非 destructive (no rm -rf / mv / del)

派工 v6 §5 反馈 类 20.52: build 后必跑 a11y health-check, critical+serious
硬断言 = 0; moderate + minor 由主指挥拍板 (WARN).
"""

from __future__ import annotations

import json
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parents[2] / "web"
WEB_PKG = WEB_DIR / "package.json"
HEALTH_CHECK_SPEC = WEB_DIR / "tests" / "visual" / "a11y" / "health-check.spec.mjs"


def _read_pkg() -> dict:
    return json.loads(WEB_PKG.read_text(encoding="utf-8"))


def test_build_a11y_script_exists() -> None:
    """web/package.json scripts.build:a11y 必存在且包含 build + health-check 链."""
    data = _read_pkg()
    scripts = data.get("scripts", {})
    assert "build:a11y" in scripts, "package.json 缺 scripts.build:a11y (W89-P-5 必加)"

    cmd = scripts["build:a11y"]
    # 必含 build 段 + a11y health-check 段
    assert "npm run build" in cmd, f"build:a11y 必调 npm run build, 实际: {cmd}"
    assert "health-check" in cmd, f"build:a11y 必 grep 'health-check', 实际: {cmd}"

    # 必同时含 test:playwright:a11y 入口 (与 a11y config 配对)
    assert "test:playwright:a11y" in scripts, (
        "缺 scripts.test:playwright:a11y, build:a11y 链断裂. "
        "W89-P-5 必加 (复用 tests/visual/a11y/playwright.a11y.config.mjs)"
    )


def test_health_check_spec_exists() -> None:
    """web/tests/visual/a11y/health-check.spec.mjs 必存在 + critical+serious 硬断言可见."""
    assert HEALTH_CHECK_SPEC.exists(), f"Missing {HEALTH_CHECK_SPEC} (W89-P-5 必新建)"

    content = HEALTH_CHECK_SPEC.read_text(encoding="utf-8")

    # 类 20.52 核心纪律: critical + serious 硬断言 = 0
    assert "critical" in content, "health-check.spec 缺 critical 断言"
    assert "serious" in content, "health-check.spec 缺 serious 断言"
    assert "expect(criticalOrSerious).toEqual([])" in content, (
        "health-check.spec 缺 expect(criticalOrSerious).toEqual([]) 硬断言 (类 20.52 必含)"
    )

    # moderate + minor 应标记为 WARN (不 block)
    assert "moderate" in content, "health-check.spec 应含 moderate 处置逻辑 (WARN)"


def test_prebuild_hook_safe() -> None:
    """prebuild hook 必非 destructive (e2e 守恒, 类 20.52 配套)."""
    data = _read_pkg()
    prebuild = data.get("scripts", {}).get("prebuild", "")

    assert prebuild, "package.json 缺 scripts.prebuild (W89-P-5 必加)"

    # destructive 操作必禁
    forbidden = ["rm -rf", "rm -fr", "mv ", "del ", "rmdir", ":(){:|:&};:"]
    for token in forbidden:
        assert token not in prebuild, (
            f"prebuild hook 含 destructive 操作 '{token}' 不允许. "
            f"实际: {prebuild}"
        )

    # 必含 echo (证明是 placeholder, 不静默执行)
    assert "echo" in prebuild, f"prebuild 必含 echo (placeholder 标识), 实际: {prebuild}"


def test_existing_build_script_unchanged() -> None:
    """回归: 已有 build script 必未被 W89-P-5 误改 (派工 v6 §1.2 守恒)."""
    data = _read_pkg()
    build = data["scripts"]["build"]
    # CLAUDE.md 永久纪律: vite build && node scripts/postbuild-fix-manifest.js
    assert "vite build" in build
    assert "postbuild-fix-manifest.js" in build