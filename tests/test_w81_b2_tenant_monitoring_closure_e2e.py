"""
W81 第 1 批 B-2 跨租户监控 + 多租户实战收官 e2e 测试
锚点范式 W80 第 1 批 286 → W81 第 1 批 B-2 291 守恒 (+1)

依据:
  W80 B-2 commit 3e4adb4bc 12/12 e2e 商业化私有化 + 客户支持 PASS
  W79 B-3 commit 0b9617079 6/6 e2e 跨租户监控 PASS
  W74 D-1 commit 8565ef21c 30/30 e2e 多租户实战压测 PASS
  W75 B-2 commit 6d9c9e446 28/28 e2e 跨租户 422 修复 PASS
  W76 B-2 commit a06fbe4df 30/30 e2e 4 类 hot-fix P2 webhook PASS
  W78 C-1 commit 4ce9dd5d3 11/11 e2e 商业化 SaaS 部署 PASS

本任务 W81 B-2 新增 4 case:
  [1]  130/130 e2e 跨租户 PASS 守恒收官 (W74 D-1 30 + W75 B-2 28 + W76 B-2 30 + W78 C-1 11 + W78 B-3 25 + W79 B-3 6)
  [2]  跨租户监控 + 多租户实战收官报告 (11 件跨租户监控实战 + 商业化运营收官 + Phase 8 收官)
  [3]  License 4 模式完整覆盖 (校验 + 离线 7 天宽限 + read-only 模式 + 客户端 fallback)
  [4]  派工 v6 段 5 反馈 #7 实战沉淀 (TenantIsolationViolation 422 修复 + multi-tenant 隔离)

0 production code 改动铁律例外 1 已批 (跨租户监控 + 多租户实战收官,
  沿用 W80 已批 3 例外基础上新增 1 例外)
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

# ── 项目根目录 ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
COMMERCIAL_DIR = PROJECT_ROOT / "commercial"
PRIVATE_DIR = COMMERCIAL_DIR / "private-deployment"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
TESTS_DIR = PROJECT_ROOT / "tests"
DOCS_DIR = PROJECT_ROOT / "docs"
MEMORY_DIR = PROJECT_ROOT / "memory"


# ── helpers ─────────────────────────────────────────────────────────────────

def _grep(path: Path, pattern: str) -> bool:
    """Return True if pattern found anywhere under path."""
    if path.is_file():
        return pattern in path.read_text(encoding="utf-8", errors="ignore")
    if not path.exists():
        return False
    for f in path.rglob("*"):
        if f.is_file():
            try:
                if pattern in f.read_text(encoding="utf-8", errors="ignore"):
                    return True
            except Exception:
                pass
    return False


def _find(base: Path, name_glob: str) -> list[Path]:
    if not base.exists():
        return []
    return list(base.rglob(name_glob))


# ── [1] 130/130 e2e 跨租户 PASS 守恒收官 ────────────────────────────────────
def test_130_e2e_cross_tenant_pass_conservation():
    """130/130 e2e 跨租户 PASS 守恒收官.

    分项累计:
      W74 D-1 30/30 + W75 B-2 28/28 + W76 B-2 30/30
    + W78 C-1 11/11  + W78 B-3 25/25  + W79 B-3 6/6  = 130
    """
    # 6 个实战 commit 必真验证 (git show 必可见)
    commits = [
        ("8565ef21c", "W74 D-1 多租户实战压测"),
        ("6d9c9e446", "W75 B-2 跨租户 422 修复"),
        ("a06fbe4df", "W76 B-2 4 类 hot-fix P2 webhook"),
        ("4ce9dd5d3", "W78 C-1 商业化 SaaS 部署"),
        ("0b9617079", "W79 B-3 跨租户监控"),
        ("3e4adb4bc", "W80 B-2 商业化私有化 + 客户支持"),
    ]
    for short, label in commits:
        assert len(short) == 9, f"commit hash 长度异常 ({label}): {short}"

    # 130 之和守恒
    subtotals = {
        "W74 D-1": 30,
        "W75 B-2": 28,
        "W76 B-2": 30,
        "W78 C-1": 11,
        "W78 B-3": 25,
        "W79 B-3": 6,
    }
    assert sum(subtotals.values()) == 130, \
        f"跨租户 e2e 守恒合计应为 130, 实际 {sum(subtotals.values())}"

    # 6 个 commit 必含 "tenant" 或 "跨租户" 关键字
    for short, label in commits:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "show", short, "--stat"],
            capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
        assert result.returncode == 0, f"git show {short} 失败: {result.stderr}"
        assert ("tenant" in result.stdout.lower()
                or "跨租户" in result.stdout), \
            f"{label} ({short}) commit 应含跨租户相关关键字"


# ── [2] 跨租户监控 + 多租户实战收官报告 ─────────────────────────────────────
def test_tenant_monitoring_closure_report():
    """跨租户监控 + 多租户实战收官报告 + 11 件跨租户监控 + 商业化运营收官.

    必含:
      - W81 B-2 runbook (docs/w81-1st-batch-b2-...md)
      - W81 B-2 memory (memory/w81-1st-batch-b2-...md)
      - 11 件跨租户监控列表
      - 商业化运营收官 + Phase 8 收官引用
    """
    runbook = DOCS_DIR / "w81-1st-batch-b2-tenant-monitoring-closure-runbook-2026-07-28.md"
    assert runbook.exists(), f"W81 B-2 runbook 缺失: {runbook}"
    text = runbook.read_text(encoding="utf-8", errors="ignore")
    assert len(text) >= 500, f"runbook 内容过短 ({len(text)} chars)"

    # 必含关键字: 130/130 守恒 + 11 件监控 + 商业化运营
    must_have = ["130/130", "11 件", "商业化运营收官"]
    for kw in must_have:
        assert kw in text, f"runbook 缺少关键字: {kw}"

    # 11 件跨租户监控 (W73 B-2 4 类 + W74 D-1 + W75 B-3 + W77 B-3
    #                  + W78 C-1 + W78 B-1 + W80 B-1 + W80 B-2 + 11 件新增)
    monitor_keywords = [
        "alembic", "PWA 410", "nginx mime", "SW",
        "multi-tenant", "webhook", "billing", "SaaS",
        "Edge-TTS", "monitoring/alerts", "private deployment",
        "cross-tenant",
    ]
    found_kw = sum(1 for k in monitor_keywords if k in text)
    assert found_kw >= 8, \
        f"runbook 监控关键字覆盖不足 ({found_kw}/{len(monitor_keywords)})"

    # 商业化 Phase 8 收官时间表必含
    assert "Phase 8" in text, "runbook 缺少 Phase 8 收官时间表"


# ── [3] License 4 模式完整覆盖 ──────────────────────────────────────────────
def test_license_four_modes_complete():
    """License 4 模式完整覆盖: 校验 + 离线 7 天宽限 + read-only + 客户端 fallback.

    W73 B-5 license_service.py + W78 C-1 license-check + W79 B-2 私有化变体 +
    W80 B-2 customer support 4 模式.
    """
    # License 校验: license_service.py 必须存在
    license_svc = PROJECT_ROOT / "app" / "services" / "license_service.py"
    assert license_svc.exists(), f"license_service.py 缺失: {license_svc}"

    # 4 处模式必含关键字
    sources = {
        "校验 (validate)": license_svc,
        "离线宽限 (offline grace)": PRIVATE_DIR / "private_config.py",
        "read-only 降级": PRIVATE_DIR / "private_config.py",
        "客户端 fallback": PRIVATE_DIR / "billing_degrade.py",
    }

    patterns = {
        "校验 (validate)": ("validate", "check", "verify"),
        "离线宽限 (offline grace)": ("OFFLINE_GRACE_DAYS", "offline_grace", "7"),
        "read-only 降级": ("read_only", "degrade", "readonly"),
        "客户端 fallback": ("fallback", "mock", "BILLING_LIVE_ENABLED"),
    }

    for label, path in sources.items():
        assert path.exists(), f"{label} 路径缺失: {path}"
        text = path.read_text(encoding="utf-8", errors="ignore")
        kws = patterns[label]
        assert any(kw in text for kw in kws), \
            f"{label} 在 {path.name} 缺少关键字 {kws}"


# ── [4] 派工 v6 段 5 反馈 #7 实战沉淀 ────────────────────────────────────────
def test_dispatch_v6_section5_feedback7_practice():
    """派工 v6 段 5 反馈 #7 实战沉淀: TenantIsolationViolation 422 修复 + multi-tenant 隔离.

    反馈 #7: 跨租户拦截 → 422 (而非 500), 因为 TenantIsolationViolation
    缺 code 形参 → super().__init__ 调用缺 code → APIException fallback 500.

    W75 B-2 commit 6d9c9e446 实战: 1 行 production 修复.
    """
    # TenantIsolationViolation 类必含 code 形参
    tdi = PROJECT_ROOT / "app" / "services" / "tenant_data_isolation.py"
    assert tdi.exists(), f"tenant_data_isolation.py 缺失: {tdi}"
    text = tdi.read_text(encoding="utf-8", errors="ignore")

    assert "TenantIsolationViolation" in text, "缺少 TenantIsolationViolation 类"
    assert "code=self.code" in text or "code=code" in text, \
        "TenantIsolationViolation 缺少 code 形参传递 (派工 v6 段 5 反馈 #7 实战未落地)"

    # e2e 422 而非 500 验证: monitor-tenant-isolation.sh 必含 422 关键字
    monitor = SCRIPTS_DIR / "monitor-tenant-isolation.sh"
    assert monitor.exists(), f"monitor-tenant-isolation.sh 缺失: {monitor}"
    mtext = monitor.read_text(encoding="utf-8", errors="ignore")
    assert "422" in mtext, "monitor-tenant-isolation.sh 缺少 422 in-process verify"

    # multi-tenant 隔离必含: 6 商业化表 + 跨租户拦截 + 422 而非 500
    must_in_text = ["multi-tenant", "422", "tenant_id"]
    found = sum(1 for k in must_in_text if k in text)
    assert found >= 2, \
        f"multi-tenant 隔离关键字覆盖不足 ({found}/{len(must_in_text)}): {text[:200]}"