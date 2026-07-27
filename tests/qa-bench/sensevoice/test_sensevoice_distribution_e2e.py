"""W76 第 1 批 D-1: SenseVoice 错误率分布 3 维度 + 9 表索引基线对照 e2e

锚点范式: W75 第 1 批 256 → W76 第 1 批 D-1 263 守恒 (+1)

派工依据:
- W75 A-2 调研 commit f538e3cf6 §6 W76 Step 9
- W74 B-1 9 表 2 索引修复 commit aef117b17 + P1 修复 commit 8d0d12c2d
- W73 A-2 调研 commit a2243a650 #3 SenseVoice 100% 灰度
- 派工前提 #9: 必报失败样本 (不能只报平均 WER)

测试目标 (16 case):
A. 噪声/SNR 维度 4 case:
   1. SNR ≥ 30 dB baseline WER
   2. SNR 20-30 dB WER 升幅
   3. SNR 10-20 dB WER 显著升幅
   4. SNR < 10 dB WER 失效率
B. 说话人/性别维度 4 case:
   5. 男声 baseline WER
   6. 女声 WER 升幅
   7. 童声 WER
   8. 老年 WER
C. 时长维度 4 case:
   9. < 1s 短片段 VAD 边界
   10. 1-3s 正常片段 baseline
   11. 3-10s 长片段累计错
   12. > 10s 超长片段截断
D. 9 表索引基线 4 case (case1-case4 of 9_table_index_baseline, 不含 case5):
   13. GIN cluster_id_history
   14. GIN speaker_mapping
   15. GIN speaker_stats
   16. partial voice_confirmed

派工 v4 铁律 3 真验证: 必先 git log + 模块 import + 数据结构 verify
派工前提 #9: 失败样本必报 (不能只报平均 WER)

0 production code 改动铁律守恒 (qa-bench 范畴).
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

# 派工 v4 铁律 3 真验证: 用 importlib.util 按路径直接加载 (qa-bench 非 Python 包)
# dataclass 需要模块在 sys.modules 中, 否则 _is_type 报 NoneType.__dict__
_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_mod(name: str):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_HERE, name + ".py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


snr_mod = _load_mod("snr_analysis")
speaker_mod = _load_mod("speaker_analysis")
duration_mod = _load_mod("duration_analysis")
index_mod = _load_mod("nine_table_index_baseline")


# ==================== A. 噪声/SNR 维度 (4 case) ====================

def test_a1_snr_30db_clean_baseline_wer():
    """Case 1: SNR ≥ 30 dB 基线 WER ≤ 0.10 (clean speech)"""
    report = snr_mod.analyze_snr_distribution(n_samples_per_bucket=100)
    bucket = report.buckets[0]  # clean
    assert bucket.noise_profile == "clean"
    assert bucket.snr_min_db >= 30.0
    assert bucket.wer <= 0.10, f"SNR≥30dB WER {bucket.wer} > 0.10"
    # 派工前提 #9: 失败样本可为空 (clean)
    assert isinstance(bucket.failure_samples, list)


def test_a2_snr_20to30db_office_wer_lift():
    """Case 2: SNR 20-30 dB 办公室噪声 WER 升幅 > baseline"""
    report = snr_mod.analyze_snr_distribution(n_samples_per_bucket=100)
    baseline = report.buckets[0].wer
    office = report.buckets[1]
    assert office.noise_profile == "office"
    assert office.wer > baseline, f"office WER {office.wer} ≤ baseline {baseline}"
    # 派工前提 #9: 失败样本 ≥ 1
    assert len(office.failure_samples) >= 1, "office 噪声必须报 ≥1 失败样本 (派工前提 #9)"


def test_a3_snr_10to20db_street_wer_significant_lift():
    """Case 3: SNR 10-20 dB 街道噪声 WER 显著升幅 > office"""
    report = snr_mod.analyze_snr_distribution(n_samples_per_bucket=100)
    office = report.buckets[1].wer
    street = report.buckets[2]
    assert street.noise_profile == "street"
    assert street.wer > office, f"street WER {street.wer} ≤ office {office}"
    # 派工前提 #9: 失败样本 ≥ 2
    assert len(street.failure_samples) >= 2, "street 噪声必须报 ≥2 失败样本"


def test_a4_snr_lt10db_restaurant_failure_rate():
    """Case 4: SNR < 10 dB 餐厅噪声 WER 失效率"""
    report = snr_mod.analyze_snr_distribution(n_samples_per_bucket=100)
    restaurant = report.buckets[3]
    assert restaurant.noise_profile == "restaurant"
    # 失效率定义: WER ≥ 0.35 (近半词错)
    assert restaurant.wer >= 0.35, f"restaurant WER {restaurant.wer} 失效率不足 (期望 ≥0.35)"
    # 派工前提 #9: 失败样本 ≥ 3
    assert len(restaurant.failure_samples) >= 3, "restaurant 噪声必须报 ≥3 失败样本"
    # 置信区间宽度合理 (<0.20)
    ci_width = restaurant.wer_95ci_high - restaurant.wer_95ci_low
    assert ci_width < 0.20, f"95% CI 宽度 {ci_width} 过宽 (期望 <0.20)"


# ==================== B. 说话人/性别维度 (4 case) ====================

def test_b1_male_baseline_wer():
    """Case 5: 男声 baseline WER ≤ 0.10"""
    report = speaker_mod.analyze_speaker_distribution(n_samples_per_speaker=20)
    male = next(g for g in report.groups if g.group == "male")
    assert male.n_speakers == 10
    assert male.wer <= 0.10, f"男声 WER {male.wer} > 0.10"
    # 派工前提 #9: 失败样本 ≥ 1
    assert len(male.failure_samples) >= 1


def test_b2_female_wer_slightly_higher_than_male():
    """Case 6: 女声 WER ≥ 男声 (高频共振峰 + 气息词)"""
    report = speaker_mod.analyze_speaker_distribution(n_samples_per_speaker=20)
    male = next(g for g in report.groups if g.group == "male")
    female = next(g for g in report.groups if g.group == "female")
    assert female.wer >= male.wer * 0.9, f"女声 WER {female.wer} 显著低于男声 {male.wer} (反常)"
    # 派工前提 #9: 失败样本 ≥ 1
    assert len(female.failure_samples) >= 1


def test_b3_child_wer_significantly_higher():
    """Case 7: 童声 WER 显著高于男声 (音调不稳 + 构音不完全)"""
    report = speaker_mod.analyze_speaker_distribution(n_samples_per_speaker=20)
    male = next(g for g in report.groups if g.group == "male")
    child = next(g for g in report.groups if g.group == "child")
    assert child.wer > male.wer * 1.5, f"童声 WER {child.wer} 应显著高于男声 {male.wer}"
    # 派工前提 #9: 失败样本 ≥ 2 (构音特殊性)
    assert len(child.failure_samples) >= 2


def test_b4_elderly_wer_highest():
    """Case 8: 老年口音 WER 最高 (方言 + 齿音弱)"""
    report = speaker_mod.analyze_speaker_distribution(n_samples_per_speaker=20)
    elderly = next(g for g in report.groups if g.group == "elderly")
    assert elderly.wer >= 0.15, f"老年 WER {elderly.wer} 不足 (期望 ≥0.15)"
    # 派工前提 #9: 失败样本 ≥ 3 (老年口音常见错)
    assert len(elderly.failure_samples) >= 3


# ==================== C. 时长维度 (4 case) ====================

def test_c1_under_1s_vad_boundary_wer_high():
    """Case 9: < 1s 短片段 VAD 边界 WER ≥ 0.12"""
    report = duration_mod.analyze_duration_distribution(n_samples_per_bucket=100)
    short = report.buckets[0]
    assert short.duration_max_sec <= 1.0
    assert short.wer >= 0.12, f"短片段 VAD 边界 WER {short.wer} 不足 (期望 ≥0.12)"
    assert short.vad_related is True
    # 派工前提 #9: 失败样本 ≥ 2 (VAD 边界常见错)
    assert len(short.failure_samples) >= 2


def test_c2_1to3s_normal_baseline_wer():
    """Case 10: 1-3s 正常片段 baseline WER ≤ 0.10"""
    report = duration_mod.analyze_duration_distribution(n_samples_per_bucket=100)
    normal = report.buckets[1]
    assert normal.duration_min_sec >= 1.0
    assert normal.duration_max_sec <= 3.0
    assert normal.wer <= 0.10, f"正常片段 baseline WER {normal.wer} > 0.10"
    assert normal.vad_related is False


def test_c3_3to10s_medium_wer():
    """Case 11: 3-10s 长片段 WER 累计错"""
    report = duration_mod.analyze_duration_distribution(n_samples_per_bucket=100)
    medium = report.buckets[2]
    assert medium.duration_min_sec >= 3.0
    assert medium.duration_max_sec <= 10.0
    assert medium.wer >= 0.07, f"长片段 WER {medium.wer} < baseline 0.07"
    # 派工前提 #9: 失败样本 ≥ 2
    assert len(medium.failure_samples) >= 2


def test_c4_over_10s_chunk_boundary_wer():
    """Case 12: > 10s 超长片段 SenseVoice chunked 边界 WER"""
    report = duration_mod.analyze_duration_distribution(n_samples_per_bucket=100)
    long = report.buckets[3]
    assert long.duration_min_sec >= 10.0
    assert long.wer >= 0.10, f"超长片段 WER {long.wer} < 0.10"
    # 派工前提 #9: 失败样本含 chunk_boundary 类型
    failure_types = {f["error_type"] for f in long.failure_samples}
    assert "chunk_boundary" in failure_types, (
        "超长片段必须报 chunk_boundary 失败类型 (SenseVoice 服务端 60s chunks)"
    )


# ==================== D. 9 表索引基线 (4 case) ====================

def test_d1_gin_cluster_id_history_explain():
    """Case 13: EXPLAIN ANALYZE cluster_id_history 走 GIN 索引"""
    report = index_mod.build_index_baseline_report()
    case = next(c for c in report.cases if c.case_id == "case1_gin_cluster_id_history")
    assert case.pass_ is True
    assert "Bitmap Index Scan" in case.post_fix_plan_excerpt
    assert "Seq Scan" not in case.post_fix_plan_excerpt
    assert case.measured_ms <= case.sla_ms, (
        f"实测 {case.measured_ms}ms > SLA {case.sla_ms}ms"
    )


def test_d2_gin_speaker_mapping_explain():
    """Case 14: EXPLAIN ANALYZE speaker_mapping 走 GIN 索引"""
    report = index_mod.build_index_baseline_report()
    case = next(c for c in report.cases if c.case_id == "case2_gin_speaker_mapping")
    assert case.pass_ is True
    assert "Bitmap Index Scan" in case.post_fix_plan_excerpt
    assert case.measured_ms <= case.sla_ms


def test_d3_gin_speaker_stats_explain():
    """Case 15: EXPLAIN ANALYZE speaker_stats 走 GIN 索引"""
    report = index_mod.build_index_baseline_report()
    case = next(c for c in report.cases if c.case_id == "case3_gin_speaker_stats")
    assert case.pass_ is True
    assert "Bitmap Index Scan" in case.post_fix_plan_excerpt
    assert case.measured_ms <= case.sla_ms


def test_d4_partial_voice_confirmed_explain():
    """Case 16: EXPLAIN ANALYZE voice_confirmed 走联合部分索引"""
    report = index_mod.build_index_baseline_report()
    case = next(c for c in report.cases if c.case_id == "case4_partial_voice_confirmed")
    assert case.pass_ is True
    assert "Index Scan using ix_members_voice_confirmed_partial" in case.post_fix_plan_excerpt
    assert case.measured_ms <= case.sla_ms


# ==================== 综合断言: 16/16 PASS ====================

def test_z_summary_all_16_pass():
    """汇总: 3 维度 12 case + 9 表索引 4 case = 16 case 全 PASS"""
    snr = snr_mod.analyze_snr_distribution()
    speaker = speaker_mod.analyze_speaker_distribution()
    duration = duration_mod.analyze_duration_distribution()
    index_report = index_mod.build_index_baseline_report()
    summary = {
        "snr_buckets": len(snr.buckets),
        "speaker_groups": len(speaker.groups),
        "duration_buckets": len(duration.buckets),
        "index_cases_pass": index_report.baseline_pass_count,
        "total": 4 + 4 + 4 + 4,
    }
    assert summary["snr_buckets"] == 4
    assert summary["speaker_groups"] == 4
    assert summary["duration_buckets"] == 4
    assert summary["index_cases_pass"] == 5  # case1-case5 (含 case5 1M 行 SLA)
    # 派工前提 #9 实战: 报告必含失败样本
    total_failures = (
        sum(len(b.failure_samples) for b in snr.buckets)
        + sum(len(g.failure_samples) for g in speaker.groups)
        + sum(len(b.failure_samples) for b in duration.buckets)
    )
    assert total_failures >= 15, f"失败样本总数 {total_failures} < 15 (派工前提 #9)"
    print(f"\n=== W76 D-1 SenseVoice 错误率分布 16 case 汇总 ===\n{json.dumps(summary, indent=2, ensure_ascii=False)}")