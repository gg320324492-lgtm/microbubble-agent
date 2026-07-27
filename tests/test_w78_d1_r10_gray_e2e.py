"""W78 第 1 批 D-1 R10 weights_v4 灰度迁移 e2e (22/22).

覆盖边界:
- 17 case 复用 W76 D-1 SenseVoice + 9 表索引测试（不复制实现逻辑）；
- 5 case 验证 W78 新增的 7 维评分商业化灰度配套；
- 所有测试均在 tests/qa-bench 范畴，不调用生产 API，不改老 QA 链路。

运行:
    pytest tests/test_w78_d1_r10_gray_e2e.py -v
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
QA_BENCH = ROOT / "tests" / "qa-bench"

sys.path.insert(0, str(QA_BENCH))
sys.path.insert(0, str(QA_BENCH / "scoring"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


r10 = _load("w78_r10_gray_migration", QA_BENCH / "r10_gray_migration.py")
round10 = _load("w78_round10_bge_m3", QA_BENCH / "round10-bge-m3.py")
sensevoice_tests = _load(
    "w78_reused_sensevoice_e2e",
    QA_BENCH / "sensevoice" / "test_sensevoice_distribution_e2e.py",
)


# ---------------------------------------------------------------------------
# 17 reused W76 D-1 cases (the underlying tests remain the single source of truth)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "case",
    [
        sensevoice_tests.test_a1_snr_30db_clean_baseline_wer,
        sensevoice_tests.test_a2_snr_20to30db_office_wer_lift,
        sensevoice_tests.test_a3_snr_10to20db_street_wer_significant_lift,
        sensevoice_tests.test_a4_snr_lt10db_restaurant_failure_rate,
        sensevoice_tests.test_b1_male_baseline_wer,
        sensevoice_tests.test_b2_female_wer_slightly_higher_than_male,
        sensevoice_tests.test_b3_child_wer_significantly_higher,
        sensevoice_tests.test_b4_elderly_wer_highest,
        sensevoice_tests.test_c1_under_1s_vad_boundary_wer_high,
        sensevoice_tests.test_c2_1to3s_normal_baseline_wer,
        sensevoice_tests.test_c3_3to10s_medium_wer,
        sensevoice_tests.test_c4_over_10s_chunk_boundary_wer,
        sensevoice_tests.test_d1_gin_cluster_id_history_explain,
        sensevoice_tests.test_d2_gin_speaker_mapping_explain,
        sensevoice_tests.test_d3_gin_speaker_stats_explain,
        sensevoice_tests.test_d4_partial_voice_confirmed_explain,
        sensevoice_tests.test_z_summary_all_16_pass,
    ],
    ids=[
        "snr-clean", "snr-office", "snr-street", "snr-restaurant",
        "speaker-male", "speaker-female", "speaker-child", "speaker-elderly",
        "duration-short", "duration-normal", "duration-medium", "duration-long",
        "index-cluster-history", "index-speaker-mapping", "index-speaker-stats",
        "index-voice-confirmed", "sensevoice-summary",
    ],
)
def test_reused_w76_sensevoice_case(case):
    """复用 W76 D-1 的 17/17 实战，不重新实现 SenseVoice 统计逻辑."""
    case()


# ---------------------------------------------------------------------------
# Five new W78 D-1 commercial gray-migration cases
# ---------------------------------------------------------------------------
def test_w78_r10_contract_has_12_subdimensions_and_6_detectors():
    """R10 weights_v4 schema + W73 six-detector registry are present."""
    contract = r10.weights_v4_contract()
    assert contract["version"] == "4.0"
    assert contract["subdimension_count"] == 12
    assert abs(contract["weight_sum"] - 1.0) < 1e-9
    assert contract["detector_count"] == 6
    assert contract["veto_thresholds"] == {
        "content_factual": 0.5,
        "defense_compliance": 0.7,
        "content_billing_calc": 0.6,
    }


def test_w78_combined_240_sha_and_seven_preconditions():
    """240-question lock and all seven implementation preconditions are auditable."""
    lock = r10.verify_combined_v4_lock()
    assert lock["passed"] is True
    assert lock["question_count"] == 240
    preconditions = r10.implementation_preconditions()
    for number in range(1, 8):
        assert preconditions[f"{number}_" + {
            1: "question_version_lock",
            2: "data_sanitization",
            3: "model_endpoint_lock",
            4: "ci_secret_check",
            5: "baseline_comparison",
            6: "retry_and_artifacts",
            7: "gate",
        }[number]]["passed"] is True
    assert preconditions["required_assets"]["passed"] is True


def test_w78_commercial_40_questions_and_12d_score_pipeline():
    """The 200+40 fixture remains intact and a commercial item scores through 12d."""
    data_path = QA_BENCH / "data" / "combined_v4.jsonl"
    rows = [
        json.loads(line)
        for line in data_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    commercial = [row for row in rows if str(row.get("id", "")).startswith("commercial_")]
    assert len(rows) == 240
    assert len(commercial) == 40
    assert {row["category"] for row in commercial} == {"subscribe", "billing", "tenant", "rbac", "e2e"}

    scorer = _load("w78_twelve_dim_v4_test", QA_BENCH / "scoring" / "twelve_dim_v4.py")
    item = {
        "response": "团队版价格 ¥99/月，订阅可退款，license active",
        "predicted_intent": "subscribe",
        "tool_calls": ["show_plans", "billing_create_subscription"],
        "billing_response": "¥99/月",
        "rich_blocks": [{"type": "billing_card"}],
        "compliance_checked": True,
        "latency_ms": 200,
        "billing_latency_ms": 300,
    }
    benchmark = {
        "expected_intent": "subscribe",
        "expected_tools": ["show_plans"],
        "expected_billing_tools": ["billing_create_subscription"],
        "content_keywords": ["团队版", "订阅"],
        "billing_keywords": ["¥", "月"],
        "billing_sla_ms": 1000,
    }
    result = scorer.score_12d_item(item, benchmark=benchmark)
    assert set(result["scores"]) == set(scorer.TWELVE_DIMENSIONS)
    assert result["version"] == "4.0"
    assert result["veto"] is None
    assert result["grade"] in {"A", "B", "C", "D"}


def test_w78_sensevoice_three_dimension_association_has_27_failures():
    """SNR, speaker/age, and duration distributions feed rollout evidence."""
    association = r10.sensevoice_association()
    assert association["dimensions"] == ["snr", "speaker_gender_age", "duration"]
    assert association["associated_subdimensions"] == [
        "content_factual", "perf_latency", "consistency"
    ]
    assert association["bucket_count"] == 12
    assert association["wilson_95ci"] is True
    assert association["failure_sample_gate"] == {"minimum": 27, "passed": True}


def test_w78_four_week_rollout_dry_run_gate_and_v3_rollback():
    """4-week promotion percentages, gate thresholds, and rollback stay safe."""
    expected = {
        1: (5, 12, 0.70, 5),
        2: (10, 24, 0.75, 5),
        3: (25, 60, 0.78, 5),
        4: (100, 240, 0.80, 4),
    }
    for week, (percentage, sample_size, min_pass_rate, max_f_count) in expected.items():
        plan = r10.ROLLOUT_WEEKS[week]
        assert (plan["percentage"], plan["sample_size"], plan["min_pass_rate"], plan["max_f_count"]) == (
            percentage, sample_size, min_pass_rate, max_f_count
        )
        dry_run = round10.run_week(week, dry_run=True)
        assert dry_run["status"] == "dry_run"
        assert dry_run["items_count"] == sample_size

    report = r10.migration_dry_run()
    assert report["mode"] == "dry_run"
    assert report["traffic_enabled"] is False
    assert report["legacy_v3_retained"] is True
    assert report["schema_change"] is False
    assert report["all_preconditions_present"] is True
    assert report["schema_preflight"].startswith("N/A")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
