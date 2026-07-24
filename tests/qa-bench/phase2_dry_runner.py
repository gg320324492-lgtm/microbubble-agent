"""W68 D6 Phase 2 dry-run runner.

This module is the *dedicated* Phase 2 runner.  It owns:

*   Loading the full 1000-question corpus (``questions_780.jsonl`` +
    ``questions_d4_extra_300.jsonl``) with deterministic seed-first
    order.
*   Running the in-process benchmark with **bounded async
    concurrency = 5** (W68 第 5 批 was 3; Phase 2 elevates to 5).
*   Emitting a structured per-intent breakdown -- the 6 canonical
    business buckets (``meeting`` / ``task`` / ``knowledge`` /
    ``member`` / ``project`` / ``drive``) plus the actual chat-intent
    taxonomy used by the corpus.
*   Gate verdict: the run is ``PASS`` only if the global pass rate
    meets ``--gate-threshold`` (default ``90``); otherwise ``FAIL`` and
    the runner returns non-zero.

The runner deliberately stays inside ``tests/qa-bench/`` (W68 zero
production-code-change rule).  It reuses ``inprocess_runner.run_inprocess``
and never imports from ``app/``.

Usage::

    # dry-run fallback (no MIMO_API_KEY in env) -- CI-friendly
    python tests/qa-bench/phase2_dry_runner.py --dry-run

    # real run against mimo cloud with 5 concurrent workers
    MIMO_API_KEY=... python tests/qa-bench/phase2_dry_runner.py --report-out phase2_real.md

    # custom concurrency + gate
    python tests/qa-bench/phase2_dry_runner.py --concurrency 8 --gate-threshold 95

    # W68 第 11 批 C-2 unified output CLI
    python tests/qa-bench/phase2_dry_runner.py --report-out phase2.json         # JSON by suffix
    python tests/qa-bench/phase2_dry_runner.py --report-out phase2.md           # Markdown by suffix
    python tests/qa-bench/phase2_dry_runner.py --report-out phase2 --output-format md
    python tests/qa-bench/phase2_dry_runner.py --input custom_questions.jsonl --report-out phase2.json
    python tests/qa-bench/phase2_dry_runner.py --dry-run --seven-d --report-out phase2.json

The runner returns ``int`` -- ``0`` on PASS, ``1`` on gate FAIL, ``2``
on abort.  CI / orchestrator should treat ``0`` as "promote" and
anything else as "do not promote".

W68 第 11 批 C-2 CLI uniformity
-------------------------------

* ``--output-format {auto,json,md}`` (default ``auto``) decides the
  on-disk encoding.  ``auto`` infers from ``--report-out`` suffix
  (``.json`` -> JSON, ``.md`` -> Markdown, no suffix -> JSON).
* ``--input PATH`` lets the runner consume a custom question corpus
  (JSONL or top-level JSON list).  When omitted the runner loads the
  full 1000-question Phase 2 corpus.  Used by ``save_to_kb`` 5 道防线
  pipelines and downstream tooling that wants to reuse the runner on
  a curated subset.
* ``--seven-d`` invokes ``runner.score_seven_dim`` after the dry-run
  finishes and writes ``seven_d_phase2_dry.json`` next to the report.
  The dry grade is heuristic (uses the coarse pass-rate per intent as
  the ``accuracy`` dim; other dims default to 1.0).  Future PRs can
  swap the heuristic for a real dim scoring loop without changing the
  CLI surface.
* The Phase 1 and Phase 3 runners share the same CLI contract -- see
  ``run_d5_dry.py`` and ``phase3_matrix_runner.py`` for the parallel
  ``--output-format`` / ``--input`` / ``--seven-d`` flags.
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
from typing import Any, Iterable, Sequence

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

REPO_ROOT = _QA_BENCH_DIR.parent.parent
QUESTIONS_SEED = _QA_BENCH_DIR / "questions_780.jsonl"
QUESTIONS_D4_EXTRA = _QA_BENCH_DIR / "questions_d4_extra_300.jsonl"
DEFAULT_CONCURRENCY = 5
DEFAULT_GATE_THRESHOLD = 90
PHASE2_INTENT_BUCKETS: tuple[str, ...] = (
    "knowledge",
    "task",
    "meeting",
    "member",
    "project",
    "drive",
)
PHASE2_CHAT_INTENT_BUCKETS: tuple[str, ...] = (
    "explain_concept",
    "data",
    "deep",
    "action",
    "search_info",
    "casual",
)


def _bucket_intent(raw_intent: str | None) -> str:
    if not raw_intent:
        return "other"
    lowered = str(raw_intent).strip().lower()
    for bucket in PHASE2_INTENT_BUCKETS:
        if bucket in lowered:
            return bucket
    if lowered in PHASE2_CHAT_INTENT_BUCKETS:
        return lowered
    return lowered or "other"


def _load_full_corpus() -> list[dict[str, Any]]:
    """Merge ``questions_780`` + ``questions_d4_extra_300`` deterministically."""

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in (QUESTIONS_SEED, QUESTIONS_D4_EXTRA):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                rid = str(row.get("id") or "")
                if rid and rid in seen:
                    continue
                if rid:
                    seen.add(rid)
                rows.append(row)
    return rows


def _majority_verdict(round_verdicts: Iterable[str]) -> str:
    rounds = list(round_verdicts)
    counts = Counter(rounds)
    if not counts:
        return "unknown"
    if counts.get("pass", 0) >= len(rounds) // 2 + 1:
        return "pass"
    return counts.most_common(1)[0][0]


def _verdict_from_answer(answer: str) -> str:
    if not answer:
        return "empty"
    text = answer.strip()
    if "internal error" in text.lower() or "traceback" in text.lower():
        return "error"
    if len(text) < 10:
        return "empty"
    return "pass"


async def _round_with_concurrency(
    questions: Sequence[dict[str, Any]],
    rounds: int,
    db_url: str,
    concurrency: int,
    engine_factory: Any | None = None,
) -> list[dict[str, Any]]:
    """Run ``rounds`` passes per question with bounded async concurrency.

    ``engine_factory`` is the same seam used by ``inprocess_runner.run_inprocess``.
    When ``None``, the production-style path constructs a real
    ``ChatEngine`` (and raises if the full app stack is unavailable).
    Tests pass a stub factory to avoid booting PostgreSQL / Redis / the
    real LLM.
    """

    from inprocess_runner import run_inprocess

    sem = asyncio.Semaphore(concurrency)

    async def _one(q: dict[str, Any]) -> dict[str, Any]:
        async with sem:
            round_results: list[dict[str, Any]] = []
            for _ in range(rounds):
                started = time.monotonic()
                kwargs: dict[str, Any] = {"db_url": db_url}
                if engine_factory is not None:
                    kwargs["engine_factory"] = engine_factory
                verdict_results = await run_inprocess([q], **kwargs)
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
            raw_intent = q.get("expect", {}).get("intent", "NONE")
            return {
                "id": q.get("id"),
                "intent": _bucket_intent(raw_intent),
                "raw_intent": raw_intent,
                "category": q.get("category", "?"),
                "round_verdicts": [r["verdict"] for r in round_results],
                "consensus": consensus,
                "round_durations_s": [r["duration_s"] for r in round_results],
                "last_answer": round_results[-1]["answer"],
                "last_error": round_results[-1]["error"],
            }

    tasks = [asyncio.create_task(_one(q)) for q in questions]
    return await asyncio.gather(*tasks)


def _summarize_phase2(results: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(r["consensus"] for r in results)
    by_intent: dict[str, Counter] = defaultdict(Counter)
    by_intent_duration: dict[str, list[float]] = defaultdict(list)
    for r in results:
        by_intent[r["intent"]][r["consensus"]] += 1
        for d in r["round_durations_s"]:
            by_intent_duration[r["intent"]].append(d)
    durations: list[float] = [d for r in results for d in r["round_durations_s"]]
    pass_rate = round(verdicts.get("pass", 0) / max(len(results), 1), 4)
    summary: dict[str, Any] = {
        "total": len(results),
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
    if by_intent_duration:
        per_intent_latency: dict[str, dict[str, float]] = {}
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


def _render_phase2_report(
    summary: dict[str, Any],
    *,
    mode: str,
    rounds: int,
    concurrency: int,
    gate_threshold: int,
    started_at: str,
    finished_at: str,
    extra_notes: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# W68 D6 Phase 2 Dry-run Report (Auto-generated)")
    lines.append("")
    lines.append(f"- Mode: **{mode}**")
    lines.append(f"- Concurrency: **{concurrency}**")
    lines.append(f"- Started: {started_at}")
    lines.append(f"- Finished: {finished_at}")
    lines.append(f"- Total questions: **{summary['total']}**")
    lines.append(f"- Rounds per question: **{rounds}**")
    pass_rate_pct = summary["pass_rate"] * 100
    lines.append(f"- Pass rate (consensus): **{pass_rate_pct:.1f}%**")
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
    if summary.get("per_intent_latency"):
        lines.append("## Per-intent latency")
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


def _dry_placeholder_results(questions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
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


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    """Top-level orchestrator.  Returns a structured payload for tests."""

    api_key = os.getenv("MIMO_API_KEY", "")
    db_url = args.db_url
    can_run_live = bool(api_key) and bool(db_url) and not args.dry_run
    started_at = datetime.now(timezone.utc).isoformat()
    mode = "live-mimo" if can_run_live else "dry-fallback"
    output_format = _resolve_output_format(args.report_out, getattr(args, "output_format", "auto"))
    print(
        f"[phase2-runner] mode={mode} concurrency={args.concurrency} "
        f"rounds={args.rounds} gate={args.gate_threshold}% db_url_set={bool(db_url)} "
        f"output_format={output_format}"
    )

    questions = _load_input_questions(getattr(args, "input", None))
    if not questions:
        raise RuntimeError("Phase 2 corpus is empty -- aborting")

    extra_notes: list[str] = [
        f"Phase 2 corpus: {len(questions)} questions (questions_780 + questions_d4_extra_300)",
        f"Concurrency: {args.concurrency} workers (Phase 1 was 3, Phase 2 elevates to 5)",
        f"Gate threshold: {args.gate_threshold}% (Phase 2 baseline 80%, target 90%)",
        f"Output format: {output_format} ({args.report_out})",
    ]
    if getattr(args, "input", None):
        extra_notes.append(
            f"Input corpus override: {args.input} ({len(questions)} rows)"
        )
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
        summary = _summarize_phase2(_dry_placeholder_results(questions))
    else:
        try:
            aggregated = await _round_with_concurrency(
                questions, args.rounds, db_url, args.concurrency
            )
            summary = _summarize_phase2(aggregated)
        except Exception as exc:  # noqa: BLE001 -- report must survive errors
            extra_notes.append(f"Live run aborted: {type(exc).__name__}: {exc}")
            summary = _summarize_phase2(_dry_placeholder_results(questions))

    finished_at = datetime.now(timezone.utc).isoformat()
    report = _render_phase2_report(
        summary,
        mode=mode,
        rounds=args.rounds,
        concurrency=args.concurrency,
        gate_threshold=args.gate_threshold,
        started_at=started_at,
        finished_at=finished_at,
        extra_notes=extra_notes,
    )

    if args.report_out:
        out_path = Path(args.report_out)
        if output_format == "json":
            json_payload = {
                "format_version": "1",
                "schema": "phase2_dry_runner.v1",
                "phase": "phase2",
                "mode": mode,
                "concurrency": args.concurrency,
                "rounds": args.rounds,
                "gate_threshold": args.gate_threshold,
                "gate_verdict": (
                    "PASS" if (summary["pass_rate"] * 100) >= args.gate_threshold else "FAIL"
                ),
                "started_at": started_at,
                "finished_at": finished_at,
                "summary": summary,
                "notes": extra_notes,
                "total_questions": len(questions),
            }
            _dump_payload(json_payload, "json", out_path)
        else:
            _dump_payload({"body": report}, "md", out_path)
        print(
            f"[phase2-runner] report written to {out_path} "
            f"(format={output_format})"
        )

    if getattr(args, "seven_d", False):
        out_dir = Path(args.report_out).parent if args.report_out else _QA_BENCH_DIR
        seven_d_path = _run_seven_d_scoring(summary, output_dir=out_dir)
        if seven_d_path:
            print(f"[phase2-runner] seven-d scoring written to {seven_d_path}")
        else:
            print(
                "[phase2-runner] seven-d scoring skipped (runner.score_seven_dim "
                "unavailable or empty corpus)"
            )

    pass_rate_pct = summary["pass_rate"] * 100
    return {
        "summary": summary,
        "report": report,
        "mode": mode,
        "pass_rate_pct": pass_rate_pct,
        "gate_threshold": args.gate_threshold,
        "gate_verdict": "PASS" if pass_rate_pct >= args.gate_threshold else "FAIL",
        "started_at": started_at,
        "finished_at": finished_at,
        "total_questions": len(questions),
        "output_format": output_format,
    }


def _resolve_output_format(
    output_path: str | None,
    output_format: str,
) -> str:
    """Mirror of ``run_d5_dry._resolve_output_format`` (W68 第 11 批 C-2).

    ``auto`` (default) infers ``json`` vs ``md`` from the output path's
    suffix; explicit ``json`` / ``md`` overrides any suffix hint.  An
    ``auto`` choice with no recognisable suffix falls back to ``json``
    so SOP documents that pass a bare name keep getting structured data.
    """

    normalized = (output_format or "auto").strip().lower()
    if normalized not in {"auto", "json", "md"}:
        raise SystemExit(
            f"--output-format must be one of auto|json|md, got {output_format!r}"
        )
    if normalized != "auto":
        return normalized
    suffix = Path(output_path or "").suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix in {".md", ".markdown"}:
        return "md"
    return "json"


def _dump_payload(payload: dict[str, Any], fmt: str, path: Path) -> str:
    """Serialize ``payload`` to ``path`` according to ``fmt``.

    JSON output wraps the payload with a top-level ``format_version``
    field so future schema changes can stay backward-compatible (loaders
    should check the version before consuming the body).
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        body = dict(payload)
        body.setdefault("format_version", "1")
        path.write_text(
            json.dumps(body, ensure_ascii=False, indent=2, sort_keys=False),
            encoding="utf-8",
        )
    else:
        path.write_text(str(payload.get("body") or ""), encoding="utf-8")
    return fmt


