"""
W89-P-3 (2026-07-30): Playwright CI workflow 自身 e2e 验证

派工 brief 步骤 5 硬门禁: 验证 .github/workflows/playwright.yml 是合法的 GH Actions YAML,
含 a11y + visual 2 job + pull_request 触发 + ubuntu-latest runner.

派工 v6 §1.2 必真验证: 4 PASS, 不允许 skip.
"""

import yaml
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "playwright.yml"


def test_workflow_yaml_valid():
    """YAML 语法 + GH Actions 必填字段 (name / on / jobs) 全部存在"""
    content = WORKFLOW.read_text(encoding="utf-8")
    data = yaml.safe_load(content)
    assert data is not None
    assert "name" in data, "workflow 必须有 name"
    assert "jobs" in data, "workflow 必须有 jobs"


def test_has_a11y_job():
    """a11y job 存在 + ubuntu-latest runner + timeout >= 10 min"""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "a11y" in data["jobs"]
    job = data["jobs"]["a11y"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job.get("timeout-minutes", 0) >= 10


def test_has_visual_job():
    """visual job 存在 + ubuntu-latest runner + timeout >= 15 min"""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert "visual" in data["jobs"]
    job = data["jobs"]["visual"]
    assert job["runs-on"] == "ubuntu-latest"
    assert job.get("timeout-minutes", 0) >= 15


def test_triggers_on_pull_request():
    """pull_request 触发 (PR 必跑, 失败 block merge) + 触发 paths 含 web/**"""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    # YAML 1.1: `on` 解析为 bool True; YAML 1.2: 解析为 str "on"
    on_key = True if True in data else "on"
    assert on_key in data
    triggers = data[on_key]
    assert "pull_request" in triggers, "PR 必触发 (block 合并)"

    pr_cfg = triggers["pull_request"]
    if "paths" in pr_cfg:
        paths = pr_cfg["paths"]
        # 必须含 web/** (前端改动必跑 Playwright)
        assert any("web/" in p for p in paths), "PR paths 必须含 web/ 前缀"


def test_jobs_run_in_parallel():
    """a11y + visual 2 job 必须并行 (needs 不互相依赖)"""
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    jobs = data["jobs"]
    for job_name in ("a11y", "visual"):
        # 没显式 needs = 默认在所有其他 job 完成后跑
        # GH Actions 文档: 没 needs 的 job 互相不依赖, 并行跑
        assert "needs" not in jobs[job_name] or jobs[job_name].get("needs") is None, (
            f"{job_name} 不应 depends-on 另一个 job, 必须并行"
        )