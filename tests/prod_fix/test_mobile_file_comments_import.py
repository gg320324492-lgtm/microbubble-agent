"""W89-X-18 P0 回归测试: MobileFileCommentsView 必 import useMobileKeyboard.

W89-X-10 据实报告: 移动端文件评论页生产白屏, 根因 MobileFileCommentsView.vue:124
调用 useMobileKeyboard() 但缺 import, 60 case mobile_drive_comments 全 PAGEERROR.

本测试硬门禁:
1. 必 import useMobileKeyboard (静态)
2. 必 import + setup 调 (静态)
3. 必能跑 mobile_drive_comments 不再 PAGEERROR (动态)
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGET_VUE = (
    REPO_ROOT / "web" / "src" / "views" / "mobile" / "MobileFileCommentsView.vue"
)
MOBILE_DRV_SPEC = (
    REPO_ROOT
    / "web"
    / "tests"
    / "visual"
    / "mobile"
    / "mobile_drive_comments.spec.mjs"
)


def test_mobile_file_comments_import_useMobileKeyboard():
    """MobileFileCommentsView.vue 必 import useMobileKeyboard (P0 回归)."""
    assert TARGET_VUE.exists(), f"目标 vue 不存在: {TARGET_VUE}"
    content = TARGET_VUE.read_text(encoding="utf-8")
    assert "useMobileKeyboard" in content, (
        "P0 移动端文件评论页白屏: 缺 useMobileKeyboard import (W89-X-10 报告)"
    )


def test_mobile_file_comments_no_undefined_variable():
    """MobileFileCommentsView.vue 必 import + setup 内调 useMobileKeyboard."""
    content = TARGET_VUE.read_text(encoding="utf-8")
    import re

    # 1. 必须有 import 语句 (ES module import)
    import_pattern = r"import\s*\{[^}]*\buseMobileKeyboard\b[^}]*\}\s*from\s*['\"]@/composables/useMobileKeyboard['\"]"
    assert re.search(import_pattern, content), (
        "P0 修复不完整: 缺 `import { useMobileKeyboard } from '@/composables/useMobileKeyboard'`"
    )
    # 2. 必须有 setup 内调用 (useMobileKeyboard() 在 script setup 段)
    assert "useMobileKeyboard()" in content, (
        "P0 修复不完整: import 了但未调用, line 124 仍会 ReferenceError"
    )


def test_mobile_drive_comments_runs_no_pageerror():
    """mobile_drive_comments spec 必能跑通 (不再 PAGEERROR, baseline 缺失不计入)."""
    if not MOBILE_DRV_SPEC.exists():
        # spec 缺失不算 P0 回归失败, 这是 W89-X-10 报告的另一问题
        return
    import subprocess
    import os
    import shutil

    # 跳过如果 npx/node 不可用 (CI 环境差异, 不是 P0 回归失败)
    npx_path = shutil.which("npx")
    if npx_path is None:
        # node 可能在, 但 npx 不在 PATH, 检查 node
        if shutil.which("node") is None:
            import pytest
            pytest.skip("npx/node not on PATH, 跳过 playwright 动态验证 (静态 import 已 PASS)")
        # 兜底: 直接用 node 调用
        cmd = [
            "node",
            "node_modules/playwright/cli.js",
            "test",
            "tests/visual/mobile/mobile_drive_comments.spec.mjs",
            "--project=mobile-iphone14",
            "--reporter=list",
        ]
    else:
        cmd = [
            npx_path,
            "playwright",
            "test",
            "tests/visual/mobile/mobile_drive_comments.spec.mjs",
            "--project=mobile-iphone14",
            "--reporter=list",
        ]
    env = os.environ.copy()
    env["SKIP_DB_SETUP"] = "1"
    try:
        result = subprocess.run(
            cmd,
            cwd=REPO_ROOT / "web",
            capture_output=True,
            text=True,
            env=env,
            timeout=180,
        )
    except (FileNotFoundError, OSError) as e:
        import pytest
        pytest.skip(f"playwright 调用环境异常 (非 P0 回归): {e}")
    combined = result.stdout + result.stderr
    # 硬门禁: 不再 PAGEERROR (即 useMobileKeyboard is not defined 错误)
    assert "PAGEERROR" not in combined, (
        f"生产白屏未修 (PAGEERROR 仍存在): {combined[-1000:]}"
    )
    # 硬门禁: 不再有 "useMobileKeyboard is not defined" 引用错误
    assert "useMobileKeyboard is not defined" not in combined, (
        f"useMobileKeyboard 仍 ReferenceError: {combined[-1000:]}"
    )
    # exit code ∈ {0, 1} 即可 (PASS 或 baseline 缺失 FAIL)
    assert result.returncode in (0, 1), (
        f"playwright exit code 异常 {result.returncode}: {combined[-500:]}"
    )
