"""对比 4 轮 Self-RAG benchmark 数据.

用法:
  python scripts/compare_self_rag_rounds.py \\
    --r1 tests/qa-bench/results/self-rag-benchmark/round1-off/results.json \\
    --r2 tests/qa-bench/results/self-rag-benchmark/round2-on/results.json \\
    --r3 tests/qa-bench/results/self-rag-benchmark/round3-balanced-selfrag-on-<ts>/results.json \\
    --r4 tests/qa-bench/results/self-rag-benchmark/round4-balanced-selfrag-off-<ts>/results.json

输出:
  - 每轮: 总数/OK/ERR/pass_rate/avg/p50/p95/max/retrieval_assessment 触发率
  - per-category pass rate (A-F 6 大类)
  - 4 轮横向对比表 (markdown)
"""

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_round(path: Path) -> dict:
    """加载一轮结果, 返回聚合统计."""
    if not path.exists():
        print(f"WARN: {path} 不存在, 跳过", file=sys.stderr)
        return {"total": 0, "ok": 0, "err": 0, "results": []}
    d = json.load(open(path, encoding="utf-8"))
    results = d.get("results", [])
    if not isinstance(results, list):
        results = []
    ok = sum(1 for r in results if r and "content" in r)
    err = len(results) - ok
    durs = [r.get("duration_ms") or int((r.get("duration_s") or 0) * 1000) for r in results if "content" in r]
    retrievals = [r for r in results if r.get("retrieval")]
    retrieval_ids = [r["id"] for r in retrievals]

    # per-category pass rate
    cat_stats = defaultdict(lambda: {"total": 0, "ok": 0})
    for r in results:
        cat = r.get("category", "?")
        cat_stats[cat]["total"] += 1
        if "content" in r:
            cat_stats[cat]["ok"] += 1

    return {
        "path": str(path),
        "total": len(results),
        "ok": ok,
        "err": err,
        "pass_rate": 100 * ok / max(1, len(results)),
        "durations": durs,
        "retrieval_count": len(retrievals),
        "retrieval_ids": retrieval_ids,
        "cat_stats": dict(cat_stats),
        "results": results,
    }


def summarize(name: str, s: dict) -> str:
    """格式化为单行 markdown 摘要."""
    if s["total"] == 0:
        return f"| {name} | (skip) | - | - | - | - | - | - | - |"
    durs = s["durations"]
    if durs:
        durs_sorted = sorted(durs)
        avg = sum(durs) / len(durs)
        p50 = durs_sorted[len(durs_sorted) // 2]
        p95 = durs_sorted[int(len(durs_sorted) * 0.95)] if len(durs_sorted) > 1 else durs_sorted[0]
        mx = max(durs)
    else:
        avg = p50 = p95 = mx = 0
    return (
        f"| {name} | {s['total']} | {s['ok']} | {s['err']} | "
        f"{s['pass_rate']:.1f}% | {avg:.0f}ms | {p50:.0f}ms | {p95:.0f}ms | {mx:.0f}ms | "
        f"{s['retrieval_count']} ({100*s['retrieval_count']/s['total']:.1f}%) |"
    )


def per_cat_table(name: str, s: dict, all_cats: list[str]) -> str:
    """per-category pass rate 表."""
    if s["total"] == 0:
        return f"\n### {name} (skip)\n"
    lines = [f"\n### {name}", "| Category | Total | OK | Pass Rate |", "|---|---|---|---|"]
    for cat in all_cats:
        if cat in s["cat_stats"]:
            st = s["cat_stats"][cat]
            rate = 100 * st["ok"] / max(1, st["total"])
            lines.append(f"| {cat} | {st['total']} | {st['ok']} | {rate:.1f}% |")
        else:
            lines.append(f"| {cat} | 0 | 0 | - |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--r1", required=False, default="")
    ap.add_argument("--r2", required=False, default="")
    ap.add_argument("--r3", required=False, default="")
    ap.add_argument("--r4", required=False, default="")
    args = ap.parse_args()

    rounds = []
    labels = []
    if args.r1:
        rounds.append(load_round(Path(args.r1))); labels.append("R1 (anthropic SelfRAG OFF)")
    if args.r2:
        rounds.append(load_round(Path(args.r2))); labels.append("R2 (anthropic SelfRAG ON)")
    if args.r3:
        rounds.append(load_round(Path(args.r3))); labels.append("R3 (ollama balanced SelfRAG ON)")
    if args.r4:
        rounds.append(load_round(Path(args.r4))); labels.append("R4 (ollama balanced SelfRAG OFF)")

    if not rounds:
        print("ERROR: 至少传 1 轮 --r1..--r4", file=sys.stderr)
        sys.exit(1)

    # 收集所有出现过的 category
    all_cats = sorted({c for s in rounds for c in s.get("cat_stats", {}).keys()})

    # 1. 主对比表
    print("\n## 总览对比\n")
    print("| Round | Total | OK | ERR | Pass Rate | Avg | p50 | p95 | Max | Retrieval Assess |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for label, s in zip(labels, rounds):
        print(summarize(label, s))

    # 2. per-category
    for label, s in zip(labels, rounds):
        print(per_cat_table(label, s, all_cats))

    # 3. Retrieval Assessment 详情
    print("\n## Retrieval Assessment 触发详情\n")
    for label, s in zip(labels, rounds):
        print(f"\n### {label}: {s['retrieval_count']} 次触发\n")
        if s["retrieval_ids"]:
            print(f"题目 IDs: {', '.join(s['retrieval_ids'][:20])}{' ...' if len(s['retrieval_ids'])>20 else ''}")

    # 4. 决策建议（自动算 Self-RAG ON vs OFF delta）
    print("\n## Self-RAG ON vs OFF Delta (同 backend 内对比)\n")
    # 配对: R2 vs R1 (anthropic), R3 vs R4 (ollama)
    pairs = []
    if len(rounds) >= 2 and "anthropic" in labels[0]:
        pairs.append(("anthropic (R2-R1)", rounds[1], rounds[0]))
    if len(rounds) >= 4:
        pairs.append(("ollama (R3-R4)", rounds[2], rounds[3]))

    for tag, on, off in pairs:
        if on["total"] == 0 or off["total"] == 0:
            continue
        pass_delta = on["pass_rate"] - off["pass_rate"]
        if on["durations"] and off["durations"]:
            avg_delta = (sum(on["durations"])/len(on["durations"])) - (sum(off["durations"])/len(off["durations"]))
            p95_delta = sorted(on["durations"])[int(len(on["durations"])*0.95)] - sorted(off["durations"])[int(len(off["durations"])*0.95)]
        else:
            avg_delta = p95_delta = 0
        print(f"\n### {tag}")
        print(f"- Pass rate: ON {on['pass_rate']:.1f}% vs OFF {off['pass_rate']:.1f}% → Δ {pass_delta:+.1f}%")
        print(f"- Avg latency: ON {sum(on['durations'])/len(on['durations']):.0f}ms vs OFF {sum(off['durations'])/len(off['durations']):.0f}ms → Δ {avg_delta:+.0f}ms")
        print(f"- p95 latency: ON {sorted(on['durations'])[int(len(on['durations'])*0.95)]:.0f}ms vs OFF {sorted(off['durations'])[int(len(off['durations'])*0.95)]:.0f}ms → Δ {p95_delta:+.0f}ms")
        print(f"- Retrieval assessment: ON 触发 {on['retrieval_count']}/{on['total']} ({100*on['retrieval_count']/on['total']:.1f}%) vs OFF 触发 {off['retrieval_count']}/{off['total']}")


if __name__ == "__main__":
    main()