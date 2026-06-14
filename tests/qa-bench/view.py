"""
qa-bench/inspect.py — 读 results.json 显示指定 qid 的详情（utf-8 干净输出）
"""
import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", default="results/smoke/results.json")
    parser.add_argument("--qid", help="只看指定 qid（不填则全显示）")
    parser.add_argument("--fail-only", action="store_true")
    args = parser.parse_args()

    with open(args.results, encoding="utf-8") as f:
        d = json.load(f)

    for r in d["results"]:
        if args.qid and r["id"] != args.qid:
            continue
        if args.fail_only and r.get("verdict") not in ("FAIL", "WARN"):
            continue
        print(f"\n{'='*70}")
        print(f"{r['id']} ({r['category']}) — {r.get('verdict', 'ERROR')}")
        print(f"问题: {r.get('question', '')}")
        if "error" in r:
            print(f"Error: {r['error']}")
            continue
        a = r.get("actual", {})
        print(f"intent: {a.get('intent')}")
        print(f"tools: {a.get('tools_called')}")
        print(f"grounded_names: {a.get('grounded_names')}")
        print(f"critique_score: {a.get('critique_score')}")
        print(f"duration_ms: {a.get('duration_ms')}")
        print(f"issues: {[i['type'] for i in r.get('issues', [])]}")
        content = a.get("content", "")
        print(f"--- 回答 ({len(content)} 字符) ---")
        print(content[:1500])
        if len(content) > 1500:
            print(f"... (后 {len(content)-1500} 字符省略)")


if __name__ == "__main__":
    main()
