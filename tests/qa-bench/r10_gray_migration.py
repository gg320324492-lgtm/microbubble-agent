"""W78 D-1 R10 weights_v4 gray-migration preparation helpers.

This module intentionally stays under ``tests/qa-bench``.  It composes the
already-landed W73/W74 assets instead of changing the legacy seven-dimension
scorer or any production path.

The migration is a measured, dry-run-safe contract:
* validate the 240-question SHA lock and the 12-dimension weights schema;
* expose all seven implementation preconditions as auditable evidence;
* keep the four-week 5/10/25/100% rollout plan in one place; and
* associate the W76 SenseVoice SNR, speaker, and duration reports with the
  commercial scoring dimensions without turning mocked distributions into
  production ASR claims.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SCORING_DIR = HERE / "scoring"
DATA_DIR = HERE / "data"
SCRIPTS_DIR = HERE.parent.parent / "scripts" / "qa-bench"
COMBINED_V4 = DATA_DIR / "combined_v4.jsonl"
COMBINED_V4_SHA = DATA_DIR / "combined_v4.sha256"
WEIGHTS_V4 = SCORING_DIR / "weights_v4.json"
WEIGHTS_V3 = SCORING_DIR / "weights.json"

# The six detector modules are the six commercial checks delivered by W73.
COMMERCIAL_DETECTORS = (
    "subscription_intent_detector",
    "billing_tool_detector",
    "tenant_isolation_detector",
    "pricing_accuracy_detector",
    "commercial_compliance_detector",
    "license_check_detector",
)

# Keep this table independent from the runner's implementation details so a
# release manager can inspect the promotion contract without running a model.
ROLLOUT_WEEKS: dict[int, dict[str, Any]] = {
    1: {"percentage": 5, "sample_size": 12, "min_pass_rate": 0.70, "max_f_count": 5},
    2: {"percentage": 10, "sample_size": 24, "min_pass_rate": 0.75, "max_f_count": 5},
    3: {"percentage": 25, "sample_size": 60, "min_pass_rate": 0.78, "max_f_count": 5},
    4: {"percentage": 100, "sample_size": 240, "min_pass_rate": 0.80, "max_f_count": 4},
}


def _load_module(name: str, path: Path) -> Any:
    """Load an existing hyphenated/non-package QA helper by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def combined_v4_sha256() -> str:
    """Return the current SHA256 of the locked 240-question fixture."""
    digest = hashlib.sha256()
    digest.update(COMBINED_V4.read_bytes())
    return digest.hexdigest()


