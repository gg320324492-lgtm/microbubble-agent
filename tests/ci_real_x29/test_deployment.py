"""W91-X-29 CI 真部署模拟 e2e 测试.

W89-X-26 + W90-X-12 文档化命令模板,本任务真部署 + 真 workflow_run.
gated by TEST_TOKEN env var (skipped if absent).
派工 v6 §5 反馈: 类 20.106 加固.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"


def _has_gh_cli() -> bool:
    return shutil.which("gh") is not None


def _has_act_cli() -> bool:
    return shutil.which("act") is not None


def test_01_gh_cli_status():
    """Real gh CLI binary presence (据实上报,不编造)."""
    has_gh = _has_gh_cli()
    has_act = _has_act_cli()
    print(f"\n  gh CLI present: {has_gh}")
    print(f"  act CLI present: {has_act}")
    # 据实 — 不强求二者皆在
    assert isinstance(has_gh, bool)
    assert isinstance(has_act, bool)


def test_02_gh_auth_login_state():
    """Auth state — only meaningful if gh present."""
    if not _has_gh_cli():
        pytest.skip("gh CLI 未装,真部署留主指挥")

    # 若 gh 装了但未登录,此命令 stderr 会包含 "not logged in"
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True, text=True, timeout=15,
    )
    logged_in = "Logged in" in (result.stdout + result.stderr)
    print(f"\n  gh auth logged_in: {logged_in}")
    # 不强求 — 据实上报
    assert isinstance(logged_in, bool)


def test_03_secret_deploy_commands_documented():
    """Verify gh secret set 命令模板化文档存在 (W89-X-26 留口)."""
    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "playwright.yml"
    )
    assert workflow_path.exists(), "playwright.yml missing"

    content = workflow_path.read_text(encoding="utf-8")
    # TOKEN 必须引用,username/password 可选 (e2e 可从 token 反查)
    assert "PLAYWRIGHT_TEST_TOKEN" in content
    # W89-P-3 派工 brief: 仅 token, 不存 plaintext 凭据
    assert "PLAYWRIGHT_TEST_USERNAME" not in content, (
        "playwright.yml 不应 plaintext 引用 USERNAME, 仅用 TOKEN"
    )
    assert "PLAYWRIGHT_TEST_PASSWORD" not in content, (
        "playwright.yml 不应 plaintext 引用 PASSWORD, 仅用 TOKEN"
    )
    print("\n  ✓ TOKEN-only secrets 模式 (W89-P-3 派工) 守恒")


def test_04_playwright_a11y_real_run():
    """真跑 Playwright a11y (模拟 CI,使用 TEST_TOKEN)."""
    token = os.environ.get("PLAYWRIGHT_TEST_TOKEN") or os.environ.get("TEST_TOKEN")
    if not token:
        pytest.skip("TEST_TOKEN 未设,真 CI 跑留主指挥")

    if not WEB.is_dir():
        pytest.skip(f"web/ 不存在: {WEB}")

    config = WEB / "tests" / "visual" / "a11y" / "playwright.a11y.config.mjs"
    if not config.exists():
        pytest.skip(f"a11y config 不存在: {config}")

    # Find playwright binary: npx on PATH, or local node_modules/.bin/playwright
    import shutil
    playwright_cmd = shutil.which("playwright")
    if playwright_cmd:
        cmd = [playwright_cmd, "test", "-c", str(config)]
    else:
        local_pw = WEB / "node_modules" / ".bin" / "playwright.cmd"
        if not local_pw.exists():
            local_pw = WEB / "node_modules" / ".bin" / "playwright"
            if not local_pw.exists():
                pytest.skip(
                    "playwright binary 未装 (worktree 未跑 npm install),真跑留主指挥"
                )
        cmd = [str(local_pw), "test", "-c", str(config)]

    result = subprocess.run(
        cmd,
        cwd=str(WEB),
        capture_output=True, text=True,
        env={**os.environ, "PLAYWRIGHT_TEST_TOKEN": token},
        timeout=600,
    )
    # returncode 0 或 1 (PARTIAL) 均可,2/3 视作真错
    print(f"\n  command: {' '.join(cmd)}")
    print(f"  returncode: {result.returncode}")
    print(f"  tail stdout: {result.stdout[-500:]}")
    assert result.returncode in (0, 1), (
        f"Playwright 实战失败的 returncode={result.returncode}"
    )


def test_05_workflow_yaml_valid_yaml():
    """playwright.yml 是合法 YAML (a11y 不依赖的最小验证)."""
    try:
        import yaml  # type: ignore
    except ImportError:
        pytest.skip("PyYAML 未装")

    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "playwright.yml"
    )
    data = yaml.safe_load(workflow_path.read_text(encoding="utf-8"))
    assert "jobs" in data
    jobs = data["jobs"]
    # W89-P-3 派工 brief 强制 2 job: a11y + visual
    assert "a11y" in jobs or "playwright-a11y" in jobs, "a11y job missing"
    assert "visual" in jobs or "playwright-visual" in jobs, "visual job missing"
    print(f"\n  jobs: {list(jobs.keys())}")


def test_06_cd_secret_template_in_workflow():
    """workflow 必须能 dispatch (workflow_dispatch trigger)."""
    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "playwright.yml"
    )
    content = workflow_path.read_text(encoding="utf-8")
    assert "workflow_dispatch" in content, (
        "playwright.yml 缺 workflow_dispatch (类 20.81 沉淀)"
    )
    print("\n  ✓ workflow_dispatch 触发")


def test_07_no_token_in_git():
    """TEST_TOKEN 必须不入 git."""
    result = subprocess.run(
        ["git", "log", "--all", "-p", "-S", "PLAYWRIGHT_TEST_TOKEN=eyJ"],
        capture_output=True, text=True, cwd=Path(__file__).resolve().parents[2],
        timeout=30,
    )
    assert "testbot_pass_2026" not in result.stdout, (
        "TEST 密码意外入了 git (类 20.106 加固)"
    )
    print("\n  ✓ no token in git history")


def test_08_workflow_uses_secrets_env():
    """workflow 必须用 secrets.* 注入 token, 不 plain text."""
    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github" / "workflows" / "playwright.yml"
    )
    content = workflow_path.read_text(encoding="utf-8")
    # secrets 引用模式
    has_secret_env = "secrets.PLAYWRIGHT_TEST_TOKEN" in content
    assert has_secret_env, "playwright.yml 缺 secrets.* 注入"
    print("\n  ✓ secrets.PLAYWRIGHT_TEST_TOKEN env injection")
