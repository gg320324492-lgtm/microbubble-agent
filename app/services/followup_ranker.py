"""Follow-up Ranker — Phase 14.1 §3.

Ranks follow-up questions using a weighted formula derived from the
``FollowUpQuestion`` fields.

Per spec:

    score = 0.4 * intent_match
          + 0.3 * knowledge_gap
          + 0.2 * usefulness
          + 0.1 * novelty

Each component is normalized into [0.0, 1.0]. Total score is in [0.0, 1.0].
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence

from app.services.followup_schema import (
    CATEGORY_COMPARISON,
    CATEGORY_DETAIL,
    CATEGORY_EXPLANATION,
    CATEGORY_KNOWLEDGE_GAP,
    CATEGORY_NEXT_ACTION,
    DEFAULT_CATEGORIES,
    FollowUpQuestion,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Scoring weights (per spec §3)
# ---------------------------------------------------------------------------
W_INTENT_MATCH = 0.4
W_KNOWLEDGE_GAP = 0.3
W_USEFULNESS = 0.2
W_NOVELTY = 0.1


# Higher-priority category hierarchy — used to compose intent_match & usefulness
_CATEGORY_USEFULNESS = {
    CATEGORY_NEXT_ACTION: 0.95,
    CATEGORY_KNOWLEDGE_GAP: 0.85,
    CATEGORY_COMPARISON: 0.7,
    CATEGORY_EXPLANATION: 0.65,
    CATEGORY_DETAIL: 0.55,
}


def _intent_match(fq: FollowUpQuestion, expected_intent: str) -> float:
    """intent_match in [0.0, 1.0]."""
    if not expected_intent:
        return 0.5
    fq_intent = (fq.intent or "").strip().lower()
    exp = expected_intent.strip().lower()
    if not fq_intent:
        return 0.3
    if fq_intent == exp:
        return 1.0
    # Token overlap (cheap partial-match)
    fq_tokens = set(fq_intent.replace("_", " ").split())
    exp_tokens = set(exp.replace("_", " ").split())
    if not exp_tokens:
        return 0.5
    overlap = len(fq_tokens & exp_tokens)
    if overlap == 0:
        return 0.2
    return min(1.0, 0.5 + 0.5 * (overlap / len(exp_tokens)))


def _knowledge_gap_signal(fq: FollowUpQuestion) -> float:
    """knowledge_gap in [0.0, 1.0].

    Strong if category is knowledge_gap, or metadata carries gap_signal.
    """
    if fq.category == CATEGORY_KNOWLEDGE_GAP:
        base = 0.85
    elif fq.category == CATEGORY_NEXT_ACTION:
        base = 0.6
    elif fq.category == CATEGORY_COMPARISON:
        base = 0.55
    else:
        base = 0.4
    meta_signal = fq.metadata.get("gap_signal") if fq.metadata else None
    if isinstance(meta_signal, (int, float)):
        base = max(base, float(meta_signal))
    return min(1.0, max(0.0, base))


def _usefulness(fq: FollowUpQuestion) -> float:
    """usefulness in [0.0, 1.0] — driven by category + confidence."""
    cat_score = _CATEGORY_USEFULNESS.get(fq.category, 0.5)
    confidence = max(0.0, min(1.0, float(fq.confidence)))
    return min(1.0, 0.6 * cat_score + 0.4 * confidence)


def _novelty(fq: FollowUpQuestion, seen_questions: Sequence[str]) -> float:
    """novelty in [0.0, 1.0] — penalises duplicates in the running set.

    The first occurrence scores 1.0; an identical question later scores 0.0.
    """
    q = (fq.question or "").strip().lower()
    if not q:
        return 0.0
    for s in seen_questions:
        if q == s.strip().lower():
            return 0.0
    return 1.0


def _score_one(fq: FollowUpQuestion, expected_intent: str, seen_questions: Sequence[str]) -> float:
    """Compose final score for a single follow-up question."""
    i = _intent_match(fq, expected_intent)
    k = _knowledge_gap_signal(fq)
    u = _usefulness(fq)
    n = _novelty(fq, seen_questions)
    score = (
        W_INTENT_MATCH * i
        + W_KNOWLEDGE_GAP * k
        + W_USEFULNESS * u
        + W_NOVELTY * n
    )
    return round(min(1.0, max(0.0, score)), 4)


def rank_followups(
    followups: List[FollowUpQuestion],
    *,
    expected_intent: str = "",
    top_k: Optional[int] = None,
) -> List[FollowUpQuestion]:
    """Phase 14.1 §3: rank follow-up questions and return top-k.

    Args:
        followups: list of ``FollowUpQuestion``.
        expected_intent: optional target intent string. When supplied,
            categories with ``intent`` matching ``expected_intent`` rank up.
        top_k: optional cap. ``None`` returns all; ``0`` returns ``[]``.

    Returns:
        Sorted list (highest score first), each item's ``metadata`` now
        containing ``score`` and component breakdown.
    """
    if not followups:
        return []
    if top_k == 0:
        return []

    seen: List[str] = []
    scored: List[tuple] = []
    for fq in followups:
        s = _score_one(fq, expected_intent, seen)
        components = {
            "intent_match": round(_intent_match(fq, expected_intent), 4),
            "knowledge_gap": round(_knowledge_gap_signal(fq), 4),
            "usefulness": round(_usefulness(fq), 4),
            "novelty": round(_novelty(fq, seen), 4),
            "score": s,
        }
        # Stash components in metadata without mutating the caller's
        # original dictionary references (use a shallow copy).
        if fq.metadata is None:
            fq.metadata = {}
        else:
            fq.metadata = dict(fq.metadata)
        fq.metadata["score"] = s
        fq.metadata["score_components"] = components
        scored.append((s, fq))
        seen.append(fq.question or "")

    # Stable sort: highest score first; preserve input order on ties.
    scored.sort(key=lambda item: (-item[0],))
    ordered = [item[1] for item in scored]

    if top_k is None:
        return ordered
    return ordered[: max(0, int(top_k))]


__all__ = [
    "rank_followups",
    "W_INTENT_MATCH",
    "W_KNOWLEDGE_GAP",
    "W_USEFULNESS",
    "W_NOVELTY",
]
