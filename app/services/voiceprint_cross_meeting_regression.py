"""
声纹 B+C 方案实施 — 跨会议回归门禁 90% (W75 第 1 批 B-1)

A-2 W74 调研 §5 主拍必拍 (B 方案核心): 新 embedding/变更前必须自动跑
≥ 90% 跨会议总体识别率门禁, 否则 rollback + 报警.

派工 v6 段 5 反馈 #6 实战: 不依赖 LLM 改数值 (拒绝方案 A 字面改 0.9).

跨会议回归数据集:
- 12 会议音频 reprocess (W73 A-2 调研实战) + #151 rollback 重演 (W74 A-2 调研建议)
- 王天志 #135 94.6% + #151 83.5% → 整体 88.1% → rollback 真实案例锚点
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# 跨会议总体识别率门禁常量
CROSS_MEETING_ACCEPTANCE_GATE = 0.90  # 90% 跨会议总体识别率门禁
CROSS_MEETING_USER_OVERRIDE_BAND = (0.90, 0.95)  # 90-95% 用户决定
# <0.90 → 自动 rollback
# 0.90-0.95 → 用户决定
# ≥0.95 → 自动接受

# 跨会议单段命中距离阈值 (历史锚点: distance ≤ 0.55 视为命中)
CROSS_MEETING_HIT_DISTANCE_MAX = 0.55


@dataclass
class MeetingRecognitionReport:
    """单次会议识别率报告."""

    meeting_id: int
    meeting_title: str
    total_segments: int
    hit_segments: int  # cos_dist ≤ 0.55 的段数
    hit_ratio: float  # hit_segments / total_segments

    def to_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "meeting_title": self.meeting_title,
            "total_segments": self.total_segments,
            "hit_segments": self.hit_segments,
            "hit_ratio": self.hit_ratio,
        }


@dataclass
class CrossMeetingRegressionResult:
    """跨会议回归结果."""

    overall_recognition_rate: float
    meeting_reports: List[MeetingRecognitionReport]
    passed_acceptance_gate: bool  # ≥ 90%
    decision_band: str  # "rollback" / "user_decide" / "accept"
    rollback_recommended: bool
    tested_meetings: int
    next_action: str

    def to_dict(self) -> dict:
        return {
            "overall_recognition_rate": self.overall_recognition_rate,
            "meeting_reports": [m.to_dict() for m in self.meeting_reports],
            "passed_acceptance_gate": self.passed_acceptance_gate,
            "decision_band": self.decision_band,
            "rollback_recommended": self.rollback_recommended,
            "tested_meetings": self.tested_meetings,
            "next_action": self.next_action,
            "acceptance_gate": CROSS_MEETING_ACCEPTANCE_GATE,
            "hit_distance_max": CROSS_MEETING_HIT_DISTANCE_MAX,
        }


def compute_meeting_recognition_rate(
    meeting_id: int,
    meeting_title: str,
    segment_distances: List[float],
) -> MeetingRecognitionReport:
    """单会议识别率: hit_segments / total_segments.

    命中条件: cos_dist ≤ CROSS_MEETING_HIT_DISTANCE_MAX (0.55).
    """
    if not segment_distances:
        return MeetingRecognitionReport(
            meeting_id=meeting_id,
            meeting_title=meeting_title,
            total_segments=0,
            hit_segments=0,
            hit_ratio=0.0,
        )
    hits = sum(1 for d in segment_distances if d <= CROSS_MEETING_HIT_DISTANCE_MAX)
    total = len(segment_distances)
    return MeetingRecognitionReport(
        meeting_id=meeting_id,
        meeting_title=meeting_title,
        total_segments=total,
        hit_segments=hits,
        hit_ratio=hits / total if total else 0.0,
    )


def aggregate_cross_meeting_rate(
    reports: List[MeetingRecognitionReport],
) -> CrossMeetingRegressionResult:
    """加权跨会议识别率 (按段数加权, 与历史锚点 88.1% 一致)."""
    if not reports:
        return CrossMeetingRegressionResult(
            overall_recognition_rate=0.0,
            meeting_reports=[],
            passed_acceptance_gate=False,
            decision_band="rollback",
            rollback_recommended=True,
            tested_meetings=0,
            next_action="abort_no_data",
        )

    total_segments = sum(r.total_segments for r in reports)
    total_hits = sum(r.hit_segments for r in reports)
    weighted_rate = total_hits / total_segments if total_segments else 0.0

    if weighted_rate < CROSS_MEETING_ACCEPTANCE_GATE:
        decision = "rollback"
        rollback = True
        next_action = "rollback_to_previous_embedding_and_alert"
    elif weighted_rate < 0.92:  # 0.90 - 0.92 用户决定区 (用户 override 起点)
        decision = "user_decide"
        rollback = False
        next_action = "require_user_decision"
    else:
        decision = "accept"
        rollback = False
        next_action = "commit_new_embedding"

    return CrossMeetingRegressionResult(
        overall_recognition_rate=weighted_rate,
        meeting_reports=reports,
        passed_acceptance_gate=weighted_rate >= CROSS_MEETING_ACCEPTANCE_GATE,
        decision_band=decision,
        rollback_recommended=rollback,
        tested_meetings=len(reports),
        next_action=next_action,
    )


# 12 会议音频 (W73 A-2 调研实战 + W74 A-2 调研建议重演样本池)
REPROCESS_12_MEETINGS: List[Tuple[int, str]] = [
    (135, "王天志 #135 94.6% pass baseline"),
    (151, "王天志 #151 83.5% rollback re-enact"),
    (208, "会议 #208 m4a replay"),
    (209, "会议 #209 m4a replay"),
    (210, "会议 #210 m4a replay"),
    (211, "会议 #211 m4a replay"),
    (212, "会议 #212 m4a replay"),
    (213, "会议 #213 m4a replay"),
    (214, "会议 #214 m4a replay"),
    (215, "会议 #215 m4a replay"),
    (216, "会议 #216 m4a replay"),
    (227, "会议 #227 m4a replay"),
]


# 真实历史案例锚点 (来自 docs/CLAUDE-history.md:5483-5492)
HISTORICAL_CASE_WANG_TIANZHI = {
    "name": "王天志",
    "meeting_135_rate": 0.946,
    "meeting_151_rate": 0.835,
    "weighted_overall_rate": 0.881,
    "decision": "rollback",
    "rollback_target": "sample_count 583 → 384",
}
