"""
声纹 B+C 方案实施 — 确定性渐进质量门 (W75 第 1 批 B-1)

A-2 W74 调研 §5 主拍必拍 (B 方案 + C 方案), 0 production code 改动铁律守恒.

派工 v6 段 5 反馈 #6 实战: 拒绝方案 A 字面改 0.9, B 方案必确定性
(LLM 最多解释歧义, 不得越过门禁).

4 子门禁 (全部通过才确认成员, 否则 rollback):
1. 单段距离门禁: distance ≤ 0.7 (不破坏 MATCH_THRESHOLD 实战语义)
2. top1-top2 margin 门禁: top1_distance - top2_distance ≥ 0.05 (避免混淆)
3. cluster votes 门禁: votes ≥ 3 (跨会议累积验证, KMeans 实战)
4. anchor 状态门禁: member.voice_confirmed_at IS NOT NULL (CLAUDE.md 永久锚点 v60-v67)

锚点范式: W74 第 1 批 249 → W75 第 1 批 B-1 253 守恒 (+1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

# 4 子门禁常量 (B 方案确定性渐进质量门)
SINGLE_DISTANCE_MAX = 0.7  # 子门禁 1: 单段余弦距离上限 (与 MATCH_THRESHOLD 实战保持一致)
TOP1_TOP2_MARGIN_MIN = 0.05  # 子门禁 2: top1-top2 margin 下限 (避免混淆)
CLUSTER_VOTES_MIN = 3  # 子门禁 3: cluster votes 下限 (跨会议累积验证)
ANCHOR_REQUIRED = True  # 子门禁 4: anchor 状态门禁 (voice_confirmed_at IS NOT NULL)


@dataclass
class CandidateScore:
    """单个候选成员的距离 + votes."""

    member_id: int
    member_name: str
    distance: float
    votes: int
    is_anchor: bool
    voice_confirmed_at: Optional[datetime] = None


@dataclass
class QualityGateResult:
    """质量门禁评估结果."""

    passed: bool
    candidate: Optional[CandidateScore] = None
    failed_subgates: List[str] = field(default_factory=list)
    subgate_details: dict = field(default_factory=dict)
    rollback_recommended: bool = False

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "candidate": self.candidate.__dict__ if self.candidate else None,
            "failed_subgates": self.failed_subgates,
            "subgate_details": self.subgate_details,
            "rollback_recommended": self.rollback_recommended,
        }


def evaluate_single_distance_gate(distance: float) -> Tuple[bool, dict]:
    """子门禁 1: 单段距离 ≤ SINGLE_DISTANCE_MAX (0.7)."""
    ok = distance <= SINGLE_DISTANCE_MAX
    return ok, {"threshold": SINGLE_DISTANCE_MAX, "value": distance, "ok": ok}


def evaluate_top1_top2_margin_gate(
    top1_distance: float, top2_distance: Optional[float]
) -> Tuple[bool, dict]:
    """子门禁 2: top1-top2 margin ≥ TOP1_TOP2_MARGIN_MIN (0.05).

    注意: 距离越小越相似 (cosine distance), 因此 margin 应该是
    top2 - top1 (差距越大越能区分).
    若只有 1 个候选, margin 视为 ∞ (自动通过).
    """
    if top2_distance is None:
        margin = float("inf")
        ok = True
    else:
        # 距离语义: 越小越相似, 区分度 = top2(差) - top1(好)
        margin = top2_distance - top1_distance
        ok = margin >= TOP1_TOP2_MARGIN_MIN
    return ok, {
        "threshold": TOP1_TOP2_MARGIN_MIN,
        "margin": margin if margin != float("inf") else None,
        "top1": top1_distance,
        "top2": top2_distance,
        "ok": ok,
    }


def evaluate_cluster_votes_gate(votes: int) -> Tuple[bool, dict]:
    """子门禁 3: cluster votes ≥ CLUSTER_VOTES_MIN (3)."""
    ok = votes >= CLUSTER_VOTES_MIN
    return ok, {"threshold": CLUSTER_VOTES_MIN, "value": votes, "ok": ok}


def evaluate_anchor_state_gate(
    is_anchor: bool, voice_confirmed_at: Optional[datetime] = None
) -> Tuple[bool, dict]:
    """子门禁 4: anchor 状态门禁 (voice_confirmed_at IS NOT NULL)."""
    ok = is_anchor and voice_confirmed_at is not None if ANCHOR_REQUIRED else True
    return ok, {
        "anchor_required": ANCHOR_REQUIRED,
        "is_anchor": is_anchor,
        "voice_confirmed_at": (
            voice_confirmed_at.isoformat() if voice_confirmed_at else None
        ),
        "ok": ok,
    }


def evaluate_quality_gate(candidates: List[CandidateScore]) -> QualityGateResult:
    """评估 4 子门禁 (全部通过才返回 passed=True).

    Args:
        candidates: 全部候选按距离升序排列 (top1 在 index 0).

    Returns:
        QualityGateResult.passed = True 仅当 4 子门禁全部通过.
        任一子门禁失败 → rollback_recommended = True (W74 D-1 派工 v6 段 5 反馈 #7 实战).
    """
    if not candidates:
        return QualityGateResult(
            passed=False,
            failed_subgates=["all"],
            subgate_details={"reason": "no candidates"},
            rollback_recommended=True,
        )

    top1 = candidates[0]
    top2 = candidates[1] if len(candidates) > 1 else None

    gate1_ok, gate1_detail = evaluate_single_distance_gate(top1.distance)
    gate2_ok, gate2_detail = evaluate_top1_top2_margin_gate(
        top1.distance, top2.distance if top2 else None
    )
    gate3_ok, gate3_detail = evaluate_cluster_votes_gate(top1.votes)
    gate4_ok, gate4_detail = evaluate_anchor_state_gate(
        top1.is_anchor, top1.voice_confirmed_at
    )

    all_ok = gate1_ok and gate2_ok and gate3_ok and gate4_ok
    failed = []
    if not gate1_ok:
        failed.append("single_distance")
    if not gate2_ok:
        failed.append("top1_top2_margin")
    if not gate3_ok:
        failed.append("cluster_votes")
    if not gate4_ok:
        failed.append("anchor_state")

    return QualityGateResult(
        passed=all_ok,
        candidate=top1,
        failed_subgates=failed,
        subgate_details={
            "single_distance": gate1_detail,
            "top1_top2_margin": gate2_detail,
            "cluster_votes": gate3_detail,
            "anchor_state": gate4_detail,
        },
        rollback_recommended=not all_ok,
    )


def should_rollback(result: QualityGateResult) -> bool:
    """B 方案核心: 任一子门禁失败则 rollback (W74 D-1 派工 v6 段 5 反馈 #7)."""
    return result.rollback_recommended
