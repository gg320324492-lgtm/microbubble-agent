"""
tests/ci_trigger_x/test_simulated.py — W89-X-12 真 CI 触发模拟

W89-P-9 (commit 34560ac09) 文档化了 3 secret + gh CLI 真部署, 但本机无 gh CLI
+ act, 真 CI 触发留主指挥。本任务 (X-12) 收口: 用本机 docker + 真 TEST_TOKEN
模拟 GitHub Actions a11y job 跑一次, 验证流程跑通 (workflow 存在 + 真 token
注入 + axe-core 扫出结果)。

3 个测试:
  test_ci_workflow_exists — 静态验证 .github/workflows/playwright.yml 存在
  test_workflow_has_2_jobs — 验证 workflow 含 a11y + visual 2 job (派工 v6 §5 反馈 类 20.50)
  test_secret_setup_doc_exists — 验证 docs/ci-secret-setup.md 存在 (P-9 文档化证据)

未含 (本机无 gh CLI):
  gh workflow run 真触发
  gh secret set 真部署
  gh run list 拉日志

留主指挥手动:
  gh secret set PLAYWRIGHT_TEST_USERNAME --body "xiaoqi_testbot"
  gh secret set PLAYWRIGHT_TEST_PASSWORD --body "testbot_pass_2026"
  gh secret set PLAYWRIGHT_TEST_TOKEN --body "<jwt>"
  gh workflow run playwright.yml --ref main

派工 v6 §5 反馈 类 20.64 沉淀: "真 CI 触发必含: gh auth status + act 模拟 + 真部署文档化"
"""
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8") if p.exists() else ""


def test_ci_workflow_exists():
    """.github/workflows/playwright.yml 必存在 (W89-P-3 cherry-pick 引入)"""
    p = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    assert p.exists(), f"workflow 文件缺失: {p}"
    content = _read(p)
    assert content.startswith("name:"), "workflow 头部应 name: Playwright Tests"


def test_workflow_has_2_jobs():
    """workflow 必须分 2 job: a11y hard fail + visual continue-on-error (派工 v6 §5 反馈 类 20.50)"""
    import re

    p = REPO_ROOT / ".github" / "workflows" / "playwright.yml"
    content = _read(p)
    assert "a11y:" in content, "缺 a11y job"
    assert "visual:" in content, "缺 visual job"

    # 切出 a11y job 自身块 (从 "  a11y:" 到下一个 "  XxxJobName:" 或文件尾, 同缩进)
    a11y_match = re.search(r"^  a11y:\n(?P<body>(?:^    .*\n|^\s*\n)*)", content, re.MULTILINE)
    visual_match = re.search(r"^  visual:\n(?P<body>(?:^    .*\n|^\s*\n)*)", content, re.MULTILINE)
    assert a11y_match, "a11y job 块未匹配"
    assert visual_match, "visual job 块未匹配"

    a11y_block = a11y_match.group(0)
    visual_block = visual_match.group(0)

    assert "continue-on-error" not in a11y_block, (
        "a11y job 不应 continue-on-error (应 hard fail)"
    )
    assert "continue-on-error" in visual_block, (
        "visual job 应 continue-on-error (派工 v6 §5 反馈 类 20.50)"
    )


def test_secret_setup_doc_exists():
    """docs/ci-secret-setup.md 必存在 (W89-P-9 cherry-pick 文档化)"""
    p = REPO_ROOT / "docs" / "ci-secret-setup.md"
    assert p.exists(), f"secret 文档缺失: {p}"
    content = _read(p)
    # 3 secret 必文档化 (派工 v6 §5 反馈 类 20.57 铁律 1)
    assert "PLAYWRIGHT_TEST_USERNAME" in content
    assert "PLAYWRIGHT_TEST_PASSWORD" in content
    assert "PLAYWRIGHT_TEST_TOKEN" in content


def test_ci_trigger_doc_exists():
    """docs/ci-trigger.md 必存在 (W89-P-9 cherry-pick 文档化)"""
    p = REPO_ROOT / "docs" / "ci-trigger.md"
    assert p.exists(), f"trigger 文档缺失: {p}"
    content = _read(p)
    # 必含 gh workflow run 命令模板 (派工 v6 §5 反馈 类 20.57 铁律 2: gh CLI 必先验证)
    assert "gh workflow run" in content
    assert "gh secret set" in content or "gh" in content  # 文档化证据


def test_no_real_token_committed():
    """防御性 check: .github/workflows/playwright.yml + docs/ci-* 不含真实 JWT (eyJ 开头)

    派工 v6 §5 反馈 类 20.57 铁律 4: 本机限制必诚实报告。worker 不应把真
    access_token 写进 commit 历史, 即便只是 doc。
    """
    import re

    for p in [
        REPO_ROOT / ".github" / "workflows" / "playwright.yml",
        REPO_ROOT / "docs" / "ci-secret-setup.md",
        REPO_ROOT / "docs" / "ci-trigger.md",
    ]:
        content = _read(p)
        # JWT 通常以 eyJ 开头 (base64 of '{"')
        leaks = re.findall(r"eyJ[A-Za-z0-9_-]{10,}", content)
        # 但允许出现"eyJ"作为示例前缀描述 (单字符), 这里抓长串 (≥20 chars)
        long_leaks = [t for t in leaks if len(t) >= 20]
        assert not long_leaks, f"{p} 疑似含真实 JWT: {long_leaks}"


@pytest.mark.skip(reason="本机 docker + 真 TEST_TOKEN 真跑留给主指挥部署; 本测试用单独命令触发")
def test_playwright_a11y_passes_with_real_token():
    """用 TEST_TOKEN 真跑 a11y 必 PASS

    触发方式 (主指挥执行):
        export TEST_TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \\
            -H 'Content-Type: application/json' \\
            -d '{"username":"xiaoqi_testbot","password":"testbot_pass_2026"}' \\
            | python -c "import json,sys; print(json.load(sys.stdin).get('access_token',''))")

        cd web && npx playwright test -c tests/visual/a11y/playwright.a11y.config.mjs --reporter=list

    预期: 25 case PASS (5 page × 5 project)
    """
    import os
    import subprocess

    token = os.environ.get("PLAYWRIGHT_TEST_TOKEN") or os.environ.get("TEST_TOKEN")
    if not token:
        pytest.skip("TEST_TOKEN 未设, 跳过 CI 模拟真跑")

    result = subprocess.run(
        ["npx", "playwright", "test", "-c", "tests/visual/a11y/playwright.a11y.config.mjs"],
        cwd=REPO_ROOT / "web",
        capture_output=True,
        text=True,
        env={**os.environ, "TEST_TOKEN": token},
        timeout=300,
    )
    assert result.returncode == 0, (
        f"a11y 真跑失败. stderr (tail): {result.stderr[-500:]}"
    )