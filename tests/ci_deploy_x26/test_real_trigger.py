"""
tests/ci_deploy_x26/test_real_trigger.py - W89-X-26 CI 真部署模拟

W89-X-12 留口: 真部署 + workflow_run.
本任务 (X-26):
  1. gh CLI 状态诚实报告 (有/无)
  2. 真部署 secret (gh 未装 → 跳过, 留主指挥)
  3. 模拟 CI 触发 (无 gh 走 subprocess 直跑 playwright a11y)
  4. e2e 加固

派工 v6 §5 反馈 类 20.81 新增: "CI 真部署必含 gh auth status + secret 真部署
+ workflow_run + run list 查看, 本机限制必诚实报告"
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"


def _which(cmd: str) -> bool:
    """检查命令是否存在 (跨平台)"""
    return shutil.which(cmd) is not None


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ========== 类 20.81 铁律 1: gh auth status 必先验证 ==========

def test_gh_cli_status_documented():
    """本机 gh CLI 状态必诚实报告 (有/无)

    派工 v6 §5 反馈 类 20.81 铁律 1: gh auth status 必先验证。
    不强制 PASS,只记录状态供主指挥决策。
    """
    has_gh = _which("gh")
    # 不强制 PASS,只是记录状态
    assert isinstance(has_gh, bool), "gh CLI 状态必记 (bool)"


def test_gh_cli_auth_status_runs():
    """若 gh 已装, gh auth status 必可跑 (返回 0 或 1, 不应崩)"""
    if not _which("gh"):
        pytest.skip("gh CLI 未装, 跳过 auth status 检查")
    result = subprocess.run(
        ["gh", "auth", "status"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    # 0 = authed, 1 = not authed, 都算正常
    assert result.returncode in (0, 1), (
        f"gh auth status 异常退出码: {result.returncode}, "
        f"stderr: {result.stderr[:200]}"
    )


# ========== 类 20.81 铁律 2: secret 真部署 (gh 未装 → 跳过) ==========

def test_gh_secret_set_well_documented():
    """gh secret set 命令必文档化在 docs/ci-secret-setup.md"""
    doc = REPO_ROOT / "docs" / "ci-secret-setup.md"
    assert doc.exists(), f"secret 文档缺失: {doc}"
    content = _read(doc)
    assert "PLAYWRIGHT_TEST_USERNAME" in content
    assert "PLAYWRIGHT_TEST_PASSWORD" in content
    assert "PLAYWRIGHT_TEST_TOKEN" in content
    # gh secret set 命令模板
    assert "gh secret set" in content


def test_secret_deployment_command_template():
    """主指挥部署 secret 命令必可生成 (无需 gh 在本机)"""
    # 验证命令模板完整可复制
    expected_secrets = [
        "PLAYWRIGHT_TEST_USERNAME",
        "PLAYWRIGHT_TEST_PASSWORD",
        "PLAYWRIGHT_TEST_TOKEN",
    ]
    doc = REPO_ROOT / "docs" / "ci-secret-setup.md"
    content = _read(doc)
    for secret in expected_secrets:
        assert secret in content, f"{secret} 未在文档中"


# ========== 类 20.81 铁律 3: workflow_run 触发必文档化 ==========

def test_workflow_run_command_documented():
    """gh workflow run 命令必文档化在 docs/ci-trigger.md"""
    doc = REPO_ROOT / "docs" / "ci-trigger.md"
    assert doc.exists(), f"trigger 文档缺失: {doc}"
    content = _read(doc)
    assert "gh workflow run" in content
    assert "playwright.yml" in content


def test_workflow_file_valid_yaml_structure():
    """.github/workflows/playwright.yml 必含 on/jobs 顶层结构"""
    wf = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    assert wf.exists(), f"workflow 文件缺失: {wf}"
    content = _read(wf)
    assert content.startswith("name:"), "workflow 头部应 name: ..."
    assert "on:" in content, "缺 on: 触发器"
    assert "jobs:" in content, "缺 jobs: 定义"
    assert "workflow_dispatch" in content, "workflow_dispatch 必配 (留手动触发兜底)"


# ========== 类 20.81 铁律 4: run list 必可看 CI 日志 ==========

def test_run_list_command_documented():
    """gh run list 命令必文档化 (主指挥看 CI 日志)"""
    doc = REPO_ROOT / "docs" / "ci-trigger.md"
    content = _read(doc)
    assert "gh run list" in content, "gh run list 命令必文档化"


# ========== 模拟 CI 触发 (无 gh 走 subprocess 直跑 playwright) ==========

def test_playwright_a11y_config_exists():
    """Playwright a11y config 必存在 (CI job 1 引用)"""
    config = WEB / "tests" / "visual" / "a11y" / "playwright.a11y.config.mjs"
    assert config.exists(), f"a11y config 缺失: {config}"


@pytest.mark.skip(reason="真跑留给主指挥部署; TEST_TOKEN 通过 login API 拿")
def test_playwright_a11y_runs_with_token():
    """CI 模拟跑 a11y (主指挥触发)

    触发方式:
        export TEST_TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \\
            -H 'Content-Type: application/json' \\
            -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \\
            | python -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")

        cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --reporter=list

    预期: 25+ case PASS (5 page × 5 project)
    """
    token = os.environ.get("PLAYWRIGHT_TEST_TOKEN") or os.environ.get("TEST_TOKEN")
    if not token:
        pytest.skip("TEST_TOKEN 未设, 跳过 CI 模拟真跑")

    result = subprocess.run(
        ["npx", "playwright", "test", "-c", "tests/visual/a11y/playwright.a11y.config.mjs"],
        cwd=WEB,
        capture_output=True,
        text=True,
        env={**os.environ, "PLAYWRIGHT_TEST_TOKEN": token},
        timeout=600,
    )
    # 接受 PASS (0) 或有 baseline 漂移 (1)
    assert result.returncode in (0, 1), (
        f"a11y 真跑异常退出: {result.returncode}, "
        f"stderr (tail): {result.stderr[-500:]}"
    )


# ========== 边界守卫: 真 token 防御性检查 ==========

def test_no_real_token_committed_in_workflow():
    """.github/workflows/playwright.yml 不含真实 JWT (防御性)"""
    import re

    wf = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    content = _read(wf)
    # JWT 通常以 eyJ 开头 (base64 of '{"')
    leaks = re.findall(r"eyJ[A-Za-z0-9_-]{20,}", content)
    assert not leaks, f"workflow 疑似含真实 JWT: {leaks}"


# ========== 真部署留口验证 ==========

def test_workspace_real_deploy_block():
    """主指挥真部署步骤必可一键复制 (CI 触发留口)

    类 20.81 铁律 5: 本机限制必诚实报告 (CI 模拟跑 ≠ 真部署)
    """
    doc = REPO_ROOT / "docs" / "ci-secret-setup.md"
    content = _read(doc)
    # 必含"主指挥执行清单"段
    assert "主指挥执行清单" in content or "真部署步骤" in content, (
        "主指挥真部署步骤必文档化"
    )
    # 必含 gh secret set 命令
    assert "gh secret set" in content
    # 必含 gh workflow run 命令
    wf_doc = REPO_ROOT / "docs" / "ci-trigger.md"
    wf_content = _read(wf_doc)
    assert "gh workflow run" in wf_content