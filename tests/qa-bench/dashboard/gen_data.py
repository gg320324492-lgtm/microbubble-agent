"""
dashboard/gen_data.py — 把 runner.py 输出的 results.json 转换为 Dashboard data.json

用法：
  python tests/qa-bench/dashboard/gen_data.py \
      --input results/run-2026-06-30/results.json \
      --output tests/qa-bench/dashboard/data.json
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="生成 Dashboard data.json")
    parser.add_argument("--input", "-i", required=True, help="runner.py 的 results.json 路径")
    parser.add_argument("--output", "-o", default="tests/qa-bench/dashboard/data.json",
                        help="输出 data.json 路径")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open(encoding="utf-8") as f:
        full = json.load(f)

    summary = full.get("summary", {})
    results = full.get("results", [])

    # === 按 category 聚合 ===
    by_category = defaultdict(lambda: {
        "pass": 0, "warn": 0, "fail": 0, "error": 0, "total": 0,
        "avg_score": 0, "scores": []
    })
    for r in results:
        cat = r.get("category", "unknown")
        by_category[cat]["total"] += 1
        v = r.get("verdict", "ERROR").lower()
        if v == "error":
            v = "error"
        by_category[cat][v] = by_category[cat].get(v, 0) + 1
        if "seven_dim" in r:
            by_category[cat]["scores"].append(r["seven_dim"]["total_score"])

    for cat, stats in by_category.items():
        if stats["scores"]:
            stats["avg_score"] = round(sum(stats["scores"]) / len(stats["scores"]), 1)
        del stats["scores"]  # 不暴露原始分数

    # === 按 difficulty 聚合 ===
    by_difficulty = defaultdict(lambda: {"pass": 0, "warn": 0, "fail": 0, "error": 0, "total": 0})
    for r in results:
        diff = r.get("difficulty", "unknown")
        by_difficulty[diff]["total"] += 1
        v = r.get("verdict", "ERROR").lower()
        if v == "error":
            v = "error"
        by_difficulty[diff][v] = by_difficulty[diff].get(v, 0) + 1

    # === 7 维分维度均分 ===
    seven_dim = summary.get("seven_dim", {})

    # === Issue 分布（按类型 + 频次）===
    issue_dist = summary.get("issue_distribution", {})

    # === 失败题 TOP 20 ===
    failed_questions = [
        {
            "id": r.get("id"),
            "category": r.get("category"),
            "difficulty": r.get("difficulty"),
            "verdict": r.get("verdict"),
            "question": r.get("question", "")[:80],
            "issues": [i.get("type") for i in r.get("issues", [])],
            "score": r.get("seven_dim", {}).get("total_score", 0),
            "grade": r.get("seven_dim", {}).get("grade", "?"),
        }
        for r in results
        if r.get("verdict") in ("FAIL", "WARN")
    ]
    failed_questions.sort(key=lambda r: r.get("score", 100))  # 最差优先
    failed_top20 = failed_questions[:20]

    # === 雷达图数据 (7 维归一化 0-100) ===
    radar_data = []
    for k, v in seven_dim.get("dim_avg", {}).items():
        radar_data.append({"dim": k, "score": round(v * 100, 1)})

    # === 输出 data.json ===
    data = {
        "metadata": {
            "title": "小气助手能力测评 Dashboard v3.0",
            "timestamp": summary.get("timestamp"),
            "total_questions": summary.get("total", 0),
            "pass": summary.get("pass", 0),
            "warn": summary.get("warn", 0),
            "fail": summary.get("fail", 0),
            "error": summary.get("error", 0),
            "pass_rate": round(
                summary.get("pass", 0) / max(summary.get("total", 1), 1) * 100, 1
            ),
        },
        "by_category": dict(by_category),
        "by_difficulty": dict(by_difficulty),
        "seven_dim": seven_dim,
        "radar_data": radar_data,
        "issue_distribution": issue_dist,
        "failed_top20": failed_top20,
    }

    output_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ Dashboard data 已生成: {output_path}")
    print(f"  测评时间: {summary.get('timestamp', 'N/A')}")
    print(f"  总题数: {summary.get('total', 0)} (PASS={summary.get('pass', 0)} WARN={summary.get('warn', 0)} FAIL={summary.get('fail', 0)})")
    print(f"  7 维分: {seven_dim.get('dim_avg', {})}")


if __name__ == "__main__":
    main()
