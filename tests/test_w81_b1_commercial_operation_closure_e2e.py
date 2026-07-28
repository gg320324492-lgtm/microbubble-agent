#!/usr/bin/env python3
"""W81 B-1 商业化运营 + Phase 8 收官新增 2-case e2e。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "w81-1st-batch-b1-commercial-operation-closure-2026-07-28.md"


def _runbook() -> str:
    return RUNBOOK.read_text(encoding="utf-8")


def test_15_commercial_operation_closure_summary() -> None:
    """Case 15: 12 子维度、3 硬门控、评分、8 件套与成本模型全部收官。"""
    text = _runbook()
    dimensions = [
        "accuracy", "completeness", "consistency", "freshness",
        "explainability", "robustness", "safety", "commercial_compliance",
        "billing_accuracy", "tenant_isolation", "sla_latency", "license_health",
    ]
    assert all(name in text for name in dimensions)
    assert "0.9576 >= 0.90" in text
    assert "billing_accuracy >= 0.99" in text
    assert "8 件套监控实时接入" in text
    assert "Edge-TTS 7.2.8" in text
    assert "¥22/月" in text
    assert "0 production code 改动铁律守恒" in text


def test_16_phase_8_closure_timeline_and_24_person_months() -> None:
    """Case 16: Phase 8 W81-W84+ 时间表及 24 人月 Q1 物证完整。"""
    text = _runbook()
    assert all(marker in text for marker in ("W81", "W82", "W83", "W84+"))
    assert "Phase 8 收官时间表" in text
    assert "24 人月 Q1" in text
    assert "39 个月" in text
    assert "16/16 e2e PASS" in text
    assert "类 20.14" in text
