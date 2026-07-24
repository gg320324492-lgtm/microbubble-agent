"""W68 D6 / W69 7-dimension scoring unit tests.

Ten scenarios that gate ``seven_d_scoring.score_records`` and the
companion ``verdict_consensus_v2``:

1.  Perfect pass: every round ``pass`` -> all dims hit their maximum.
2.  All error: every round ``error`` -> accuracy / recall / precision
    collapse to 0; entropy 0; consistency 1.
3.  Half correct / half empty: deterministic F1, low entropy.
4.  Entropy = 0: unanimous verdicts yield ``entropy_normalized = 0``.
5.  Entropy = max: uniform rounds yield ``entropy_normalized ≈ 1``.
6.  Mixed intents: per-intent slice exposes the right accuracy split.
7.  Latency P99: percentile helper surfaces the correct tail value.
8.  Single round: degenerate input still produces a stable score.
9.  Three rounds: standard benchmark cadence.
10. Multiple intents: aggregation keys match the input distribution.

The tests live under ``tests/qa-bench/scoring/`` and never touch
production code (W68 zero production-change rule).  Run with::

    SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/scoring/test_seven_d_scoring.py -v
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Sequence

import pytest

_SCORING_DIR = Path(__file__).resolve().parent
_QA_BENCH_DIR = _SCORING_DIR.parent
for _p in (str(_SCORING_DIR), str(_QA_BENCH_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

if not os.environ.get("SKIP_DB_SETUP"):
    pytest.skip(
        "seven-d scoring tests require SKIP_DB_SETUP=1",
        allow_module_level=True,
    )

from seven_d_scoring import (  # noqa: E402
    ANSWERED_VERDICTS,
    VerdictRecord,
    _percentile,
    score_records,
)
from verdict_consensus_v2 import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    confidence_for_question,
    confidence_verdict,
)


def _records(
    *,
    n_rounds: int,
    verdicts: Sequence[str],
    latencies_ms: Sequence[float],
    intent: str = "data",
    ground_truth_positive: bool = True,
    question_id: str = "Q-0001",
) -> list[VerdictRecord]:
    """Build ``n_rounds`` ``VerdictRecord`` instances with shared metadata."""

    assert len(verdicts) == n_rounds
    assert len(latencies_ms) == n_rounds
    return [
        VerdictRecord(
            question_id=question_id,
            verdict=v,
            ground_truth_positive=ground_truth_positive,
            latency_ms=latency,
            intent=intent,
        )
        for v, latency in zip(verdicts, latencies_ms)
    ]


# --- 1. Perfect pass -------------------------------------------------------


def test_perfect_pass_yields_max_dimensions():
    records = _records(
        n_rounds=3,
        verdicts=("pass", "pass", "pass"),
        latencies_ms=(100.0, 110.0, 105.0),
        intent="data",
    )
    seven = score_records(records)
    assert seven.total_questions == 1
    assert seven.total_rounds == 3
    assert seven.accuracy == 1.0
    assert seven.recall == 1.0
    assert seven.precision == 1.0
    assert seven.f1 == 1.0
    assert seven.consistency == 1.0
    assert seven.entropy == 0.0
    assert seven.entropy_max == pytest.approx(1.0986, abs=0.01)
    assert seven.confidence_high == 1
    assert seven.confidence_low == 0


# --- 2. All error ----------------------------------------------------------


def test_all_error_collapses_accuracy_metrics():
    records = _records(
        n_rounds=3,
        verdicts=("error", "error", "error"),
        latencies_ms=(50.0, 55.0, 60.0),
    )
    seven = score_records(records)
    assert seven.accuracy == 0.0
    assert seven.recall == 0.0
    assert seven.precision == 0.0
    assert seven.f1 == 0.0
    assert seven.consistency == 1.0  # unanimous even when "wrong"
    assert seven.entropy == 0.0
    assert seven.confidence_high == 1  # unanimous => confident
    assert seven.confidence_low == 0


# --- 3. Half correct, half empty ------------------------------------------


def test_half_correct_half_empty_f1_is_deterministic():
    rounds_q1 = _records(
        n_rounds=4,
        verdicts=("pass", "pass", "empty", "empty"),
        latencies_ms=(100.0, 110.0, 50.0, 60.0),
        question_id="Q-1",
    )
    seven = score_records(rounds_q1)
    # 2 pass / 4 rounds = 0.5 accuracy; 2 pass / 4 rounds positives = 0.5
    # recall; precision = 2 / 2 = 1.0; F1 = 2*1*0.5 / (1+0.5) = 0.6667.
    assert seven.accuracy == 0.5
    assert seven.recall == 0.5
    assert seven.precision == 1.0
    assert seven.f1 == pytest.approx(0.6667, abs=0.001)
    assert seven.consistency == 0.5


# --- 4. Entropy = 0 --------------------------------------------------------


def test_unanimous_entropy_is_zero():
    records = _records(
        n_rounds=5,
        verdicts=("pass",) * 5,
        latencies_ms=(100.0,) * 5,
    )
    seven = score_records(records)
    assert seven.entropy == 0.0
    assert seven.entropy_normalized == 0.0


# --- 5. Entropy = max ------------------------------------------------------


def test_uniform_entropy_is_max():
    verdicts = ("pass", "fail", "empty", "error")
    records = _records(
        n_rounds=4,
        verdicts=verdicts,
        latencies_ms=(100.0,) * 4,
    )
    seven = score_records(records)
    # 4 distinct verdicts in 4 rounds = max entropy = ln(4) ≈ 1.3863.
    assert seven.entropy == pytest.approx(1.3863, abs=0.01)
    assert seven.entropy_normalized == pytest.approx(1.0, abs=0.001)
    # Each verdict appears once => majority share = 0.25.
    assert seven.consistency == 0.25
    # Confidence must collapse below threshold.
    confidence = confidence_for_question(records)
    assert confidence < DEFAULT_CONFIDENCE_THRESHOLD


# --- 6. Mixed intents ------------------------------------------------------


def test_per_intent_breakdown_respects_buckets():
    rounds_data = _records(
        n_rounds=2,
        verdicts=("pass", "pass"),
        latencies_ms=(100.0, 110.0),
        intent="data",
        question_id="Q-data",
    )
    rounds_knowledge = _records(
        n_rounds=2,
        verdicts=("pass", "fail"),
        latencies_ms=(200.0, 210.0),
        intent="knowledge",
        question_id="Q-know",
    )
    rounds_meeting = _records(
        n_rounds=2,
        verdicts=("error", "error"),
        latencies_ms=(300.0, 310.0),
        intent="meeting",
        question_id="Q-meet",
    )
    seven = score_records(rounds_data + rounds_knowledge + rounds_meeting)
    assert seven.total_questions == 3
    assert seven.per_intent["data"]["accuracy"] == 1.0
    assert seven.per_intent["data"]["rounds"] == 2
    assert seven.per_intent["knowledge"]["accuracy"] == 0.5
    assert seven.per_intent["meeting"]["accuracy"] == 0.0


# --- 7. Latency P99 --------------------------------------------------------


def test_latency_p99_percentile_helper():
    samples = list(range(1, 101))  # 1..100
    p99 = _percentile(samples, 99.0)
    # Linear interpolation => index 98.01 -> 99.01.
    assert p99 == pytest.approx(99.01, abs=0.01)

    # Aggregated latency stats survive the full record path.
    records = _records(
        n_rounds=100,
        verdicts=("pass",) * 100,
        latencies_ms=[float(i + 1) for i in range(100)],
    )
    seven = score_records(records)
    assert seven.latency.count == 100
    assert seven.latency.avg_ms == pytest.approx(50.5, abs=0.01)
    assert seven.latency.p50_ms == pytest.approx(50.5, abs=0.01)
    assert seven.latency.p99_ms == pytest.approx(99.01, abs=0.01)


# --- 8. Single round -------------------------------------------------------


def test_single_round_still_scores():
    records = _records(
        n_rounds=1,
        verdicts=("pass",),
        latencies_ms=(42.0,),
        intent="casual",
    )
    seven = score_records(records)
    assert seven.total_questions == 1
    assert seven.total_rounds == 1
    assert seven.accuracy == 1.0
    assert seven.consistency == 1.0
    assert seven.entropy == 0.0
    assert seven.entropy_max == 0.0
    assert seven.entropy_normalized == 0.0
    assert seven.confidence_high == 1


# --- 9. Three rounds consensus ---------------------------------------------


def test_three_rounds_split_verdict():
    records = _records(
        n_rounds=3,
        verdicts=("pass", "pass", "fail"),
        latencies_ms=(100.0, 105.0, 110.0),
        question_id="Q-3round",
    )
    seven = score_records(records)
    # 2 hits / 3 rounds = 0.6667 accuracy.
    assert seven.accuracy == pytest.approx(0.6667, abs=0.001)
    # Majority verdict is "pass" with 2/3 share.
    assert seven.consistency == pytest.approx(0.6667, abs=0.001)
    # Confidence is *below* the default threshold because entropy is
    # non-trivial (one dissenting round out of three).  Document the
    # observed value so future regressions surface explicitly.
    confidence = confidence_for_question(records)
    assert confidence == pytest.approx(0.4206, abs=0.001)
    assert confidence < DEFAULT_CONFIDENCE_THRESHOLD
    # Aggregator marks this question as low confidence.
    assert seven.confidence_low == 1
    assert seven.confidence_high == 0


# --- 10. Multiple intents with verdict_counts ----------------------------


def test_verdict_counts_match_distribution():
    rounds = _records(
        n_rounds=2,
        verdicts=("pass", "fail"),
        latencies_ms=(80.0, 90.0),
        intent="task",
        question_id="Q-mixed",
    ) + _records(
        n_rounds=2,
        verdicts=("empty", "empty"),
        latencies_ms=(50.0, 55.0),
        intent="task",
        question_id="Q-empty",
    )
    seven = score_records(rounds)
    assert seven.verdict_counts == {"pass": 1, "fail": 1, "empty": 2}
    # 1 hit / 4 rounds = 0.25 accuracy; 1 pass / 2 answered = 0.5 precision.
    assert seven.accuracy == 0.25
    assert seven.precision == 0.5
    # Unanimous empty rounds => confidence = 1.0 => answered (model
    # is confidently saying "no answer").  Decline requires entropy.
    consensus_empty = confidence_verdict(rounds[-2:])
    assert consensus_empty.decision == "answered"
    assert consensus_empty.confidence == 1.0
    # Uniform mix (pass / fail / empty / error) produces zero confidence.
    mixed = (
        _records(
            n_rounds=4,
            verdicts=("pass", "fail", "empty", "error"),
            latencies_ms=(1.0, 2.0, 3.0, 4.0),
            question_id="Q-mix",
        )
    )
    consensus_mixed = confidence_verdict(mixed)
    assert consensus_mixed.decision == "declined"
    assert consensus_mixed.confidence == pytest.approx(0.0, abs=0.001)


# --- CLI round-trip --------------------------------------------------------


def test_cli_round_trip(tmp_path: Path):
    records = _records(
        n_rounds=2,
        verdicts=("pass", "pass"),
        latencies_ms=(100.0, 110.0),
        question_id="Q-cli",
    ) + _records(
        n_rounds=2,
        verdicts=("fail", "fail"),
        latencies_ms=(120.0, 130.0),
        intent="knowledge",
        question_id="Q-cli-k",
        ground_truth_positive=False,
    )
    input_path = tmp_path / "records.jsonl"
    output_path = tmp_path / "7d_score.json"
    with input_path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(
                json.dumps(
                    {
                        "question_id": record.question_id,
                        "verdict": record.verdict,
                        "ground_truth_positive": record.ground_truth_positive,
                        "latency_ms": record.latency_ms,
                        "intent": record.intent,
                    }
                )
                + "\n"
            )

    from seven_d_scoring import main as cli_main

    rc = cli_main(["--input", str(input_path), "--output", str(output_path)])
    assert rc == 0
    assert output_path.exists()
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["total_questions"] == 2
    assert payload["total_rounds"] == 4
    # 2 hits (Q-cli pass*2 with positive=True) / 4 rounds = 0.5 accuracy.
    assert payload["accuracy"] == 0.5
    # 2 hits / 2 positives (Q-cli only) = 1.0 recall.
    assert payload["recall"] == 1.0
    # ANSWERED_VERDICTS = ("pass", "fail") so 4 answered => precision = 2 / 4.
    assert payload["precision"] == 0.5


if __name__ == "__main__":  # pragma: no cover - allows `python ...`
    sys.exit(pytest.main([__file__, "-v"]))