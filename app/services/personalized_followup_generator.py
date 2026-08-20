"""Personalized Follow-up Generator — Phase 14.2 §3.

Generates intent-aware, profile-aware follow-up questions. Replaces
Phase 14.1's weight formula with a five-axis scoring model:

    score = 0.25 * intent_match
          + 0.25 * knowledge_gap
          + 0.25 * user_relevance
          + 0.15 * research_value
          + 0.10 * novelty

Adds two new axes the original generator did not consider:

- ``user_relevance``     — does the question match the user's research
  profile (domain, expertise, history)?
- ``research_value``     — does the question point toward measurable
  scientific next-step value (mechanism / experiment / literature)?

This module is additive — it does **not** modify the existing
``app.services.followup_generator`` (Phase 14.1).
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
from app.services.followup_context import FollowUpContext

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Weights — Phase 14.2 §3
# ---------------------------------------------------------------------------
W_INTENT_MATCH = 0.25
W_KNOWLEDGE_GAP = 0.25
W_USER_RELEVANCE = 0.25
W_RESEARCH_VALUE = 0.15
W_NOVELTY = 0.10


# ---------------------------------------------------------------------------
# Phrase banks by expertise — Phase 14.2 §3
# ---------------------------------------------------------------------------
_GENERIC_PHRASES = (
    "你了解了吗",
    "你想深入了解",
    "do you want",
    "want to know more",
    "更多内容",
    "想不想了解更多",
)

_RESEARCHER_PHRASES = (
    "kLa", "传质系数",
    "·OH", "·O2-", "自由基",
    "反应动力学",
    "DFT 计算",
    "DOE 实验设计",
    "动力学常数",
    "膜污染",
)

_PRACTITIONER_PHRASES = (
    "工程放大",
    "工艺设计",
    "运行成本",
    "设备选型",
    "处理水量",
    "工程应用",
)


def _is_generic(text: str) -> bool:
    low = (text or "").lower()
    return any(p.lower() in low for p in _GENERIC_PHRASES)


def _has_researcher_signal(text: str) -> bool:
    low = (text or "").lower()
    return any(p.lower() in low for p in _RESEARCHER_PHRASES)


def _has_practitioner_signal(text: str) -> bool:
    low = (text or "").lower()
    return any(p.lower() in low for p in _PRACTITIONER_PHRASES)


def _safe_subject(text: str) -> str:
    if not text:
        return "当前主题"
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return "当前主题"
    return cleaned if len(cleaned) <= 90 else cleaned[:87] + "..."


# ---------------------------------------------------------------------------
# Scoring components
# ---------------------------------------------------------------------------
def _intent_match(fq: FollowUpQuestion, expected_intent: str) -> float:
    if not expected_intent:
        return 0.5
    fq_intent = (fq.intent or "").strip().lower()
    exp = expected_intent.strip().lower()
    if not fq_intent:
        return 0.3
    if fq_intent == exp:
        return 1.0
    fq_tokens = set(fq_intent.replace("_", " ").split())
    exp_tokens = set(exp.replace("_", " ").split())
    if not exp_tokens:
        return 0.5
    overlap = len(fq_tokens & exp_tokens)
    return min(1.0, 0.5 + 0.5 * (overlap / len(exp_tokens))) if overlap else 0.2


def _knowledge_gap(fq: FollowUpQuestion) -> float:
    if fq.category == CATEGORY_KNOWLEDGE_GAP:
        return 0.85
    if fq.category == CATEGORY_NEXT_ACTION:
        return 0.6
    if fq.category == CATEGORY_COMPARISON:
        return 0.55
    return 0.4


def _user_relevance(fq: FollowUpQuestion, profile, expertise: str) -> float:
    """How well does the question match the user's profile?"""
    score = 0.4
    text = (fq.question or "")
    if _is_generic(text):
        return 0.05  # explicit penalty on generic patterns

    if expertise in ("researcher", "practitioner"):
        if _has_researcher_signal(text):
            score += 0.5
    if expertise == "practitioner":
        if _has_practitioner_signal(text):
            score += 0.2

    # Domain-aware boost
    if profile is not None:
        domain = getattr(profile, "domain", "") or ""
        q_low = text.lower()
        if domain == "pollution_control_water_treatment":
            if any(k.lower() in q_low for k in (
                "微纳米气泡", "microbubble", "臭氧", "ozone",
                "kLa", "传质", "水处理",
            )):
                score += 0.3
        elif domain == "advanced_oxidation_water_treatment":
            if any(k.lower() in q_low for k in (
                "aop", "高级氧化", "·OH", "oh radical",
                "羟基", "自由基",
            )):
                score += 0.3
        elif domain == "computational_chemistry":
            if any(k.lower() in q_low for k in (
                "dft", "b3lyp", "gaussian", "过渡态", "kinetic",
            )):
                score += 0.3
        elif domain:
            # If we have any domain and the question touches a domain term
            for kw in getattr(profile, "keywords", []) or []:
                if str(kw).lower() in q_low:
                    score += 0.2
                    break

    # Active topics from profile
    if profile is not None and getattr(profile, "active_topics", None):
        topics = [str(t) for t in profile.active_topics]
        q_low = text.lower()
        if any(t.lower() in q_low for t in topics):
            score += 0.15

    return min(1.0, max(0.0, score))


