"""W68 第 11 批 C-2 unified output CLI smoke tests.

Five scenarios that gate the new ``--output-format`` / ``--input`` /
``--seven-d`` flags across ``run_d5_dry`` (Phase 1 / Phase 2),
``phase2_dry_runner`` and ``phase3_matrix_runner``:

1. ``--output results.json`` -> on-disk file is valid JSON with the
   ``format_version`` + ``schema`` + ``phase`` envelope.
2. ``--output results.md`` -> on-disk file is a Markdown report that
   contains the legacy heading.
3. ``--output results`` (no suffix) -> default ``auto`` resolves to
   JSON (so SOP documents that pass a bare name keep getting
   structured data).
4. ``--input custom.jsonl`` + ``--output results.json`` round-trip ->
   the on-disk JSON's ``summary.total`` matches the input corpus row
   count, exercising both the loader and the writer.
5. ``--output-format json`` explicit override -> even when ``--output``
   has a ``.md`` suffix, the runner writes JSON.  Symmetric for ``md``
   override.

The tests live under ``tests/qa-bench/`` and must NOT touch production
code (W68 zero production-change rule).  They use the runner CLIs as
black boxes, run each in a temporary ``cwd`` so the artifacts stay
contained, and validate the on-disk envelope + a handful of summary
fields.

Run with::

    SKIP_DB_SETUP=1 python -m pytest tests/qa-bench/test_cli_format.py -v

The root ``tests/conftest.py`` boots PostgreSQL when ``SKIP_DB_SETUP``
is unset; this suite deliberately avoids DB.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_QA_BENCH_DIR = Path(__file__).resolve().parent
if str(_QA_BENCH_DIR) not in sys.path:
    sys.path.insert(0, str(_QA_BENCH_DIR))

if not os.environ.get("SKIP_DB_SETUP"):
    pytest.skip(
        "qa-bench CLI format tests require SKIP_DB_SETUP=1",
        allow_module_level=True,
    )


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Invoke a runner CLI in a controlled cwd and capture stdout/stderr.

    The runner scripts unconditionally chdir to their parent directory
    for relative path defaults (e.g. ``questions_780.jsonl``), so we
    pass an absolute ``--input`` / ``--output`` path and run from the
    script's directory.  ``cwd=Path.cwd()`` is the default; we keep it
    explicit so future refactors stay predictable.
    """

    return subprocess.run(
        [sys.executable, *args],
        cwd=str(_QA_BENCH_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


# --- 1. --output .json -> JSON envelope -------------------------------------


def test_run_d5_dry_output_json_suffix_writes_valid_json(tmp_path: Path):
    out = tmp_path / "results.json"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "5",
            "--output",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists(), f"output not written: {out}"
    payload = json.loads(out.read_text(encoding="utf-8"))
    # Envelope is the canonical contract W68 第 11 批 C-2 mandates.
    assert payload["format_version"] == "1"
    assert payload["schema"] == "run_d5_dry.v1"
    assert payload["phase"] == "phase1"
    assert payload["mode"] == "dry-fallback"
    assert payload["limit"] == 5
    assert "summary" in payload
    assert "notes" in payload
    assert "results" in payload
    assert payload["summary"]["total"] == 5


# --- 2. --output .md -> Markdown report -------------------------------------


def test_run_d5_dry_output_md_suffix_writes_markdown(tmp_path: Path):
    out = tmp_path / "results.md"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "5",
            "--output",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    assert out.exists(), f"output not written: {out}"
    body = out.read_text(encoding="utf-8")
    # Markdown headings are preserved verbatim from the legacy renderer.
    assert body.startswith("# W68 D6 Phase 1 Dry-run Report")
    assert "## Verdict counts" in body
    assert "## Per-intent breakdown" in body
    # And the file is NOT valid JSON (the on-disk format is markdown).
    with pytest.raises(json.JSONDecodeError):
        json.loads(body)


# --- 3. --output <no suffix> -> auto -> JSON --------------------------------


def test_run_d5_dry_output_without_suffix_defaults_to_json(tmp_path: Path):
    out = tmp_path / "results"  # no suffix
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "5",
            "--output",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    # The on-disk file is JSON (auto inferred).
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format_version"] == "1"
    assert payload["schema"] == "run_d5_dry.v1"


# --- 4. --input + --output round-trip ---------------------------------------


def test_run_d5_dry_input_jsonl_round_trips_into_json(tmp_path: Path):
    rows = [
        {
            "id": f"CLI-{i:04d}",
            "question": f"q{i}",
            "expect": {"intent": "EXPLAIN_CONCEPT"},
            "category": "C2",
        }
        for i in range(7)
    ]
    inp = tmp_path / "questions.jsonl"
    out = tmp_path / "round_trip.json"
    _write_jsonl(inp, rows)
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--input",
            str(inp),
            "--output",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["summary"]["total"] == 7, (
        f"--input override must drive the corpus size, got total={payload['summary']['total']}"
    )
    # The structured ``results`` array is keyed by the input rows.
    result_ids = [r["id"] for r in payload["results"]]
    assert result_ids == [f"CLI-{i:04d}" for i in range(7)]


def test_phase2_input_jsonl_round_trips_into_json(tmp_path: Path):
    rows = [
        {
            "id": f"P2-{i:04d}",
            "question": f"q{i}",
            "expect": {"intent": "EXPLAIN_CONCEPT"},
            "category": "P2",
        }
        for i in range(4)
    ]
    inp = tmp_path / "questions.jsonl"
    out = tmp_path / "phase2_round_trip.json"
    _write_jsonl(inp, rows)
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "phase2_dry_runner.py"),
            "--dry-run",
            "--input",
            str(inp),
            "--report-out",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode in (0, 1), proc.stderr  # gate FAIL is acceptable
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format_version"] == "1"
    assert payload["schema"] == "phase2_dry_runner.v1"
    assert payload["phase"] == "phase2"
    assert payload["total_questions"] == 4


def test_phase3_input_jsonl_round_trips_into_json(tmp_path: Path):
    rows = [
        {
            "id": f"P3-{i:04d}",
            "question": f"q{i}",
            "expect": {"intent": "EXPLAIN_CONCEPT"},
            "category": "P3",
        }
        for i in range(6)
    ]
    inp = tmp_path / "questions.jsonl"
    out = tmp_path / "phase3_round_trip.json"
    _write_jsonl(inp, rows)
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "phase3_matrix_runner.py"),
            "--dry-run",
            "--workers",
            "2",
            "--input",
            str(inp),
            "--report-out",
            str(out),
        ],
        cwd=tmp_path,
    )
    assert proc.returncode in (0, 1), proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["format_version"] == "1"
    assert payload["schema"] == "phase3_matrix_runner.v1"
    assert payload["phase"] == "phase3"
    assert payload["total_questions"] == 6


