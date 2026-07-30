"""W89-X-21: Vitest / Playwright 测试收集边界回归门禁。"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"
VITEST_CONFIG = WEB_DIR / "vitest.config.js"
NPX = shutil.which("npx") or shutil.which("npx.cmd")
PLAYWRIGHT_SPECS = (
    "mobile_push_notification.spec.js",
    "mobile_swipe_gesture.spec.js",
    "mobile_voice_input.spec.js",
)


def _vitest_list(*filters: str, pass_with_no_tests: bool = False) -> str:
    """用 Vitest 的只收集模式真跑指定文件，避免执行测试正文。"""
    if NPX is None:
        pytest.skip("npx 不在 PATH，无法执行 Vitest 收集门禁")
    if not (WEB_DIR / "node_modules").is_dir():
        pytest.skip("web/node_modules 不存在，请先运行 npm ci")

    env = os.environ.copy()
    env["SKIP_DB_SETUP"] = "1"
    command = [NPX, "vitest", "list", *filters]
    if pass_with_no_tests:
        command.append("--passWithNoTests")
    result = subprocess.run(
        command,
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=120,
    )
    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, f"vitest list 失败 (rc={result.returncode}):\n{output[-1000:]}"
    return output


@pytest.fixture(scope="module")
def playwright_target_collection() -> str:
    return _vitest_list(
        *(f"tests/e2e/{name}" for name in PLAYWRIGHT_SPECS),
        pass_with_no_tests=True,
    )


@pytest.fixture(scope="module")
def vitest_control_collection() -> str:
    return _vitest_list("tests/e2e/mobile_drive_comments.spec.js")


def test_vitest_config_excludes_playwright_directories():
    """配置必须显式隔离 e2e 与 visual Playwright spec。"""
    content = VITEST_CONFIG.read_text(encoding="utf-8")
    assert "**/tests/e2e/{mobile_push_notification,mobile_swipe_gesture,mobile_voice_input}.spec.{js,ts}" in content
    assert "**/tests/visual/{mobile,desktop,e2e,a11y,local-only,pwa}/**/*.spec.{js,ts,mjs}" in content


def test_playwright_specs_are_absent_from_vitest_collection(playwright_target_collection: str):
    """3 个已知 Playwright spec 都不能进入 Vitest 收集结果。"""
    leaked = [name for name in PLAYWRIGHT_SPECS if name in playwright_target_collection]
    assert not leaked, f"Playwright spec 仍被 Vitest 收集: {leaked}"


def test_vitest_still_collects_e2e_directory_unit_spec(vitest_control_collection: str):
    """负向对照：tests/e2e 中的 Vitest spec 不能被一并排除。"""
    assert "tests/e2e/mobile_drive_comments.spec.js" in vitest_control_collection
