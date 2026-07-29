"""tests/integration/test_build_a11y.py — W89-P-13 Playwright 集成真验证

设计意图 (派工 v6 §5 反馈 类 20.61):
    W89-P-3 (playwright CI workflow) + W89-P-5 (build:a11y npm script) 写了但未真跑。
    本套件断言 3 件套联动存在性 + 真跑口径, 防止"写了没跑"的假绿。

3 件套 (integration triad):
    1. .pre-commit-config.yaml            (W86-D-1, 5 hook)
    2. web/tests/visual/a11y/playwright.a11y.config.mjs  (W89-P-3)
    3. web/package.json scripts["build:a11y"]            (W89-P-5)

⚠️ 派工前提据实上报 (类 20.13 实战, 详见 memory/w89-p13-integration-2026-07-30.md):
    派工 brief 假设 3 件套已在 main。实测 main tip `3a1ab24b3` 只有 2/3 落地:
      - .pre-commit-config.yaml           ✅ 在 main (W86-D-1 已 merge)
      - playwright.a11y.config.mjs        ✅ 在 main (W87-G-1 已 merge)
      - package.json test:playwright:a11y ❌ 不在 main (W89-P-3 分支 `a765adf2f` 未 merge)
      - package.json build:a11y           ❌ 不在 main (W89-P-5 分支 `356740c44` 未 merge)
    因此 npm script 相关断言用 skipif 守卫 —— main 合入 W89-P-3/P-5 后自动转 PASS,
    不做"假 PASS"也不做"硬 FAIL 卡住收尾"。这是类 20.23 负向对照的应用。
    真跑证据 (build:a11y + health-check) 在 P-5 worktree 取得, 见 memory 沉淀。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_PKG = REPO_ROOT / "web" / "package.json"
PRECOMMIT_CFG = REPO_ROOT / ".pre-commit-config.yaml"
PW_A11Y_CFG = REPO_ROOT / "web" / "tests" / "visual" / "a11y" / "playwright.a11y.config.mjs"


def _scripts() -> dict[str, str]:
    """读 web/package.json scripts 段 (utf-8 显式, Windows 默认 gbk 会炸)."""
    return json.loads(WEB_PKG.read_text(encoding="utf-8")).get("scripts", {})


_HAS_BUILD_A11Y = WEB_PKG.exists() and "build:a11y" in _scripts()
_HAS_PW_A11Y_SCRIPT = WEB_PKG.exists() and "test:playwright:a11y" in _scripts()

requires_build_a11y = pytest.mark.skipif(
    not _HAS_BUILD_A11Y,
    reason="build:a11y 未在当前 ref (W89-P-5 分支 356740c44 未 merge 进 main), 合入后自动转 PASS",
)

requires_pw_a11y_script = pytest.mark.skipif(
    not _HAS_PW_A11Y_SCRIPT,
    reason="test:playwright:a11y 未在当前 ref (W89-P-3 分支 a765adf2f 未 merge 进 main), 合入后自动转 PASS",
)


# --- 1. pre-commit (W86-D-1) ------------------------------------------------


def test_precommit_config_exists():
    """W86-D-1 pre-commit 配置必存在."""
    assert PRECOMMIT_CFG.exists(), f"缺 {PRECOMMIT_CFG}"


def test_precommit_has_five_hooks():
    """W86-D-1 5 hook 必齐 (真跑口径: 3 PASS + 2 需装 binary / 已知违规)."""
    text = PRECOMMIT_CFG.read_text(encoding="utf-8")
    expected = [
        "gitleaks-scan",
        "dockerfile-pinning",
        "alembic-chain",
        "typing-imports",
        "dist-manifest-hash",
    ]
    missing = [h for h in expected if f"id: {h}" not in text]
    assert not missing, f"pre-commit 缺 hook: {missing}"


# --- 2. playwright a11y (W89-P-3) -------------------------------------------


def test_playwright_a11y_config_exists():
    """W89-P-3 playwright.a11y.config.mjs 必存在."""
    assert PW_A11Y_CFG.exists(), f"缺 {PW_A11Y_CFG}"


@requires_pw_a11y_script
def test_playwright_a11y_script_exists():
    """test:playwright:a11y 必指向 playwright.a11y.config.mjs (build:a11y 的被调方)."""
    script = _scripts().get("test:playwright:a11y", "")
    assert script, "web/package.json 缺 test:playwright:a11y"
    assert "playwright.a11y.config.mjs" in script, (
        f"test:playwright:a11y 未指向 a11y config: {script!r}"
    )


# --- 3. build:a11y (W89-P-5, 未 merge → skipif 守卫) -------------------------


@requires_build_a11y
def test_build_a11y_script_exists():
    """npm run build:a11y 必存在."""
    assert "build:a11y" in _scripts()


@requires_build_a11y
def test_build_a11y_chains_npm_run_build():
    """build:a11y 必走 `npm run build` (CLAUDE.md 永久纪律: vite build 直跑必坏 PWA)."""
    script = _scripts()["build:a11y"]
    assert "npm run build" in script, (
        f"build:a11y 必须链 `npm run build` 而非 `vite build` 直跑, 实测: {script!r}"
    )
    assert "vite build &&" not in script, (
        f"build:a11y 不得绕开 postbuild-fix-manifest.js, 实测: {script!r}"
    )


# --- 4. 3 件套联动 ----------------------------------------------------------


def test_integration_3_artefacts_status():
    """3 件套联动状态据实断言 (类 20.13: 不凑绿, 缺的明确报出来).

    pre-commit + playwright.a11y 必须在; build:a11y 允许缺 (W89-P-5 未 merge),
    但缺的时候必须是"确实不在文件里", 而不是读取失败/路径写错。
    """
    precommit = PRECOMMIT_CFG.exists()
    pw_a11y = PW_A11Y_CFG.exists()
    build_a11y = _HAS_BUILD_A11Y

    # 已 merge 的 2 件套硬断言
    assert precommit, "pre-commit 配置缺失 (W86-D-1 应已在 main)"
    assert pw_a11y, "playwright.a11y.config.mjs 缺失 (W89-P-3 应已在 main)"

    # 第 3 件据实上报: package.json 必可读 (排除路径/编码问题冒充"缺失")
    assert WEB_PKG.exists(), f"web/package.json 不可达: {WEB_PKG}"
    assert _scripts(), "web/package.json scripts 段为空 — 读取异常而非真缺 build:a11y"

    if not build_a11y:
        pytest.skip(
            "3 件套 2/3 就位; build:a11y 待 W89-P-5 (356740c44) merge 进 main. "
            "本 skip 是据实上报, 不是失败掩盖。"
        )
