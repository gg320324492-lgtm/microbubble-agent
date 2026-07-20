#!/usr/bin/env python3
"""2026-07-13 #P1: 三档推理模式 benchmark — 跑题库 + 切 3 个 mode + 输出 7 维分数对比表。

用法：
  1. 启 fast 配置 app (LLM_BACKEND=ollama, OLLAMA_MODEL=qwen3:8b) on port 8001
  2. 启 balanced 配置 (同上, 默认 settings) on port 8002
  3. 启 deep 配置 (OLLAMA_MODEL=deepseek-r1-distill-qwen:7b) on port 8003
  4. python scripts/benchmark_fast_vs_deep.py \
       --questions tests/qa-bench/questions_fast_vs_deep.jsonl \
       --api-base-fast http://localhost:8001 \
       --api-base-balanced http://localhost:8002 \
       --api-base-deep http://localhost:8003 \
       --output docs/benchmarks/fast-vs-deep-2026-07-13.md

  或简化的单 mode 跑（只跑 fast + balanced）:
  python scripts/benchmark_fast_vs_deep.py --modes fast balanced \
       --output /tmp/fast-vs-balanced.md

输出：Markdown 表格含
- 各 mode 的 avg_latency_ms / avg_input_tokens / avg_output_tokens
- 7 维分 (intent / tool / content / rich / defense / perf / consistency)
- thinking_tokens_used (deep 模式预期 > 0)
- cost_estimate_usd (粗估)
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_questions(path: Path) -> List[Dict[str, Any]]:
    """加载题库 jsonl, 每行一个 JSON。"""
    questions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            questions.append(json.loads(line))
    return questions


async def run_one_mode(
    api_base: str,
    questions: List[Dict[str, Any]],
    mode: str,
    concurrency: int = 4,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """对一个 mode 跑全部题, 返回每个题的结果列表。

    复用 tests/qa-bench/runner.py 的 parse_sse + score_seven_dim
    """
    sys.path.insert(0, str(Path(__file__).parent.parent / "tests" / "qa-bench"))
    # qa-bench 不是 package (无 __init__.py), 直接 import runner
    from runner import run_single_question, score_seven_dim

    import httpx

    results = []
    sem = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(timeout=httpx.Timeout(90.0)) as client:
        async def _run_one(q):
            async with sem:
                qid = q.get("id", "?")
                # 注入 thinking_mode
                q_with_mode = dict(q)
                q_with_mode["thinking_mode"] = mode
                t0 = time.monotonic()
                try:
                    result = await run_single_question(
                        client=client,
                        question_data=q_with_mode,
                        token=token or "",
                    )
                    result["mode"] = mode
                    result["duration_ms"] = int((time.monotonic() - t0) * 1000)
                    # 7 维评分
                    result["score"] = score_seven_dim(result)
                    return result
                except Exception as e:
                    return {
                        "id": qid, "mode": mode,
                        "error": str(e)[:200],
                        "duration_ms": int((time.monotonic() - t0) * 1000),
                    }

        tasks = [_run_one(q) for q in questions]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    return results


def compute_stats(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """聚合一个 mode 的统计。"""
    latencies = [r.get("duration_ms", 0) for r in results if "duration_ms" in r]
    input_toks = []
    output_toks = []
    thinking_toks = []
    scores = []

    for r in results:
        usage = r.get("usage") or {}
        if "input_tokens" in usage:
            input_toks.append(usage["input_tokens"])
        if "output_tokens" in usage:
            output_toks.append(usage["output_tokens"])
        if "thinking_tokens" in usage:
            thinking_toks.append(usage["thinking_tokens"])
        if "score" in r and isinstance(r["score"], dict):
            # 7 维分取 mean
            s = r["score"]
            if s:
                scores.append(statistics.mean(s.values()))

    def _stats(xs: List[float]) -> Dict[str, float]:
        if not xs:
            return {"count": 0, "avg": 0, "p50": 0, "p95": 0, "max": 0}
        xs_sorted = sorted(xs)
        n = len(xs_sorted)
        return {
            "count": n,
            "avg": round(statistics.mean(xs_sorted), 2),
            "p50": round(xs_sorted[n // 2], 2),
            "p95": round(xs_sorted[min(int(n * 0.95), n - 1)], 2),
            "max": round(max(xs_sorted), 2),
        }

    return {
        "count": len(results),
        "error_count": sum(1 for r in results if "error" in r),
        "latency_ms": _stats(latencies),
        "input_tokens": _stats(input_toks),
        "output_tokens": _stats(output_toks),
        "thinking_tokens": _stats(thinking_toks),
        "seven_dim_avg": _stats(scores),
    }


def render_markdown(mode_stats: Dict[str, Dict[str, Any]], questions: List[Dict]) -> str:
    """渲染对比 Markdown。"""
    lines = []
    lines.append("# Fast vs Balanced vs Deep 推理模式 Benchmark")
    lines.append("")
    lines.append(f"生成时间: {datetime.now().isoformat()}")
    lines.append(f"题数: {len(questions)}")
    lines.append("")
    lines.append("## 延迟对比")
    lines.append("")
    lines.append("| Mode | 题目数 | 平均延迟 (ms) | p50 | p95 | 最大 | 错误数 |")
    lines.append("|------|--------|---------------|-----|-----|------|--------|")
    for mode, stats in mode_stats.items():
        s = stats["latency_ms"]
        lines.append(
            f"| {mode} | {stats['count']} | {s['avg']} | {s['p50']} | {s['p95']} | {s['max']} | {stats['error_count']} |"
        )
    lines.append("")

    lines.append("## Token 使用")
    lines.append("")
    lines.append("| Mode | input_tokens avg | output_tokens avg | thinking_tokens avg |")
    lines.append("|------|------------------|-------------------|----------------------|")
    for mode, stats in mode_stats.items():
        i = stats["input_tokens"]
        o = stats["output_tokens"]
        t = stats["thinking_tokens"]
        lines.append(
            f"| {mode} | {i['avg']} (n={i['count']}) | {o['avg']} (n={o['count']}) | {t['avg']} (n={t['count']}) |"
        )
    lines.append("")

    lines.append("## 7 维分平均 (intent/tool/content/rich/defense/perf/consistency)")
    lines.append("")
    lines.append("| Mode | 平均分 | p50 | p95 |")
    lines.append("|------|--------|-----|-----|")
    for mode, stats in mode_stats.items():
        s = stats["seven_dim_avg"]
        lines.append(
            f"| {mode} | {s['avg']} | {s['p50']} | {s['p95']} |"
        )
    lines.append("")

    # 按 category 分组统计
    lines.append("## 按 category 分组 (7 维分平均)")
    lines.append("")
    cats = sorted(set(q.get("category", "unknown") for q in questions))
    lines.append("| Mode | " + " | ".join(cats) + " |")
    lines.append("|------|" + "|".join(["---"] * len(cats)) + "|")
    for mode, _ in mode_stats.items():
        # 这里需要每个 mode 的 per-category 分数, 简化先留空
        lines.append(f"| {mode} | (略) |")
    lines.append("")
    lines.append("## 结论 (自动生成)")
    lines.append("")
    lines.append("- deep 模式应该 thinking_tokens_used > 0")
    lines.append("- deep 模式应该 7 维分在 deep_concept 类题 ≥ fast 5%")
    lines.append("- fast 模式应该延迟 < balanced < deep")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="Fast vs Balanced vs Deep benchmark")
    parser.add_argument("--questions", default="tests/qa-bench/questions_fast_vs_deep.jsonl")
    parser.add_argument("--modes", nargs="+", default=["fast", "balanced", "deep"],
                        choices=["fast", "balanced", "deep"])
    parser.add_argument("--api-base-fast", default="http://localhost:8001")
    parser.add_argument("--api-base-balanced", default="http://localhost:8002")
    parser.add_argument("--api-base-deep", default="http://localhost:8003")
    parser.add_argument("--token", default=None)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", default=None, help="Markdown 输出文件路径")
    parser.add_argument("--dry-run", action="store_true", help="只 print 配置不实际跑")
    args = parser.parse_args()

    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"ERROR: 题库不存在: {questions_path}", file=sys.stderr)
        sys.exit(1)
    questions = load_questions(questions_path)
    print(f"Loaded {len(questions)} questions from {questions_path}")

    api_bases = {
        "fast": args.api_base_fast,
        "balanced": args.api_base_balanced,
        "deep": args.api_base_deep,
    }

    if args.dry_run:
        print(f"\n[DRY-RUN] 配置:")
        for mode in args.modes:
            print(f"  {mode}: {api_bases[mode]}")
        print(f"  questions: {questions_path}")
        return

    # 逐 mode 跑
    mode_stats = {}
    mode_results = {}
    for mode in args.modes:
        print(f"\n[{mode}] 跑 {len(questions)} 题 @ {api_bases[mode]}")
        os.environ["THINKING_MODE"] = mode
        results = await run_one_mode(
            api_base=api_bases[mode],
            questions=questions,
            mode=mode,
            concurrency=args.concurrency,
            token=args.token,
        )
        mode_results[mode] = results
        stats = compute_stats(results)
        mode_stats[mode] = stats
        print(f"  完成: {stats['count']} 题, {stats['error_count']} 错误, "
              f"avg 延迟 {stats['latency_ms']['avg']}ms")

    md = render_markdown(mode_stats, questions)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(md, encoding="utf-8")
        print(f"\n报告写入: {args.output}")
    else:
        print("\n" + md)


if __name__ == "__main__":
    asyncio.run(main())