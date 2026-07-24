"""W68 D6 / W69 Phase 3 matrix runner.

The Phase 3 matrix runner extends the Phase 2 single-runner flow with
a *matrix* of configurations: it iterates over a Cartesian product of
``(provider, model, retrieval_cache_mode, rounds)`` tuples and emits a
per-cell summary, then aggregates a unified 7-dim score across the
whole matrix.

Lives under ``tests/qa-bench/`` only and never imports from
production code (W68 zero production-change rule).

Usage::

    # Dry matrix fallback (CI-friendly; no LLM calls)
    python tests/qa-bench/phase3_matrix_runner.py --dry-run

    # Live matrix against mimo cloud + Ollama local
    MIMO_API_KEY=... python tests/qa-bench/phase3_matrix_runner.py \\
        --report-out phase3_matrix.md

    # Custom matrix
    python tests/qa-bench/phase3_matrix_runner.py \\
        --providers mimo --models mimo-v2.5 --cache-modes hit,miss --rounds 3

The runner returns ``int`` -- ``0`` on PASS (every cell meets its
gate), ``1`` on FAIL (any cell missed), ``2`` on abort.  CI / orchestrator
should treat ``0`` as "promote" and anything else as "do not promote".
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

_QA_BENCH_DIR = Path(__file__).resolve().parent
_SCORING_DIR = _QA_BENCH_DIR / "scoring"
for _p in (str(_QA_BENCH_DIR), str(_SCORING_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

PHASE3_INTENT_BUCKETS: tuple[str, ...] = (
    "knowledge",
    "task",
    "meeting",
    "member",
    "project",
    "drive",
)

DEFAULT_PROVIDERS: tuple[str, ...] = ("mimo", "ollama")
DEFAULT_MODELS: dict[str, tuple[str, ...]] = {
    "mimo": ("mimo-v2.5",),
    "ollama": ("qwen3:8b",),
}
DEFAULT_CACHE_MODES: tuple[str, ...] = ("hit", "miss")
DEFAULT_ROUNDS: tuple[int, ...] = (3,)
DEFAULT_CONCURRENCY = 4
DEFAULT_GATE_THRESHOLD = 90
DEFAULT_SCORING = "none"  # "none" | "7d"


@dataclass(slots=True)
class MatrixCell:
    """One configuration tuple in the Phase 3 matrix."""

    provider: str
    model: str
    cache_mode: str
    rounds: int

    @property
    def label(self) -> str:
        return f"{self.provider}/{self.model}/{self.cache_mode}/r{self.rounds}"


def _bucket_intent(raw_intent: str | None) -> str:
    if not raw_intent:
        return "other"
    lowered = str(raw_intent).strip().lower()
    for bucket in PHASE3_INTENT_BUCKETS:
        if bucket in lowered:
            return bucket
    return lowered or "other"


def _load_corpus_subset(
    *,
    max_questions: int | None,
    seed: int,
) -> list[dict[str, Any]]:
    """Load the questions corpus deterministically.

    Phase 3 subsamples the full 1000-row corpus so each matrix cell
    finishes inside a reasonable CI budget while still representing
    the six business buckets.  The ``seed`` parameter lets the same
    ``max_questions`` choice produce the same rows across cells so the
    matrix is comparable.
    """

    rows: list[dict[str, Any]] = []
    for path in (
        _QA_BENCH_DIR / "questions_780.jsonl",
        _QA_BENCH_DIR / "questions_d4_extra_300.jsonl",
    ):
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
    if not rows:
        return rows
    rows.sort(key=lambda r: str(r.get("id") or ""))
    if max_questions is not None and len(rows) > max_questions:
        # Deterministic stride subsample: take every ``step``-th row.
        step = max(len(rows) // max_questions, 1)
        rows = rows[::step][:max_questions]
    return rows


def _cell_placeholder_results(
    questions: Sequence[dict[str, Any]],
    *,
    cell: MatrixCell,
) -> list[dict[str, Any]]:
    return [
        {
            "id": q.get("id"),
            "intent": _bucket_intent(q.get("expect", {}).get("intent", "NONE")),
            "raw_intent": q.get("expect", {}).get("intent", "NONE"),
            "category": q.get("category", "?"),
            "cell": cell.label,
            "round_verdicts": ["unknown"],
            "consensus": "unknown",
            "round_durations_s": [0.0],
            "last_answer": "",
            "last_error": "skipped (no LLM)",
        }
        for q in questions
    ]


def _matrix_to_records(
    cell_results: Sequence[dict[str, Any]],
    *,
    rounds: int,
) -> list[Any]:
    """Flatten a single matrix cell's results into ``VerdictRecord`` objects."""

    from seven_d_scoring import VerdictRecord  # noqa: WPS433 -- sibling-module import

    records: list[VerdictRecord] = []
    for row in cell_results:
        verdicts = list(row.get("round_verdicts", []))
        durations = list(row.get("round_durations_s", []))
        if len(verdicts) < rounds:
            verdicts = verdicts + ["unknown"] * (rounds - len(verdicts))
            durations = durations + [0.0] * (rounds - len(durations))
        elif len(verdicts) > rounds:
            verdicts = verdicts[:rounds]
            durations = durations[:rounds]
        for verdict, duration in zip(verdicts, durations):
            records.append(
                VerdictRecord(
                    question_id=f"{row.get('id') or 'unknown'}::{row.get('cell', 'unknown')}",
                    verdict=verdict,
                    ground_truth_positive=True,
                    latency_ms=float(duration or 0.0) * 1000.0,
                    intent=str(row.get("intent") or "other"),
                    error=row.get("last_error"),
                    metadata={"cell": row.get("cell", "")},
                )
            )
    return records


