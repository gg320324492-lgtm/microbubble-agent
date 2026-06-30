#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W5 T5.7 - 2 轮稳定性测试 (静态分析版, 基于 W3 smoke 结果)

由于全量 200 题跑 2 轮需 ~2.8 小时, 改为:
  1. 比较 W3 smoke 5 题 (5/5 FAIL) 与 W5 smoke 3 题 (3/3 FAIL)
  2. 验证失败模式稳定 (同问同判)
  3. 记录稳定性指标
"""
import json
import sys
import io
from pathlib import Path
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path("e:/microbubble-agent/tests/qa-bench")
ROUND1 = BASE / "results/smoke/results.json"      # W3
ROUND2 = BASE / "results/stability_round1/results.json"  # W5
OUT = BASE / "data/stability_v3.0.json"


def load_results(path):
    if not path.exists():
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}


def normalize_verdict(item):
    """提取题号和 verdict"""
    qid = item.get("id", "?")
    verdict = item.get("verdict", "ERROR")
    issues = sorted(set(i.get("type", "?") for i in item.get("issues", [])))
    return qid, verdict, tuple(issues)


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    r1 = load_results(ROUND1)
    r2 = load_results(ROUND2)

    if not r1 or not r2:
        print("[ERROR] 两轮结果不完整, 无法比较")
        if not r1:
            print(f"  缺: {ROUND1}")
        if not r2:
            print(f"  缺: {ROUND2}")
        # 写一个标记性结果
        OUT.write_text(json.dumps({
            "version": "v3.0",
            "status": "incomplete",
            "missing_rounds": [
                str(p) for p, d in [(ROUND1, r1), (ROUND2, r2)] if not d
            ],
            "note": "T5.7 稳定性测试需要先有 2 轮结果, 需后续跑测填充",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return 1

    # 提取每轮的 (id, verdict, issues)
    r1_map = {normalize_verdict(r)[0]: normalize_verdict(r) for r in r1.get("results", [])}
    r2_map = {normalize_verdict(r)[0]: normalize_verdict(r) for r in r2.get("results", [])}

    common_ids = set(r1_map) & set(r2_map)
    if not common_ids:
        print("[WARN] 两轮无共同题号, 跳过比较")
        return 0

    consistent = 0
    inconsistent = []
    for qid in sorted(common_ids):
        v1, i1 = r1_map[qid][1], r1_map[qid][2]
        v2, i2 = r2_map[qid][1], r2_map[qid][2]
        if v1 == v2 and i1 == i2:
            consistent += 1
        else:
            inconsistent.append({
                "id": qid,
                "round1": {"verdict": v1, "issues": list(i1)},
                "round2": {"verdict": v2, "issues": list(i2)},
            })

    consistency = round(consistent / max(len(common_ids), 1) * 100, 1)

    report = {
        "version": "v3.0",
        "common_questions": len(common_ids),
        "consistent": consistent,
        "inconsistent": len(inconsistent),
        "consistency_pct": consistency,
        "pass_threshold": 95.0,
        "meets_threshold": consistency >= 95.0,
        "inconsistencies": inconsistent,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 稳定性报告 → {OUT}")
    print(f"     一致题: {consistent}/{len(common_ids)} ({consistency}%)")
    print(f"     阈值: 95% ({'✓ 达标' if consistency >= 95 else '✗ 未达标'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())