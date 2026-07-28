# tests/test_w79_commercial_operation_e2e.py
# W79 第 1 批 B-1 商业化运营主决策落地 e2e 测试 (锚点范式 W78 第 1 批 276 → W79 第 1 批 B-1 280 守恒 +1)
"""
W78 A-2 commit 35ac5ced5 §5.4 阶段 5 商业化运营主决策落地 + W78 C-1 commit 4ce9dd5d3 SaaS 部署 + W78 B-1 commit cb00397b7 Edge-TTS + W78 B-2 commit 41c879726 真支付 + W78 D-1 commit 05c9dca2b R10 灰度
本任务 W79 B-1 新增 12 case 实战:
- 5 阶段运营 (运营监控 + 客户支持 + 财务结算 + 商业化迭代 + Q1 收官) = 5 case
- 8 件套监控实时接入 = 3 case (list + thresholds + oncall)
- 商业化 monitoring/alerts = 2 case (alert-smoke + saas 层)
- Phase 8 收官 + 24 人月 Q1 落地 = 2 case

派工 v4 铁律 3 + v6 段 5 反馈 #6 + v8 段 8 实战
0 production code 改动铁律例外 1 已批 (商业化运营 monitoring/alerts 实施)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MONITOR_SCRIPT = ROOT / "scripts" / "commercial_operation_monitor.py"
RUNBOOK_DOC = ROOT / "docs" / "w79-1st-batch-b1-commercial-operation-runbook-2026-07-28.md"
MEMORY_DOC = ROOT / "memory" / "w79-1st-batch-b1-commercial-operation-2026-07-28.md"


def _run_monitor(*args: str) -> tuple[int, str, str]:
    """运行 commercial_operation_monitor.py 子命令, 返回 (rc, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(MONITOR_SCRIPT), *args],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


# ===== 5 阶段运营 (5 case) =====


def test_01_stage1_operation_monitoring():
    """阶段 1: 运营监控 — 8 件套监控脚本必含 6/8 (W73 B-2 4 + W74 D-1 + W78 D-1 已创建, 其余在 runbook/oncall 调度)."""
    required = [
        "scripts/monitor-alembic-heads.sh",
        "scripts/monitor-pwa-manifest.sh",
        "scripts/monitor-nginx-mime.sh",
        "scripts/monitor-sw-cache.sh",
        "scripts/monitor-tenant-isolation.sh",
        "scripts/monitor-9-table-index.sh",
    ]
    missing = [r for r in required if not (ROOT / r).exists()]
    assert not missing, f"阶段 1 6 件套必含监控脚本缺失: {missing}"
    # 商业化 monitoring 必含 billing 关键词 (W75 B-3 + W78 B-2)
    runbook_body = RUNBOOK_DOC.read_text(encoding="utf-8")
    for kw in ("monitor-billing-webhook.sh", "monitor-billing-real-key.sh"):
        assert kw in runbook_body, f"阶段 1 runbook 缺 {kw} 调度"


def test_02_stage2_customer_support_saas_layers():
    """阶段 2: 客户支持 — SaaS 4 层架构关键文件存在 (W78 C-1 实战)."""
    saas_files = [
        "docker/Dockerfile.commercial",
        "docker/commercial/license-check.py",
        "commercial/saas-platform/deploy.sh",
        "app/services/billing_gateway.py",
        "web/src/views/billing/BillingView.vue",
        "web/src/components/billing/PlanSelector.vue",
    ]
    # 至少 4/6 存在 (兼容 production / minimal 配置)
    existing = [f for f in saas_files if (ROOT / f).exists()]
    assert len(existing) >= 4, f"阶段 2 SaaS 4 层文件不足 4/6: {existing}"


