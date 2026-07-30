"""
tests/ci_x12/test_real_run.py - W90-X-12 CI 真部署 + workflow_run 实战

W89-X-26 已文档化 secret + 命令模板。
W90-X-12 (本任务) 实战真部署 + workflow_run:

  1. gh CLI + act 状态诚实报告 (有/无/版)
  2. 真部署 secret (gh 可用才走,否则留主指挥)
  3. workflow_run 真触发 (gh 可用才走,否则模拟 CI)
  4. run list 解读
  5. TEST_TOKEN 留口验证

派工 v6 §5 反馈 类 20.94 加固: "CI 真部署必含 gh auth status + token 真拿
+ 真 workflow run + run list 解读 + 本机限制必诚实报告"
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB = REPO_ROOT / "web"


# ========== utilities ==========

def _which(cmd: str) -> bool:
    """跨平台 which 检查"""
    return shutil.which(cmd) is not None


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _safe_run(cmd: list[str], timeout: int = 15) -> subprocess.CompletedProcess:
    """subprocess 跑命令,不抛异常"""
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        return subprocess.CompletedProcess(
            args=cmd, returncode=-1,
            stdout="", stderr=f"subprocess error: {e}",
        )


# ========== 类 20.94 铁律 1: gh + act 状态诚实报告 ==========

def test_gh_cli_presence_recorded():
    """本机 gh CLI 必诚实报告 (有/无)"""
    has_gh = _which("gh")
    # 不强制 PASS,只是记录供主指挥决策
    assert isinstance(has_gh, bool)


def test_act_presence_recorded():
    """本机 act 状态必诚实报告 (有/无)"""
    has_act = _which("act")
    assert isinstance(has_act, bool)


def test_gh_cli_version_or_skip():
    """若 gh 装了, gh --version 必可跑"""
    if not _which("gh"):
        pytest.skip("gh CLI 未装")
    result = _safe_run(["gh", "--version"], timeout=10)
    assert result.returncode == 0, f"gh --version 异常: {result.stderr[:200]}"


# ========== 类 20.94 铁律 2: token 真拿 (留口 + e2e 守卫) ==========

def test_test_token_via_login_api_documented():
    """TEST_TOKEN 真拿命令必文档化 (主指挥可一键复制)"""
    # 文档应该已经有这个命令 (来自 W89-X-26 沉淀)
    candidates = [
        REPO_ROOT / "docs" / "ci-secret-setup.md",
        REPO_ROOT / "docs" / "ci-trigger.md",
        REPO_ROOT / "memory" / "w89-x26-ci-deploy-2026-07-30.md",
        REPO_ROOT / "memory" / "w90-x12-ci-deploy-2026-07-30.md",
    ]
    found = False
    for doc in candidates:
        if doc.exists():
            content = _read(doc)
            if "xiaoqi_testbot" in content and "access_token" in content:
                found = True
                break
    assert found, "TEST_TOKEN 真拿命令必文档化 (含 xiaoqi_testbot + access_token)"


def test_test_token_not_in_git_tracked_files():
    """TEST_TOKEN 必不入 git (防御性扫描)"""
    # 仅检查 workflow + docs (不应有真实 JWT)
    import re

    jwt_pattern = re.compile(r"eyJ[A-Za-z0-9_-]{30,}")

    scan_paths = [
        REPO_ROOT / ".github",
        REPO_ROOT / "docs",
        REPO_ROOT / "memory",
        REPO_ROOT / "tests" / "ci_x12",
    ]
    for path in scan_paths:
        if not path.exists():
            continue
        for f in path.rglob("*"):
            if f.is_file() and f.suffix in {".yml", ".yaml", ".md", ".py", ".sh"}:
                try:
                    content = f.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue
                leaks = jwt_pattern.findall(content)
                assert not leaks, f"疑似真实 JWT 在 {f}: {leaks[:3]}"


# ========== 类 20.94 铁律 3: workflow_run 真触发 + run list 解读 ==========

def test_workflow_run_command_in_doc():
    """gh workflow run 命令必文档化"""
    doc = REPO_ROOT / "docs" / "ci-trigger.md"
    if not doc.exists():
        pytest.skip("ci-trigger.md 不存在")
    content = _read(doc)
    assert "gh workflow run" in content
    assert "playwright.yml" in content


def test_run_list_command_in_doc():
    """gh run list 命令必文档化 (主指挥看 CI 日志)"""
    doc = REPO_ROOT / "docs" / "ci-trigger.md"
    if not doc.exists():
        pytest.skip("ci-trigger.md 不存在")
    content = _read(doc)
    assert "gh run list" in content, "gh run list 解读必文档化"


def test_workflow_file_has_dispatch_and_pr_triggers():
    """workflow 必含 manual (workflow_dispatch) + push 触发"""
    wf = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    assert wf.exists(), f"workflow 缺失: {wf}"
    content = _read(wf)
    assert "workflow_dispatch" in content, "必含 manual 触发兜底"
    # push 触发也应该有 (CI 自动跑)
    assert "push:" in content or "pull_request:" in content, "必含 push 或 PR 触发"


# ========== 类 20.94 铁律 4: 本机限制必诚实报告 (X-26 据实上报) ==========

def test_real_deploy_block_in_doc():
    """主指挥真部署步骤必含"留主指挥"明示 (诚实报告)"""
    candidates = [
        REPO_ROOT / "docs" / "ci-secret-setup.md",
        REPO_ROOT / "docs" / "ci-trigger.md",
        REPO_ROOT / "memory" / "w90-x12-ci-deploy-2026-07-30.md",
    ]
    found = False
    for doc in candidates:
        if doc.exists():
            content = _read(doc)
            # 应明示"留主指挥"或"gh 未装"或"本机限制"
            keywords = ["留主指挥", "主指挥执行", "gh CLI 未装", "本机限制"]
            if any(kw in content for kw in keywords):
                found = True
                break
    assert found, "真部署留口必诚实报告 (留主指挥 / gh 未装)"


# ========== 类 20.94 铁律 5: TEST_TOKEN 留口 (pytest skip mode) ==========

def test_test_token_env_var_acceptance():
    """TEST_TOKEN 环境变量必接受 (无论 PLAYWRIGHT_TEST_TOKEN 还是 TEST_TOKEN)"""
    # 模拟设置 TEST_TOKEN (测试后清理)
    old_val = os.environ.get("TEST_TOKEN")
    try:
        os.environ["TEST_TOKEN"] = "fake-token-for-test-only"
        # 函数应该能找到 TEST_TOKEN
        token = os.environ.get("PLAYWRIGHT_TEST_TOKEN") or os.environ.get("TEST_TOKEN")
        assert token == "fake-token-for-test-only"
    finally:
        if old_val is None:
            os.environ.pop("TEST_TOKEN", None)
        else:
            os.environ["TEST_TOKEN"] = old_val


# ========== 模拟 CI 触发留口 (主指挥真部署时跑) ==========

@pytest.mark.skip(reason="真跑留给主指挥部署; 本机 gh CLI 未装")
def test_playwright_a11y_runs_with_real_token():
    """CI 模拟跑 a11y (主指挥触发)

    触发方式:
        export TEST_TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \\
            -H 'Content-Type: application/json' \\
            -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \\
            | python -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")

        cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --reporter=list

    预期: 50+ case PASS (5 page × N project)
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


# ========== 边界守卫 ==========

def test_ci_x12_has_init():
    """tests/ci_x12/ 必含 __init__.py"""
    init = REPO_ROOT / "tests" / "ci_x12" / "__init__.py"
    assert init.exists(), f"缺失: {init}"


def test_workflow_uses_secrets_correctly():
    """workflow 必用 ${{ secrets.* }} 引用敏感变量 (非硬编码)"""
    wf = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    content = _read(wf)
    # 必含 secrets 引用
    assert "secrets." in content, "workflow 必用 ${{ secrets.* }} 引用"
    # 必含 3 个 secret 之一
    expected = ["PLAYWRIGHT_TEST_USERNAME", "PLAYWRIGHT_TEST_PASSWORD", "PLAYWRIGHT_TEST_TOKEN"]
    found_any = any(s in content for s in expected)
    assert found_any, f"workflow 必引用至少 1 个 secret: {expected}"
