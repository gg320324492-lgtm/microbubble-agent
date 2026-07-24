"""W68 D6 / W69 7-dimension scoring algorithm.

Pure-function scorer for qa-bench.  Lives under ``tests/qa-bench/scoring/``
only and never imports from production code (W68 zero production-change
rule).

The seven dimensions are:

1.  **Accuracy**     – hits / total answers produced.
2.  **Recall**       – hits / ground-truth-positive items.
3.  **Precision**    – hits / answers marked pass/fail (truthful items).
4.  **F1**           – harmonic mean of precision and recall.
5.  **Consistency**  – share of rounds whose verdict matches the
    majority verdict (per question, averaged across questions).
6.  **Entropy**      – Shannon entropy of the per-question verdict
    distribution; lower entropy means the model converges faster.
7.  **Latency**      – aggregate timing statistics (avg / p50 / p95 / p99)
    across rounds.

A "verdict" is one of ``pass`` / ``fail`` / ``empty`` / ``error`` /
``skipped`` / ``unknown`` (string).  Each ``VerdictRecord`` represents
one round of one question.  Aggregations honour round-level data
(per-round latency, per-round verdicts) so the output is reproducible
from the raw records.

Usage::

    from verdict_consensus_v2 import confidence_verdict
    from seven_d_scoring import SevenDimScore, score_records

    records = [...]  # list[VerdictRecord]
    seven = score_records(records)
    print(seven.as_dict())

CLI::

    python -m tests.qa-bench.scoring.seven_d_scoring \\
        --input results.jsonl \\
        --output 7d_score.json

The CLI reads one ``VerdictRecord`` per line (JSONL) and emits a
structured ``SevenDimScore`` payload (JSON).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

_QA_BENCH_DIR = Path(__file__).resolve().parent.parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

# Verdict vocabulary shared with phase2_dry_runner._majority_verdict.
VALID_VERDICTS: tuple[str, ...] = (
    "pass",
    "fail",
    "empty",
    "error",
    "skipped",
    "unknown",
)
ANSWERED_VERDICTS: tuple[str, ...] = ("pass", "fail")
NEGATIVE_VERDICTS: tuple[str, ...] = ("empty", "error", "skipped")

# Latency percentile cut-points used when emitting aggregates.
LATENCY_PERCENTILES: tuple[float, ...] = (50.0, 95.0, 99.0)


@dataclass(slots=True)
class VerdictRecord:
    """One round of one question.  Multiple rounds per question are normal."""

    question_id: str
    verdict: str = "unknown"
    ground_truth_positive: bool = True
    latency_ms: float = 0.0
    intent: str = "other"
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LatencyStats:
    """Aggregate latency statistics in milliseconds."""

    count: int = 0
    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0


@dataclass(slots=True)
class SevenDimScore:
    """All seven scoring dimensions plus provenance."""

    total_questions: int = 0
    total_rounds: int = 0

    accuracy: float = 0.0
    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0

    consistency: float = 0.0
    entropy: float = 0.0
    entropy_max: float = 0.0
    entropy_normalized: float = 0.0

    latency: LatencyStats = field(default_factory=LatencyStats)
    per_intent: dict[str, dict[str, float]] = field(default_factory=dict)

    verdict_counts: dict[str, int] = field(default_factory=dict)
    confidence_high: int = 0
    confidence_low: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _percentile(samples: Sequence[float], pct: float) -> float:
    """Linear-interpolated percentile.  ``pct`` in ``[0, 100]``."""

    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (pct / 100.0) * (len(ordered) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    fraction = rank - lower
    return float(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction)


def _normalize_verdict(raw: str) -> str:
    raw_lower = (raw or "").strip().lower()
    if raw_lower in VALID_VERDICTS:
        return raw_lower
    return "unknown"


def _group_by_question(
    records: Iterable[VerdictRecord],
) -> dict[str, list[VerdictRecord]]:
    grouped: dict[str, list[VerdictRecord]] = {}
    for record in records:
        grouped.setdefault(record.question_id, []).append(record)
    return grouped


def _question_consistency(rounds: Sequence[VerdictRecord]) -> float:
    """Share of rounds whose verdict matches the majority verdict."""

    if not rounds:
        return 0.0
    verdicts = [r.verdict for r in rounds]
    counts = Counter(verdicts)
    majority_count = counts.most_common(1)[0][1]
    return majority_count / len(verdicts)


def _question_entropy(rounds: Sequence[VerdictRecord]) -> float:
    """Shannon entropy (base e) of the per-question verdict distribution."""

    if not rounds:
        return 0.0
    counts = Counter(r.verdict for r in rounds)
    total = sum(counts.values())
    entropy = 0.0
    for count in counts.values():
        if count <= 0:
            continue
        p = count / total
        entropy -= p * math.log(p)
    return entropy


def _aggregate_latency(records: Iterable[VerdictRecord]) -> LatencyStats:
    samples = [float(r.latency_ms) for r in records if r.latency_ms >= 0]
    if not samples:
        return LatencyStats()
    return LatencyStats(
        count=len(samples),
        avg_ms=round(statistics.mean(samples), 3),
        p50_ms=round(_percentile(samples, 50.0), 3),
        p95_ms=round(_percentile(samples, 95.0), 3),
        p99_ms=round(_percentile(samples, 99.0), 3),
        max_ms=round(max(samples), 3),
    )


def _score_subset(records: Sequence[VerdictRecord]) -> dict[str, float]:
    """Score accuracy / recall / precision / F1 on a record subset."""

    if not records:
        return {
            "accuracy": 0.0,
            "recall": 0.0,
            "precision": 0.0,
            "f1": 0.0,
            "hits": 0,
            "answered": 0,
            "positives": 0,
        }

    hits = 0
    answered = 0
    positives = 0
    for record in records:
        if record.ground_truth_positive:
            positives += 1
        if record.verdict in ANSWERED_VERDICTS:
            answered += 1
            if record.verdict == "pass" and record.ground_truth_positive:
                hits += 1

    accuracy = hits / len(records) if records else 0.0
    recall = hits / positives if positives else 0.0
    precision = hits / answered if answered else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    return {
        "accuracy": accuracy,
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "hits": hits,
        "answered": answered,
        "positives": positives,
    }


def score_records(records: Sequence[VerdictRecord]) -> SevenDimScore:
    """Compute the full 7-dimension score over a sequence of rounds.

    ``records`` is the flat list of ``VerdictRecord`` instances; per-question
    grouping is reconstructed internally so callers don't have to chunk
    by question id themselves.
    """

    normalized = [
        VerdictRecord(
            question_id=r.question_id,
            verdict=_normalize_verdict(r.verdict),
            ground_truth_positive=bool(r.ground_truth_positive),
            latency_ms=float(r.latency_ms),
            intent=r.intent or "other",
            error=r.error,
            metadata=dict(r.metadata or {}),
        )
        for r in records
    ]

    if not normalized:
        return SevenDimScore()

    seven = SevenDimScore(
        total_rounds=len(normalized),
        verdict_counts=dict(Counter(r.verdict for r in normalized)),
    )

    grouped = _group_by_question(normalized)
    seven.total_questions = len(grouped)

    # --- dimensions 1-4: accuracy / recall / precision / F1 -------------
    aggregate = _score_subset(normalized)
    seven.accuracy = round(aggregate["accuracy"], 4)
    seven.recall = round(aggregate["recall"], 4)
    seven.precision = round(aggregate["precision"], 4)
    seven.f1 = round(aggregate["f1"], 4)

    # --- dimension 5: consistency (averaged per-question) ---------------
    consistencies = [_question_consistency(rounds) for rounds in grouped.values()]
    seven.consistency = round(
        statistics.mean(consistencies) if consistencies else 0.0, 4
    )

    # --- dimension 6: entropy (averaged per-question) -------------------
    entropies = [_question_entropy(rounds) for rounds in grouped.values()]
    seven.entropy = round(statistics.mean(entropies) if entropies else 0.0, 4)
    max_entropy = (
        math.log(max(len(rounds) for rounds in grouped.values()))
        if grouped
        else 0.0
    )
    seven.entropy_max = round(max_entropy, 4)
    if max_entropy > 0:
        seven.entropy_normalized = round(seven.entropy / max_entropy, 4)

    # --- dimension 7: latency statistics --------------------------------
    seven.latency = _aggregate_latency(normalized)

    # --- per-intent slice ----------------------------------------------
    by_intent: dict[str, list[VerdictRecord]] = {}
    for record in normalized:
        by_intent.setdefault(record.intent, []).append(record)
    per_intent_payload: dict[str, dict[str, float]] = {}
    for intent, subset in sorted(by_intent.items()):
        sub_score = _score_subset(subset)
        latencies = [r.latency_ms for r in subset if r.latency_ms >= 0]
        per_intent_payload[intent] = {
            "questions": len({r.question_id for r in subset}),
            "rounds": len(subset),
            "accuracy": round(sub_score["accuracy"], 4),
            "recall": round(sub_score["recall"], 4),
            "precision": round(sub_score["precision"], 4),
            "f1": round(sub_score["f1"], 4),
            "avg_latency_ms": round(statistics.mean(latencies), 3)
            if latencies
            else 0.0,
        }
    seven.per_intent = per_intent_payload

    # --- confidence breakdown (delegated to verdict_consensus_v2) ------
    try:
        from verdict_consensus_v2 import confidence_for_question  # noqa: WPS433
    except ImportError:  # pragma: no cover - sibling module not on path
        confidence_for_question = None  # type: ignore[assignment]

    if confidence_for_question is not None:
        for _question_id, rounds in grouped.items():
            confidence = confidence_for_question(rounds)
            if confidence >= 0.5:
                seven.confidence_high += 1
            else:
                seven.confidence_low += 1

    return seven


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _records_from_jsonl(path: Path) -> list[VerdictRecord]:
    """Load ``VerdictRecord`` objects from a JSONL file."""

    out: list[VerdictRecord] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON on line {line_no} of {path}: {exc}"
                ) from exc
            if not isinstance(raw, Mapping):
                continue
            out.append(
                VerdictRecord(
                    question_id=str(
                        raw.get("question_id") or raw.get("id") or f"line-{line_no}"
                    ),
                    verdict=str(raw.get("verdict", "unknown")),
                    ground_truth_positive=bool(
                        raw.get("ground_truth_positive", True)
                    ),
                    latency_ms=float(raw.get("latency_ms", 0.0)),
                    intent=str(raw.get("intent", "other")),
                    error=raw.get("error"),
                    metadata=dict(raw.get("metadata") or {}),
                )
            )
    return out


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="JSONL file with one VerdictRecord per line",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Path to write the JSON SevenDimScore payload",
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Also print the JSON payload to stdout",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if not args.input.exists():
        print(f"[seven-d] input file not found: {args.input}", file=sys.stderr)
        return 2

    try:
        records = _records_from_jsonl(args.input)
    except ValueError as exc:
        print(f"[seven-d] {exc}", file=sys.stderr)
        return 2

    seven = score_records(records)
    payload = seven.as_dict()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if args.print:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"[seven-d] scored {seven.total_questions} questions "
            f"({seven.total_rounds} rounds) -> {args.output}"
        )
    return 0


__all__ = [
    "ANSWERED_VERDICTS",
    "LATENCY_PERCENTILES",
    "NEGATIVE_VERDICTS",
    "SevenDimScore",
    "VALID_VERDICTS",
    "VerdictRecord",
    "_percentile",
    "score_records",
]


if __name__ == "__main__":  # pragma: no cover - module CLI
    sys.exit(main())