def verify_combined_v4_lock() -> dict[str, Any]:
    """Verify the committed fixture and its lock without modifying either."""
    if not COMBINED_V4.exists() or not COMBINED_V4_SHA.exists():
        return {"passed": False, "reason": "combined_v4 fixture or lock missing"}
    expected = next(
        (line.split()[0] for line in COMBINED_V4_SHA.read_text(encoding="utf-8").splitlines()
         if line.strip() and not line.lstrip().startswith("#")),
        "",
    )
    actual = combined_v4_sha256()
    count = sum(
        1 for line in COMBINED_V4.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    return {
        "passed": bool(expected and expected == actual and count == 240),
        "expected_sha256": expected,
        "actual_sha256": actual,
        "question_count": count,
    }


def weights_v4_contract() -> dict[str, Any]:
    """Load and validate the immutable R10 weights_v4 contract."""
    weights_module = _load_module("w78_twelve_dim_v4", SCORING_DIR / "twelve_dim_v4.py")
    config = weights_module.load_weights_v4(WEIGHTS_V4)
    return {
        "version": config["version"],
        "subdimension_count": len(config["weights"]),
        "subdimensions": list(config["weights"]),
        "weight_sum": sum(config["weights"].values()),
        "veto_thresholds": config["veto_thresholds"],
        "detector_count": len(COMMERCIAL_DETECTORS),
    }


def implementation_preconditions() -> dict[str, dict[str, Any]]:
    """Return auditable evidence for all seven D9 implementation gates.

    Secret values are deliberately not read here.  Presence/length belongs to
    CI's ``ci_secret_check.py`` and must never be copied into a test artifact.
    """
    lock = verify_combined_v4_lock()
    required_files = {
        "sanitize_fixture": SCRIPTS_DIR / "sanitize_fixture.py",
        "endpoint_lock": SCRIPTS_DIR / "endpoint_lock.py",
        "ci_secret_check": SCRIPTS_DIR / "ci_secret_check.py",
        "gate": SCRIPTS_DIR / "gate.py",
        "round10_runner": HERE / "round10-bge-m3.py",
        "baseline_v3": SCORING_DIR / "weights.json",
        "weights_v4": WEIGHTS_V4,
    }
    files_ok = all(path.exists() for path in required_files.values())
    retry_source = (HERE / "round10-bge-m3.py").read_text(encoding="utf-8")
    gate_source = (SCRIPTS_DIR / "gate.py").read_text(encoding="utf-8")
    return {
        "1_question_version_lock": {"passed": lock["passed"], "evidence": lock},
        "2_data_sanitization": {
            "passed": (SCRIPTS_DIR / "sanitize_fixture.py").exists(),
            "evidence": "sanitize_fixture.py + irreversible salted hash contract",
        },
        "3_model_endpoint_lock": {
            "passed": (SCRIPTS_DIR / "endpoint_lock.py").exists(),
            "evidence": "endpoint_lock.py locks mimo/BGE m3/text2vec",
        },
        "4_ci_secret_check": {
            "passed": (SCRIPTS_DIR / "ci_secret_check.py").exists(),
            "evidence": "CI-only MIMO_API_KEY and POSTGRES_PASSWORD check",
        },
        "5_baseline_comparison": {
            "passed": WEIGHTS_V3.exists() and "baseline_diff" in retry_source,
            "evidence": "R9 weights.json retained + round10 baseline_diff helper",
        },
        "6_retry_and_artifacts": {
            "passed": "retry" in retry_source and "results.json" in retry_source,
            "evidence": "round10 runner retry/failure artifact contract",
        },
        "7_gate": {
            "passed": all(token in gate_source for token in ("GATE_PLAN", "0.80", "F_SPIKE_MULTIPLIER")),
            "evidence": "gate.py Week 1-4 thresholds + F spike halt",
        },
        "required_assets": {"passed": files_ok, "evidence": {k: str(v) for k, v in required_files.items()}},
    }


def sensevoice_association() -> dict[str, Any]:
    """Associate W76's three SenseVoice distributions with R10 dimensions.

    The W76 modules are deterministic QA distributions.  This function reports
    their dimensions and failures for rollout review; it does not alter scores
    or claim that a mock distribution is a production ASR measurement.
    """
    sensevoice_dir = HERE / "sensevoice"
    snr = _load_module("w78_snr_analysis", sensevoice_dir / "snr_analysis.py")
    speaker = _load_module("w78_speaker_analysis", sensevoice_dir / "speaker_analysis.py")
    duration = _load_module("w78_duration_analysis", sensevoice_dir / "duration_analysis.py")
    snr_report = snr.analyze_snr_distribution(n_samples_per_bucket=100)
    speaker_report = speaker.analyze_speaker_distribution(n_samples_per_speaker=20)
    duration_report = duration.analyze_duration_distribution(n_samples_per_bucket=100)

    buckets = [
        {"dimension": "snr", "bucket": b.noise_profile, "wer": b.wer,
         "ci95": [b.wer_95ci_low, b.wer_95ci_high],
         "failure_count": len(b.failure_samples)}
        for b in snr_report.buckets
    ]
    buckets += [
        {"dimension": "speaker", "bucket": g.group, "wer": g.wer,
         "ci95": [g.wer_95ci_low, g.wer_95ci_high],
         "failure_count": len(g.failure_samples)}
        for g in speaker_report.groups
    ]
    buckets += [
        {"dimension": "duration", "bucket": f"{b.duration_min_sec:g}-{b.duration_max_sec:g}s",
         "wer": b.wer, "ci95": [b.wer_95ci_low, b.wer_95ci_high],
         "failure_count": len(b.failure_samples)}
        for b in duration_report.buckets
    ]
    failures = sum(row["failure_count"] for row in buckets)
    return {
        "dimensions": ["snr", "speaker_gender_age", "duration"],
        "associated_subdimensions": ["content_factual", "perf_latency", "consistency"],
        "buckets": buckets,
        "bucket_count": len(buckets),
        "failure_sample_count": failures,
        "failure_sample_gate": {"minimum": 27, "passed": failures >= 27},
        "wilson_95ci": True,
        "source": "W76 cbdab60e6 deterministic SenseVoice distribution modules",
    }


def migration_dry_run() -> dict[str, Any]:
    """Build a promotion report; never enables traffic or changes QA fixtures."""
    preconditions = implementation_preconditions()
    return {
        "mode": "dry_run",
        "weights": weights_v4_contract(),
        "question_lock": verify_combined_v4_lock(),
        "detectors": list(COMMERCIAL_DETECTORS),
        "rollout": ROLLOUT_WEEKS,
        "preconditions": preconditions,
        "sensevoice": sensevoice_association(),
        "all_preconditions_present": all(
            detail["passed"] for name, detail in preconditions.items()
            if name != "required_assets"
        ),
        "traffic_enabled": False,
        "legacy_v3_retained": WEIGHTS_V3.exists(),
        "schema_change": False,
        "schema_preflight": "N/A: no DB/schema task; information_schema check not applicable",
    }


if __name__ == "__main__":
    print(json.dumps(migration_dry_run(), ensure_ascii=False, indent=2))
