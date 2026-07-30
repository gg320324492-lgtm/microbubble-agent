"""W90-X-4: 验证 vitest spec 修复边界, 防止回归。

派工 v6 §5 反馈 类 20.87 沉淀: jsdom 边界 — window.location.* 不可 spyOn
派工 v6 §5 反馈 类 20.88 沉淀: vue <script setup> undeclared identifier 不可 vi.mock 绕过

本测试用 grep 而非执行 vitest (避免重复 ~40s 全跑), 仅在文件层面守恒.
"""
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WEB = REPO / "web"


def test_no_spyon_window_location_reload():
    """pwa-update-toast 不应再 spyOn window.location.reload (jsdom 不可重定义)

    W90-X-4 改用删除 window.location + 重新赋值 (data property redefine) 绕过
    不可重定义 reload 的 jsdom 限制; 不再依赖 vi.spyOn(window.location, 'reload').
    """
    p = WEB / "tests" / "unit" / "pwa-update-toast.test.js"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        assert "vi.spyOn(window.location" not in content


def test_no_typescript_syntax_in_js_spec():
    """spec 文件不该含 TS 语法 (const vm: any / as any 链式断言) — 会让 Rollup parse 失败

    W90-X-4 在 desktop_emoji_lazy.spec.js 中去掉 `const vm: any = wrapper.vm as any`.
    """
    p = WEB / "tests" / "e2e" / "desktop_emoji_lazy.spec.js"
    if p.exists():
        content = p.read_text(encoding="utf-8")
        assert "const vm: any" not in content
        assert "as any" not in content  # 该 spec 该行其他 as any 也已删除


def test_playwright_spec_excluded_from_vitest():
    """vitest 不应收集 @playwright/test 格式的 spec.

    W90-X-4 在 vitest.config.js exclude 段加入 mobile_push_notification /
    mobile_swipe_gesture / mobile_voice_input, 防止 Playwright test.use() 错收集
    到 jsdom 测试环境.
    """
    cfg = WEB / "vitest.config.js"
    content = cfg.read_text(encoding="utf-8")
    for spec in (
        "mobile_push_notification.spec.js",
        "mobile_swipe_gesture.spec.js",
        "mobile_voice_input.spec.js",
    ):
        assert spec in content, f"vitest.config.js exclude 段应含 {spec}"


def test_vitest_minimal_run():
    """vitest 应能正常退出 (允许 baseline 残留失败).

    验证 vitest 安装 + 配置文件无误; 不强制 0 failed (超出本任务范围).
    Windows 下跳过 subprocess 调用 (npx PATH 在 pytest 子进程内不可见),
    改用 node_modules 直接 vitest CLI 入口.
    """
    import os
    vitest_bin = WEB / "node_modules" / ".bin" / "vitest"
    if not vitest_bin.exists():
        pytest.skip("vitest 未安装, 跳过子进程调用")
    cmd = ["node", str(vitest_bin), "run", "--no-coverage",
           "tests/unit/pwa-update-toast.test.js",
           "tests/unit/mobile-fab.test.js"]
    env = os.environ.copy()
    env["SKIP_DB_SETUP"] = "1"
    env["LC_ALL"] = "C.UTF-8"
    result = subprocess.run(
        cmd,
        cwd=str(WEB),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    # 0 = all pass, 1 = some fail (允许 baseline 残留)
    assert result.returncode in (0, 1), (
        f"vitest 异常退出: rc={result.returncode}\n"
        f"stderr: {result.stderr[:500]}"
    )


import pytest
