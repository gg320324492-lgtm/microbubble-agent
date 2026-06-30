#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""W5 T5.6 - 回归基线 v3.0 锁定（smoke 200 题分数快照）

输入: tests/qa-bench/results/smoke/results.json (W3 实测 5 题) + W5 静态分析
输出: data/regression_baseline_v3.0.json (锁定)
"""
import json
import sys
import io
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = Path("e:/microbubble-agent/tests/qa-bench")
SMOKE_RESULTS = BASE / "results/smoke/results.json"
SMOKE_200 = BASE / "questions_smoke_200.jsonl"
OUT_BASELINE = BASE / "data/regression_baseline_v3.0.json"


def main():
    OUT_BASELINE.parent.mkdir(parents=True, exist_ok=True)
    smoke_200 = [json.loads(l) for l in open(SMOKE_200, encoding="utf-8")]
    cat_dist = Counter(q["category"] for q in smoke_200)

    baseline = {
        "version": "v3.0",
        "lock_date": datetime.now().isoformat(),
        "total_questions": len(smoke_200),
        "category_distribution": dict(cat_dist),
        "note": "T5.6 回归基线锁定 (200 题 smoke 套件, 全 12 业务域 + P/K 覆盖)",
        "smoke_5_run": {},
        "thresholds": {
            "pass_rate_min": 80.0,  # 低于 80% 阻断 merge
            "ttft_p95_max_s": 8.0,
            "duration_p95_max_s": 60.0,
            "veto_count_max": 2,  # 一票否决次数
        },
    }

    # 合并 W3 smoke 5 题实测结果
    if SMOKE_RESULTS.exists():
        try:
            r = json.load(open(SMOKE_RESULTS, encoding="utf-8"))
            sm = r.get("summary", {})
            baseline["smoke_5_run"] = {
                "timestamp": sm.get("timestamp"),
                "total": sm.get("total"),
                "pass": sm.get("pass"),
                "warn": sm.get("warn"),
                "fail": sm.get("fail"),
                "error": sm.get("error"),
                "pass_rate": round(sm.get("pass", 0) / max(sm.get("total", 1), 1) * 100, 1),
            }
        except Exception as e:
            baseline["smoke_5_run"] = {"parse_error": str(e)}

    OUT_BASELINE.write_text(json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] 回归基线锁定 → {OUT_BASELINE}")
    print(f"     smoke 套件: {len(smoke_200)} 题")
    print(f"     通过率阈值: {baseline['thresholds']['pass_rate_min']}%")
    if "pass_rate" in baseline["smoke_5_run"]:
        print(f"     W3 5 题实测: {baseline['smoke_5_run']['pass_rate']}%")


if __name__ == "__main__":
    main()