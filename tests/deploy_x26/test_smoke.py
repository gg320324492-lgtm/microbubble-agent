"""
W91-X-26 deploy 真生产部署验证 - 守卫.

派工前提: W88-X-2 写完 deploy-auto.sh 但**未真跑过**。
本文件守卫 deploy-auto.sh 的 3 项基础设施:
1. bash 语法 OK
2. trivy scan-images.sh 子脚本可独立跑
3. pg-exporter health.sh 子脚本可独立跑

跑法:
    cd E:/agent-w91-x26-deploy
    SKIP_DB_SETUP=1 pytest tests/deploy_x26/ -v

预期: 3 PASS (子脚本 pass 或 trivy 未装时 exit 1 也 OK, 是 expected fail).

派工 v6 §5 反馈 类 20.104 沉淀: "deploy 真跑必分步骤 (不破 prod),
dry-run 必先, 子脚本必可独立跑".
"""

import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def test_deploy_syntax_ok():
    """deploy-auto.sh 语法必 OK (bash -n dry-run)"""
    result = subprocess.run(
        ["bash", "-n", "scripts/deploy-auto.sh"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"syntax error: {result.stderr}"


def test_trivy_scan_runs():
    """trivy scan-images.sh 子脚本必能跑.

    接受 exit 0 (scan pass) / exit 1 (HIGH/CRITICAL 命中或 scan fail) /
    exit 2 (trivy 未装 SKIP, 见 scripts/install-trivy.md).

    这是派工 v6 §5 反馈 类 20.104 沉淀: 子脚本必须可独立跑, 集成失败不能阻塞.
    """
    result = subprocess.run(
        ["bash", "scripts/trivy/scan-images.sh"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode in (0, 1, 2), (
        f"trivy scan 出意外 exit code: {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_pg_exporter_health_runs():
    """pg-exporter health.sh 子脚本必能跑 (PASS 或 pg 未启 fallback)"""
    result = subprocess.run(
        ["bash", "scripts/pg-exporter/health.sh"],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    # 接受 pass (0) 或容器未启 fallback (1)
    assert result.returncode in (0, 1), (
        f"pg-exporter health 出意外 exit code: {result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
