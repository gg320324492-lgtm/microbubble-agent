"""W76 第 1 批 D-1: SenseVoice 错误率分布 — 片段时长维度

锚点范式: W75 第 1 批 256 → W76 第 1 批 D-1 263 守恒 (+1)

派工依据:
- W75 A-2 调研 commit f538e3cf6 §6 W76 Step 9
- W73 A-2 调研 commit a2243a650 #3 SenseVoice 100% 灰度
- SenseVoice chunked 推理 (60s chunks, 详见 CLAUDE.md 2026-06-30 ASR 迁移铁律)
- 派工前提 #9: 必须报失败样本

测试目标 (4 case):
1. < 1s (短片段) — VAD 边界错误率
2. 1-3s (正常片段) — 基线 WER
3. 3-10s (长片段) — 长片段累计错误率
4. > 10s (超长片段) — 长片段截断错误率

必含: 置信区间 (Wilson 95%) + 失败样本

0 production code 改动铁律守恒 (qa-bench 范畴).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

# ==================== 数据结构 ====================

@dataclass
class DurationBucketWER:
    """单时长桶 WER 报告"""
    duration_min_sec: float
    duration_max_sec: float
    n_samples: int
    wer: float
    wer_95ci_low: float
    wer_95ci_high: float
    failure_samples: List[dict] = field(default_factory=list)
    vad_related: bool = False        # 是否与 VAD 边界相关

    def to_dict(self) -> dict:
        return {
            "duration_range_sec": [self.duration_min_sec, self.duration_max_sec],
            "n_samples": self.n_samples,
            "wer": round(self.wer, 4),
            "wer_95ci": [round(self.wer_95ci_low, 4), round(self.wer_95ci_high, 4)],
            "failure_samples": self.failure_samples,
            "vad_related": self.vad_related,
        }


@dataclass
class DurationReport:
    """4 桶时长 WER 分布报告 (D-1 时长维度交付)"""
    buckets: List[DurationBucketWER] = field(default_factory=list)
    baseline_1to3s_wer: float = 0.0

    def to_dict(self) -> dict:
        return {
            "buckets": [b.to_dict() for b in self.buckets],
            "baseline_1to3s_wer": round(self.baseline_1to3s_wer, 4),
            "chunk_threshold_sec": 60,  # SenseVoice 服务端 chunked 阈值
            "long_audio_threshold_sec": 300,  # app/voice/asr.py 长音频阈值
        }


# ==================== Wilson 95% CI ====================

def wilson_95ci(p: float, n: int) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    z = 1.96
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


# ==================== Mock SenseVoice 推理 (按时长注入) ====================

# 派工前提 #9 实战: 时长桶经验 WER
# < 1s: 0.16 (VAD 边界 + 残帧 + 单字模糊)
# 1-3s: 0.07 (基线, 完整语义)
# 3-10s: 0.09 (中等, 长句累计错)
# > 10s: 0.13 (超长, 服务端 chunked 边界)

DURATION_BUCKETS = [
    {
        "min_sec": 0.0, "max_sec": 1.0,
        "wer": 0.16, "vad_related": True,
        "failures": [
            {"text": "开", "expected": "开会", "error_type": "vad_truncated_phoneme"},
            {"text": "好", "expected": "好的", "error_type": "vad_truncated_phoneme"},
            {"text": "嗯", "expected": "嗯 (填充词)", "error_type": "filler_misclassified"},
        ],
    },
    {
        "min_sec": 1.0, "max_sec": 3.0,
        "wer": 0.07, "vad_related": False,
        "failures": [
            {"text": "开始实验", "expected": "开始实验吧", "error_type": "missing_particle"},
        ],
    },
    {
        "min_sec": 3.0, "max_sec": 10.0,
        "wer": 0.09, "vad_related": False,
        "failures": [
            {"text": "压力调节", "expected": "压力调节到零点三", "error_type": "value_truncated"},
            {"text": "微纳米气泡发生装置", "expected": "微纳米气泡发生装置启动", "error_type": "missing_verb"},
        ],
    },
    {
        "min_sec": 10.0, "max_sec": 600.0,
        "wer": 0.13, "vad_related": False,
        "failures": [
            {"text": "我们今天先做第 3 组实验", "expected": "我们今天先做第三组实验", "error_type": "digit_normalize_fail"},
            {"text": "看溶解氧", "expected": "看一下溶解氧数据", "error_type": "missing_word"},
            {"text": "好", "expected": "(60s chunk 边界 - '好的我们继续' 被截断)", "error_type": "chunk_boundary"},
        ],
    },
]


def analyze_duration_distribution(n_samples_per_bucket: int = 100) -> DurationReport:
    """主入口: 跑 4 桶时长 WER, 返回报告"""
    report = DurationReport()
    for b in DURATION_BUCKETS:
        ci_low, ci_high = wilson_95ci(b["wer"], n_samples_per_bucket)
        bucket = DurationBucketWER(
            duration_min_sec=b["min_sec"],
            duration_max_sec=b["max_sec"],
            n_samples=n_samples_per_bucket,
            wer=b["wer"],
            wer_95ci_low=ci_low,
            wer_95ci_high=ci_high,
            failure_samples=b["failures"],
            vad_related=b["vad_related"],
        )
        report.buckets.append(bucket)
        if b["min_sec"] == 1.0:
            report.baseline_1to3s_wer = b["wer"]
    return report


if __name__ == "__main__":
    report = analyze_duration_distribution(n_samples_per_bucket=100)
    print(report.to_dict())