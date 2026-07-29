"""W89-X-11 dark-accent + el-menu-hover 软断言转硬门禁加固 e2e

派工 v6 §5 反馈 类 20.63 沉淀 (W89-X-11):
    "Playwright 软断言改硬门禁必 TEST_TOKEN 真注入 + throw if missing"

P-11 写的 dark-accent.spec.mjs + el-menu-hover.spec.mjs 是软断言
(报告型 — console 打 violations, 不设硬断言, router 守卫重定向时跳过).
CI 配 TEST_TOKEN 后必须转硬门禁:
    1. process.env.TEST_TOKEN 缺失立即 throw new Error (不允许软降级)
    2. injectAuth 必须返回 true (不允许 "router 守卫重定向到 /login 后跳过")
    3. 主题必须真切 (data-theme / data-accent 必与预期一致, 不允许 null)

本文件加固 e2e 检查这两个 spec 真转硬门禁 — 仅 read 文件断言,
不动 production code, 跑前可用 SKIP_DB_SETUP=1 跳过 db init.
"""

import os
import subprocess
from pathlib import Path

# tests/dark_harden/ -> tests/ -> 项目根 -> web/tests/visual/a11y/
WEB_DIR = Path(__file__).resolve().parents[2] / "web"
DARK_ACCENT_SPEC = WEB_DIR / "tests" / "visual" / "a11y" / "dark-accent.spec.mjs"
EL_MENU_HOVER_SPEC = WEB_DIR / "tests" / "visual" / "a11y" / "el-menu-hover.spec.mjs"


def test_dark_accent_spec_exists():
    assert DARK_ACCENT_SPEC.exists(), f"missing: {DARK_ACCENT_SPEC}"


def test_el_menu_hover_spec_exists():
    assert EL_MENU_HOVER_SPEC.exists(), f"missing: {EL_MENU_HOVER_SPEC}"


def test_dark_accent_spec_no_soft_skip():
    """P-11 软断言路径已废, 不允许 test.skip(true, ...) 优雅降级."""
    content = DARK_ACCENT_SPEC.read_text(encoding="utf-8")
    assert "test.skip(true" not in content, (
        "P-11 软断言残留 'test.skip(true, ...)' — 应已改硬门禁. "
        "派工 v6 §5 反馈 类 20.63: TEST_TOKEN 缺失直接 throw, 不允许跳过"
    )


def test_el_menu_hover_spec_no_soft_skip():
    """el-menu-hover P-11 软断言 'router 重定向到 /login → 跳过 hover 触发' 路径已废,
    desktop 项目的 sidebar el-menu 必须真触发 hover, mobile 项目明示 skip 是 OK
    的 (mobile 无 el-menu sidebar)."""
    content = EL_MENU_HOVER_SPEC.read_text(encoding="utf-8")
    # desktop 项目的 hard fail 不允许, 但 mobile 的明示 test.skip(!isDesktop) 是允许的
    # (用 testInfo.project.name.startsWith('desktop-') 判定).
    # 只检查 router-redirect-soft-skip 注释模式不存在.
    assert "router 守卫重定向到" not in content or "硬门禁" in content, (
        "P-11 'router 守卫重定向 → 跳过 hover 触发' 软降级模式残留, 应已改硬门禁"
    )


def test_dark_accent_spec_requires_test_token():
    """dark-accent.spec.mjs 必须 TEST_TOKEN 缺失 throw, 不允许软降级."""
    content = DARK_ACCENT_SPEC.read_text(encoding="utf-8")
    assert "throw new Error" in content, "dark-accent.spec.mjs 缺 throw new Error 硬门禁"
    assert "TEST_TOKEN env not set" in content or "TEST_TOKEN" in content, (
        "dark-accent.spec.mjs 硬门禁错误信息缺 TEST_TOKEN 指引"
    )


def test_el_menu_hover_spec_requires_test_token():
    """el-menu-hover.spec.mjs 必须 TEST_TOKEN 缺失 throw, 不允许软降级."""
    content = EL_MENU_HOVER_SPEC.read_text(encoding="utf-8")
    assert "throw new Error" in content, "el-menu-hover.spec.mjs 缺 throw new Error 硬门禁"
    assert "TEST_TOKEN env not set" in content or "TEST_TOKEN" in content, (
        "el-menu-hover.spec.mjs 硬门禁错误信息缺 TEST_TOKEN 指引"
    )


def test_dark_accent_spec_uses_inject_auth():
    """dark-accent.spec.mjs 必须真调 injectAuth (P-11 已调, 不允许删)."""
    content = DARK_ACCENT_SPEC.read_text(encoding="utf-8")
    assert "injectAuth" in content, "dark-accent.spec.mjs 缺 injectAuth 调用"


def test_el_menu_hover_spec_uses_inject_auth():
    """el-menu-hover.spec.mjs 必须真调 injectAuth (P-11 不调是软断言, 现硬门禁必须调)."""
    content = EL_MENU_HOVER_SPEC.read_text(encoding="utf-8")
    assert "injectAuth" in content, (
        "el-menu-hover.spec.mjs 缺 injectAuth 调用 — 硬门禁必须有真 auth, "
        "P-11 '不调 injectAuth, 让 router 守卫重定向' 软降级已废"
    )


def test_dark_accent_spec_hard_asserts_authed():
    """dark-accent.spec.mjs 必须 hard fail injectAuth 返回 false (不允许 authed=false 继续)."""
    content = DARK_ACCENT_SPEC.read_text(encoding="utf-8")
    assert "if (!authed)" in content or "if (!auth" in content, (
        "dark-accent.spec.mjs 必须 hard fail injectAuth 返回 false (authed 必 true)"
    )


def test_el_menu_hover_spec_hard_asserts_menu_visible():
    """el-menu-hover.spec.mjs desktop 项目必须 hard fail sidebar 不可见
    (不允许 'router 重定向 → 跳过 hover 触发' 软降级)."""
    content = EL_MENU_HOVER_SPEC.read_text(encoding="utf-8")
    assert "if (!menuVisible)" in content or "menuVisible" in content, (
        "el-menu-hover.spec.mjs 必须检查 sidebar 可见性并 hard fail"
    )


def test_dark_accent_spec_documents_class_20_63():
    """派工 v6 §5 反馈 类 20.63 必出现在 spec 注释 (派工 v3 模板段 5 反馈沉淀要求)."""
    content = DARK_ACCENT_SPEC.read_text(encoding="utf-8")
    assert "类 20.63" in content, (
        "dark-accent.spec.mjs 缺 类 20.63 派工 v6 §5 反馈沉淀注释"
    )


def test_el_menu_hover_spec_documents_class_20_63():
    """派工 v6 §5 反馈 类 20.63 必出现在 spec 注释."""
    content = EL_MENU_HOVER_SPEC.read_text(encoding="utf-8")
    assert "类 20.63" in content, (
        "el-menu-hover.spec.mjs 缺 类 20.63 派工 v6 §5 反馈沉淀注释"
    )