# --- 5. --output-format json override with .md suffix ----------------------


def test_run_d5_dry_output_format_json_overrides_md_suffix(tmp_path: Path):
    out = tmp_path / "results.md"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "5",
            "--output",
            str(out),
            "--output-format",
            "json",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["schema"] == "run_d5_dry.v1"


def test_run_d5_dry_output_format_md_overrides_json_suffix(tmp_path: Path):
    out = tmp_path / "results.json"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "5",
            "--output",
            str(out),
            "--output-format",
            "md",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    body = out.read_text(encoding="utf-8")
    # Markdown wins, so a JSON parser must reject the body.
    with pytest.raises(json.JSONDecodeError):
        json.loads(body)
    assert body.startswith("# W68 D6 Phase 1 Dry-run Report")


# --- 6. --seven-d integration -----------------------------------------------


def test_run_d5_dry_seven_d_emits_intent_scoring(tmp_path: Path):
    out = tmp_path / "results.json"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "run_d5_dry.py"),
            "--skip-llm",
            "--limit",
            "10",
            "--output",
            str(out),
            "--seven-d",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode == 0, proc.stderr
    seven_d_path = tmp_path / "seven_d_phase1_dry.json"
    assert seven_d_path.exists(), (
        f"--seven-d must emit seven_d_phase1_dry.json next to {out}"
    )
    payload = json.loads(seven_d_path.read_text(encoding="utf-8"))
    assert payload["phase"] == "phase1"
    assert payload["format_version"] == "1"
    assert payload["source"] == "run_d5_dry._run_seven_d_scoring"
    assert payload["intents"], "expected at least one intent in dry-grade output"
    # Each intent carries the canonical 7-dim shape.
    first_intent = next(iter(payload["intents"].values()))
    assert set(first_intent["dim_scores"]) == {
        "intent",
        "tool",
        "content",
        "structure",
        "accuracy",
        "defense",
        "latency",
    }
    assert "total_score" in first_intent
    assert "grade" in first_intent


def test_phase2_seven_d_emits_intent_scoring(tmp_path: Path):
    out = tmp_path / "phase2_results.json"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "phase2_dry_runner.py"),
            "--dry-run",
            "--report-out",
            str(out),
            "--seven-d",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode in (0, 1), proc.stderr
    seven_d_path = tmp_path / "seven_d_phase2_dry.json"
    assert seven_d_path.exists(), "--seven-d must emit seven_d_phase2_dry.json"
    payload = json.loads(seven_d_path.read_text(encoding="utf-8"))
    assert payload["phase"] == "phase2"


def test_phase3_seven_d_emits_intent_scoring(tmp_path: Path):
    out = tmp_path / "phase3_results.json"
    proc = _run_cli(
        [
            str(_QA_BENCH_DIR / "phase3_matrix_runner.py"),
            "--dry-run",
            "--workers",
            "2",
            "--report-out",
            str(out),
            "--seven-d",
        ],
        cwd=tmp_path,
    )
    assert proc.returncode in (0, 1), proc.stderr
    seven_d_path = tmp_path / "seven_d_phase3_dry.json"
    assert seven_d_path.exists(), "--seven-d must emit seven_d_phase3_dry.json"
    payload = json.loads(seven_d_path.read_text(encoding="utf-8"))
    assert payload["phase"] == "phase3"


if __name__ == "__main__":  # pragma: no cover - allows `python ...`
    sys.exit(pytest.main([__file__, "-v"]))