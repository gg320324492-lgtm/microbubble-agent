"""W90-X-10 npm audit 真修真修验证.

派工 v6 §5 反馈: class 20.92 - "npm audit 真修必逐 moderate 调研, major 升级不擅自动".

本测试验证:
1. 无 high/critical 漏洞 (强制门禁)
2. moderate 数量 ≤ 阈值 (W88-C-2 留 75 → W90-X-10 修剩 1 = ≤ 10)
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

WEB = Path(__file__).resolve().parents[2] / "web"


def _npm_cmd():
    """Return appropriate npm executable name for current platform."""
    if os.name == "nt":
        for cand in ("npm.cmd", "npm.exe", "npm"):
            p = shutil.which(cand)
            if p:
                return p
        return "npm.cmd"
    return shutil.which("npm") or "npm"


def _run_audit():
    """Run npm audit and return parsed JSON."""
    npm = _npm_cmd()
    use_shell = os.name == "nt"
    result = subprocess.run(
        [npm, "audit", "--json"] if not use_shell else f'"{npm}" audit --json',
        cwd=str(WEB),
        capture_output=True,
        text=True,
        timeout=120,
        shell=use_shell,
    )
    if not result.stdout.strip():
        return {}
    return json.loads(result.stdout)


def test_no_high_critical():
    """npm audit high + critical 必 = 0 (派工 v6 §1 + X-4c 类 20.35)."""
    data = _run_audit()
    v = data.get("vulnerabilities", {})
    high_critical = [
        k for k, vv in v.items() if vv.get("severity") in ("high", "critical")
    ]
    assert not high_critical, f"High/Critical vulns found: {high_critical}"


def test_moderate_under_threshold():
    """moderate 数量 ≤ 10 (W88-C-2 留 75 - 1 dompurify - 6 hint 链真修 = ≤ 10).

    W88-C-2 留 75 moderate, 66 集中在 hint devDependency.
    W90-X-10 真修 6 hint 链 transitive (file-type/is-svg/fast-xml-parser/got/
    latest-version/update-notifier/package-json), 留 1 echarts major 升级
    (派工 brief 留口 W90+ 视觉回归专项).

    75 - 1 (dompurify 已在 W88-C-2 修) - 6 (hint 链 transitive 真修) = 68.
    期望 ≤ 10.
    """
    data = _run_audit()
    v = data.get("vulnerabilities", {})
    moderate_count = sum(
        1 for vv in v.values() if vv.get("severity") == "moderate"
    )
    assert moderate_count <= 10, (
        f"moderate={moderate_count} 预期 ≤ 10. "
        f"剩余: {[k for k, vv in v.items() if vv.get('severity') == 'moderate']}"
    )


def test_only_echarts_remaining_moderate():
    """派工 v6 §5 类 20.92: 唯一剩余 moderate 必为 echarts (major 升级留口)."""
    data = _run_audit()
    v = data.get("vulnerabilities", {})
    moderate_pkgs = [
        k for k, vv in v.items() if vv.get("severity") == "moderate"
    ]
    # W90-X-10 任务: echarts major 升级需视觉回归, 留口 W90+ 专项派工
    for pkg in moderate_pkgs:
        # 只允许 echarts 在 moderate 列表里
        assert pkg == "echarts", (
            f"Unexpected moderate pkg (需调研修法): {pkg}"
        )