def _research_value(fq: FollowUpQuestion, profile) -> float:
    """Does the question point toward measurable scientific next-step value?"""
    base = 0.35
    text = (fq.question or "")
    q_low = text.lower()
    if fq.category in (CATEGORY_NEXT_ACTION, CATEGORY_COMPARISON):
        base += 0.2
    if fq.category == CATEGORY_KNOWLEDGE_GAP:
        base += 0.15
    if _has_researcher_signal(text):
        base += 0.3
    if profile is not None and getattr(profile, "active_topics", None):
        topics = [str(t) for t in profile.active_topics]
        if any(t.lower() in q_low for t in topics):
            base += 0.1
    return min(1.0, max(0.0, base))


def _novelty(fq: FollowUpQuestion, seen_questions: list) -> float:
    q = (fq.question or "").strip().lower()
    if not q:
        return 0.0
    for s in seen_questions:
        if q == (s or "").strip().lower():
            return 0.0
    return 1.0


def _score(fq: FollowUpQuestion, ctx, expected_intent: str, seen: list) -> float:
    profile = getattr(ctx, "user_profile", None)
    expertise = getattr(ctx, "user_expertise_level", "general") or "general"
    s = (
        W_INTENT_MATCH * _intent_match(fq, expected_intent)
        + W_KNOWLEDGE_GAP * _knowledge_gap(fq)
        + W_USER_RELEVANCE * _user_relevance(fq, profile, expertise)
        + W_RESEARCH_VALUE * _research_value(fq, profile)
        + W_NOVELTY * _novelty(fq, seen)
    )
    return round(min(1.0, max(0.0, s)), 4)


# ---------------------------------------------------------------------------
# Candidate builders — Phase 14.2 §3 (researcher-aware)
# ---------------------------------------------------------------------------
def _researcher_deep_mechanism(subject: str, keywords: list) -> FollowUpQuestion:
    extra = ""
    if keywords:
        # Pick the strongest signal keyword
        head = keywords[0]
        extra = f"（结合{head}相关指标）"
    return make_followup(
        question=(
            f"在{subject}过程中，如何结合传质系数、自由基产率与动力学常数"
            f"系统解释其强化机制{extra}？"
        ),
        category=CATEGORY_EXPLANATION,
        intent="deepen_mechanism",
        reason="研究用户需要机制层级的深度解释",
        confidence=0.85,
        priority=0.85,
        metadata={"generator": "personalized", "dimension": "mechanism"},
    )


def _researcher_experiment_design(subject: str) -> FollowUpQuestion:
    return make_followup(
        question=(
            f"如何设计一组DOE实验，定量评估{subject}的关键影响因素，"
            f"并通过方差分析给出最优工艺窗口？"
        ),
        category=CATEGORY_NEXT_ACTION,
        intent="design_experiment",
        reason="研究用户需要可量化的实验路径",
        confidence=0.8,
        priority=0.8,
        metadata={"generator": "personalized", "dimension": "experiment"},
    )


def _researcher_literature(subject: str) -> FollowUpQuestion:
    return make_followup(
        question=(
            f"近5年与{subject}相关的CEJ/JHM/WR等顶刊研究路线如何演化，"
            f"下一步值得切入的研究空白是什么？"
        ),
        category=CATEGORY_KNOWLEDGE_GAP,
        intent="literature_review",
        reason="研究用户需要文献脉络与空白识别",
        confidence=0.78,
        priority=0.78,
        metadata={"generator": "personalized", "dimension": "literature"},
    )


def _researcher_engineering(subject: str) -> FollowUpQuestion:
    return make_followup(
        question=(
            f"将{subject}从实验室放大到工程级，需突破哪些传质/反应器设计"
            f"瓶颈，量化放大效应？"
        ),
        category=CATEGORY_NEXT_ACTION,
        intent="engineering_design",
        reason="研究用户关注落地路径",
        confidence=0.72,
        priority=0.72,
        metadata={"generator": "personalized", "dimension": "engineering"},
    )


def _practitioner_practical(subject: str) -> FollowUpQuestion:
    return make_followup(
        question=(
            f"在{subject}实际工程应用中，工艺参数、设备选型与运行成本"
            f"如何平衡？"
        ),
        category=CATEGORY_NEXT_ACTION,
        intent="practical_application",
        reason="实践者关注可落地的工艺与成本",
        confidence=0.7,
        priority=0.7,
        metadata={"generator": "personalized", "level": "practitioner"},
    )


