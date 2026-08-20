"""Follow-up Generator — Phase 14.1 §2.

Generates intent-aware follow-up questions for a research agent answer.

Strategy:
1. Deterministic rules first (intent + keywords + memory gaps).
2. Optional LLM refinement (skipped if unavailable).
3. Always returns fallback questions if rules/llm produce none.

Four generation dimensions (per spec):
- Deep understanding → CATEGORY_DETAIL / CATEGORY_EXPLANATION
- Related analysis   → CATEGORY_COMPARISON
- Next action suggestion → CATEGORY_NEXT_ACTION
- Knowledge gap completion → CATEGORY_KNOWLEDGE_GAP
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from app.services.followup_schema import (
    CATEGORY_COMPARISON,
    CATEGORY_DETAIL,
    CATEGORY_EXPLANATION,
    CATEGORY_KNOWLEDGE_GAP,
    CATEGORY_NEXT_ACTION,
    DEFAULT_CATEGORIES,
    FollowUpQuestion,
    make_followup,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tokens for intent inference — Phase 14.1 §2
# ---------------------------------------------------------------------------
_DETAIL_TOKENS = (
    "how",
    "why",
    "what is",
    "explain",
    "details",
    "describe",
    "elaborate",
)
_COMPARISON_TOKENS = (
    "compare",
    "versus",
    "vs",
    "alternative",
    "instead of",
    "differ",
)
_NEXT_ACTION_TOKENS = (
    "next step",
    "what should",
    "follow up",
    "after this",
    "proceed",
    "action plan",
    "next",
)
_KNOWLEDGE_GAP_TOKENS = (
    "missing",
    "gap",
    "unknown",
    "don't know",
    "uncertain",
    "limitation",
    "not enough",
    "incomplete",
)


# ---------------------------------------------------------------------------
# Deterministic scoring helpers
# ---------------------------------------------------------------------------
def _score(prompt: str, tokens: tuple) -> float:
    """Return normalized token-match score in [0.0, 1.0]."""
    if not prompt:
        return 0.0
    lower = prompt.lower()
    hits = 0
    for t in tokens:
        if t in lower:
            hits += 1
    return min(1.0, hits / max(1, len(tokens) // 2))


def _infer_intent_label(intent) -> str:
    """Phase 14.1 §2: extract intent label from Phase 8.0 ResearchIntent or None."""
    if intent is None:
        return ""
    # Most common attributes on ResearchIntent: objective, domain, task_type
    return (
        getattr(intent, "task_type", "")
        or getattr(intent, "domain", "")
        or (getattr(intent, "objective", "") or "")[:60]
    )


def _memory_gap_signal(memory_hits) -> float:
    """Phase 14.1 §2: knowledge-gap signal from memory hits.

    Empty/weaker memory → larger gap → higher score.
    """
    if not memory_hits:
        return 0.8
    try:
        n = len(memory_hits)
    except TypeError:
        return 0.5
    if n == 0:
        return 0.8
    if n <= 2:
        return 0.5
    if n <= 5:
        return 0.3
    return 0.1


def _reasoning_signal(reasoning_output) -> float:
    """Phase 14.1 §2: 'more detail' signal driven by reasoning posterior."""
    if reasoning_output is None:
        return 0.3
    posterior = getattr(reasoning_output, "bayesian_posterior", None)
    if posterior is None:
        return 0.3
    # Lower posterior → more uncertainty → ask deeper
    try:
        v = float(posterior)
    except (TypeError, ValueError):
        return 0.3
    return max(0.0, min(1.0, 1.0 - v))


def _safe_subject(user_prompt: str) -> str:
    """Subject string (first non-trivial noun phrase, fallback = the prompt)."""
    if not user_prompt:
        return "this topic"
    cleaned = re.sub(r"\s+", " ", user_prompt.strip())
    if not cleaned:
        return "this topic"
    return cleaned if len(cleaned) <= 90 else cleaned[:87] + "..."


# ---------------------------------------------------------------------------
# Deterministic rule generators
# ---------------------------------------------------------------------------
def _detail_question(prompt: str, subject: str) -> FollowUpQuestion:
    return make_followup(
        question=f"Can you walk me through the key steps or assumptions behind {subject}?",
        category=CATEGORY_DETAIL,
        intent="deep_dive",
        reason="user requested deeper understanding",
        confidence=0.6,
        priority=0.55,
        metadata={"generator": "rules", "dimension": "deep_understanding"},
    )


def _explanation_question(prompt: str, subject: str, score: float) -> FollowUpQuestion:
    priority = 0.5 + 0.3 * score
    confidence = 0.55 + 0.25 * score
    return make_followup(
        question=f"What underlying mechanism or theory best explains {subject}?",
        category=CATEGORY_EXPLANATION,
        intent="explain_mechanism",
        reason="user wants mechanism/explanation",
        confidence=round(confidence, 3),
        priority=round(priority, 3),
        metadata={"generator": "rules", "dimension": "deep_understanding"},
    )


def _comparison_question(prompt: str, subject: str, score: float) -> FollowUpQuestion:
    priority = 0.4 + 0.4 * score
    confidence = 0.5 + 0.2 * score
    return make_followup(
        question=f"How does {subject} compare to alternative approaches or methods?",
        category=CATEGORY_COMPARISON,
        intent="compare_alternatives",
        reason="user mentioned comparison/alternatives",
        confidence=round(confidence, 3),
        priority=round(priority, 3),
        metadata={"generator": "rules", "dimension": "related_analysis"},
    )


def _next_action_question(prompt: str, subject: str, score: float) -> FollowUpQuestion:
    priority = 0.5 + 0.4 * score
    confidence = 0.55 + 0.2 * score
    return make_followup(
        question=f"What should be the next concrete step to act on {subject}?",
        category=CATEGORY_NEXT_ACTION,
        intent="recommend_next_step",
        reason="user wants actionable next step",
        confidence=round(confidence, 3),
        priority=round(priority, 3),
        metadata={"generator": "rules", "dimension": "next_action_suggestion"},
    )


def _knowledge_gap_question(prompt: str, subject: str, gap_score: float) -> FollowUpQuestion:
    priority = 0.6 + 0.3 * gap_score
    confidence = 0.55 + 0.2 * gap_score
    return make_followup(
        question=f"Which aspects of {subject} remain unclear or under-documented?",
        category=CATEGORY_KNOWLEDGE_GAP,
        intent="knowledge_gap_completion",
        reason="memory retrieval suggests knowledge gaps",
        confidence=round(confidence, 3),
        priority=round(priority, 3),
        metadata={
            "generator": "rules",
            "dimension": "knowledge_gap_completion",
            "gap_signal": round(gap_score, 3),
        },
    )


# ---------------------------------------------------------------------------
# Optional LLM refinement — gracefully skipped if unavailable
# ---------------------------------------------------------------------------
def _try_llm_refinement(
    candidates: List[FollowUpQuestion],
    user_prompt: str,
    answer: str,
) -> List[FollowUpQuestion]:
    """Phase 14.1 §2: optional LLM refinement.

    Returns the input list unchanged if no LLM client is available or the
    client returns malformed data. This guarantees the deterministic
    fallback path always works.
    """
    try:
        from app.agent.llm_client import get_default_llm_client  # type: ignore
    except Exception as exc:  # pragma: no cover - environment bound
        _logger.debug("LLM client import failed: %s", exc)
        return candidates

    try:
        client = get_default_llm_client()
        if client is None:
            return candidates
    except Exception as exc:  # pragma: no cover
        _logger.debug("LLM client unavailable: %s", exc)
        return candidates

    # Build a compact JSON-friendly prompt. We never block on this — if the
    # client doesn't support `complete`, fall back.
    try:
        refinement_prompt = (
            "Refine the following research follow-up questions so each is "
            "specific, clear, and actionable. Return JSON list with same "
            "fields.\n\n"
            f"User prompt: {user_prompt[:400]}\n"
            f"Answer summary: {answer[:300]}\n"
            f"Candidates: {[c.to_dict() for c in candidates]}\n"
        )
        result = client.complete(refinement_prompt)  # type: ignore[attr-defined]
        if not result:
            return candidates
        refined: List[FollowUpQuestion] = []
        if isinstance(result, list):
            for item in result:
                if not isinstance(item, dict):
                    continue
                qtext = item.get("question") or ""
                if not qtext:
                    continue
                refined.append(
                    make_followup(
                        question=qtext,
                        category=item.get("category") or CATEGORY_DETAIL,
                        intent=item.get("intent") or "llm_refined",
                        reason=item.get("reason") or "llm_refinement",
                        confidence=float(item.get("confidence", 0.7) or 0.7),
                        priority=float(item.get("priority", 0.6) or 0.6),
                        metadata={"generator": "llm"},
                    )
                )
        if refined:
            return refined
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("LLM refinement failed: %s", exc)
    return candidates


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_followup_questions(
    user_prompt: str,
    answer: str,
    context: Optional[Dict[str, Any]] = None,
    memory_hits: Optional[List[Any]] = None,
    reasoning_output: Optional[Any] = None,
    intent: Optional[Any] = None,
    max_questions: int = 3,
) -> List[FollowUpQuestion]:
    """Phase 14.1 §2: generate intent-aware follow-up questions.

    Args:
        user_prompt: original research question.
        answer: research agent's answer (may be empty).
        context: optional context dict (unused by deterministic path,
            reserved for LLM refinement).
        memory_hits: optional list of memory hits (used to compute
            knowledge-gap signal).
        reasoning_output: optional Bayesian posterior (used to drive deep
            understanding signal).
        intent: optional Phase 8.0 ResearchIntent (informational).
        max_questions: number of follow-ups to return (default 3).

    Returns:
        list of ``FollowUpQuestion`` (length <= ``max_questions``).
        Always non-empty — falls back to a generic question.
    """
    subject = _safe_subject(user_prompt or "")
    intent_label = _infer_intent_label(intent)

    # Base candidates from deterministic rules
    candidates: List[FollowUpQuestion] = []
    detail_score = max(_score(user_prompt, _DETAIL_TOKENS), 0.55)
    cmp_score = _score(user_prompt, _COMPARISON_TOKENS)
    next_score = _score(user_prompt, _NEXT_ACTION_TOKENS)
    gap_score = _memory_gap_signal(memory_hits)
    reasoning_score = _reasoning_signal(reasoning_output)

    candidates.append(_detail_question(user_prompt, subject))

    explanation_score = max(detail_score, reasoning_score)
    candidates.append(
        _explanation_question(user_prompt, subject, explanation_score)
    )

    if cmp_score > 0:
        candidates.append(
            _comparison_question(user_prompt, subject, cmp_score)
        )

    if next_score > 0:
        candidates.append(
            _next_action_question(user_prompt, subject, next_score)
        )

    if gap_score >= 0.5:
        candidates.append(
            _knowledge_gap_question(user_prompt, subject, gap_score)
        )

    # Tag intent label onto metadata if available
    if intent_label:
        for c in candidates:
            c.metadata.setdefault("intent_label", intent_label)

    # Optional LLM refinement (non-blocking)
    candidates = _try_llm_refinement(candidates, user_prompt or "", answer or "")

    # Trim or pad to max_questions
    out = candidates[:max_questions] if max_questions > 0 else []

    if not out:
        # Fallback (per spec requirement: fallback required)
        out.append(
            make_followup(
                question=f"What aspect of {subject} would you like to explore next?",
                category=CATEGORY_NEXT_ACTION,
                intent="explore_research_topic",
                reason="fallback_question",
                confidence=0.45,
                priority=0.45,
                metadata={"generator": "fallback"},
            )
        )

    # If we still have fewer than max_questions, ensure unique categories
    seen_categories = {c.category for c in out}
    pool = [
        _detail_question(user_prompt, subject),
        _explanation_question(user_prompt, subject, explanation_score),
        _comparison_question(user_prompt, subject, cmp_score),
        _next_action_question(user_prompt, subject, next_score),
        _knowledge_gap_question(user_prompt, subject, gap_score),
    ]
    for cand in pool:
        if len(out) >= max_questions:
            break
        if cand.category not in seen_categories:
            out.append(cand)
            seen_categories.add(cand.category)

    return out[:max_questions] if max_questions > 0 else out


__all__ = [
    "generate_followup_questions",
    "DEFAULT_CATEGORIES",
]
