"""
tests/inject_auth_x4/test_fail_loud.py — W92-X-4 injectAuth fail-loud 守卫 (类 20.23 负向对照)

W91-X-18 据实: injectAuth() 缺 TEST_TOKEN 时 return false 静默降级 = 3 次假绿根因 (P-6 / X-29 / X-14).
本任务 (W92-X-4) 改 throw fail-loud, 加 2 个守卫保证假绿永不再现:

1. test_inject_auth_throws_without_token
   - 无 TEST_TOKEN: exit code != 0 (throw 触发守卫), stderr/stdout 含 'TEST_TOKEN'
   - 拒绝静默 PASS (类 20.85)

2. test_inject_auth_passes_with_token
   - 有 TEST_TOKEN: 接受 pass (rc==0) 或 baseline 漂移 (rc==1)
   - 若环境无 token: skip 而不是 fail (符合派工 v6 段 5 反馈 "token 是 a11y baseline 必填, 但守卫自身不该要求 token")

调用方式: cd <repo-root> && SKIP_DB_SETUP=1 pytest tests/inject_auth_x4/ -v
"""
import os
import subprocess
import sys
from pathlib import Path


WEB = Path(__file__).resolve().parents[2] / "web"
PLAYWRIGHT_BIN = WEB / "node_modules" / ".bin" / ("playwright.cmd" if sys.platform == "win32" else "playwright")


def _run_a11y(env: dict) -> subprocess.CompletedProcess:
    """跑 desktop-chrome project 1 case — 验证 injectAuth 失败行为而非全 suite."""
    return subprocess.run(
        [
            str(PLAYWRIGHT_BIN), "test",
            "-c", "tests/visual/a11y/playwright.a11y.config.mjs",
            "tests/visual/a11y/a11y-baseline.spec.mjs",
            "--project=desktop-chrome",
            "--grep=01-chat baseline",
        ],
        cwd=str(WEB),
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
        encoding="utf-8",
        errors="replace",
    )


def test_inject_auth_throws_without_token():
    """无 TEST_TOKEN 时 injectAuth 必 throw (类 20.85 fail-loud)"""
    env = os.environ.copy()
    env.pop("PLAYWRIGHT_TEST_TOKEN", None)
    env.pop("TEST_TOKEN", None)
    env["SKIP_DB_SETUP"] = "1"
    # 强制 utf-8 输出 (Windows 默认 GBK 会让 Playwright 抛 UnicodeDecodeError)
    env["PYTHONIOENCODING"] = "utf-8"
    env["LC_ALL"] = "C.UTF-8"

    result = _run_a11y(env)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = stdout + stderr

    # 期望 exit code != 0 (throw 后守卫 fail-loud)
    assert result.returncode != 0, (
        f"injectAuth 未 throw, 假绿 (rc={result.returncode}):\n"
        f"STDOUT: {stdout[-1000:]}\n"
        f"STDERR: {stderr[-1000:]}"
    )
    # 期望 stdout/stderr 含 'TEST_TOKEN' 错误信息
    assert "TEST_TOKEN" in combined, (
        f"应含 'TEST_TOKEN' 错误信息:\n"
        f"STDOUT: {stdout[-1000:]}\n"
        f"STDERR: {stderr[-1000:]}"
    )


def test_inject_auth_passes_with_token():
    """有 TEST_TOKEN 时 injectAuth 必能跑通 (接受 pass 或 baseline 漂移)"""
    import pytest

    token = os.environ.get("PLAYWRIGHT_TEST_TOKEN") or os.environ.get("TEST_TOKEN")
    if not token:
        pytest.skip("TEST_TOKEN 未设 — 守卫 1 已验证 throw fail-loud")

    env = {**os.environ, "PLAYWRIGHT_TEST_TOKEN": token, "TEST_TOKEN": token, "SKIP_DB_SETUP": "1",
           "PYTHONIOENCODING": "utf-8", "LC_ALL": "C.UTF-8"}
    result = _run_a11y(env)
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    combined = stdout + stderr

    # 接受 pass (rc==0) 或 baseline 漂移 (rc==1) — baseline 漂移是 W88 D-1 已批问题, 不算 fail-loud 守卫失败
    assert result.returncode in (0, 1), (
        f"有 token 时 rc 异常 ({result.returncode}):\n"
        f"STDOUT: {stdout[-500:]}\n"
        f"STDERR: {stderr[-500:]}"
    )
    # 关键: 任何 throw 应该已被 injectAuth 自己 try/catch → 失败也应该以 Playwright 自身的 case fail 形式出现,
    # 而不是来自 injectAuth 改 throw 后残留的 "TEST_TOKEN" 错误 (无 token 才会出)
    if result.returncode != 0:
        # 排除 "TEST_TOKEN" 错误 (那意味着 token 没真生效 — 守卫 1 失败模式)
        assert "injectAuth: TEST_TOKEN" not in combined, (
            f"token 看似传了但 injectAuth 仍报 TEST_TOKEN 错:\n{combined[-1000:]}"
        )