def _general_basics(subject: str) -> FollowUpQuestion:
    return make_followup(
        question=f"{subject}的核心原理是什么，与传统方法相比有哪些优势？",
        category=CATEGORY_DETAIL,
        intent="understand_basics",
        reason="普通用户需要先建立基本认知",
        confidence=0.7,
        priority=0.7,
        metadata={"generator": "personalized", "level": "general"},
    )


def _build_candidates(ctx: FollowUpContext) -> List[FollowUpQuestion]:
    subject = _safe_subject(getattr(ctx, "current_question", ""))
    profile = getattr(ctx, "user_profile", None)
    expertise = getattr(ctx, "user_expertise_level", "general") or "general"
    keywords = list(getattr(profile, "keywords", []) or []) if profile else []
    candidates: List[FollowUpQuestion] = []

    if expertise == "researcher":
        candidates.append(_researcher_deep_mechanism(subject, keywords))
        candidates.append(_researcher_experiment_design(subject))
        candidates.append(_researcher_literature(subject))
        candidates.append(_researcher_engineering(subject))
    elif expertise == "practitioner":
        candidates.append(_researcher_deep_mechanism(subject, keywords))
        candidates.append(_practitioner_practical(subject))
        candidates.append(_researcher_literature(subject))
    else:
        candidates.append(_general_basics(subject))
        # Bridge: even a general user benefits from understanding mechanism
        candidates.append(_researcher_deep_mechanism(subject, keywords))
    return candidates


def _dedupe_and_pad(
    candidates: List[FollowUpQuestion],
    ctx: FollowUpContext,
    max_questions: int,
) -> List[FollowUpQuestion]:
    seen_cat: set = set()
    out: List[FollowUpQuestion] = []
    for c in candidates:
        if c.category in seen_cat:
            continue
        if _is_generic(c.question):
            continue
        out.append(c)
        seen_cat.add(c.category)
    while len(out) < max_questions:
        # Pad with researcher_deep_mechanism (always safe)
        padded = _researcher_deep_mechanism(
            _safe_subject(getattr(ctx, "current_question", "")),
            list(getattr(ctx.user_profile, "keywords", []) or [])
            if getattr(ctx, "user_profile", None)
            else [],
        )
        out.append(padded)
        break
    return out[:max_questions] if max_questions > 0 else out


def rank_personalized(
    candidates: List[FollowUpQuestion],
    ctx: FollowUpContext,
    *,
    expected_intent: str = "",
    top_k: Optional[int] = None,
) -> List[FollowUpQuestion]:
    """Phase 14.2 §3: rank personalized follow-ups using the 5-axis formula."""
    if not candidates:
        return []
    if top_k == 0:
        return []
    seen: List[str] = []
    scored: List[tuple] = []
    for fq in candidates:
        s = _score(fq, ctx, expected_intent, seen)
        if fq.metadata is None:
            fq.metadata = {}
        else:
            fq.metadata = dict(fq.metadata)
        components = {
            "intent_match": round(_intent_match(fq, expected_intent), 4),
            "knowledge_gap": round(_knowledge_gap(fq), 4),
            "user_relevance": round(
                _user_relevance(
                    fq,
                    getattr(ctx, "user_profile", None),
                    getattr(ctx, "user_expertise_level", "general") or "general",
                ),
                4,
            ),
            "research_value": round(
                _research_value(fq, getattr(ctx, "user_profile", None)),
                4,
            ),
            "novelty": round(_novelty(fq, seen), 4),
            "score": s,
        }
        fq.metadata["score"] = s
        fq.metadata["score_components"] = components
        scored.append((s, fq))
        seen.append(fq.question or "")
    scored.sort(key=lambda item: (-item[0],))
    ordered = [item[1] for item in scored]
    return ordered if top_k is None else ordered[: max(0, int(top_k))]


def generate_personalized_followups(
    ctx,
    *,
    max_questions: int = 3,
    expected_intent: str = "",
) -> List[FollowUpQuestion]:
    """Phase 14.2 §3: end-to-end personalized follow-up generator.

    Args:
        ctx: a ``FollowUpContext`` (or duck-typed equivalent).
        max_questions: cap (default 3).
        expected_intent: optional intent string for ``intent_match``.

    Returns:
        Ranked, deduplicated list of ``FollowUpQuestion`` — never empty.
    """
    candidates = _build_candidates(ctx)
    candidates = _dedupe_and_pad(candidates, ctx, max(max_questions, 1))
    ranked = rank_personalized(
        candidates, ctx, expected_intent=expected_intent
    )
    if not ranked:
        ranked = [_researcher_deep_mechanism(
            _safe_subject(getattr(ctx, "current_question", "")),
            [],
        )]
    return ranked


__all__ = [
    "generate_personalized_followups",
    "rank_personalized",
    "W_INTENT_MATCH",
    "W_KNOWLEDGE_GAP",
    "W_USER_RELEVANCE",
    "W_RESEARCH_VALUE",
    "W_NOVELTY",
]