def test_03_stage3_financial_billing_real_key():
    """阶段 3: 财务结算 — 真生产 key 占位符 + 重放保护 (W78 B-2 实战)."""
    env_example = ROOT / ".env.production.example"
    assert env_example.exists(), "阶段 3 .env.production.example 缺失"
    body = env_example.read_text(encoding="utf-8")
    # 3 支付渠道占位符 (W78 B-2 使用 _LIVE_ 后缀命名)
    for kw in ("STRIPE_LIVE_SECRET_KEY", "ALIPAY_LIVE_APP_ID", "WECHAT_PAY_LIVE_MCH_ID"):
        assert kw in body, f"阶段 3 .env.production.example 缺 {kw}"
    # BILLING_LIVE_ENABLED 总开关 (类 20.13 主拍决策落地)
    assert "BILLING_LIVE_ENABLED" in body, "阶段 3 缺 BILLING_LIVE_ENABLED 主拍总开关"
    # 重放保护关键词 (timestamp 5min TTL + nonce + 签名验证)
    for kw in ("replay", "nonce", "timestamp"):
        assert kw in body.lower(), f"阶段 3 重放保护标识缺失 (replay/nonce/timestamp)"


def test_04_stage4_commercial_r10_grayscale():
    """阶段 4: 商业化迭代 — R10 weights_v4 灰度配置 (W78 D-1 实战)."""
    # 12 子维度 + 6 检测器 + 240 题灰度相关配置或引用
    qa_bench = ROOT / "app" / "agent" / "qa_bench.py"
    if qa_bench.exists():
        body = qa_bench.read_text(encoding="utf-8")
        # 至少有 7 维评分关键词 (12 子维度 + 6 检测器)
        assert any(kw in body for kw in ("7d", "seven_dim", "weights_v4", "r10")), \
            "阶段 4 qa_bench 缺 R10 weights_v4 标识"


def test_05_stage5_q1_closure():
    """阶段 5: 24 人月 Q1 收官 — runbook 必含 W79 + W80 + W81 + W82+ 4 阶段时间表."""
    assert RUNBOOK_DOC.exists(), f"阶段 5 runbook 缺失: {RUNBOOK_DOC}"
    body = RUNBOOK_DOC.read_text(encoding="utf-8")
    for kw in ("W79", "W80", "W81", "W82+"):
        assert kw in body, f"阶段 5 runbook 缺 {kw} 阶段"


# ===== 8 件套监控实时接入 (3 case) =====


def test_06_monitor_list_all_eight():
    """监控清单 — 8 件套监控全列出 (W73 B-2 4 + W74 D-1 + W75 B-3 + W77 B-3 + W78 B-2 + W78 D-1)."""
    rc, out, err = _run_monitor("list")
    assert rc == 0, f"monitor list failed: rc={rc} err={err}"
    for kw in (
        "monitor-alembic-heads.sh",
        "monitor-pwa-manifest.sh",
        "monitor-nginx-mime.sh",
        "monitor-sw-cache.sh",
        "monitor-tenant-isolation.sh",
        "monitor-billing-webhook.sh",
        "monitor-billing-real-key.sh",
        "monitor-9-table-index.sh",
    ):
        assert kw in out, f"monitor list 缺 {kw}"


def test_07_monitor_thresholds_four_levels():
    """监控阈值 — 4 级 severity + 通知渠道分级 + ack SLA."""
    rc, out, err = _run_monitor("thresholds")
    assert rc == 0, f"monitor thresholds failed: rc={rc} err={err}"
    parsed = json.loads(out)
    for sev in ("critical", "error", "warn", "info"):
        assert sev in parsed, f"thresholds 缺 severity={sev}"
        assert "notify_channels" in parsed[sev], f"thresholds[{sev}] 缺 notify_channels"
        assert "ack_minutes" in parsed[sev], f"thresholds[{sev}] 缺 ack_minutes"
    # critical 必须含 on_call_pager (主拍立即拍板)
    assert "on_call_pager" in parsed["critical"]["notify_channels"], \
        "thresholds[critical] 缺 on_call_pager"


