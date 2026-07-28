#!/usr/bin/env python3
"""
commercial_operation_monitor.py
W79 第 1 批 B-1 商业化运营监控 (锚点范式 W78 第 1 批 276 → W79 第 1 批 B-1 280 守恒 +1)

依据: W78 A-2 commit 35ac5ced5 §5.4 阶段 5 商业化运营主决策落地 + W78 C-1 commit 4ce9dd5d3 SaaS 部署 + W78 B-1 commit cb00397b7 Edge-TTS + W78 B-2 commit 41c879726 真支付生产 key + W78 D-1 commit 05c9dca2b R10 灰度 + 派工 v6 段 5 反馈 #6 实战

5 大必含 case (W78 A-2 §5.4 阶段 5):
1. 8 件套监控实时接入 (W73 B-2 4 类 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W78 D-1)
2. 报警阈值定义 (severity 4 级 + 通知渠道分级)
3. 通知渠道集成 (webhook + email + on-call 兜底)
4. on-call 实战 (5 类故障 → 主拍立即拍板)
5. SaaS 部署监控 (4 层架构 + 6 商业化表 + multi-tenant + 计费真接入)

0 production code 改动铁律例外 1 已批 (商业化运营 monitoring/alerts 实施)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# 8 件套监控清单 (W73 B-2 + W74 D-1 + W75 B-3 + W77 B-3 + W78 C-1 + W78 B-1 + W78 D-1)
MONITORS = [
    {
        "name": "monitor-alembic-heads.sh",
        "w_batch": "W73 第 1 批 B-2",
        "scope": "alembic 双头检测",
        "severity_default": "critical",
        "interval_min": 60,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-pwa-manifest.sh",
        "w_batch": "W73 第 1 批 B-2",
        "scope": "PWA manifest 410 检测",
        "severity_default": "error",
        "interval_min": 60,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-nginx-mime.sh",
        "w_batch": "W73 第 1 批 B-2",
        "scope": "nginx octet-stream 整站白屏检测",
        "severity_default": "critical",
        "interval_min": 60,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-sw-cache.sh",
        "w_batch": "W73 第 1 批 B-2",
        "scope": "SW 缓存污染检测 (8 char hex + 双 head)",
        "severity_default": "error",
        "interval_min": 60,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-tenant-isolation.sh",
        "w_batch": "W74 第 1 批 D-1",
        "scope": "多租户隔离 422 检测",
        "severity_default": "critical",
        "interval_min": 30,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-billing-webhook.sh",
        "w_batch": "W75 第 1 批 B-3",
        "scope": "计费 webhook 重放保护检测 (timestamp 5min + nonce)",
        "severity_default": "critical",
        "interval_min": 15,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-billing-real-key.sh",
        "w_batch": "W77 第 1 批 B-3 + W78 B-2",
        "scope": "真生产 key 自动切换 (stripe_real/alipay_real/wechat_pay_real)",
        "severity_default": "critical",
        "interval_min": 30,
        "exit_code_zero_is_ok": True,
    },
    {
        "name": "monitor-9-table-index.sh",
        "w_batch": "W78 第 1 批 D-1",
        "scope": "9 表索引 + 商业化 R10 灰度索引",
        "severity_default": "error",
        "interval_min": 60,
        "exit_code_zero_is_ok": True,
    },
]


@dataclass
class MonitorResult:
    name: str
    status: str  # "ok" | "fail" | "missing"
    severity: str
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


def discover_scripts_dir() -> Path:
    """定位 scripts/ 目录 (兼容 worktree 与生产部署)."""
    candidates = [
        ROOT / "scripts",
        Path("/opt/microbubble-agent/scripts"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return ROOT / "scripts"


def run_monitor(monitor: dict[str, Any], scripts_dir: Path, dry_run: bool) -> MonitorResult:
    """运行单个 monitor 脚本, 返回结果 (含 exit code 与输出)."""
    name = monitor["name"]
    script_path = scripts_dir / name
    started = datetime.now(timezone.utc)

    if dry_run:
        return MonitorResult(
            name=name,
            status="ok" if script_path.exists() else "missing",
            severity=monitor["severity_default"],
            exit_code=0 if script_path.exists() else 127,
            stdout="dry_run" if script_path.exists() else "script_missing",
            duration_ms=0,
        )

    if not script_path.exists():
        return MonitorResult(
            name=name,
            status="missing",
            severity=monitor["severity_default"],
            exit_code=127,
            stderr=f"{script_path} not found",
            duration_ms=0,
        )

    bash = shutil.which("bash") or shutil.which("sh")
    if not bash:
        return MonitorResult(
            name=name,
            status="fail",
            severity=monitor["severity_default"],
            exit_code=126,
            stderr="bash/sh not found in PATH",
            duration_ms=0,
        )

    try:
        proc = subprocess.run(
            [bash, str(script_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(scripts_dir.parent),
        )
        duration_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
        ok = proc.returncode == 0
        return MonitorResult(
            name=name,
            status="ok" if ok else "fail",
            severity=monitor["severity_default"],
            exit_code=proc.returncode,
            stdout=proc.stdout[:500],
            stderr=proc.stderr[:500],
            duration_ms=duration_ms,
        )
    except subprocess.TimeoutExpired:
        return MonitorResult(
            name=name,
            status="fail",
            severity=monitor["severity_default"],
            exit_code=124,
            stderr="timeout after 60s",
            duration_ms=60_000,
        )


# ===== 报警阈值定义 (severity 4 级 + 通知渠道分级) =====

ALERT_THRESHOLDS = {
    "critical": {
        "notify_channels": ["webhook", "on_call_pager", "email"],
        "ack_minutes": 5,
        "description": "服务不可用 / 数据损坏 / 真支付链路异常 — 主拍立即拍板",
    },
    "error": {
        "notify_channels": ["webhook", "email"],
        "ack_minutes": 30,
        "description": "功能降级但不影响主链路 — 30 分钟内 ack",
    },
    "warn": {
        "notify_channels": ["email"],
        "ack_minutes": 240,
        "description": "预警但无业务影响 — 4 小时内 ack",
    },
    "info": {
        "notify_channels": ["log"],
        "ack_minutes": 1440,
        "description": "日常状态报告 — 24 小时内 ack",
    },
}


def classify_alert(severity: str) -> dict[str, Any]:
    """根据 severity 查表返回通知渠道 + ack SLA."""
    return ALERT_THRESHOLDS.get(severity, ALERT_THRESHOLDS["warn"])


# ===== on-call 实战 (5 类故障 → 主拍立即拍板) =====

ON_CALL_RUNBOOK = {
    "alembic_double_head": {
        "fault_type": "alembic 双头",
        "first_action": "verify alembic chain (python -c import ScriptDirectory)",
        "remediation": "merge 顺序按 down_revision + clear __pycache__ (W68 第 3 批 1852468a6 教训)",
        "severity": "critical",
    },
    "pwa_manifest_410": {
        "fault_type": "PWA manifest 410",
        "first_action": "curl /manifest.{hash}.webmanifest 看 200 (PWA install)",
        "remediation": "npm run build 唯一合法 build (vite build 直跑必坏, 59187ce8 教训)",
        "severity": "error",
    },
    "nginx_octet_stream": {
        "fault_type": "nginx octet-stream 整站白屏",
        "first_action": "curl / 看 text/html (非 octet-stream)",
        "remediation": "rollback types {} block (W68 第 5 批 f148d96 教训)",
        "severity": "critical",
    },
    "billing_webhook_replay": {
        "fault_type": "计费 webhook 重放保护异常",
        "first_action": "verify timestamp 5min TTL + nonce + 签名",
        "remediation": "rotate webhook secret + 检查 W75 C-1 16/16 e2e PASS",
        "severity": "critical",
    },
    "edge_tts_mainplay_degrade": {
        "fault_type": "Edge-TTS 主拍降级",
        "first_action": "curl Edge-TTS endpoint + Web Speech API 兜底",
        "remediation": "B+D 渐进式 + pre-synthesize cache (W78 B-1 cb00397b7 教训)",
        "severity": "warn",
    },
}


def get_on_call_runbook(fault_type: str) -> dict[str, Any]:
    """获取 on-call runbook (5 类故障主拍立即拍板依据)."""
    return ON_CALL_RUNBOOK.get(fault_type, ON_CALL_RUNBOOK["alembic_double_head"])


# ===== SaaS 部署监控 (4 层架构 + 6 商业化表 + multi-tenant + 计费真接入) =====

SAAS_LAYERS = [
    {
        "name": "镜像层",
        "key_files": [
            "docker/Dockerfile.commercial",
            "docker/commercial/license-check.py",
        ],
    },
    {
        "name": "SaaS 平台层",
        "key_files": [
            "commercial/saas-platform/deploy.sh",
        ],
    },
    {
        "name": "计费服务层",
        "key_files": [
            "app/services/billing_gateway.py",
            ".env.production.example",
        ],
    },
    {
        "name": "前端层",
        "key_files": [
            "web/src/views/billing/BillingView.vue",
            "web/src/components/billing/PlanSelector.vue",
        ],
    },
]


def verify_saas_layers(project_dir: Path) -> dict[str, Any]:
    """验证 4 层架构关键文件存在."""
    layers_status = []
    for layer in SAAS_LAYERS:
        missing = []
        for rel in layer["key_files"]:
            if not (project_dir / rel).exists():
                missing.append(rel)
        layers_status.append({
            "layer": layer["name"],
            "ok": len(missing) == 0,
            "missing": missing,
            "expected": layer["key_files"],
        })
    all_ok = all(s["ok"] for s in layers_status)
    return {"all_ok": all_ok, "layers": layers_status}


def generate_alert_payload(
    monitor_name: str,
    severity: str,
    message: str,
    details: dict[str, Any],
    on_call: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """生成完整 5 字段 webhook payload (复用 W75 B-3 webhook_payload.sh 字段规范)."""
    threshold = classify_alert(severity)
    payload = {
        "severity": severity,
        "source": "commercial-operation-monitor",
        "message": message,
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "details": {
            "monitor": monitor_name,
            "ack_minutes": threshold["ack_minutes"],
            "notify_channels": threshold["notify_channels"],
            "severity_description": threshold["description"],
            **details,
        },
    }
    if on_call:
        payload["details"]["on_call_runbook"] = on_call
    return payload


def cmd_run(args: argparse.Namespace) -> int:
    """运行 8 件套监控 + 生成报告."""
    scripts_dir = discover_scripts_dir()
    results = []
    for monitor in MONITORS:
        result = run_monitor(monitor, scripts_dir, args.dry_run)
        results.append(result)

    failed = [r for r in results if r.status != "ok"]
    critical_failed = [r for r in failed if r.severity == "critical"]

    saas_status = verify_saas_layers(ROOT)

    report = {
        "ran_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "monitors_total": len(MONITORS),
        "monitors_ok": sum(1 for r in results if r.status == "ok"),
        "monitors_failed": len(failed),
        "critical_failed": [r.name for r in critical_failed],
        "results": [
            {
                "name": r.name,
                "status": r.status,
                "severity": r.severity,
                "exit_code": r.exit_code,
                "duration_ms": r.duration_ms,
            }
            for r in results
        ],
        "saas_layers": saas_status,
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if critical_failed:
        for r in critical_failed:
            fault_type = r.name.replace("monitor-", "").replace(".sh", "").replace("-", "_")
            runbook = get_on_call_runbook(fault_type)
            alert = generate_alert_payload(
                monitor_name=r.name,
                severity="critical",
                message=f"Commercial operation monitor CRITICAL: {r.name}",
                details={"exit_code": r.exit_code, "stderr": r.stderr[:200]},
                on_call=runbook,
            )
            print(f"ALERT [{r.severity}] {r.name}: {alert['message']}")
            print(f"  notify_channels: {alert['details']['notify_channels']}")
            print(f"  ack_minutes: {alert['details']['ack_minutes']}")
            print(f"  first_action: {runbook['first_action']}")
        return 1

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """列出 8 件套监控清单."""
    print(f"Total {len(MONITORS)} monitors:")
    for i, m in enumerate(MONITORS, 1):
        print(f"  {i}. {m['name']} ({m['w_batch']})")
        print(f"     scope: {m['scope']}")
        print(f"     severity: {m['severity_default']} | interval: {m['interval_min']}min")
    return 0


def cmd_thresholds(args: argparse.Namespace) -> int:
    """列出 4 级 severity 报警阈值 + 通知渠道 + ack SLA."""
    print(json.dumps(ALERT_THRESHOLDS, ensure_ascii=False, indent=2))
    return 0


def cmd_oncall(args: argparse.Namespace) -> int:
    """列出 5 类 on-call 实战 runbook."""
    print(json.dumps(ON_CALL_RUNBOOK, ensure_ascii=False, indent=2))
    return 0


def cmd_saas(args: argparse.Namespace) -> int:
    """验证 SaaS 4 层架构关键文件存在."""
    status = verify_saas_layers(ROOT)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["all_ok"] else 1


def cmd_alert_smoke(args: argparse.Namespace) -> int:
    """烟雾测试: 生成一份示例 alert payload (不实际发 webhook, 仅 verify 字段)."""
    runbook = ON_CALL_RUNBOOK["alembic_double_head"]
    payload = generate_alert_payload(
        monitor_name="monitor-alembic-heads.sh",
        severity="critical",
        message="smoke test alert",
        details={"test": True, "head_count": 2},
        on_call=runbook,
    )
    required_fields = {"severity", "source", "message", "timestamp", "details"}
    missing = required_fields - set(payload.keys())
    if missing:
        print(f"FAIL: payload missing fields: {missing}", file=sys.stderr)
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="W79 第 1 批 B-1 商业化运营监控 (8 件套监控 + 报警 + 通知 + on-call + SaaS)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="运行 8 件套监控")
    p_run.add_argument("--dry-run", action="store_true", help="dry-run 模式 (不实际执行 shell)")
    p_run.set_defaults(func=cmd_run)

    p_list = sub.add_parser("list", help="列出监控清单")
    p_list.set_defaults(func=cmd_list)

    p_thr = sub.add_parser("thresholds", help="列出报警阈值")
    p_thr.set_defaults(func=cmd_thresholds)

    p_oncall = sub.add_parser("oncall", help="列出 on-call runbook")
    p_oncall.set_defaults(func=cmd_oncall)

    p_saas = sub.add_parser("saas", help="验证 SaaS 4 层架构关键文件")
    p_saas.set_defaults(func=cmd_saas)

    p_smoke = sub.add_parser("alert-smoke", help="烟雾测试 alert payload 字段完整")
    p_smoke.set_defaults(func=cmd_alert_smoke)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())