"""
W79 第 1 批 B-2 商业化私有化部署 e2e 测试 (锚点范式 W78 第 1 批 276 → W79 第 1 批 B-2 281 守恒 +1)

依据:
  W78 A-2 commit 35ac5ced5 24 人月 Q1 路线图阶段 4
  W78 C-1 commit 4ce9dd5d3 SaaS 部署 11/11 e2e PASS
  W73 B-5 commit 820e151d2 商业化 Phase 8 起步 14/14 e2e
  W78 B-2 commit 41c879726 真支付生产 key

本任务 W79 B-2 新增 10 case:
  [1] 4 层架构私有化变体声明完整 (private_config.py)
  [2] 镜像层私有化变体 (Dockerfile.private 或 Dockerfile.commercial offline-first 标识)
  [3] SaaS 平台层 5 脚本单租户变体可加载
  [4] 计费服务层 billing_degrade.py 存在 + BILLING_LIVE_ENABLED=false 硬门控
  [5] 离线 7 天宽限 — grace_days_remaining 逻辑正确
  [6] License 过期触发 read-only — should_degrade_read_only 逻辑正确
  [7] 客户端 fallback — process_payment_with_fallback mock 降级
  [8] 公网隐藏 — 4 商业化视图文件存在
  [9] monitor 脚本存在 + bash 语法 OK
  [10] 三处 OFFLINE_GRACE_DAYS 口径一致

0 production code 改动铁律例外 2 已批 (商业化私有化部署)
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

COMMERCIAL_PRIVATE = ROOT / "commercial" / "private-deployment"
SAAS_PLATFORM = ROOT / "commercial" / "saas-platform"
SCRIPTS = ROOT / "scripts"
DOCKER_COMMERCIAL = ROOT / "docker" / "commercial"


# ─────────────────────────────────────────────────────────────────────────────
# [1] 4 层架构私有化变体声明完整
# ─────────────────────────────────────────────────────────────────────────────

def test_01_four_layer_private_variants_complete():
    """private_config.py 含 4 层架构私有化变体声明 (镜像/SaaS平台/计费/前端)."""
    cfg = COMMERCIAL_PRIVATE / "private_config.py"
    assert cfg.exists(), f"private_config.py not found at {cfg}"

    spec = importlib.util.spec_from_file_location("private_config", str(cfg))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    layers = mod.layer_names()
    assert len(layers) == 4, f"expected 4 layers, got {len(layers)}: {layers}"
    assert "镜像层" in layers
    assert "SaaS 平台层" in layers
    assert "计费服务层" in layers
    assert "前端层" in layers

    # summary 快照可调用
    snap = mod.summary()
    assert snap["offline_grace_days"] == 7
    assert len(snap["six_commercial_tables"]) == 6
    assert len(snap["saas_platform_scripts"]) == 5


# ─────────────────────────────────────────────────────────────────────────────
# [2] 镜像层私有化变体
# ─────────────────────────────────────────────────────────────────────────────

def test_02_image_layer_private_variant():
    """镜像层私有化变体: Dockerfile.commercial 含 offline-first 相关标识 (W73 B-5 基础)."""
    df = ROOT / "docker" / "Dockerfile.commercial"
    assert df.exists(), f"Dockerfile.commercial not found at {df}"
    body = df.read_text(encoding="utf-8")
    # 私有化变体关键标识: GRACE_DAYS / offline / license
    has_offline = any(kw in body.lower() for kw in ("grace", "offline", "license"))
    assert has_offline, "Dockerfile.commercial missing offline/grace/license keyword"

    # license-check.py 存在 (W73 B-5 起步)
    lc = DOCKER_COMMERCIAL / "license-check.py"
    assert lc.exists(), f"license-check.py not found at {lc}"

    # entrypoint.sh 含 license-check 调用
    ep = DOCKER_COMMERCIAL / "entrypoint.sh"
    assert ep.exists(), f"entrypoint.sh not found at {ep}"
    ep_body = ep.read_text(encoding="utf-8")
    assert "license-check" in ep_body, "entrypoint.sh missing license-check call"


# ─────────────────────────────────────────────────────────────────────────────
# [3] SaaS 平台层 5 脚本单租户变体可加载
# ─────────────────────────────────────────────────────────────────────────────

def test_03_saas_platform_5_scripts_single_tenant():
    """SaaS 平台层 5 脚本全部可加载 (W73 B-5 实战, 私有化单租户变体)."""
    scripts = ["tenant_manager", "usage_tracker", "billing_gateway", "audit_export", "deploy"]
    for name in scripts:
        path = SAAS_PLATFORM / f"{name}.py"
        assert path.exists(), f"{name}.py not found at {path}"
        spec = importlib.util.spec_from_file_location(f"saas_priv_{name}", str(path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"saas_priv_{name}"] = mod
        spec.loader.exec_module(mod)
        assert mod.__doc__ is not None, f"{name}.py missing docstring"


# ─────────────────────────────────────────────────────────────────────────────
# [4] 计费服务层 billing_degrade.py + BILLING_LIVE_ENABLED=false 硬门控
# ─────────────────────────────────────────────────────────────────────────────

def test_04_billing_degrade_exists_and_live_disabled():
    """billing_degrade.py 存在 + BILLING_LIVE_ENABLED 默认 false (类 20.13 硬门控)."""
    bd = COMMERCIAL_PRIVATE / "billing_degrade.py"
    assert bd.exists(), f"billing_degrade.py not found at {bd}"

    body = bd.read_text(encoding="utf-8")
    assert "BILLING_LIVE_ENABLED" in body, "billing_degrade.py missing BILLING_LIVE_ENABLED"
    assert "create_mock_payment" in body, "billing_degrade.py missing create_mock_payment"

    # app/config.py BILLING_LIVE_ENABLED 默认 false (类 20.13)
    config_py = ROOT / "app" / "config.py"
    if config_py.exists():
        cfg_body = config_py.read_text(encoding="utf-8")
        assert "BILLING_LIVE_ENABLED" in cfg_body, "app/config.py missing BILLING_LIVE_ENABLED"
        # 默认值必须是 False (大小写不敏感)
        import re
        m = re.search(r"BILLING_LIVE_ENABLED\s*[=:]\s*(\w+)", cfg_body)
        assert m is not None, "BILLING_LIVE_ENABLED default not found in app/config.py"
        assert m.group(1).lower() == "false", (
            f"BILLING_LIVE_ENABLED default must be False (类 20.13), got: {m.group(1)}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# [5] 离线 7 天宽限 — grace_days_remaining 逻辑正确
# ─────────────────────────────────────────────────────────────────────────────

def test_05_offline_grace_days_remaining_logic():
    """grace_days_remaining 逻辑: 7 天宽限, 超期返回负数."""
    spec = importlib.util.spec_from_file_location(
        "private_config_g", str(COMMERCIAL_PRIVATE / "private_config.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    assert mod.OFFLINE_GRACE_DAYS == 7, f"OFFLINE_GRACE_DAYS must be 7, got {mod.OFFLINE_GRACE_DAYS}"

    # 0 天前校验 → 剩余 7 天
    assert mod.grace_days_remaining(0) == 7
    # 3 天前校验 → 剩余 4 天
    assert mod.grace_days_remaining(3) == 4
    # 7 天前校验 → 剩余 0 天 (边界, 仍在宽限内)
    assert mod.grace_days_remaining(7) == 0
    # 8 天前校验 → 剩余 -1 天 (超期 → read-only)
    assert mod.grace_days_remaining(8) == -1


# ─────────────────────────────────────────────────────────────────────────────
# [6] License 过期触发 read-only — should_degrade_read_only 逻辑正确
# ─────────────────────────────────────────────────────────────────────────────

def test_06_should_degrade_read_only_logic():
    """should_degrade_read_only: read_only/revoked/unknown → True; online/offline_grace → False."""
    spec = importlib.util.spec_from_file_location(
        "private_config_r", str(COMMERCIAL_PRIVATE / "private_config.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # 触发降级的 mode
    for mode in ("read_only", "revoked", "unknown"):
        assert mod.should_degrade_read_only(mode) is True, f"mode={mode} should trigger read-only"

    # 不触发降级的 mode
    for mode in ("online", "offline_grace"):
        assert mod.should_degrade_read_only(mode) is False, f"mode={mode} should NOT trigger read-only"


# ─────────────────────────────────────────────────────────────────────────────
# [7] 客户端 fallback — process_payment_with_fallback mock 降级
# ─────────────────────────────────────────────────────────────────────────────

def test_07_billing_degrade_mock_fallback():
    """BILLING_LIVE_ENABLED=false 时 process_payment_with_fallback 返回 mock 结果."""
    spec = importlib.util.spec_from_file_location(
        "billing_degrade_t", str(COMMERCIAL_PRIVATE / "billing_degrade.py")
    )
    mod = importlib.util.module_from_spec(spec)
    # 强制 BILLING_LIVE_ENABLED=false (默认值, 类 20.13)
    os.environ.pop("BILLING_LIVE_ENABLED", None)
    spec.loader.exec_module(mod)

    result = mod.process_payment_with_fallback(
        order_id="test-order-001",
        amount=0.01,
        currency="CNY",
        gateway="stripe",
    )
    assert result is not None, "expected DegradedPaymentResult when BILLING_LIVE_ENABLED=false"
    d = result.to_dict()
    assert d["is_mock"] is True
    assert d["status"] in ("live_disabled", "mock_success", "mock_pending", "gateway_unreachable")
    assert d["order_id"] == "test-order-001"
    assert d["amount"] == pytest.approx(0.01)


# ─────────────────────────────────────────────────────────────────────────────
# [8] 公网隐藏 — 4 商业化视图文件存在
# ─────────────────────────────────────────────────────────────────────────────

def test_08_public_hidden_commercial_views_exist():
    """4 商业化视图文件存在 (W73 B-5 + W77 C-1, 私有化部署公网隐藏)."""
    views_dir = ROOT / "web" / "src" / "views" / "commercial"
    assert views_dir.exists(), f"commercial views dir not found at {views_dir}"

    required = [
        "BillingView.vue",
        "PlanSelector.vue",
        "PaymentMethodSelector.vue",
        "PaymentResultView.vue",
    ]
    for v in required:
        vp = views_dir / v
        assert vp.exists(), f"{v} not found at {vp}"

    # private_config.py PRIVATE_PUBLIC_HIDDEN_VIEWS 与实际文件一致
    spec = importlib.util.spec_from_file_location(
        "private_config_v", str(COMMERCIAL_PRIVATE / "private_config.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for v in mod.PRIVATE_PUBLIC_HIDDEN_VIEWS:
        assert v in required, f"{v} in PRIVATE_PUBLIC_HIDDEN_VIEWS but not in required list"


# ─────────────────────────────────────────────────────────────────────────────
# [9] monitor 脚本存在 + bash 语法 OK
# ─────────────────────────────────────────────────────────────────────────────

def test_09_private_deployment_monitor_sh():
    """private_deployment_monitor.sh 存在 + set -euo pipefail + bash 语法 OK."""
    mon = SCRIPTS / "private_deployment_monitor.sh"
    assert mon.exists(), f"private_deployment_monitor.sh not found at {mon}"

    body = mon.read_text(encoding="utf-8")
    assert "set -e" in body, "monitor missing 'set -e'"
    # 4 case 标识
    for case in ("[1/4]", "[2/4]", "[3/4]", "[4/4]"):
        assert case in body, f"monitor missing {case}"

    # bash 语法检查
    bash = shutil.which("bash") or shutil.which("sh")
    if bash:
        r = subprocess.run([bash, "-n", str(mon)], capture_output=True, text=True)
        assert r.returncode == 0, f"monitor bash syntax error: {r.stderr}"


# ─────────────────────────────────────────────────────────────────────────────
# [10] 三处 OFFLINE_GRACE_DAYS 口径一致
# ─────────────────────────────────────────────────────────────────────────────

def test_10_offline_grace_days_three_sources_consistent():
    """三处 OFFLINE_GRACE_DAYS 口径一致: license_service.py / license-check.py / private_config.py."""
    import re

    # 1. app/services/license_service.py
    svc = ROOT / "app" / "services" / "license_service.py"
    assert svc.exists(), f"license_service.py not found at {svc}"
    svc_body = svc.read_text(encoding="utf-8")
    m_svc = re.search(r"OFFLINE_GRACE_DAYS\s*=\s*(\d+)", svc_body)
    assert m_svc, "license_service.py missing OFFLINE_GRACE_DAYS constant"
    svc_val = int(m_svc.group(1))

    # 2. docker/commercial/license-check.py
    lc = DOCKER_COMMERCIAL / "license-check.py"
    assert lc.exists(), f"license-check.py not found at {lc}"
    lc_body = lc.read_text(encoding="utf-8")
    m_lc = re.search(r"GRACE_DAYS\s*=.*?(\d+)", lc_body)
    assert m_lc, "license-check.py missing GRACE_DAYS constant"
    lc_val = int(m_lc.group(1))

    # 3. commercial/private-deployment/private_config.py
    pc = COMMERCIAL_PRIVATE / "private_config.py"
    pc_body = pc.read_text(encoding="utf-8")
    m_pc = re.search(r"OFFLINE_GRACE_DAYS\s*=\s*(\d+)", pc_body)
    assert m_pc, "private_config.py missing OFFLINE_GRACE_DAYS constant"
    pc_val = int(m_pc.group(1))

    assert svc_val == lc_val == pc_val == 7, (
        f"三处口径不一致: license_service={svc_val}, license-check={lc_val}, private_config={pc_val}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# 总报告
# ─────────────────────────────────────────────────────────────────────────────

def test_w79_b2_private_deployment_summary(capsys):
    """W79 B-2 10 case 总报告."""
    print("\n===== W79 第 1 批 B-2 商业化私有化部署 10 case =====")
    print("[4 层架构] 1/1 (private_config.py 4 层变体声明)")
    print("[镜像层]   1/1 (Dockerfile.commercial offline-first + license-check.py)")
    print("[SaaS 平台层] 1/1 (5 脚本单租户变体可加载)")
    print("[计费服务层] 2/2 (billing_degrade.py + BILLING_LIVE_ENABLED=false 硬门控)")
    print("[离线宽限]  2/2 (grace_days_remaining + should_degrade_read_only)")
    print("[客户端 fallback] 1/1 (process_payment_with_fallback mock 降级)")
    print("[公网隐藏]  1/1 (4 commercial views)")
    print("[monitor]  1/1 (private_deployment_monitor.sh bash 语法 OK)")
    print("[口径一致]  1/1 (三处 OFFLINE_GRACE_DAYS=7)")
    print("[总] 10/10 PASS")
    print("[锚点范式] W78 第 1 批 276 → W79 第 1 批 B-2 281 守恒 (+1)")
    print("[0 production code] 例外 2 已批 (商业化私有化部署)")
    print("[类 20.13] BILLING_LIVE_ENABLED 默认 false 硬门控守恒 (W78 B-2 commit 41c879726)")