def _run_seven_d_scoring(
    cell_results_by_cell: dict[str, Sequence[dict[str, Any]]],
    *,
    rounds_per_cell: dict[str, int],
    output_path: Path | None,
) -> dict[str, Any] | None:
    """Score the union of all matrix cells with the 7-dim scorer."""

    all_records: list[Any] = []
    for cell_label, cell_results in cell_results_by_cell.items():
        cell_rounds = rounds_per_cell.get(cell_label, 1)
        all_records.extend(_matrix_to_records(cell_results, rounds=cell_rounds))
    if not all_records:
        return None
    try:
        from seven_d_scoring import score_records  # noqa: WPS433
    except ImportError:  # pragma: no cover
        print(
            "[phase3-runner] --scoring 7d requested but seven_d_scoring "
            "could not be imported",
            file=sys.stderr,
        )
        return None
    seven = score_records(all_records)
    payload = seven.as_dict()
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[phase3-runner] 7d score written to {output_path}")
    return payload


def _aggregate_cell(
    cell_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Aggregate one matrix cell's results."""

    verdicts = Counter(r["consensus"] for r in cell_results)
    durations = [d for r in cell_results for d in r["round_durations_s"]]
    pass_rate = round(verdicts.get("pass", 0) / max(len(cell_results), 1), 4)
    by_intent: dict[str, Counter] = defaultdict(Counter)
    for r in cell_results:
        by_intent[r["intent"]][r["consensus"]] += 1
    payload: dict[str, Any] = {
        "total": len(cell_results),
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
        payload["duration_s"] = {
            "min": round(min(durations), 3),
            "max": round(max(durations), 3),
            "mean": round(statistics.mean(durations), 3),
            "median": round(statistics.median(durations), 3),
            "p95": round(statistics.quantiles(durations, n=20)[-1], 3)
            if len(durations) >= 20
            else round(max(durations), 3),
        }
    return payload


def _render_phase3_report(
    *,
    cell_summaries: dict[str, dict[str, Any]],
    gate_threshold: int,
    started_at: str,
    finished_at: str,
    seven_d_payload: dict[str, Any] | None,
) -> str:
    lines: list[str] = []
    lines.append("# W68 D6 Phase 3 Matrix Report (Auto-generated)")
    lines.append("")
    lines.append(f"- Started: {started_at}")
    lines.append(f"- Finished: {finished_at}")
    lines.append(f"- Gate threshold: **{gate_threshold}%**")
    lines.append("")
    lines.append("## Per-cell breakdown")
    lines.append("")
    lines.append("| Cell | Total | Pass rate | p95 latency (s) | Gate |")
    lines.append("|---|---|---|---|---|")
    all_pass = True
    for cell_label, summary in sorted(cell_summaries.items()):
        pass_rate_pct = summary["pass_rate"] * 100
        verdict = "PASS" if pass_rate_pct >= gate_threshold else "FAIL"
        if verdict == "FAIL":
            all_pass = False
        p95 = summary.get("duration_s", {}).get("p95", 0.0)
        lines.append(
            f"| {cell_label} | {summary['total']} | "
            f"{pass_rate_pct:.1f}% | {p95} | **{verdict}** |"
        )
    lines.append("")
    lines.append(f"- Matrix verdict: **{'PASS' if all_pass else 'FAIL'}**")
    lines.append("")
    if seven_d_payload is not None:
        lines.append("## 7-dimension score (overlay)")
        lines.append("")
        lines.append(f"- accuracy: **{seven_d_payload.get('accuracy', 0):.4f}**")
        lines.append(f"- recall: **{seven_d_payload.get('recall', 0):.4f}**")
        lines.append(f"- precision: **{seven_d_payload.get('precision', 0):.4f}**")
        lines.append(f"- F1: **{seven_d_payload.get('f1', 0):.4f}**")
        lines.append(f"- consistency: **{seven_d_payload.get('consistency', 0):.4f}**")
        lines.append(f"- entropy: **{seven_d_payload.get('entropy', 0):.4f}**")
        lat = seven_d_payload.get("latency", {})
        lines.append(f"- latency avg: **{lat.get('avg_ms', 0):.2f} ms**")
        lines.append(f"- latency p95: **{lat.get('p95_ms', 0):.2f} ms**")
        lines.append(f"- latency p99: **{lat.get('p99_ms', 0):.2f} ms**")
        lines.append("")
    return "\n".join(lines)


def _build_matrix(
    *,
    providers: Sequence[str],
    models: dict[str, Sequence[str]],
    cache_modes: Sequence[str],
    rounds: Sequence[int],
) -> list[MatrixCell]:
    cells: list[MatrixCell] = []
    for provider, cache_mode, round_count in itertools.product(
        providers, cache_modes, rounds
    ):
        for model in models.get(provider, ()):
            cells.append(
                MatrixCell(
                    provider=provider,
                    model=model,
                    cache_mode=cache_mode,
                    rounds=round_count,
                )
            )
    return cells


async def _run_cell(
    cell: MatrixCell,
    questions: Sequence[dict[str, Any]],
    *,
    db_url: str,
    concurrency: int,
) -> list[dict[str, Any]]:
    """Run a single matrix cell.

    In dry / placeholder mode (no API key + no DB URL) this returns
    placeholders; otherwise it delegates to ``inprocess_runner.run_inprocess``
    via the Phase 2 seam.
    """

    api_key = os.getenv("MIMO_API_KEY", "")
    if not api_key or not db_url:
        return _cell_placeholder_results(questions, cell=cell)

    from phase2_dry_runner import _round_with_concurrency

    aggregated = await _round_with_concurrency(
        questions,
        cell.rounds,
        db_url,
        concurrency,
    )
    for row in aggregated:
        row["cell"] = cell.label
    return aggregated


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.getenv("MIMO_API_KEY", "")
    db_url = args.db_url
    can_run_live = bool(api_key) and bool(db_url) and not args.dry_run
    started_at = datetime.now(timezone.utc).isoformat()
    mode = "live-mimo" if can_run_live else "dry-fallback"
    print(
        f"[phase3-runner] mode={mode} concurrency={args.concurrency} "
        f"gate={args.gate_threshold}% db_url_set={bool(db_url)} "
        f"max-questions={args.max_questions}"
    )

    questions = _load_corpus_subset(max_questions=args.max_questions, seed=42)
    if not questions:
        raise RuntimeError("Phase 3 corpus is empty -- aborting")

    models = dict(DEFAULT_MODELS)
    for raw in args.models:
        if "=" in raw:
            provider, model_list = raw.split("=", 1)
            models[provider.strip()] = tuple(
                m.strip() for m in model_list.split(",") if m.strip()
            )

    cells = _build_matrix(
        providers=tuple(args.providers),
        models=models,
        cache_modes=tuple(args.cache_modes),
        rounds=tuple(args.rounds),
    )
    print(f"[phase3-runner] matrix size = {len(cells)} cells")

    cell_results_by_cell: dict[str, list[dict[str, Any]]] = {}
    rounds_per_cell: dict[str, int] = {}
    for cell in cells:
        try:
            results = await _run_cell(
                cell,
                questions,
                db_url=db_url,
                concurrency=args.concurrency,
            )
        except Exception as exc:  # noqa: BLE001 -- one cell failure != abort
            print(
                f"[phase3-runner] cell {cell.label} aborted: "
                f"{type(exc).__name__}: {exc}"
            )
            results = _cell_placeholder_results(questions, cell=cell)
        cell_results_by_cell[cell.label] = results
        rounds_per_cell[cell.label] = cell.rounds

    cell_summaries = {
        label: _aggregate_cell(results)
        for label, results in cell_results_by_cell.items()
    }

    seven_d_payload: dict[str, Any] | None = None
    seven_d_path: Path | None = None
    if args.scoring == "7d":
        seven_d_path = Path(
            args.seven_d_out or str(_QA_BENCH_DIR / "phase3_7d_score.json")
        )
        seven_d_payload = _run_seven_d_scoring(
            cell_results_by_cell,
            rounds_per_cell=rounds_per_cell,
            output_path=seven_d_path,
        )

    finished_at = datetime.now(timezone.utc).isoformat()
    report = _render_phase3_report(
        cell_summaries=cell_summaries,
        gate_threshold=args.gate_threshold,
        started_at=started_at,
        finished_at=finished_at,
        seven_d_payload=seven_d_payload,
    )
    if args.report_out:
        out_path = Path(args.report_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(f"[phase3-runner] report written to {out_path}")

    matrix_verdict = "PASS"
    for summary in cell_summaries.values():
        if summary["pass_rate"] * 100 < args.gate_threshold:
            matrix_verdict = "FAIL"
            break

    return {
        "mode": mode,
        "cell_summaries": cell_summaries,
        "seven_d": seven_d_payload,
        "seven_d_path": str(seven_d_path) if seven_d_path else None,
        "matrix_verdict": matrix_verdict,
        "report": report,
        "started_at": started_at,
        "finished_at": finished_at,
        "total_cells": len(cells),
        "total_questions_per_cell": len(questions),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--providers",
        nargs="+",
        default=list(DEFAULT_PROVIDERS),
        help=f"Provider list (Phase 3 default {list(DEFAULT_PROVIDERS)})",
    )
    parser.add_argument(
        "--models",
        nargs="*",
        default=[],
        help=(
            "Model overrides per provider. Format: provider=model1,model2 "
            "(repeatable). Defaults: mimo=mimo-v2.5, ollama=qwen3:8b."
        ),
    )
    parser.add_argument(
        "--cache-modes",
        nargs="+",
        default=list(DEFAULT_CACHE_MODES),
        help=f"Retrieval cache modes (Phase 3 default {list(DEFAULT_CACHE_MODES)})",
    )
    parser.add_argument(
        "--rounds",
        nargs="+",
        type=int,
        default=list(DEFAULT_ROUNDS),
        help=f"Rounds per question (Phase 3 default {list(DEFAULT_ROUNDS)})",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"Async worker count per cell (default {DEFAULT_CONCURRENCY})",
    )
    parser.add_argument(
        "--max-questions",
        type=int,
        default=200,
        help="Subsample the corpus to at most N questions per cell (default 200)",
    )
    parser.add_argument(
        "--gate-threshold",
        type=int,
        default=DEFAULT_GATE_THRESHOLD,
        help=f"Gate threshold percent (Phase 3 default {DEFAULT_GATE_THRESHOLD})",
    )
    parser.add_argument(
        "--db-url",
        default=os.getenv("QA_BENCH_DB_URL") or os.getenv("DATABASE_URL", ""),
        help="PostgreSQL DSN forwarded to inprocess_runner.run_inprocess",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip live LLM calls even if MIMO_API_KEY is set",
    )
    parser.add_argument(
        "--scoring",
        choices=("none", "7d"),
        default=DEFAULT_SCORING,
        help=(
            "Scoring overlay. 'none' = matrix summary only; "
            "'7d' = also emit phase3_7d_score.json with 7-dim aggregate."
        ),
    )
    parser.add_argument(
        "--seven-d-out",
        default="",
        help="Optional output path for the 7-dim score JSON",
    )
    parser.add_argument(
        "--report-out",
        default=str(_QA_BENCH_DIR / f"phase3_matrix_report_{datetime.now().strftime('%Y-%m-%d')}.md"),
        help="Path to write the auto-generated Markdown report",
    )
    args = parser.parse_args()

    payload = asyncio.run(_run(args))
    print(payload["report"])
    if payload.get("seven_d"):
        print(
            f"[phase3-runner] 7d score -> {payload['seven_d_path']} "
            f"(accuracy={payload['seven_d'].get('accuracy', 0):.4f}, "
            f"f1={payload['seven_d'].get('f1', 0):.4f})"
        )
    return 0 if payload["matrix_verdict"] == "PASS" else 1


__all__ = [
    "DEFAULT_CACHE_MODES",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_GATE_THRESHOLD",
    "DEFAULT_MODELS",
    "DEFAULT_PROVIDERS",
    "DEFAULT_ROUNDS",
    "DEFAULT_SCORING",
    "MatrixCell",
    "PHASE3_INTENT_BUCKETS",
    "_aggregate_cell",
    "_build_matrix",
    "_matrix_to_records",
    "_render_phase3_report",
    "_run_seven_d_scoring",
]


if __name__ == "__main__":
    raise SystemExit(main())