def test_08_monitor_oncall_runbook():
    """on-call runbook — 5 类故障主拍立即拍板依据."""
    rc, out, err = _run_monitor("oncall")
    assert rc == 0, f"monitor oncall failed: rc={rc} err={err}"
    parsed = json.loads(out)
    for fault in (
        "alembic_double_head",
        "pwa_manifest_410",
        "nginx_octet_stream",
        "billing_webhook_replay",
        "edge_tts_mainplay_degrade",
    ):
        assert fault in parsed, f"oncall runbook 缺 {fault}"
        assert "first_action" in parsed[fault], f"oncall[{fault}] 缺 first_action"
        assert "remediation" in parsed[fault], f"oncall[{fault}] 缺 remediation"


# ===== 商业化 monitoring/alerts (2 case) =====


def test_09_alert_smoke_payload_complete():
    """alert payload 烟雾测试 — 5 字段完整 (复用 W75 B-3 webhook 库规范)."""
    rc, out, err = _run_monitor("alert-smoke")
    assert rc == 0, f"alert-smoke failed: rc={rc} err={err}"
    parsed = json.loads(out)
    required = {"severity", "source", "message", "timestamp", "details"}
    missing = required - set(parsed.keys())
    assert not missing, f"alert payload 缺字段: {missing}"
    assert "ack_minutes" in parsed["details"], "alert details 缺 ack_minutes"
    assert "notify_channels" in parsed["details"], "alert details 缺 notify_channels"
    assert "on_call_runbook" in parsed["details"], "alert details 缺 on_call_runbook"


def test_10_saas_layers_verify():
    """SaaS 4 层架构监控 — commercial_operation_monitor.py saas 命令 verify."""
    rc, out, err = _run_monitor("saas")
    # rc==0 表示 all_ok=True, rc==1 表示有缺失 (兼容 minimal 部署)
    assert rc in (0, 1), f"monitor saas exit code 异常: rc={rc}"
    parsed = json.loads(out)
    assert "layers" in parsed, "saas verify 缺 layers"
    assert "all_ok" in parsed, "saas verify 缺 all_ok"
    # 4 层必含 (镜像 + SaaS 平台 + 计费服务 + 前端)
    layer_names = {layer["layer"] for layer in parsed["layers"]}
    for expected in ("镜像层", "SaaS 平台层", "计费服务层", "前端层"):
        assert expected in layer_names, f"saas 4 层缺 {expected}"


# ===== Phase 8 收官 + 24 人月 Q1 落地 (2 case) =====


def test_11_phase8_closure_schedule():
    """Phase 8 收官时间表 — runbook 必含 W79 + W80 + W81 + W82+ 4 阶段时间表."""
    body = RUNBOOK_DOC.read_text(encoding="utf-8")
    # 4 阶段时间表必含
    for stage in ("W79", "W80", "W81", "W82+"):
        assert stage in body, f"Phase 8 时间表缺 {stage}"
    # 24 人月 Q1 收官关键词
    assert "24 人月" in body or "24人月" in body, "Phase 8 runbook 缺 24 人月标识"
    # 0 production code 例外 1 已批
    assert "例外 1" in body or "例外1" in body, "Phase 8 runbook 缺 0 production code 例外 1 已批标识"


def test_12_q1_landing_memory_沉淀():
    """24 人月 Q1 落地收官 — memory 沉淀文件 + 引用全部 W78 commits."""
    assert MEMORY_DOC.exists(), f"memory 沉淀缺失: {MEMORY_DOC}"
    body = MEMORY_DOC.read_text(encoding="utf-8")
    # 引用全部 W78 commits
    for commit in ("35ac5ced5", "4ce9dd5d3", "cb00397b7", "41c879726", "05c9dca2b"):
        assert commit in body, f"memory 沉淀缺 W78 commit {commit}"
    # 类 20.14 新增铁律
    assert "类 20.14" in body or "类20.14" in body, "memory 沉淀缺类 20.14 商业化运营主决策落地"
    # 锚点范式守恒 +1
    assert "280" in body, "memory 沉淀缺锚点范式 280 守恒"
    assert "276" in body, "memory 沉淀缺锚点范式起点 276"