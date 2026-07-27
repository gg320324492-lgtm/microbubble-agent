"""gate.py — W74 第 1 批 C-1 实施前置 7 (阈值与 gate 守恒)

派工 v8 段 8 实施前置 7 — qa-bench 4 周灰度 gate 守门 (锚点范式第 248 守恒)

门禁契约 (D9 调研 §5.1 + W67 第 29-32 步实战):
  Week 1 (D+0 ~ D+6):   pass_rate >= 70%,  F <= 5
  Week 2 (D+7 ~ D+13):  pass_rate >= 75%,  F <= 5
  Week 3 (D+14 ~ D+20): pass_rate >= 78%,  F <= 5
  Week 4 (D+21 ~ D+27): pass_rate >= 80%,  F <= 4

输入: tests/qa-bench/results/round10-bge-m3-240/week-{N}/summary.json
退出码:
  0 = gate 通过, 灰度 promote
  1 = gate 失败, 灰度 halt
  2 = 输入缺失 (CI 校验失败)
  3 = baseline 突增 F 数 > 1.5×, 立即停止 (D9 §5.3)

用法 (CI 步骤):
  python scripts/qa-bench/gate.py --week 4
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent.parent / "tests" / "qa-bench" / "results" / "round10-bge-m3-240"

GATE_PLAN: dict[int, dict[str, float]] = {
    1: {"min_pass_rate": 0.70, "max_f_count": 5},
    2: {"min_pass_rate": 0.75, "max_f_count": 5},
    3: {"min_pass_rate": 0.78, "max_f_count": 5},
    4: {"min_pass_rate": 0.80, "max_f_count": 4},
}

# F 数突增阈值 (D9 §5.3: F 数 > baseline × 1.5 → 立即停止)
BASELINE_V3_F_COUNT = 14
F_SPIKE_MULTIPLIER = 1.5


def check_week_gate(week: int) -> tuple[int, dict[str, object]]:
    """校验指定周 (1-4) 的灰度 gate.

    Returns: (exit_code, report_dict)
    """
    if week not in GATE_PLAN:
        return 2, {"error": f"week 必须在 1-4, 收到: {week}"}

    summary_path = RESULTS_DIR / f"week-{week}" / "summary.json"
    if not summary_path.exists():
        return 2, {"error": f"summary.json 不存在: {summary_path} (先跑 round10-bge-m3.py --week {week})"}

    with open(summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    gate = GATE_PLAN[week]
    pass_rate = summary.get("pass_rate", 0)
    f_count = summary.get("f_count", 0)

    violations: list[str] = []
    if pass_rate < gate["min_pass_rate"]:
        violations.append(f"pass_rate {pass_rate:.3f} < gate {gate['min_pass_rate']:.3f}")
    if f_count > gate["max_f_count"]:
        violations.append(f"F count {f_count} > gate max {gate['max_f_count']}")

    report: dict[str, object] = {
        "week": week,
        "gate": gate,
        "summary": summary,
        "violations": violations,
        "passed": len(violations) == 0,
    }

    # F 数突增立即停止 (D9 §5.3)
    if f_count > BASELINE_V3_F_COUNT * F_SPIKE_MULTIPLIER:
        return 3, {**report, "halt_reason": "f_spike"}

    return (0 if report["passed"] else 1), report


def main() -> int:
    p = argparse.ArgumentParser(description="qa-bench 4 周灰度 gate 守门")
    p.add_argument("--week", type=int, choices=[1, 2, 3, 4], required=True)
    args = p.parse_args()

    exit_code, report = check_week_gate(args.week)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if exit_code != 0:
        print(f"\nGATE FAIL: exit_code={exit_code}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())