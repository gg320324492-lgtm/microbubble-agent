"""W68 D6 Phase 3 matrix 4 runner parallel executor.

This module is the *dedicated* Phase 3 runner.  It owns:

*   Splitting the 1000-question corpus into ``--workers`` shards (default 4
    shards of 250 questions each).
*   Running each shard through the in-process benchmark with bounded
    async concurrency (``--matrix`` controls cross-shard concurrency, default 4).
*   Each shard runs the same 3-round verdict consensus as Phase 2 (majority
    vote per question).
*   Aggregating the per-shard results into a single "phase 3 matrix" report
    that includes per-worker timings, per-intent pass rate and a strict
    "all-4-workers PASS" gate.

The runner deliberately stays inside ``tests/qa-bench/`` (W68 zero
production-code-change rule).  It reuses ``phase2_dry_runner._round_with_concurrency``
and ``inprocess_runner.run_inprocess``; it never imports from ``app/``.

Usage::

    # dry-run fallback (no MIMO_API_KEY in env) -- CI-friendly
    python tests/qa-bench/phase3_matrix_runner.py --dry-run

    # real run against mimo cloud with 4 workers x 4 concurrency
    MIMO_API_KEY=... python tests/qa-bench/phase3_matrix_runner.py --report-out phase3.md

    # custom matrix shape -- 2 workers, 250 concurrency, 95 gate
    python tests/qa-bench/phase3_matrix_runner.py --workers 2 --matrix 8 --gate-threshold 95

The runner returns ``int`` -- ``0`` when *all* workers clear the gate
("matrix PASS"), ``1`` when any worker falls below gate ("matrix FAIL"),
``2`` on abort.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

# Reuse Phase 2 corpus loading + verdict logic + per-question runner.
from phase2_dry_runner import (  # noqa: E402  -- sys.path adjusted above
    PHASE2_CHAT_INTENT_BUCKETS,
    PHASE2_INTENT_BUCKETS,
    _bucket_intent,
    _load_full_corpus,
    _majority_verdict,
    _verdict_from_answer,
)

REPO_ROOT = _QA_BENCH_DIR.parent.parent
DEFAULT_WORKERS = 4
DEFAULT_MATRIX_CONCURRENCY = 4
DEFAULT_GATE_THRESHOLD = 90
DEFAULT_ROUNDS = 3


# ---------------------------------------------------------------------------
# Sharding helpers
# ---------------------------------------------------------------------------


def _shard_questions(
    questions: Sequence[dict[str, Any]],
    workers: int,
) -> list[list[dict[str, Any]]]:
    """Round-robin shuffle the corpus into ``workers`` shards.

    The algorithm uses ``index % workers`` so the assignment is deterministic
    across runs and balanced: for 1000 questions and 4 workers the user
    gets 250 questions per shard.  When the corpus is not evenly divisible
    the last shard absorbs the extra rows (e.g. 1001 / 4 -> 250/250/250/251).
    """

    if workers <= 0:
        raise ValueError(f"workers must be > 0, got {workers}")
    shards: list[list[dict[str, Any]]] = [[] for _ in range(workers)]
    for index, question in enumerate(questions):
        shards[index % workers].append(question)
    return shards


# ---------------------------------------------------------------------------
# Per-worker execution
# ---------------------------------------------------------------------------


async def _run_one_worker(
    worker_id: int,
    shard: Sequence[dict[str, Any]],
    *,
    rounds: int,
    db_url: str,
    matrix_concurrency: int,
) -> dict[str, Any]:
    """Run one shard and return its summary payload."""

    from phase2_dry_runner import _round_with_concurrency

    started = time.monotonic()
    print(
        f"[matrix-worker-{worker_id}] start shard={len(shard)} "
        f"rounds={rounds} concurrency={matrix_concurrency}"
    )
    results = await _round_with_concurrency(
        shard, rounds, db_url, matrix_concurrency
    )
    wall_clock_s = time.monotonic() - started

    verdicts = Counter(r["consensus"] for r in results)
    pass_rate = round(verdicts.get("pass", 0) / max(len(results), 1), 4)
    durations: list[float] = [
        d for r in results for d in r["round_durations_s"]
    ]
    duration_stats: dict[str, float] = {}
    if durations:
        duration_stats = {
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
            "mean": round(statistics.mean(durations), 3),
            "median": round(statistics.median(durations), 3),
            "p95": round(
                statistics.quantiles(durations, n=20)[-1], 3
            )
            if len(durations) >= 20
            else round(max(durations), 3),
        }

    by_intent: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_intent[r["intent"]][r["consensus"]] += 1

    summary = {
        "worker_id": worker_id,
        "shard_size": len(shard),
        "wall_clock_s": round(wall_clock_s, 3),
        "duration_s": duration_stats,
        "verdict_counts": dict(verdicts),
        "pass_rate": pass_rate,
        "by_intent": {
            intent: {
                "counts": dict(counter),
                "pass_rate": round(
                    counter.get("pass", 0) / max(sum(counter.values()), 1), 4
                ),
            }
            for intent, counter in sorted(by_intent.items())
        },
    }
    print(
        f"[matrix-worker-{worker_id}] done in {wall_clock_s:.2f}s "
        f"pass_rate={pass_rate * 100:.1f}% verdict={dict(verdicts)}"
    )
    return summary


async def _run_matrix(
    shards: Sequence[Sequence[dict[str, Any]]],
    *,
    matrix_concurrency: int,
    rounds: int,
    db_url: str,
) -> list[dict[str, Any]]:
    """Run all shards concurrently, bounded by ``matrix_concurrency``."""

    sem = asyncio.Semaphore(matrix_concurrency)

    async def _guarded(worker_id: int, shard: Sequence[dict[str, Any]]) -> dict[str, Any]:
        async with sem:
            return await _run_one_worker(
                worker_id,
                shard,
                rounds=rounds,
                db_url=db_url,
                matrix_concurrency=matrix_concurrency,
            )

    tasks = [
        asyncio.create_task(_guarded(worker_id, shard))
        for worker_id, shard in enumerate(shards)
    ]
    return await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Roll-up aggregation
# ---------------------------------------------------------------------------


def _aggregate_matrix(
    worker_summaries: Sequence[dict[str, Any]],
    *,
    gate_threshold: int,
) -> dict[str, Any]:
    """Combine per-worker summaries into a single matrix roll-up."""

    total_questions = sum(item["shard_size"] for item in worker_summaries)
    combined_counts: Counter = Counter()
    combined_by_intent: dict[str, Counter] = defaultdict(Counter)
    for item in worker_summaries:
        for verdict, count in item["verdict_counts"].items():
            combined_counts[verdict] += count
        for intent, info in item["by_intent"].items():
            for verdict, count in info["counts"].items():
                combined_by_intent[intent][verdict] += count

    pass_rate = round(combined_counts.get("pass", 0) / max(total_questions, 1), 4)
    wall_clocks = [item["wall_clock_s"] for item in worker_summaries]
    slowest_worker_s = max(wall_clocks) if wall_clocks else 0.0
    total_wall_s = sum(wall_clocks)
    serial_estimate_s = sum(
        item["duration_s"].get("mean", 0.0) * item["shard_size"] * 3
        for item in worker_summaries
        if item["duration_s"]
    )
    speedup = round(serial_estimate_s / slowest_worker_s, 2) if slowest_worker_s else 0.0

    # Per-worker gate verdict: each worker must clear gate_threshold on its own.
    per_worker_gate = {
        item["worker_id"]: "PASS"
        if item["pass_rate"] * 100 >= gate_threshold
        else "FAIL"
        for item in worker_summaries
    }
    matrix_gate = "PASS" if all(v == "PASS" for v in per_worker_gate.values()) else "FAIL"

    return {
        "total_questions": total_questions,
        "verdict_counts": dict(combined_counts),
        "pass_rate": pass_rate,
        "by_intent": {
            intent: {
                "counts": dict(counter),
                "pass_rate": round(
                    counter.get("pass", 0) / max(sum(counter.values()), 1), 4
                ),
            }
            for intent, counter in sorted(combined_by_intent.items())
        },
        "wall_clock_s": {
            "max": round(slowest_worker_s, 3),
            "total": round(total_wall_s, 3),
            "serial_estimate_s": round(serial_estimate_s, 3),
            "speedup": speedup,
        },
        "per_worker_gate": per_worker_gate,
        "matrix_gate": matrix_gate,
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_phase3_report(
    rollup: dict[str, Any],
    worker_summaries: Sequence[dict[str, Any]],
    *,
    mode: str,
    workers: int,
    matrix_concurrency: int,
    rounds: int,
    gate_threshold: int,
    started_at: str,
    finished_at: str,
    extra_notes: Sequence[str],
) -> str:
    lines: list[str] = []
    lines.append("# W68 D6 Phase 3 Matrix Report (Auto-generated)")
    lines.append("")
    lines.append(f"- Mode: **{mode}**")
    lines.append(f"- Matrix workers: **{workers}**")
    lines.append(f"- Per-worker concurrency: **{matrix_concurrency}**")
    lines.append(f"- Rounds per question: **{rounds}**")
    lines.append(f"- Gate threshold: **{gate_threshold}%**")
    lines.append(f"- Started: {started_at}")
    lines.append(f"- Finished: {finished_at}")
    lines.append(f"- Total questions: **{rollup['total_questions']}**")
    pass_rate_pct = rollup["pass_rate"] * 100
    lines.append(f"- Combined pass rate: **{pass_rate_pct:.1f}%**")
    lines.append(f"- Matrix gate verdict: **{rollup['matrix_gate']}**")
    lines.append("")

    lines.append("## Wall clock summary")
    lines.append("")
    wc = rollup["wall_clock_s"]
    lines.append(f"- slowest worker: **{wc['max']}s**")
    lines.append(f"- sum-of-shards (serial reference): **{wc['total']}s**")
    lines.append(f"- estimated serial @ mean per question: **{wc['serial_estimate_s']}s**")
    lines.append(f"- estimated speedup: **{wc['speedup']}x**")
    lines.append("")

    lines.append("## Per-worker breakdown")
    lines.append("")
    lines.append("| Worker | Shard size | Wall clock (s) | Pass rate | Gate |")
    lines.append("|---|---|---|---|---|")
    for item in worker_summaries:
        gate = rollup["per_worker_gate"][item["worker_id"]]
        lines.append(
            f"| {item['worker_id']} | {item['shard_size']} | "
            f"{item['wall_clock_s']} | {item['pass_rate'] * 100:.1f}% | {gate} |"
        )
    lines.append("")

    lines.append("## Per-worker verdict counts")
    lines.append("")
    lines.append("| Worker | pass | empty | error | unknown | other |")
    lines.append("|---|---|---|---|---|---|")
    for item in worker_summaries:
        counts = item["verdict_counts"]
        rows = [
            str(counts.get("pass", 0)),
            str(counts.get("empty", 0)),
            str(counts.get("error", 0)),
            str(counts.get("unknown", 0)),
            str(counts.get("other", 0)),
        ]
        lines.append(f"| {item['worker_id']} | " + " | ".join(rows) + " |")
    lines.append("")

    lines.append("## Per-worker latency")
    lines.append("")
    lines.append("| Worker | min (s) | mean (s) | median (s) | p95 (s) | max (s) |")
    lines.append("|---|---|---|---|---|---|")
    for item in worker_summaries:
        d = item["duration_s"]
        if not d:
            lines.append(f"| {item['worker_id']} | n/a | n/a | n/a | n/a | n/a |")
            continue
        lines.append(
            f"| {item['worker_id']} | {d['min']} | {d['mean']} | "
            f"{d['median']} | {d['p95']} | {d['max']} |"
        )
    lines.append("")

    lines.append("## Combined per-intent breakdown")
    lines.append("")
    lines.append("| Intent | Pass rate | Counts |")
    lines.append("|---|---|---|")
    for intent, info in rollup["by_intent"].items():
        counts_str = ", ".join(
            f"{k}={v}" for k, v in sorted(info["counts"].items())
        )
        lines.append(
            f"| {intent} | {info['pass_rate'] * 100:.1f}% | {counts_str} |"
        )
    lines.append("")

    lines.append("## Gate verdict")
    lines.append("")
    lines.append(
        f"Matrix gate: **{rollup['matrix_gate']}** "
        f"(combined pass rate {pass_rate_pct:.1f}% vs "
        f"{gate_threshold}%; every worker must clear gate)."
    )
    lines.append("")
    if extra_notes:
        lines.append("## Notes")
        lines.append("")
        for note in extra_notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dry-run fallback (matches Phase 2 shape)
# ---------------------------------------------------------------------------


def _dry_placeholder_results(
    questions: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": q.get("id"),
            "intent": _bucket_intent(q.get("expect", {}).get("intent", "NONE")),
            "raw_intent": q.get("expect", {}).get("intent", "NONE"),
            "category": q.get("category", "?"),
            "round_verdicts": ["unknown"],
            "consensus": "unknown",
            "round_durations_s": [0.0],
            "last_answer": "",
            "last_error": "skipped (no LLM)",
        }
        for q in questions
    ]


def _dry_worker_summary(
    worker_id: int,
    shard: Sequence[dict[str, Any]],
    wall_clock_s: float,
) -> dict[str, Any]:
    by_intent: dict[str, Counter] = defaultdict(Counter)
    for q in shard:
        intent = _bucket_intent(q.get("expect", {}).get("intent", "NONE"))
        by_intent[intent]["unknown"] += 1
    return {
        "worker_id": worker_id,
        "shard_size": len(shard),
        "wall_clock_s": round(wall_clock_s, 3),
        "duration_s": {},
        "verdict_counts": {"unknown": len(shard)},
        "pass_rate": 0.0,
        "by_intent": {
            intent: {
                "counts": dict(counter),
                "pass_rate": 0.0,
            }
            for intent, counter in sorted(by_intent.items())
        },
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.getenv("MIMO_API_KEY", "")
    db_url = args.db_url
    can_run_live = bool(api_key) and bool(db_url) and not args.dry_run
    mode = "live-mimo" if can_run_live else "dry-fallback"
    started_at = datetime.now(timezone.utc).isoformat()
    print(
        f"[phase3-matrix] mode={mode} workers={args.workers} "
        f"matrix_concurrency={args.matrix} rounds={args.rounds} "
        f"gate={args.gate_threshold}%"
    )

    questions = _load_full_corpus()
    if not questions:
        raise RuntimeError("Phase 3 corpus is empty -- aborting")

    shards = _shard_questions(questions, args.workers)
    extra_notes: list[str] = [
        f"Phase 3 corpus: {len(questions)} questions (questions_780 + questions_d4_extra_300)",
        f"Workers: {args.workers} shards ({args.workers} x ~{len(questions) // args.workers} questions)",
        f"Per-worker concurrency: {args.matrix} (matrix minimum 4, lower falls back to per-shard serial)",
        f"Gate threshold: {args.gate_threshold}% (matrix gate requires ALL workers to clear)",
    ]
    if not can_run_live:
        if not api_key:
            extra_notes.append("MIMO_API_KEY not present -> skipped live run")
        if not db_url:
            extra_notes.append("DATABASE_URL / QA_BENCH_DB_URL not present -> skipped live run")
        if args.dry_run:
            extra_notes.append("--dry-run flag set -> skipped live run on purpose")
        extra_notes.append(
            "Action: main orchestrator must SSH onto the runner host with "
            "MIMO_API_KEY + DATABASE_URL exported and rerun this script verbatim."
        )
        # Dry run: simulate each worker run with a tiny wall clock.
        worker_summaries = [
            _dry_worker_summary(worker_id, shard, wall_clock_s=0.0)
            for worker_id, shard in enumerate(shards)
        ]
    else:
        try:
            worker_summaries = await _run_matrix(
                shards,
                matrix_concurrency=args.matrix,
                rounds=args.rounds,
                db_url=db_url,
            )
        except Exception as exc:  # noqa: BLE001 -- report must survive errors
            extra_notes.append(f"Live matrix run aborted: {type(exc).__name__}: {exc}")
            worker_summaries = [
                _dry_worker_summary(worker_id, shard, wall_clock_s=0.0)
                for worker_id, shard in enumerate(shards)
            ]

    rollup = _aggregate_matrix(worker_summaries, gate_threshold=args.gate_threshold)
    finished_at = datetime.now(timezone.utc).isoformat()
    report = _render_phase3_report(
        rollup,
        worker_summaries,
        mode=mode,
        workers=args.workers,
        matrix_concurrency=args.matrix,
        rounds=args.rounds,
        gate_threshold=args.gate_threshold,
        started_at=started_at,
        finished_at=finished_at,
        extra_notes=extra_notes,
    )

    if args.report_out:
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"[phase3-matrix] report written to {out_path}")

    return {
        "rollup": rollup,
        "worker_summaries": worker_summaries,
        "report": report,
        "mode": mode,
        "gate_verdict": rollup["matrix_gate"],
        "started_at": started_at,
        "finished_at": finished_at,
        "total_questions": len(questions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of matrix shards (default {DEFAULT_WORKERS} → 4 x 250 questions)",
    )
    parser.add_argument(
        "--matrix",
        type=int,
        default=DEFAULT_MATRIX_CONCURRENCY,
        help=(
            f"Cross-shard concurrency cap (default {DEFAULT_MATRIX_CONCURRENCY}). "
            "Each worker still runs its own questions with --matrix internal concurrency."
        ),
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=DEFAULT_ROUNDS,
        help="Rounds per question for verdict consensus (default 3)",
    )
    parser.add_argument(
        "--gate-threshold",
        type=int,
        default=DEFAULT_GATE_THRESHOLD,
        help=(
            f"Per-worker gate threshold percent (default {DEFAULT_GATE_THRESHOLD}). "
            "All workers must clear the gate for the matrix to PASS."
        ),
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("QA_BENCH_DB_URL") or os.getenv("DATABASE_URL", ""),
        help="PostgreSQL DSN forwarded to inprocess_runner.run_inprocess",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip live LLM calls even if MIMO_API_KEY is set; emit dry-report only",
    )
    parser.add_argument(
        "--report-out",
        default=str(
            _QA_BENCH_DIR
            / f"phase3_matrix_report_{datetime.now().strftime('%Y-%m-%d')}.md"
        ),
        help="Path to write the auto-generated Markdown report",
    )
    args = parser.parse_args()

    payload = asyncio.run(_run(args))
    print(payload["report"])
    return 0 if payload["gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