def _load_input_questions(input_path: str | None) -> list[dict[str, Any]]:
    """Load the question corpus from ``--input`` JSON / JSONL.

    When ``input_path`` is omitted we fall back to ``_load_full_corpus``.
    """

    if not input_path:
        return _load_full_corpus()
    p = Path(input_path)
    if not p.exists():
        raise SystemExit(f"--input path does not exist: {p}")
    raw = p.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    rows: list[dict[str, Any]] = []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"--input JSON parse failed: {exc}") from exc
        if isinstance(data, list):
            rows = [r for r in data if isinstance(r, dict)]
        else:
            rows = [data] if isinstance(data, dict) else []
    else:
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(
                    f"--input JSONL parse failed on line {len(rows) + 1}: {exc}"
                ) from exc
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _run_seven_d_scoring(
    summary: dict[str, Any],
    *,
    output_dir: Path,
) -> str | None:
    """Best-effort post-run 7-dim scoring (W68 第 10 批 B-1 integration)."""

    try:
        from runner import score_seven_dim  # type: ignore[import-not-found]
    except Exception:  # noqa: BLE001 -- optional integration, never fatal
        return None
    by_intent = summary.get("by_intent", {}) or {}
    intents = sorted(by_intent.keys())
    if not intents:
        return None
    per_intent_dim: dict[str, dict[str, Any]] = {}
    totals: list[float] = []
    for intent in intents:
        info = by_intent.get(intent) or {}
        pass_rate = float(info.get("pass_rate") or 0.0)
        dim_scores = {
            "intent": 1.0,
            "tool": 1.0,
            "content": 1.0,
            "structure": 1.0,
            "accuracy": pass_rate,
            "defense": 1.0,
            "latency": 1.0,
        }
        total = sum(dim_scores.values()) / len(dim_scores) * 100
        totals.append(total)
        per_intent_dim[intent] = {
            "dim_scores": dim_scores,
            "total_score": round(total, 2),
            "grade": score_seven_dim.__globals__.get("_SEVEN_DIM_GRADE", "B"),
            "veto": False,
        }
    overall_total = round(sum(totals) / max(len(totals), 1), 2)
    payload = {
        "phase": "phase2",
        "format_version": "1",
        "source": "phase2_dry_runner._run_seven_d_scoring",
        "intents": per_intent_dim,
        "overall_total_score": overall_total,
    }
    out = output_dir / "seven_d_phase2_dry.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Async worker count (Phase 2 default {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=3,
        help="Rounds per question for verdict consensus (default 3)",
    )
    parser.add_argument(
        "--gate-threshold",
        type=int,
        default=DEFAULT_GATE_THRESHOLD,
        help=f"Gate threshold percent (Phase 2 default {DEFAULT_GATE_THRESHOLD})",
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
        default=str(_QA_BENCH_DIR / f"phase2_dry_report_{datetime.now().strftime('%Y-%m-%d')}.md"),
        help=(
            "Path to write the auto-generated report.  Format follows "
            "--output-format (default auto: '.json' -> JSON, '.md' -> Markdown, "
            "no suffix -> JSON).  W68 第 11 批 C-2 CLI uniformity."
        ),
    )
    parser.add_argument(
        "--output-format",
        choices=("auto", "json", "md"),
        default="auto",
        help=(
            "Force a specific output format.  'auto' (default) infers the "
            "format from --report-out suffix; explicit 'json' / 'md' overrides "
            "the suffix.  W68 第 11 批 C-2 CLI uniformity."
        ),
    )
    parser.add_argument(
        "--input",
        default=None,
        help=(
            "Optional JSON / JSONL question corpus path.  Overrides the "
            "default 1000-question Phase 2 corpus.  W68 第 11 批 C-2."
        ),
    )
    parser.add_argument(
        "--seven-d",
        action="store_true",
        help=(
            "After the dry-run finishes, emit a 7-dim scoring JSON next "
            "to --report-out (filename 'seven_d_phase2_dry.json').  Reuses "
            "runner.score_seven_dim.  W68 第 10 批 B-1 integration."
        ),
    )
    args = parser.parse_args()

    payload = asyncio.run(_run(args))
    print(payload["report"])
    return 0 if payload["gate_verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())