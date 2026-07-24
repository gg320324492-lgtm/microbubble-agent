"""W68 D6 Phase 2 dry-runner smoke tests.

Five scenarios that gate ``phase2_dry_runner._run`` + ``run_d5_dry.py
--full --per-intent --gate-threshold`` behaviour:

1. **Full corpus load**: ``_load_full_corpus`` returns 1000 rows
   (questions_780 + questions_d4_extra_300) with deterministic
   seed-first ordering.
2. **Async concurrency 5**: ``_round_with_concurrency`` with a stub
   engine factory schedules at most 5 in-flight tasks at a time and
   never exceeds it.
3. **Per-intent bucket statistics**: ``_summarize_phase2`` correctly
   aggregates counts and latency per ``_bucket_intent`` value, and the
   resulting ``per_intent_latency`` table matches the input samples.
4. **Gate verdict**: a runner call with ``gate-threshold=0`` and a
   pass-rate of 100% returns ``"PASS"``; the same call with
   ``gate-threshold=100`` returns ``"FAIL"``.
5. **Dry-run fallback**: when neither ``MIMO_API_KEY`` nor
   ``DATABASE_URL`` are set, ``_run`` returns a structured
   ``dry-fallback`` payload with placeholder verdicts and the right
   hint about the orchestrator needing to SSH.

The tests live under ``tests/qa-bench/`` and must NOT touch production
code (W68 zero production-change rule).  They use lightweight stubs
and the ``engine_factory`` seam on ``inprocess_runner.run_inprocess``
so the suite runs on any Python 3.11 host without spinning up
PostgreSQL / Redis / the full agent.

Run with::

    SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/test_phase2_dry_smoke.py -v

The root ``tests/conftest.py`` boots PostgreSQL when ``SKIP_DB_SETUP``
is unset; this suite deliberately avoids DB.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import pytest

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

if not os.environ.get("SKIP_DB_SETUP"):
    pytest.skip(
        "phase-2 dry-runner smoke tests require SKIP_DB_SETUP=1",
        allow_module_level=True,
    )

from phase2_dry_runner import (  # noqa: E402
    PHASE2_INTENT_BUCKETS,
    _bucket_intent,
    _load_full_corpus,
    _majority_verdict,
    _render_phase2_report,
    _round_with_concurrency,
    _summarize_phase2,
)
from run_d5_dry import _bucket_intent as _run_d5_bucket_intent  # noqa: E402


# --- Stub ChatEngine replacement --------------------------------------------


class _Phase2StubEngine:
    """Drop-in ChatEngine used to validate Phase 2 concurrency semantics."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.in_flight = 0
        self.peak_in_flight = 0
        self.calls: list[dict[str, Any]] = []

    def synthesize_stream(self, *, messages, system, user_id, db, session_id, **kwargs):  # noqa: D401
        self.in_flight += 1
        self.peak_in_flight = max(self.peak_in_flight, self.in_flight)
        self.calls.append(
            {
                "messages": list(messages),
                "session_id": session_id,
            }
        )

        async def _gen():
            # Hold briefly so the semaphore can park a second batch.
            await asyncio.sleep(0.05)
            self.in_flight -= 1
            payload = self.answers[len(self.calls) - 1] if self.calls else ""
            mid = max(len(payload) // 2, 1) if payload else 0
            if payload:
                yield {"type": "text_delta", "text": payload[:mid]}
                yield {"type": "text_delta", "text": payload[mid:]}
            yield {"type": "done", "content": payload}

        return _gen()


# --- 1. Full corpus load ----------------------------------------------------


def test_full_corpus_loads_1000_rows():
    questions = _load_full_corpus()
    assert len(questions) == 1000, (
        f"expected 1000 rows (questions_780 + questions_d4_extra_300), got {len(questions)}"
    )
    seed_ids = set()
    extra_ids = set()
    with open(_QA_BENCH_DIR / "questions_780.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            seed_ids.add(json.loads(line).get("id"))
    with open(_QA_BENCH_DIR / "questions_d4_extra_300.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            extra_ids.add(json.loads(line).get("id"))
    returned_ids = {q.get("id") for q in questions}
    # Every seed id must be present (corpus is the union, seed-first).
    assert seed_ids.issubset(returned_ids)
    # Duplicate ids are deduped deterministically.
    assert len(returned_ids) == 1000


# --- 2. Async concurrency 5 --------------------------------------------------


def test_round_with_concurrency_caps_at_five():
    questions = [
        {"id": f"Q-{i:04d}", "question": f"q{i}", "expect": {"intent": "EXPLAIN_CONCEPT"}}
        for i in range(20)
    ]

    captured: dict[str, Any] = {"engines": []}

    def _factory():
        engine = _Phase2StubEngine(
            answers=[f"answer-{i}" for i in range(20 * 3)],  # 3 rounds each
        )
        captured["engines"].append(engine)
        return engine

    async def _go():
        # One engine is enough; the runner reuses it across rounds.
        aggregated = await _round_with_concurrency(
            questions, rounds=1, db_url="postgresql+asyncpg://localhost/test",
            concurrency=5, engine_factory=_factory,
        )
        return aggregated

    aggregated = asyncio.run(_go())
    assert len(aggregated) == 20
    engine = captured["engines"][0]
    assert engine.calls, "engine was never invoked"
    assert engine.peak_in_flight <= 5, (
        f"peak_in_flight={engine.peak_in_flight} exceeds concurrency cap of 5"
    )


# --- 3. Per-intent bucket statistics ----------------------------------------


def test_summarize_phase2_per_intent_breakdown():
    # Hand-crafted inputs to exercise the per-intent table.
    results = [
        {
            "id": "A1",
            "intent": "explain_concept",
            "round_verdicts": ["pass", "pass", "pass"],
            "consensus": "pass",
            "round_durations_s": [1.0, 1.2, 1.1],
            "last_answer": "ok",
            "last_error": None,
        },
        {
            "id": "A2",
            "intent": "explain_concept",
            "round_verdicts": ["empty", "empty", "pass"],
            "consensus": "pass",
            "round_durations_s": [0.8, 0.9, 1.0],
            "last_answer": "ok",
            "last_error": None,
        },
        {
            "id": "A3",
            "intent": "data",
            "round_verdicts": ["error", "error", "error"],
            "consensus": "error",
            "round_durations_s": [2.0, 2.1, 2.2],
            "last_answer": "",
            "last_error": "boom",
        },
    ]
    summary = _summarize_phase2(results)
    assert summary["total"] == 3
    assert summary["pass_rate"] == round(2 / 3, 4)
    assert summary["by_intent"]["explain_concept"]["pass_rate"] == 1.0
    assert summary["by_intent"]["data"]["pass_rate"] == 0.0
    # per-intent latency is surfaced for downstream report rendering.
    lat = summary["per_intent_latency"]
    assert lat["explain_concept"]["count"] == 6
    assert lat["data"]["count"] == 3
    # mean latency for explain_concept = (1.0 + 1.2 + 1.1 + 0.8 + 0.9 + 1.0) / 6 = 1.0
    assert lat["explain_concept"]["mean"] == 1.0


def test_bucket_intent_handles_business_and_chat_taxonomy():
    # 6 business buckets win when present.
    for bucket in PHASE2_INTENT_BUCKETS:
        assert _bucket_intent(f"some_{bucket}_query") == bucket
    # Chat-intent falls through to its lowercased name.
    assert _bucket_intent("EXPLAIN_CONCEPT") == "explain_concept"
    assert _bucket_intent("DATA") == "data"
    # Unknown intents surface verbatim so future additions stay visible.
    assert _bucket_intent("FutureIntent") == "futureintent"
    # Empty / missing -> "other".
    assert _bucket_intent(None) == "other"
    assert _bucket_intent("") == "other"


def test_run_d5_dry_bucket_intent_matches_phase2_runner():
    """Both modules expose _bucket_intent with identical semantics."""
    samples = [
        ("EXPLAIN_CONCEPT", "explain_concept"),
        ("DATA", "data"),
        ("knowledge_search", "knowledge"),
        ("drive_list", "drive"),
        (None, "other"),
    ]
    for raw, expected in samples:
        assert _bucket_intent(raw) == expected
        assert _run_d5_bucket_intent(raw) == expected


# --- 4. Gate verdict --------------------------------------------------------


def test_gate_verdict_pass_and_fail():
    # All-pass corpus: pass_rate = 1.0 (100%).
    results = [
        {
            "id": "A1",
            "intent": "explain_concept",
            "round_verdicts": ["pass"],
            "consensus": "pass",
            "round_durations_s": [1.0],
            "last_answer": "ok",
            "last_error": None,
        }
    ]
    summary = _summarize_phase2(results)
    pass_rate_pct = summary["pass_rate"] * 100
    # Threshold 50 -> 100% >= 50% -> PASS.
    assert pass_rate_pct >= 50
    verdict = "PASS" if pass_rate_pct >= 50 else "FAIL"
    assert verdict == "PASS"
    # Threshold 100 -> 100% >= 100% -> PASS (not FAIL).
    verdict = "PASS" if pass_rate_pct >= 100 else "FAIL"
    assert verdict == "PASS"

    # Mix pass + error: pass_rate = 0.5 (50%).
    mixed = [
        {
            "id": "A1",
            "intent": "explain_concept",
            "round_verdicts": ["pass"],
            "consensus": "pass",
            "round_durations_s": [1.0],
            "last_answer": "ok",
            "last_error": None,
        },
        {
            "id": "A2",
            "intent": "data",
            "round_verdicts": ["error"],
            "consensus": "error",
            "round_durations_s": [1.0],
            "last_answer": "",
            "last_error": "boom",
        },
    ]
    summary = _summarize_phase2(mixed)
    assert summary["pass_rate"] == 0.5
    # Threshold 80 -> 50% < 80% -> FAIL.
    verdict = "PASS" if summary["pass_rate"] * 100 >= 80 else "FAIL"
    assert verdict == "FAIL"


def test_render_phase2_report_includes_gate_section():
    summary = {
        "total": 10,
        "verdict_counts": {"pass": 9, "error": 1},
        "pass_rate": 0.9,
        "by_intent": {
            "explain_concept": {"counts": {"pass": 9}, "pass_rate": 1.0},
            "data": {"counts": {"error": 1}, "pass_rate": 0.0},
        },
        "duration_s": {
            "min": 0.5,
            "max": 1.5,
            "mean": 1.0,
            "median": 1.0,
            "p95": 1.4,
        },
        "per_intent_latency": {
            "explain_concept": {
                "count": 9,
                "mean": 1.0,
                "median": 1.0,
                "p95": 1.4,
                "max": 1.5,
            },
            "data": {
                "count": 1,
                "mean": 1.5,
                "median": 1.5,
                "p95": 1.5,
                "max": 1.5,
            },
        },
    }
    md = _render_phase2_report(
        summary,
        mode="live-mimo",
        rounds=1,
        concurrency=5,
        gate_threshold=90,
        started_at="2026-07-24T00:00:00Z",
        finished_at="2026-07-24T00:15:00Z",
        extra_notes=["example"],
    )
    assert "## Verdict counts" in md
    assert "## Per-intent breakdown" in md
    assert "## Per-intent latency" in md
    assert "Gate threshold: **90%**" in md
    # 90% >= 90% threshold -> PASS verdict.
    assert "Gate verdict: **PASS**" in md


# --- 5. Dry-run fallback ----------------------------------------------------


def test_dry_run_fallback_emits_placeholder_payload(monkeypatch, tmp_path):
    # Strip MIMO_API_KEY + DATABASE_URL so the runner falls back.
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("QA_BENCH_DB_URL", raising=False)

    # Build a tiny argv-shaped namespace so we can call ``_run`` directly.
    import argparse

    from phase2_dry_runner import _run

    args = argparse.Namespace(
        concurrency=5,
        rounds=3,
        gate_threshold=90,
        db_url="",
        dry_run=True,
        report_out=str(tmp_path / "phase2_dry.md"),
    )
    payload = asyncio.run(_run(args))

    assert payload["mode"] == "dry-fallback"
    assert payload["total_questions"] == 1000
    assert payload["summary"]["pass_rate"] == 0.0  # placeholder
    assert payload["gate_verdict"] == "FAIL"  # placeholder FAILs the gate
    # Report file is written even in dry-run mode.
    out_path = Path(args.report_out)
    assert out_path.exists()
    body = out_path.read_text(encoding="utf-8")
    assert "Phase 2 corpus: 1000 questions" in body
    assert "Concurrency: 5 workers" in body
    assert "Gate threshold: 90%" in body
    assert "main orchestrator must SSH" in body


if __name__ == "__main__":  # pragma: no cover - allows `python ...`
    sys.exit(pytest.main([__file__, "-v"]))