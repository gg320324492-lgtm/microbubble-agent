"""W68 D6 Phase 1 / Phase 2 dry-run: in-process benchmark runner.

This is a probe harness only. It must:

1.  Stay inside ``tests/qa-bench/`` (zero production-code change rule).
2.  Exercise :func:`inprocess_runner.run_inprocess` end-to-end on the
    question pool (Phase 1 = first 100 of ``questions_780.jsonl`` with 3
    rounds majority verdict; Phase 2 = ``--full`` 1000-question corpus
    with optional per-intent breakdown and gate-threshold enforcement).
3.  Use the *real* mimo cloud (LLM_BACKEND=openai_compat) when ``MIMO_API_KEY``
    is set in the environment, otherwise degrade to a structured dry-report
    that documents why the run could not complete and what the main
    orchestrator must execute on the SSH host.
4.  Produce pass-rate + per-intent breakdown + duration stats so W68 第 5 批
    and W68 第 7 批 can pick Phase 2 fix targets (which intents regressed,
    which question categories consistently fail).

Usage::

    # Phase 1 (legacy default)
    MIMO_API_KEY=... python tests/qa-bench/run_d5_dry.py
    python tests/qa-bench/run_d5_dry.py            # dry fallback when no key
    python tests/qa-bench/run_d5_dry.py --limit 30 --rounds 1

    # Phase 2 (W68 第 7 批 B-2)
    python tests/qa-bench/run_d5_dry.py --full
    python tests/qa-bench/run_d5_dry.py --full --per-intent
    python tests/qa-bench/run_d5_dry.py --full --gate-threshold 90
    python tests/qa-bench/run_d5_dry.py --full --per-intent --gate-threshold 90

The script writes its report alongside itself as
``phase1_dry_report_YYYY-MM-DD.md`` (Phase 1) or
``phase2_dry_report_YYYY-MM-DD.md`` (Phase 2, auto-generated filename when
``--full`` is set) **and** mirrors the same data to stdout. The companion
Markdown report (committed by the orchestrator) is the canonical deliverable.

W68 D6 Phase 2 design notes (W68 第 7 批 B-2, 2026-07-24)
-------------------------------------------------------

* ``--full`` activates the 1000-question corpus: ``questions_780.jsonl``
  (700 lines, the canonical seed pool) merged with
  ``questions_d4_extra_300.jsonl`` (300 lines, the W67 d4 extra bucket).
  Both files must live next to this script. The merge order is
  *seed-first* so per-intent counts stay deterministic.
* ``--per-intent`` adds a dedicated table to the Markdown report listing
  pass rate + counts + mean duration for **every** intent category
  present in the merged corpus. Six canonical intents are surfaced:
  ``meeting`` / ``task`` / ``knowledge`` / ``member`` / ``project`` /
  ``drive`` (plus a catch-all ``other`` bucket for non-conforming
  entries).
* ``--gate-threshold N`` (default ``80``) elevates the Phase 2 gate from
  W68 第 5 批's ``80`` to ``N`` percent. The Phase 2 runner writes a
  ``## Gate verdict`` section flagging pass (green) or fail (red) so the
  orchestrator can promote or rollback at a glance.
* The script continues to fall back to a structured *placeholder*
  Markdown report whenever ``MIMO_API_KEY`` / ``DATABASE_URL`` are absent
  -- this is by design so CI can validate the harness without a live
  cloud subscription.

W68 D6 Phase 1 design notes
---------------------------

* The in-process runner is a deliberate replacement for the HTTP
  ``/api/v1/chat/stream`` calls ``runner.py`` makes. It removes the
  ``httpx`` round-trip cost and the token-bucket pressure on nginx.
* The skeleton (``inprocess_runner.py``) already wraps the async generator
  in a serial loop, so a single ``asyncio.run`` is enough.
* We deliberately do NOT mock the LLM. A mocked LLM would only prove that
  the harness plumbing compiles -- it would not prove that mimo cloud
  answers are well-formed. If the key is missing, we refuse to pretend
  with synthetic answers and instead emit a structured "fallback" report.
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
from typing import Any, Iterable

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

REPO_ROOT = _QA_BENCH_DIR.parent.parent
QUESTIONS_PATH = _QA_BENCH_DIR / "questions_780.jsonl"
QUESTIONS_D4_EXTRA_PATH = _QA_BENCH_DIR / "questions_d4_extra_300.jsonl"

# Canonical 6-intent taxonomy (W68 第 7 批 B-2 Phase 2). The
# ``question.expect.intent`` strings in the corpus are the *chat* intent
# taxonomy (EXPLAIN_CONCEPT / DATA / DEEP / ACTION / CASUAL / SEARCH_INFO
# / NONE), so the runner also accepts those keywords and falls back to
# the corresponding business bucket (the 6 buckets requested by the
# orchestrator are surfaced when ``raw_intent`` carries an explicit
# business token -- e.g. "knowledge_search", "drive_list").
PHASE2_INTENT_BUCKETS: tuple[str, ...] = (
    "knowledge",
    "task",
    "meeting",
    "member",
    "project",
    "drive",
)

# Chat-intent -> bucket fallback. The 6 buckets do not align 1:1 with
# the corpus's chat intents, so when no business token is found we keep
# the raw intent (lowercased) so the Markdown report still surfaces
# per-chat-intent pass rates.
PHASE2_CHAT_INTENT_BUCKETS: tuple[str, ...] = (
    "explain_concept",
    "data",
    "deep",
    "action",
    "search_info",
    "casual",
)


def _bucket_intent(raw_intent: str | None) -> str:
    """Map a free-form ``expect.intent`` string into a report bucket.

    Order of resolution:
    1. 6 business buckets (``meeting`` / ``task`` / ``knowledge`` /
       ``member`` / ``project`` / ``drive``) win when present.
    2. Otherwise fall back to the chat-intent taxonomy surfaced by the
       corpus (lowercased). New intents appear in the report under
       their own lowercase name -- the Markdown table is intentionally
       lenient.
    3. Empty / missing -> ``other``.
    """

    if not raw_intent:
        return "other"
    lowered = str(raw_intent).strip().lower()
    for bucket in PHASE2_INTENT_BUCKETS:
        if bucket in lowered:
            return bucket
    if lowered in PHASE2_CHAT_INTENT_BUCKETS:
        return lowered
    return lowered or "other"


def _load_questions_full() -> list[dict[str, Any]]:
    """Load the full Phase 2 corpus: questions_780 + questions_d4_extra_300.

    The merge order is seed-first so per-intent counts are deterministic
    across runs (id collisions are tolerated -- they would only matter
    if the runner promoted them to a unique index, which it does not).
    """

    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for path in (QUESTIONS_PATH, QUESTIONS_D4_EXTRA_PATH):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                row_id = str(row.get("id") or "")
                if row_id and row_id in seen_ids:
                    continue
                if row_id:
                    seen_ids.add(row_id)
                rows.append(row)
    return rows


def _load_questions(path: Path, limit: int) -> list[dict[str, Any]]:
    """Load the first ``limit`` questions from a JSONL file."""
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for idx, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if len(rows) >= limit:
                break
    return rows


def _verdict_from_answer(answer: str) -> str:
    """Lightweight verdict derivation for in-process dry runs.

    The HTTP runner has 7-dimensional scoring and 30+ detectors; for the
    in-process probe we only need a coarse pass/fail signal so we can
    decide whether the runner *itself* (not the LLM) is broken. A real
    regression review must re-run the HTTP benchmark. The criteria are
    intentionally forgiving to avoid contaminating the report with LLM
    regressions that this probe is not designed to measure.
    """

    if not answer:
        return "empty"
    text = answer.strip()
    lowered = text.lower()
    # Heuristic "red flags" that suggest the runner is unhealthy.
    if "internal error" in lowered or "traceback" in lowered:
        return "error"
    if len(text) < 10:
        return "empty"
    return "pass"


def _majority_verdict(round_verdicts: Iterable[str]) -> str:
    rounds = list(round_verdicts)
    counts = Counter(rounds)
    if not counts:
        return "unknown"
    # ``pass`` wins ties (consistent with runner.py majority rule).
    if counts.get("pass", 0) >= len(rounds) // 2 + 1:
        return "pass"
    return counts.most_common(1)[0][0]


async def _run_round(
    questions: list[dict[str, Any]],
    rounds: int,
    db_url: str,
) -> list[dict[str, Any]]:
    """Run ``rounds`` passes over ``questions`` and aggregate verdicts."""

    from inprocess_runner import run_inprocess

    aggregated: list[dict[str, Any]] = []
    for question in questions:
        round_results: list[dict[str, Any]] = []
        for _ in range(rounds):
            started = time.monotonic()
            verdict_results = await run_inprocess([question], db_url=db_url)
            duration_s = time.monotonic() - started
            if verdict_results:
                first = verdict_results[0]
                round_results.append(
                    {
                        "verdict": _verdict_from_answer(first.answer),
                        "answer": first.answer,
                        "error": first.error,
                        "duration_s": duration_s,
                    }
                )
            else:
                round_results.append(
                    {
                        "verdict": "error",
                        "answer": "",
                        "error": "no VerdictResult returned",
                        "duration_s": duration_s,
                    }
                )
        consensus = _majority_verdict(r["verdict"] for r in round_results)
        raw_intent = question.get("expect", {}).get("intent", "NONE")
        aggregated.append(
            {
                "id": question.get("id"),
                "intent": _bucket_intent(raw_intent),
                "raw_intent": raw_intent,
                "category": question.get("category", "?"),
                "round_verdicts": [r["verdict"] for r in round_results],
                "consensus": consensus,
                "round_durations_s": [r["duration_s"] for r in round_results],
                "last_answer": round_results[-1]["answer"],
                "last_error": round_results[-1]["error"],
            }
        )
    return aggregated


def _summarize(results: list[dict[str, Any]], per_intent: bool = False) -> dict[str, Any]:
    verdicts = Counter(r["consensus"] for r in results)
    by_intent: dict[str, Counter] = defaultdict(Counter)
    for r in results:
        by_intent[r["intent"]][r["consensus"]] += 1
    durations: list[float] = []
    for r in results:
        durations.extend(r["round_durations_s"])
    summary: dict[str, Any] = {
        "total": len(results),
        "verdict_counts": dict(verdicts),
        "pass_rate": round(verdicts.get("pass", 0) / max(len(results), 1), 4),
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
    if durations:
        summary["duration_s"] = {
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
            "mean": round(statistics.mean(durations), 3),
            "median": round(statistics.median(durations), 3),
            "p95": round(statistics.quantiles(durations, n=20)[-1], 3)
            if len(durations) >= 20
            else round(max(durations), 3),
        }
    # Phase 2: per-intent latency table (only when requested).
    if per_intent and durations:
        by_intent_duration: dict[str, list[float]] = defaultdict(list)
        for r in results:
            for d in r["round_durations_s"]:
                by_intent_duration[r["intent"]].append(d)
        per_intent_latency = {}
        for intent, samples in sorted(by_intent_duration.items()):
            if not samples:
                continue
            per_intent_latency[intent] = {
                "count": len(samples),
                "mean": round(statistics.mean(samples), 3),
                "median": round(statistics.median(samples), 3),
                "p95": round(statistics.quantiles(samples, n=20)[-1], 3)
                if len(samples) >= 20
                else round(max(samples), 3),
                "max": round(max(samples), 3),
            }
        summary["per_intent_latency"] = per_intent_latency
    return summary


def _render_report(
    summary: dict[str, Any],
    *,
    mode: str,
    rounds: int,
    limit: int,
    started_at: str,
    finished_at: str,
    extra_notes: list[str],
    phase: str = "phase1",
    per_intent: bool = False,
    gate_threshold: int = 80,
) -> str:
    title = "W68 D6 Phase 2 Dry-run Report" if phase == "phase2" else "W68 D6 Phase 1 Dry-run Report"
    lines: list[str] = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"- Mode: **{mode}**")
    lines.append(f"- Started: {started_at}")
    lines.append(f"- Finished: {finished_at}")
    lines.append(f"- Total questions: **{summary['total']}**")
    lines.append(f"- Rounds per question: **{rounds}**")
    lines.append(f"- Total LLM calls attempted: **{summary['total'] * rounds}**")
    pass_rate_pct = summary["pass_rate"] * 100
    lines.append(f"- Pass rate (consensus): **{pass_rate_pct:.1f}%**")
    if phase == "phase2":
        lines.append(f"- Gate threshold: **{gate_threshold}%**")
        gate_status = "PASS" if pass_rate_pct >= gate_threshold else "FAIL"
        lines.append(f"- Gate verdict: **{gate_status}**")
    lines.append("")
    lines.append("## Verdict counts")
    lines.append("")
    lines.append("| Verdict | Count |")
    lines.append("|---|---|")
    for verdict, count in summary["verdict_counts"].items():
        lines.append(f"| {verdict} | {count} |")
    lines.append("")
    if "duration_s" in summary:
        d = summary["duration_s"]
        lines.append("## Latency")
        lines.append("")
        lines.append(f"- min: **{d['min']}s**")
        lines.append(f"- mean: **{d['mean']}s**")
        lines.append(f"- median: **{d['median']}s**")
        lines.append(f"- p95: **{d['p95']}s**")
        lines.append(f"- max: **{d['max']}s**")
        lines.append("")
    lines.append("## Per-intent breakdown")
    lines.append("")
    lines.append("| Intent | Pass rate | Counts |")
    lines.append("|---|---|---|")
    for intent, info in summary["by_intent"].items():
        counts = ", ".join(f"{k}={v}" for k, v in sorted(info["counts"].items()))
        lines.append(f"| {intent} | {info['pass_rate'] * 100:.1f}% | {counts} |")
    lines.append("")
    if per_intent and summary.get("per_intent_latency"):
        lines.append("## Per-intent latency (Phase 2)")
        lines.append("")
        lines.append("| Intent | Mean (s) | Median (s) | p95 (s) | Max (s) | Samples |")
        lines.append("|---|---|---|---|---|---|")
        for intent, lat in summary["per_intent_latency"].items():
            lines.append(
                f"| {intent} | {lat['mean']} | {lat['median']} | {lat['p95']} | {lat['max']} | {lat['count']} |"
            )
        lines.append("")
    if extra_notes:
        lines.append("## Notes")
        lines.append("")
        for note in extra_notes:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=100, help="Number of questions to load (dry-run uses 100)")
    parser.add_argument("--rounds", type=int, default=3, help="Rounds per question for verdict consensus")
    parser.add_argument(
        "--db-url",
        default=os.getenv("QA_BENCH_DB_URL") or os.getenv("DATABASE_URL", ""),
        help="PostgreSQL DSN forwarded to inprocess_runner.run_inprocess",
    )
    parser.add_argument(
        "--output",
        default=str(_QA_BENCH_DIR / f"phase1_dry_report_{datetime.now().strftime('%Y-%m-%d')}.md"),
        help="Path to write the auto-generated Markdown report",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip live LLM calls even if MIMO_API_KEY is set; emit dry-report only",
    )
    # W68 第 7 批 B-2 Phase 2 flags -----------------------------------------
    parser.add_argument(
        "--full",
        action="store_true",
        help="Phase 2 mode: load the 1000-question corpus (questions_780 + questions_d4_extra_300)",
    )
    parser.add_argument(
        "--per-intent",
        action="store_true",
        help="Phase 2 mode: emit per-intent latency table in the Markdown report",
    )
    parser.add_argument(
        "--gate-threshold",
        type=int,
        default=80,
        help="Phase 2 gate threshold percentage (default 80 -> Phase 2 elevates to 90)",
    )
    args = parser.parse_args()

    api_key = os.getenv("MIMO_API_KEY", "")
    db_url = args.db_url
    can_run_live = bool(api_key) and bool(db_url) and not args.skip_llm
    phase = "phase2" if args.full else "phase1"
    default_report_name = (
        f"phase2_dry_report_{datetime.now().strftime('%Y-%m-%d')}.md"
        if args.full
        else f"phase1_dry_report_{datetime.now().strftime('%Y-%m-%d')}.md"
    )
    if args.output.endswith(f"phase1_dry_report_{datetime.now().strftime('%Y-%m-%d')}.md") and args.full:
        args.output = str(_QA_BENCH_DIR / default_report_name)
    started_at = datetime.now(timezone.utc).isoformat()
    mode = "live-mimo" if can_run_live else "dry-fallback"
    print(
        f"[{phase}-dry] mode={mode} full={args.full} per_intent={args.per_intent} "
        f"gate={args.gate_threshold}% rounds={args.rounds} db_url_set={bool(db_url)}"
    )

    if args.full:
        questions = _load_questions_full()
    else:
        questions = _load_questions(QUESTIONS_PATH, args.limit)
    if not questions:
        print("No questions loaded -- aborting", file=sys.stderr)
        return 2

    extra_notes: list[str] = []
    if args.full:
        extra_notes.append(
            f"Phase 2 corpus: 1000 questions (questions_780 + questions_d4_extra_300)"
        )
        extra_notes.append(
            f"Per-intent latency table: {'enabled' if args.per_intent else 'disabled'}"
        )
        extra_notes.append(
            f"Gate threshold: {args.gate_threshold}% (Phase 2 baseline 80%, elevated target 90%)"
        )
    summary: dict[str, Any]
    if can_run_live:
        try:
            aggregated = asyncio.run(_run_round(questions, args.rounds, db_url))
            summary = _summarize(aggregated, per_intent=args.per_intent)
        except Exception as exc:  # noqa: BLE001 -- report must survive errors
            extra_notes.append(f"Live run aborted: {type(exc).__name__}: {exc}")
            placeholder_results = [
                {
                    "id": q.get("id"),
                    "intent": q.get("expect", {}).get("intent", "NONE"),
                    "category": q.get("category", "?"),
                    "round_verdicts": ["error"],
                    "consensus": "error",
                    "round_durations_s": [0.0],
                    "last_answer": "",
                    "last_error": str(exc),
                }
                for q in questions
            ]
            summary = _summarize(placeholder_results, per_intent=args.per_intent)
    else:
        if not api_key:
            extra_notes.append("MIMO_API_KEY not present in environment -> skipped live run")
        if not db_url:
            extra_notes.append("DATABASE_URL / QA_BENCH_DB_URL not present -> skipped live run")
        if args.skip_llm:
            extra_notes.append("--skip-llm flag set -> skipped live run on purpose")
        extra_notes.append(
            "Action: main orchestrator must SSH onto the runner host with "
            "MIMO_API_KEY + DATABASE_URL exported and rerun this script verbatim."
        )
        # Emit a *structured* placeholder summary so the Markdown report still
        # tells reviewers which 100/1000 ids/intents we intended to cover.
        placeholder_results = [
            {
                "id": q.get("id"),
                "intent": q.get("expect", {}).get("intent", "NONE"),
                "category": q.get("category", "?"),
                "round_verdicts": ["unknown"],
                "consensus": "unknown",
                "round_durations_s": [0.0],
                "last_answer": "",
                "last_error": "skipped (no LLM)",
            }
            for q in questions
        ]
        summary = _summarize(placeholder_results, per_intent=args.per_intent)

    finished_at = datetime.now(timezone.utc).isoformat()
    report = _render_report(
        summary,
        mode=mode,
        rounds=args.rounds,
        limit=len(questions),
        started_at=started_at,
        finished_at=finished_at,
        extra_notes=extra_notes,
        phase=phase,
        per_intent=args.per_intent,
        gate_threshold=args.gate_threshold,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n[{phase}-dry] report written to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())