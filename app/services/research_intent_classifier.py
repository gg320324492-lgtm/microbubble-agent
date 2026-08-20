"""Research Intent Classifier — Phase 14.3 §2.

Hybrid classifier: rule + keyword + (optional) profile + memory context.

Pipeline:
1. Pre-compute per-intent keyword score from the user prompt.
2. Optional profile-aware boost (pollution_control + researcher skews
   MECHANISM_ANALYSIS, etc.).
3. Optional memory-context boost: if memory blobs reinforce an intent that
   is only loosely present in the prompt, raise its confidence.
4. Return the strongest intent + confidence + reasoning.

Pure rule-based — never calls an LLM.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.research_intent_schema import (
    DEFAULT_INTENTS,
    INTENT_CONCEPT_EXPLANATION,
    INTENT_DATA_ANALYSIS,
    INTENT_ENGINEERING_DESIGN,
    INTENT_EXPERIMENT_DESIGN,
    INTENT_LITERATURE_REVIEW,
    INTENT_MECHANISM_ANALYSIS,
    INTENT_METHOD_COMPARISON,
    INTENT_PAPER_WRITING,
    INTENT_RESEARCH_PLANNING,
    INTENT_DESCRIPTIONS,
    IntentClassification,
    RESEARCH_LEVEL_BEGINNER,
    RESEARCH_LEVEL_EXPERT,
    RESEARCH_LEVEL_RESEARCHER,
    RESEARCH_LEVEL_STUDENT,
    make_intent_classification,
)

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-intent keyword tables — Phase 14.3 §2
# ---------------------------------------------------------------------------
INTENT_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    INTENT_CONCEPT_EXPLANATION: (
        "什么是", "是什么", "简介", "介绍", "基础",
        "概念", "原理是什么", "what is", "intro", "overview",
    ),
    INTENT_MECHANISM_ANALYSIS: (
        "机制", "机理", "原理", "为什么", "原因",
        "路径", "机理", "模型", "mechanism", "pathway",
        "原因", "传质", "·OH", "自由基", "kLa",
        "反应动力学", "动力学", "氧化", "还原机理",
    ),
    INTENT_EXPERIMENT_DESIGN: (
        "实验设计", "方案", "如何验证", "怎么测",
        "变量", "参数优化", "DOE", "实验方案",
        "experimental design", "experimental setup",
        "测试方法", "实验装置",
    ),
    INTENT_LITERATURE_REVIEW: (
        "综述", "论文", "研究进展", "cej", "jhm",
        "wr", "近几年", "近五年", "literature",
        "review", "research progress", "overview of",
        "文献", "进展", "代表性",
    ),
    INTENT_DATA_ANALYSIS: (
        "数据分析", "分析数据", "拟合", "相关性",
        "data analysis", "plot", "chart", "统计",
        "显著性", "方差", "ANOVA", "regression",
        "kinetics fitting",
    ),
    INTENT_ENGINEERING_DESIGN: (
        "放大", "设备", "工程", "系统", "规模化",
        "产业化", "工艺设计", "反应器", "工程化",
        "scaling", "scale up", "pilot", "industrial",
        "工程应用", "产业化", "反应器",
    ),
    INTENT_PAPER_WRITING: (
        "创新点", "摘要", "投稿", "审稿",
        "回复意见", "paper", "manuscript",
        "manuscript", "submission", "abstract",
        "innovation", "novelty",
    ),
    INTENT_METHOD_COMPARISON: (
        "对比", "比较", "vs", "versus",
        "alternative", "differ", "相对", "advantages and disadvantages",
        "pros and cons", "compare",
    ),
    INTENT_RESEARCH_PLANNING: (
        "研究计划", "研究规划", "路线图",
        "下一步", "选题", "方向", "roadmap",
        "research plan", "research planning",
        "课题", "开题",
    ),
}


# Per-intent domain/profile boost configuration.
# When the profile domain matches, these scores add to the raw score.
DOMAIN_INTENT_BOOST: Dict[str, Dict[str, float]] = {
    "pollution_control_water_treatment": {
        INTENT_MECHANISM_ANALYSIS: 0.25,
        INTENT_EXPERIMENT_DESIGN: 0.18,
        INTENT_ENGINEERING_DESIGN: 0.18,
    },
    "advanced_oxidation_water_treatment": {
        INTENT_MECHANISM_ANALYSIS: 0.30,
        INTENT_EXPERIMENT_DESIGN: 0.20,
    },
    "computational_chemistry": {
        INTENT_MECHANISM_ANALYSIS: 0.20,
        INTENT_DATA_ANALYSIS: 0.30,
    },
    "membrane_separation": {
        INTENT_ENGINEERING_DESIGN: 0.20,
        INTENT_MECHANISM_ANALYSIS: 0.15,
    },
}

EXPERTISE_INTENT_BOOST: Dict[str, Dict[str, float]] = {
    RESEARCH_LEVEL_BEGINNER: {
        INTENT_CONCEPT_EXPLANATION: 0.30,
    },
    RESEARCH_LEVEL_STUDENT: {
        INTENT_CONCEPT_EXPLANATION: 0.10,
        INTENT_LITERATURE_REVIEW: 0.10,
    },
    RESEARCH_LEVEL_RESEARCHER: {
        INTENT_MECHANISM_ANALYSIS: 0.10,
        INTENT_EXPERIMENT_DESIGN: 0.10,
        INTENT_PAPER_WRITING: 0.10,
    },
    RESEARCH_LEVEL_EXPERT: {
        INTENT_MECHANISM_ANALYSIS: 0.15,
        INTENT_RESEARCH_PLANNING: 0.10,
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    return (text or "").strip().lower()


def _keyword_hits(text_lower: str, keywords: tuple) -> List[str]:
    """Return all keywords found in the lower-cased text, deduped."""
    out: List[str] = []
    seen = set()
    for kw in keywords:
        if kw.lower() in text_lower and kw not in seen:
            out.append(kw)
            seen.add(kw)
    return out


def _score_for_intent(
    prompt_lower: str,
    memory_blobs: Iterable[str],
    intent: str,
) -> Tuple[float, List[str]]:
    raw_score = 0.0
    matched: List[str] = []

    # Direct keyword match in the prompt
    direct_hits = _keyword_hits(prompt_lower, INTENT_KEYWORDS.get(intent, ()))
    if direct_hits:
        raw_score += min(1.0, 0.5 + 0.15 * len(direct_hits))
        matched.extend(direct_hits)

    # Memory-boost: if memory strongly contains keywords for an intent that
    # is weakly present in the prompt, bump it.
    if memory_blobs:
        mem_corpus = " ".join(memory_blobs).lower()
        mem_hits = _keyword_hits(mem_corpus, INTENT_KEYWORDS.get(intent, ()))
        if mem_hits and not direct_hits:
            # Memory hits alone: moderate signal
            raw_score += min(0.6, 0.20 + 0.10 * len(mem_hits))
            matched.extend([f"mem:{m}" for m in mem_hits])
        elif mem_hits and direct_hits:
            raw_score += min(0.4, 0.10 + 0.05 * len(mem_hits))
            matched.extend([f"mem:{m}" for m in mem_hits])

    return raw_score, matched


def _memory_blobs(memory_context) -> List[str]:
    """Phase 14.3 §2: extract text from a memory_context (list / dict / mixed)."""
    out: List[str] = []
    if not memory_context:
        return out
    items = (
        memory_context
        if isinstance(memory_context, (list, tuple))
        else [memory_context]
    )
    for item in items:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            for k in ("text", "content", "summary", "title", "snippet"):
                v = item.get(k)
                if v:
                    out.append(str(v))
                    break
        else:
            for attr in ("text", "content", "summary", "preview"):
                v = getattr(item, attr, None)
                if v:
                    out.append(str(v))
                    break
    return out


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class ResearchIntentClassifier:
    """Phase 14.3 §2: hybrid rule + keyword + profile + memory classifier."""

    def __init__(
        self,
        *,
        prefer_researcher_mechanism: bool = True,
    ) -> None:
        self.prefer_researcher_mechanism = prefer_researcher_mechanism

    def classify(
        self,
        user_prompt: str,
        *,
        profile: Optional[Any] = None,
        memory_context: Optional[Any] = None,
    ) -> IntentClassification:
        """Classify a research prompt.

        Args:
            user_prompt: original question string.
            profile: optional ``ResearchProfile``-like object with ``.domain``
                and ``.expertise_level`` attributes (Phase 14.2-compatible).
            memory_context: optional list of memory strings / dicts / objects.

        Returns:
            ``IntentClassification`` with the strongest intent.
        """
        prompt_lower = _normalize(user_prompt or "")
        mem_blobs = _memory_blobs(memory_context)

        scored: List[Tuple[str, float, List[str]]] = []
        for intent in DEFAULT_INTENTS:
            base_score, matched = _score_for_intent(prompt_lower, mem_blobs, intent)
            scored.append((intent, base_score, matched))

        # Profile boost (pollution_control + researcher → MECHANISM_ANALYSIS)
        profile_domain = ""
        profile_expertise = ""
        if profile is not None:
            profile_domain = getattr(profile, "domain", "") or ""
            profile_expertise = (
                getattr(profile, "expertise_level", "") or ""
            )

        # Apply domain boosts
        if profile_domain in DOMAIN_INTENT_BOOST:
            domain_boost = DOMAIN_INTENT_BOOST[profile_domain]
            for idx, (intent, score, matched) in enumerate(scored):
                if intent in domain_boost:
                    new_score = min(
                        1.0,
                        score + domain_boost[intent],
                    )
                    scored[idx] = (intent, new_score, matched)

        # Apply expertise boosts
        if profile_expertise in EXPERTISE_INTENT_BOOST:
            expert_boost = EXPERTISE_INTENT_BOOST[profile_expertise]
            for idx, (intent, score, matched) in enumerate(scored):
                if intent in expert_boost:
                    new_score = min(
                        1.0,
                        score + expert_boost[intent],
                    )
                    scored[idx] = (intent, new_score, matched)

        # Pick the highest. Stable tiebreak by canonical order.
        best_intent = INTENT_CONCEPT_EXPLANATION
        best_score = 0.0
        best_matched: List[str] = []
        for intent in DEFAULT_INTENTS:
            for (i, score, matched) in scored:
                if i == intent and score > best_score:
                    best_intent = intent
                    best_score = score
                    best_matched = matched
                    break
                if i == intent and score == best_score:
                    # Stable: prefer earlier in DEFAULT_INTENTS
                    pass

        # If no signal at all, fall back to concept explanation (most
        # conservative) and clamp confidence to 0.4 so downstream code can
        # detect "uncertain".
        if best_score == 0.0:
            best_intent = INTENT_CONCEPT_EXPLANATION
            confidence = 0.4
            reasoning = "no keyword/profile/memory signal; default to concept explanation"
        else:
            confidence = round(best_score, 4)
            if profile_domain and profile_expertise == RESEARCH_LEVEL_RESEARCHER:
                if best_intent == INTENT_MECHANISM_ANALYSIS:
                    confidence = max(confidence, 0.8)
            reasoning = (
                f"keyword signals={best_matched}; "
                f"profile=({profile_domain},{profile_expertise})"
            )

        # Map profile expertise → research_level
        research_level = profile_expertise or RESEARCH_LEVEL_RESEARCHER
        if research_level not in (
            RESEARCH_LEVEL_BEGINNER,
            RESEARCH_LEVEL_STUDENT,
            RESEARCH_LEVEL_RESEARCHER,
            RESEARCH_LEVEL_EXPERT,
        ):
            research_level = RESEARCH_LEVEL_RESEARCHER

        return make_intent_classification(
            intent=best_intent,
            confidence=confidence,
            research_level=research_level,
            domain=profile_domain,
            reasoning=reasoning,
            expected_output_style=_style_for_intent(best_intent),
            matched_keywords=best_matched,
        )


def _style_for_intent(intent: str) -> str:
    return {
        INTENT_CONCEPT_EXPLANATION: "narrative",
        INTENT_MECHANISM_ANALYSIS: "structured_with_equations",
        INTENT_EXPERIMENT_DESIGN: "structured_with_tables",
        INTENT_LITERATURE_REVIEW: "narrative_with_citations",
        INTENT_DATA_ANALYSIS: "data_driven",
        INTENT_ENGINEERING_DESIGN: "system_diagram",
        INTENT_PAPER_WRITING: "academic",
        INTENT_METHOD_COMPARISON: "table_comparison",
        INTENT_RESEARCH_PLANNING: "roadmap",
    }.get(intent, "structured")


def classify_intent(
    user_prompt: str,
    *,
    profile: Optional[Any] = None,
    memory_context: Optional[Any] = None,
    classifier: Optional[ResearchIntentClassifier] = None,
) -> IntentClassification:
    """Phase 14.3 §2: convenience wrapper. Uses module-level singleton by default."""
    cls = classifier or ResearchIntentClassifier()
    return cls.classify(
        user_prompt=user_prompt,
        profile=profile,
        memory_context=memory_context,
    )


__all__ = [
    "ResearchIntentClassifier",
    "classify_intent",
    "INTENT_KEYWORDS",
    "DOMAIN_INTENT_BOOST",
    "EXPERTISE_INTENT_BOOST",
]
