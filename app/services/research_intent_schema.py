"""Research Intent Schema — Phase 14.3 §1.

Canonical taxonomy + classification dataclass for the research intent
intelligence layer. Additive — does not modify any Phase 8-14 module.

Public API:
- ResearchIntent (string enum, 9 canonical categories)
- IntentClassification (dataclass)
- DEFAULT_INTENTS tuple + INTENT_DESCRIPTIONS dict
- RESEARCH_LEVEL_BEGINNER / STUDENT / RESEARCHER / EXPERT constants
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Intent enum constants — Phase 14.3 §1
# ---------------------------------------------------------------------------
INTENT_CONCEPT_EXPLANATION = "concept_explanation"
INTENT_MECHANISM_ANALYSIS = "mechanism_analysis"
INTENT_EXPERIMENT_DESIGN = "experiment_design"
INTENT_LITERATURE_REVIEW = "literature_review"
INTENT_DATA_ANALYSIS = "data_analysis"
INTENT_ENGINEERING_DESIGN = "engineering_design"
INTENT_PAPER_WRITING = "paper_writing"
INTENT_METHOD_COMPARISON = "method_comparison"
INTENT_RESEARCH_PLANNING = "research_planning"

DEFAULT_INTENTS: tuple = (
    INTENT_CONCEPT_EXPLANATION,
    INTENT_MECHANISM_ANALYSIS,
    INTENT_EXPERIMENT_DESIGN,
    INTENT_LITERATURE_REVIEW,
    INTENT_DATA_ANALYSIS,
    INTENT_ENGINEERING_DESIGN,
    INTENT_PAPER_WRITING,
    INTENT_METHOD_COMPARISON,
    INTENT_RESEARCH_PLANNING,
)

INTENT_DESCRIPTIONS: dict = {
    INTENT_CONCEPT_EXPLANATION: "基础概念解释",
    INTENT_MECHANISM_ANALYSIS: "机理分析",
    INTENT_EXPERIMENT_DESIGN: "实验设计",
    INTENT_LITERATURE_REVIEW: "文献综述",
    INTENT_DATA_ANALYSIS: "数据分析",
    INTENT_ENGINEERING_DESIGN: "工程设计",
    INTENT_PAPER_WRITING: "论文写作",
    INTENT_METHOD_COMPARISON: "方法对比",
    INTENT_RESEARCH_PLANNING: "研究规划",
}

# Default research-level taxonomy
RESEARCH_LEVEL_BEGINNER = "beginner"
RESEARCH_LEVEL_STUDENT = "student"
RESEARCH_LEVEL_RESEARCHER = "researcher"
RESEARCH_LEVEL_EXPERT = "expert"

DEFAULT_RESEARCH_LEVELS: tuple = (
    RESEARCH_LEVEL_BEGINNER,
    RESEARCH_LEVEL_STUDENT,
    RESEARCH_LEVEL_RESEARCHER,
    RESEARCH_LEVEL_EXPERT,
)


@dataclass
class IntentClassification:
    """Phase 14.3 §1: structured result of intent classification."""

    intent: str = INTENT_CONCEPT_EXPLANATION
    confidence: float = 0.5
    research_level: str = RESEARCH_LEVEL_RESEARCHER
    domain: str = ""
    reasoning: str = ""
    expected_output_style: str = "structured"
    matched_keywords: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.intent not in DEFAULT_INTENTS:
            self.intent = INTENT_CONCEPT_EXPLANATION
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        if self.research_level not in DEFAULT_RESEARCH_LEVELS:
            self.research_level = RESEARCH_LEVEL_RESEARCHER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "intent_label": INTENT_DESCRIPTIONS.get(self.intent, self.intent),
            "confidence": self.confidence,
            "research_level": self.research_level,
            "domain": self.domain,
            "reasoning": self.reasoning,
            "expected_output_style": self.expected_output_style,
            "matched_keywords": list(self.matched_keywords),
            "metadata": dict(self.metadata),
        }


def make_intent_classification(
    intent: str = INTENT_CONCEPT_EXPLANATION,
    *,
    confidence: float = 0.5,
    research_level: str = RESEARCH_LEVEL_RESEARCHER,
    domain: str = "",
    reasoning: str = "",
    expected_output_style: str = "structured",
    matched_keywords: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> IntentClassification:
    """Phase 14.3 §1: factory helper used by the classifier + tests."""
    return IntentClassification(
        intent=intent,
        confidence=confidence,
        research_level=research_level,
        domain=domain,
        reasoning=reasoning,
        expected_output_style=expected_output_style,
        matched_keywords=list(matched_keywords or []),
        metadata=dict(metadata or {}),
    )


__all__ = [
    "DEFAULT_INTENTS",
    "INTENT_DESCRIPTIONS",
    "ResearchIntent" if False else "INTENT_MECHANISM_ANALYSIS",
    "INTENT_CONCEPT_EXPLANATION",
    "INTENT_MECHANISM_ANALYSIS",
    "INTENT_EXPERIMENT_DESIGN",
    "INTENT_LITERATURE_REVIEW",
    "INTENT_DATA_ANALYSIS",
    "INTENT_ENGINEERING_DESIGN",
    "INTENT_PAPER_WRITING",
    "INTENT_METHOD_COMPARISON",
    "INTENT_RESEARCH_PLANNING",
    "DEFAULT_RESEARCH_LEVELS",
    "RESEARCH_LEVEL_BEGINNER",
    "RESEARCH_LEVEL_STUDENT",
    "RESEARCH_LEVEL_RESEARCHER",
    "RESEARCH_LEVEL_EXPERT",
    "IntentClassification",
    "make_intent_classification",
]


# Backwards-compat alias for tests/imports referencing the spec name.
class _ResearchIntent:
    """Phase 14.3 §1: alias so imports ``ResearchIntent.MECHANISM_ANALYSIS`` work."""

    CONCEPT_EXPLANATION = INTENT_CONCEPT_EXPLANATION
    MECHANISM_ANALYSIS = INTENT_MECHANISM_ANALYSIS
    EXPERIMENT_DESIGN = INTENT_EXPERIMENT_DESIGN
    LITERATURE_REVIEW = INTENT_LITERATURE_REVIEW
    DATA_ANALYSIS = INTENT_DATA_ANALYSIS
    ENGINEERING_DESIGN = INTENT_ENGINEERING_DESIGN
    PAPER_WRITING = INTENT_PAPER_WRITING
    METHOD_COMPARISON = INTENT_METHOD_COMPARISON
    RESEARCH_PLANNING = INTENT_RESEARCH_PLANNING

    def __getitem__(self, key: str) -> str:
        return {
            "CONCEPT_EXPLANATION": INTENT_CONCEPT_EXPLANATION,
            "MECHANISM_ANALYSIS": INTENT_MECHANISM_ANALYSIS,
            "EXPERIMENT_DESIGN": INTENT_EXPERIMENT_DESIGN,
            "LITERATURE_REVIEW": INTENT_LITERATURE_REVIEW,
            "DATA_ANALYSIS": INTENT_DATA_ANALYSIS,
            "ENGINEERING_DESIGN": INTENT_ENGINEERING_DESIGN,
            "PAPER_WRITING": INTENT_PAPER_WRITING,
            "METHOD_COMPARISON": INTENT_METHOD_COMPARISON,
            "RESEARCH_PLANNING": INTENT_RESEARCH_PLANNING,
        }.get(key, key)


ResearchIntent = _ResearchIntent()
