"""Research Quality Evaluator — Phase 15.0 §6.

Per-answer quality scorer. Five metrics mapped 0..1:
1. intent_score        — alignment with the classified intent strategy
2. depth_score         — scientific depth (equations / mechanism etc.)
3. evidence_score      — citation / evidence support
4. completeness_score — required-elements coverage
5. overall_score       — weighted aggregate
Plus ``missing_elements`` + ``suggestions``.

Public API:
- ResearchQualityScore (dataclass)
- ResearchQualityEvaluator.evaluate_answer(...)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Weights — Phase 15.0 §6
# ---------------------------------------------------------------------------
W_INTENT = 0.30
W_DEPTH = 0.25
W_EVIDENCE = 0.20
W_COMPLETENESS = 0.25


@dataclass
class ResearchQualityScore:
    """Phase 15.0 §6: per-answer quality summary."""

    intent_score: float = 0.5
    depth_score: float = 0.5
    evidence_score: float = 0.5
    completeness_score: float = 0.5
    overall_score: float = 0.5
    missing_elements: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    metrics_breakdown: Dict[str, float] = field(default_factory=dict)
    intent: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent_score": round(self.intent_score, 4),
            "depth_score": round(self.depth_score, 4),
            "evidence_score": round(self.evidence_score, 4),
            "completeness_score": round(self.completeness_score, 4),
            "overall_score": round(self.overall_score, 4),
            "missing_elements": list(self.missing_elements),
            "suggestions": list(self.suggestions),
            "metrics_breakdown": {
                k: round(v, 4) for k, v in self.metrics_breakdown.items()
            },
            "intent": self.intent,
        }


# ---------------------------------------------------------------------------
# Per-intent required elements (subset of Phase 14.3 strategy)
# ---------------------------------------------------------------------------
_INTENT_REQUIRED: Dict[str, List[str]] = {
    "mechanism_analysis": [
        "mechanism chain",
        "quantitative variables",
        "research gaps",
    ],
    "experiment_design": [
        "DOE structure",
        "control variables",
        "data analysis plan",
    ],
    "literature_review": [
        "timeline",
        "research hot-spots",
        "representative citations",
    ],
    "engineering_design": [
        "process flow",
        "dimensioning",
        "scale-up economics",
    ],
    "paper_writing": [
        "novelty statement",
        "comparison table",
        "submission strategy",
    ],
    "concept_explanation": [
        "definition",
        "定义",
        "simple example",
        "例子",
        "解释",
    ],
    "method_comparison": [
        "comparison table",
        "scenario recommendation",
    ],
    "data_analysis": [
        "summary stats",
        "visualization",
        "uncertainty",
    ],
    "research_planning": [
        "milestones",
        "deliverables",
        "contingency plan",
    ],
}


# ---------------------------------------------------------------------------
# Score helpers
# ---------------------------------------------------------------------------
def _kw_score(text: str, keywords: Iterable[str]) -> Tuple[float, List[str]]:
    """Fraction of keywords present in text. Returns (score 0..1, missing).

    Match rule (lenient): a required element X is considered present if
    EVERY token in X appears somewhere in the text (token containment,
    not strict substring). Tokens are split on non-alphanumeric chars
    so this handles both English ("quantitative variables" → 2 tokens)
    AND Chinese (each Han char counts as its own token). This handles
    morphology (variables vs variable) without requiring exact phrasing.
    """
    if not keywords:
        return 1.0, []
    text_lower = (text or "").lower()
    # Split on whitespace + non-token chars. Use a per-codepoint split for
    # Chinese text: every Han char becomes its own token.
    text_tokens = set()
    for ch in text_lower:
        if ch.isalnum():
            text_tokens.add(ch)
    # Also add multi-char tokens for non-Chinese substrings
    for m in re.finditer(r"[a-z0-9_·]+", text_lower):
        text_tokens.add(m.group(0))

    present, missing = [], []
    keyword_list = list(keywords)
    for k in keyword_list:
        k_tokens = []
        for ch in str(k).lower():
            if ch.isalnum():
                k_tokens.append(ch)
        for m in re.finditer(r"[a-z0-9_·]+", str(k).lower()):
            k_tokens.append(m.group(0))
        if not k_tokens:
            continue
        if all(t in text_tokens for t in k_tokens):
            present.append(k)
        else:
            missing.append(k)
    if not keyword_list:
        return 1.0, []
    return len(present) / len(keyword_list), missing


def _depth_heuristics(text: str) -> float:
    """Phase 15.0 §6: depth heuristics (equations / mechanism / numerical)."""
    if not text:
        return 0.3
    score = 0.3
    if re.search(r"[A-Za-z]\d?\s*=", text):
        score += 0.15  # looks like equation
    if re.search(r"\b\d+\.?\d*\s*(mg|mol|kPa|kHz|nm|μm|%)\b", text):
        score += 0.15  # numerical data
    for needle in (
        "机理", "机制", "动力学", "kLa", "·OH", "mechanism",
        "kinetics", "model", "rate constant",
    ):
        if needle in text:
            score += 0.05
            if score >= 0.95:
                break
    return min(1.0, score)


def _evidence_heuristics(text: str, citations: Optional[List[str]]) -> float:
    """Phase 15.0 §6: evidence_score (0..1)."""
    if not text:
        return 0.2
    score = 0.2
    if citations:
        score += min(0.5, 0.10 * len(citations))
    if re.search(r"实验|验证|EPR|LC-MS|test|experiment|evidence", text):
        score += 0.2
    return min(1.0, score)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
class ResearchQualityEvaluator:
    """Phase 15.0 §6: quality evaluator (rule-based, no LLM)."""

    def evaluate_answer(
        self,
        answer: str,
        *,
        intent: str = "",
        citations: Optional[List[str]] = None,
    ) -> ResearchQualityScore:
        """Phase 15.0 §6: score an answer against the intent's strategy."""
        required = _INTENT_REQUIRED.get(intent, [])
        intent_score, missing = _kw_score(answer, required)
        depth = _depth_heuristics(answer)
        evidence = _evidence_heuristics(answer, citations)
        completeness = intent_score  # required-elements coverage proxy

        # If we have all required elements, intent/completeness → 1.0
        intent_boost = 0.0
        if required and not missing:
            intent_boost = 0.15

        intent_score = min(1.0, intent_score + intent_boost)
        completeness = intent_score  # mirror with boost

        overall = (
            W_INTENT * intent_score
            + W_DEPTH * depth
            + W_EVIDENCE * evidence
            + W_COMPLETENESS * completeness
        )

        suggestions: List[str] = []
        for m in missing:
            suggestions.append(f"补充关键元素: {m}")
        if depth < 0.5:
            suggestions.append("加入定量模型或方程以提升科学深度")
        if evidence < 0.5:
            suggestions.append("补充实验验证或文献引用以提升证据强度")

        return ResearchQualityScore(
            intent_score=intent_score,
            depth_score=depth,
            evidence_score=evidence,
            completeness_score=completeness,
            overall_score=overall,
            missing_elements=missing,
            suggestions=suggestions,
            metrics_breakdown={
                "intent": intent_score,
                "depth": depth,
                "evidence": evidence,
                "completeness": completeness,
            },
            intent=intent,
        )


__all__ = [
    "ResearchQualityScore",
    "ResearchQualityEvaluator",
    "W_INTENT",
    "W_DEPTH",
    "W_EVIDENCE",
    "W_COMPLETENESS",
]
