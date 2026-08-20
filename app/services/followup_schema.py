"""Follow-up Intelligence Schema — Phase 14.1 §1.

Additive-only enhancement over Phase 14.0 research report. Defines the
canonical shape of intent-aware follow-up questions attached to research
reports.

Public API:
- FollowUpCategory: enum-like (5 categories)
- FollowUpQuestion: dataclass (question + 5 metadata fields)
- DEFAULT_CATEGORIES: tuple of all 5 category names
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Category constants — Phase 14.1 §1
# ---------------------------------------------------------------------------
CATEGORY_DETAIL = "detail"
CATEGORY_EXPLANATION = "explanation"
CATEGORY_COMPARISON = "comparison"
CATEGORY_NEXT_ACTION = "next_action"
CATEGORY_KNOWLEDGE_GAP = "knowledge_gap"

DEFAULT_CATEGORIES: tuple = (
    CATEGORY_DETAIL,
    CATEGORY_EXPLANATION,
    CATEGORY_COMPARISON,
    CATEGORY_NEXT_ACTION,
    CATEGORY_KNOWLEDGE_GAP,
)


@dataclass
class FollowUpQuestion:
    """Phase 14.1 §1: single intent-aware follow-up question.

    All fields are optional except ``question`` and ``category``.
    Designed to be created deterministically (rules) or via LLM refinement;
    downstream ranking treats ``confidence`` and ``priority`` as primary
    signals.
    """

    question: str
    category: str = CATEGORY_DETAIL
    intent: str = ""
    reason: str = ""
    confidence: float = 0.5
    priority: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Clamp confidence/priority into [0.0, 1.0]
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        self.priority = max(0.0, min(1.0, float(self.priority)))
        # Validate category
        if self.category not in DEFAULT_CATEGORIES:
            # Downgrade unknown categories to detail rather than raising
            self.category = CATEGORY_DETAIL
        # Default intent + reason fallback
        if not self.intent:
            self.intent = "explore_research_topic"
        if not self.reason:
            self.reason = "improve_research_understanding"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "question": self.question,
            "category": self.category,
            "intent": self.intent,
            "reason": self.reason,
            "confidence": self.confidence,
            "priority": self.priority,
            "metadata": dict(self.metadata),
        }


def make_followup(
    question: str,
    *,
    category: str = CATEGORY_DETAIL,
    intent: str = "",
    reason: str = "",
    confidence: float = 0.5,
    priority: float = 0.5,
    metadata: Optional[Dict[str, Any]] = None,
) -> FollowUpQuestion:
    """Factory helper used by generator + ranker + tests."""
    return FollowUpQuestion(
        question=question,
        category=category,
        intent=intent,
        reason=reason,
        confidence=confidence,
        priority=priority,
        metadata=dict(metadata or {}),
    )


def followups_to_dicts(followups: List[FollowUpQuestion]) -> List[Dict[str, Any]]:
    """Batch-serialize follow-up list."""
    return [f.to_dict() for f in (followups or [])]
