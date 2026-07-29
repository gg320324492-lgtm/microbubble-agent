"""W87-X-4c: web/ npm audit high + critical 门禁 e2e.

门禁口径 (类 20.35):
- high == 0 且 critical == 0 是**硬门禁**
- moderate / low **不设门禁** — 由 web/package.json overrides 逐步兜底, 留 W88 排期

npm audit 需要访问 registry; 无网络 / npm 缺失时 skip 而非 fail
(派工 v6 §1.2: 门禁必须真验证, 但环境缺失不得伪装成 PASS).
"""

from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = REPO_ROOT / "web"

# npm 在 Windows 上是 npm.cmd, shutil.which 负责解析
NPM = shutil.which("npm") or shutil.which("npm.cmd")


@pytest.fixture(scope="module")
def audit_data() -> dict:
    """跑一次 npm audit --json, 全模块复用 (单次 ~30s, 不重复跑 3 遍)."""
    if NPM is None:
        pytest.skip("npm 不在 PATH, 跳过 npm audit 门禁")
    assert WEB_DIR.is_dir(), f"缺失 web 目录: {WEB_DIR}"
    assert (WEB_DIR / "package-lock.json").is_file(), "缺失 web/package-lock.json"

    result = subprocess.run(
        [NPM, "audit", "--json"],
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",  # Windows 默认 gbk 会在 advisory 文本上 UnicodeDecodeError
        errors="replace",
        timeout=600,
    )
    # 有漏洞时 npm audit exit code = 1, JSON 仍然有效; 只有拿不到 JSON 才算环境问题
    if not (result.stdout or "").strip():
        pytest.skip(f"npm audit 无输出 (可能无网络): {(result.stderr or '')[:200]}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - 环境异常分支
        pytest.skip(f"npm audit 输出非法 JSON: {exc}")


def test_audit_json_valid(audit_data: dict):
    """npm audit JSON 必须含 vulnerabilities 段."""
    assert "vulnerabilities" in audit_data


def test_summary_has_severity_buckets(audit_data: dict):
    """metadata.vulnerabilities 必须含 high / critical 计数字段."""
    summary = audit_data.get("metadata", {}).get("vulnerabilities", {})
    assert "high" in summary, f"audit summary 缺 high 字段: {summary}"
    assert "critical" in summary, f"audit summary 缺 critical 字段: {summary}"


def test_no_critical_vulnerabilities(audit_data: dict):
    """critical 必须为 0 (W87-X-4c: tar 1 个已由 overrides 清零)."""
    summary = audit_data.get("metadata", {}).get("vulnerabilities", {})
    offenders = sorted(
        name
        for name, item in audit_data.get("vulnerabilities", {}).items()
        if item.get("severity") == "critical"
    )
    assert summary.get("critical", 0) == 0, f"critical 漏洞仍存在: {offenders}"


def test_no_high_vulnerabilities(audit_data: dict):
    """high 必须为 0 (W87-X-4c: 23 个已由 overrides + semver 内 update 清零)."""
    summary = audit_data.get("metadata", {}).get("vulnerabilities", {})
    offenders = sorted(
        name
        for name, item in audit_data.get("vulnerabilities", {}).items()
        if item.get("severity") == "high"
    )
    assert summary.get("high", 0) == 0, f"high 漏洞仍存在: {offenders}"


def test_overrides_block_present():
    """web/package.json overrides 段必须保留 — 删掉会让 high/critical 回归."""
    pkg = json.loads((WEB_DIR / "package.json").read_text(encoding="utf-8"))
    overrides = pkg.get("overrides", {})
    # 这 9 个是 W87-X-4c 压 high/critical 的兜底锚点
    for name in (
        "tar",
        "brace-expansion",
        "fast-uri",
        "form-data",
        "immutable",
        "js-yaml",
        "undici",
        "ws",
        "tar-fs",
    ):
        assert name in overrides, f"overrides 缺 {name} (W87-X-4c 兜底锚点)"
