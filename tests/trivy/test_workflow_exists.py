"""W86-C-1: image-scan workflow 存在性 + 关键配置 e2e 断言."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "image-scan.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW.is_file(), f"缺失 workflow: {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_exists():
    assert WORKFLOW.is_file(), ".github/workflows/image-scan.yml 不存在"


def test_uses_trivy_action(workflow_text: str):
    """必须用 aquasecurity/trivy-action."""
    assert "aquasecurity/trivy-action" in workflow_text


def test_triggers(workflow_text: str):
    """pull_request (paths 过滤) + schedule 每周一 5 点."""
    assert "pull_request:" in workflow_text
    assert "schedule:" in workflow_text
    assert "0 5 * * 1" in workflow_text
    for path_glob in ("Dockerfile*", "docker/**", "docker-compose*.yml"):
        assert path_glob in workflow_text, f"paths 缺 {path_glob}"


def test_severity_and_formats(workflow_text: str):
    """severity CRITICAL,HIGH + sarif 上传 + table 写 log."""
    assert "CRITICAL,HIGH" in workflow_text
    assert "sarif" in workflow_text
    assert "'table'" in workflow_text
    assert "upload-sarif" in workflow_text


def test_matrix_covers_all_dockerfiles(workflow_text: str):
    """矩阵覆盖 8 个 Dockerfile."""
    for df in (
        "Dockerfile.db",
        "Dockerfile.funasr",
        "Dockerfile.mcp",
        "Dockerfile.voice-pipeline",
        "Dockerfile.whisper",
        "web/Dockerfile",
        "docker/Dockerfile.commercial",
    ):
        assert df in workflow_text, f"矩阵缺 {df}"


def test_pr_is_advisory_only(workflow_text: str):
    """PR 上仅 advisory (不 block), schedule 才 exit-code 1."""
    assert "continue-on-error" in workflow_text
    assert "github.event_name == 'pull_request'" in workflow_text


def test_scan_scripts_exist():
    """本地扫描脚本 + 安装说明齐备."""
    for rel in (
        "scripts/install-trivy.md",
        "scripts/trivy/scan-images.sh",
        "scripts/trivy/scan-all.sh",
    ):
        assert (REPO_ROOT / rel).is_file(), f"缺失: {rel}"
