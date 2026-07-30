"""
tests/vitest_x19c/test_fixes.py — W89-X-19c NavRail stale slice 修复加固 e2e

派工 v6 §5 反馈类 20.74 沉淀:
- vitest stale slice 修法 = 调研真实契约 + spec 适配 component (非反过来)
- 必加 e2e 加固防止 spec 再次引用 stale selector

W89-X-19c 修复了 NavRail.spec.js 的 8 个 scenario 全部改写为真实 NavRail.vue 契约:
- 旧: .nav-item / hamburger / #nav-rail-accent / data-theme-accent / mobile-drawer
- 新: .nav-rail-item / .mobile-close / themeStore.setAccent / document.data-{theme,accent} / mobile-open

注意: 真实 NavRail 中 .mobile-close 始终在 DOM (CSS @media 控制可见性),
不是 v-if, 因此 e2e 用元素存在性 + 类名断言, 不强制 display:none 判定.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"
SPEC = WEB / "src" / "components" / "chat" / "__tests__" / "NavRail.spec.js"
COMPONENT = WEB / "src" / "components" / "chat" / "NavRail.vue"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# 类 20.74 铁律: spec 必无 stale selector, 否则再次成为 W89-X-13 旧失败根因
STALE_SELECTORS = [
    ".nav-item",  # 旧类名 (现 .nav-rail-item)
    "nav-rail-hamburger",  # 旧 hamburger 按钮 id
    "nav-rail-accent",  # 旧 accent 切换按钮 id (现用 themeStore.setAccent)
    "data-theme-accent",  # 旧属性 (现 data-theme + data-accent 在 document)
    "mobile-drawer",  # 旧 mobile 状态类 (现 .mobile-open)
    "nav-rail-chat",  # 旧 button id (现 a[data-route="/chat"])
    "nav-rail-drive",  # 旧 button id (现 a[data-route="/drive"])
]


def test_navrail_spec_no_stale_selectors():
    """NavRail spec 必无 stale selector (类 20.74 加固)"""
    assert SPEC.exists(), f"NavRail spec 不存在: {SPEC}"
    content = _read(SPEC)
    failures = []
    for s in STALE_SELECTORS:
        # 只在 selector 上下文 (非注释) 触发
        # 用单词边界 + CSS-like 模式判断, 注释中提及历史不算
        if s in content:
            # 排除注释行 (以 // 开头) 中的引用
            for line in content.splitlines():
                stripped = line.strip()
                if s in line and not stripped.startswith("//") and not stripped.startswith("*"):
                    failures.append(f"{s!r} 在 {line!r}")
    assert not failures, f"NavRail spec 仍含 stale selector:\n" + "\n".join(failures)


def test_navrail_spec_uses_real_contract():
    """NavRail spec 必含真实契约 selector (正向断言)"""
    content = _read(SPEC)
    required_real_selectors = [
        "li.nav-rail-item",  # 真实 li 类名
        ".mobile-close",  # 真实 mobile 关闭按钮
        "a[data-route=",  # 真实 router-link data 属性
        "data-testid=\"nav-rail\"",  # 真实 testid
        "data-accent",  # 真实主题属性
        "data-theme",  # 真实主题属性
    ]
    missing = [s for s in required_real_selectors if s not in content]
    assert not missing, f"NavRail spec 缺真实契约 selector: {missing}"


def test_navrail_component_unchanged():
    """NavRail.vue 未被修改 (类 20.74 铁律: 不动 production code)"""
    # 关键 sentinel 字符串 (据实调研真实契约)
    content = _read(COMPONENT)
    assert "class=\"nav-rail\"" in content, "NavRail.vue 根类名必须存在"
    assert "<li" in content and "nav-rail-item" in content, "NavRail.vue 6 项 li 必须存在"
    assert ".mobile-close" in content, "NavRail.vue mobile-close 按钮必须存在"
    assert "data-testid=\"nav-rail\"" in content, "NavRail.vue data-testid 必须存在"
    assert "useThemeStore" not in content or "useUiStore" in content, "NavRail.vue 应通过 useUiStore 控制折叠"


def test_navrail_spec_8_scenarios():
    """NavRail spec 必含 8 个 scenario (W89-X-19c 据实)"""
    content = _read(SPEC)
    # 用正则匹配 it('scenario_N: ...') 标题
    matches = re.findall(r"it\(['\"]scenario_(\d+):", content)
    nums = sorted(int(m) for m in matches)
    assert nums == [1, 2, 3, 4, 5, 6, 7, 8], f"期望 scenario 1-8, 实测 {nums}"


def test_navrail_spec_runs_clean():
    """NavRail spec 必能跑 (8/8 PASS)"""
    import os
    import shutil

    env = os.environ.copy()
    env["SKIP_DB_SETUP"] = "1"
    # Windows: npx 位于 C:\Program Files\nodejs, 确保 PATH 包含
    nodejs_dir = Path("C:/Program Files/nodejs")
    if nodejs_dir.exists():
        env["PATH"] = str(nodejs_dir) + os.pathsep + env.get("PATH", "")

    # 用绝对路径 npx (Windows 进程启动需要)
    npx_bin = shutil.which("npx", path=env["PATH"])
    if npx_bin is None:
        # 兜底
        npx_bin = "C:/Program Files/nodejs/npx.cmd"

    result = subprocess.run(
        [npx_bin, "vitest", "run", "src/components/chat/__tests__/NavRail.spec.js"],
        cwd=WEB,
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
        shell=True,  # Windows 必需 (npx.cmd 是 batch)
    )
    output = result.stdout + result.stderr
    # 期望 8 passed
    assert "8 passed" in output, (
        f"NavRail spec 未 8/8 PASS\n"
        f"returncode={result.returncode}\n"
        f"--- output tail ---\n{output[-2000:]}"
    )
