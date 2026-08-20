"""Research Progress Tracker — Phase 15.0 §5.

Score-based progress evaluation across 5 dimensions:
literature_progress, hypothesis_progress, evidence_progress,
experiment_progress, paper_progress + overall_score.

Produces a next-action recommendation by inspecting the lowest-scoring
dimension.

Public API:
- ResearchProgress dataclass
- ResearchProgressTracker
    evaluate_workspace(workspace)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.research_workspace_manager import (
    WorkspaceSnapshot,
)


# ---------------------------------------------------------------------------
# Dimension weight constants — Phase 15.0 §5
# ---------------------------------------------------------------------------
W_LITERATURE = 0.15
W_HYPOTHESIS = 0.25
W_EVIDENCE = 0.25
W_EXPERIMENT = 0.25
W_PAPER = 0.10

DIMENSIONS: tuple = (
    "literature_progress",
    "hypothesis_progress",
    "evidence_progress",
    "experiment_progress",
    "paper_progress",
)


@dataclass
class ResearchProgress:
    """Phase 15.0 §5: score-based research progress snapshot."""

    literature_progress: float = 0.0
    hypothesis_progress: float = 0.0
    evidence_progress: float = 0.0
    experiment_progress: float = 0.0
    paper_progress: float = 0.0
    overall_score: float = 0.0
    next_action: str = ""
    dimension_breakdown: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "literature_progress": round(self.literature_progress, 4),
            "hypothesis_progress": round(self.hypothesis_progress, 4),
            "evidence_progress": round(self.evidence_progress, 4),
            "experiment_progress": round(self.experiment_progress, 4),
            "paper_progress": round(self.paper_progress, 4),
            "overall_score": round(self.overall_score, 4),
            "next_action": self.next_action,
            "dimension_breakdown": {
                k: round(v, 4) for k, v in self.dimension_breakdown.items()
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _score_literature(workspace: WorkspaceSnapshot) -> float:
    """Phase 15.0 §5: literature_progress (0..1).

    Explicit ``progress_payload["literature_progress"]`` wins. Otherwise:
      - progress_payload["literature_done"] is True → 1.0
      - evidence_summary has any entry → 0.4
      - hypotheses present → 0.25
      - current_stage == literature → 0.15
      - fallback → 0.05
    """
    explicit = workspace.progress_payload.get("literature_progress")
    if explicit is not None:
        return _clamp01(explicit)
    if workspace.progress_payload.get("literature_done") is True:
        return 1.0
    if workspace.evidence_summary:
        return 0.4
    if workspace.hypotheses:
        return 0.25
    if workspace.current_stage == "literature":
        return 0.15
    return 0.05


def _score_hypothesis(workspace: WorkspaceSnapshot) -> float:
    """Phase 15.0 §5: hypothesis_progress (0..1).

    Explicit ``progress_payload["hypothesis_progress"]`` wins.
    """
    n = len(workspace.hypotheses)
    explicit = workspace.progress_payload.get("hypothesis_progress")
    if explicit is not None:
        return _clamp01(explicit)
    if n >= 3:
        return 0.85
    if n == 2:
        return 0.7
    if n == 1:
        return 0.45
    return 0.1


def _score_evidence(workspace: WorkspaceSnapshot) -> float:
    """Phase 15.0 §5: evidence_progress (0..1).

    Explicit ``progress_payload["evidence_progress"]`` wins.
    """
    n = len(workspace.evidence_summary)
    explicit = workspace.progress_payload.get("evidence_progress")
    if explicit is not None:
        return _clamp01(explicit)
    if n >= 4:
        return 0.9
    if n >= 3:
        return 0.7
    if n == 2:
        return 0.5
    if n == 1:
        return 0.3
    return 0.1


def _score_experiment(workspace: WorkspaceSnapshot) -> float:
    """Phase 15.0 §5: experiment_progress (0..1).

    Explicit ``progress_payload["experiment_progress"]`` wins.
    """
    explicit = workspace.progress_payload.get("experiment_progress")
    if explicit is not None:
        return _clamp01(explicit)
    if workspace.current_stage == "experiment":
        return 0.4
    if workspace.current_stage in ("analysis", "writing"):
        return 0.7
    if workspace.evidence_summary:
        return 0.45
    return 0.1


def _score_paper(workspace: WorkspaceSnapshot) -> float:
    """Phase 15.0 §5: paper_progress (0..1).

    Explicit ``progress_payload["paper_progress"]`` wins.
    """
    explicit = workspace.progress_payload.get("paper_progress")
    if explicit is not None:
        return _clamp01(explicit)
    if workspace.current_stage == "writing":
        return 0.6
    if workspace.evidence_summary and len(workspace.hypotheses) > 0:
        return 0.25
    return 0.05


# ---------------------------------------------------------------------------
# Next-action recommendation
# ---------------------------------------------------------------------------
_NEXT_ACTIONS: Dict[str, str] = {
    "literature_progress": "梳理近 5 年顶刊文献路线并整理研究空白",
    "hypothesis_progress": "补充第 2-3 个科学假设并明确可证伪命题",
    "evidence_progress": "补齐关键实验证据（如自由基捕获、动力学常数）",
    "experiment_progress": "执行下一步关键实验（如 radical quenching experiment）",
    "paper_progress": "搭建论文骨架（创新点定位 + 文献对比 + 图表规划）",
}


def _pick_next_action(scores: Dict[str, float]) -> str:
    """Phase 15.0 §5: pick the lowest-scoring dimension as the next gap."""
    if not scores:
        return _NEXT_ACTIONS["hypothesis_progress"]
    weakest = min(scores.items(), key=lambda item: item[1])
    return _NEXT_ACTIONS.get(
        weakest[0],
        "补充下一步研究动作",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class ResearchProgressTracker:
    """Phase 15.0 §5: progress tracker (rule-based, no LLM)."""

    def evaluate_workspace(
        self,
        workspace: WorkspaceSnapshot,
    ) -> ResearchProgress:
        """Phase 15.0 §5: compute scores + next-action recommendation."""
        scores = {
            "literature_progress": _score_literature(workspace),
            "hypothesis_progress": _score_hypothesis(workspace),
            "evidence_progress": _score_evidence(workspace),
            "experiment_progress": _score_experiment(workspace),
            "paper_progress": _score_paper(workspace),
        }
        overall = (
            W_LITERATURE * scores["literature_progress"]
            + W_HYPOTHESIS * scores["hypothesis_progress"]
            + W_EVIDENCE * scores["evidence_progress"]
            + W_EXPERIMENT * scores["experiment_progress"]
            + W_PAPER * scores["paper_progress"]
        )
        return ResearchProgress(
            literature_progress=scores["literature_progress"],
            hypothesis_progress=scores["hypothesis_progress"],
            evidence_progress=scores["evidence_progress"],
            experiment_progress=scores["experiment_progress"],
            paper_progress=scores["paper_progress"],
            overall_score=overall,
            next_action=_pick_next_action(scores),
            dimension_breakdown=scores,
        )


__all__ = [
    "ResearchProgress",
    "ResearchProgressTracker",
    "DIMENSIONS",
    "W_LITERATURE",
    "W_HYPOTHESIS",
    "W_EVIDENCE",
    "W_EXPERIMENT",
    "W_PAPER",
]
