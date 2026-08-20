"""Research Answer Strategy — Phase 14.3 §3.

Given a classified intent, return an ``AnswerStrategy`` describing how to
structure the answer: sections, required elements, depth, formula /
experiment / citation flags.

Public API:
- AnswerStrategy (dataclass)
- get_strategy(intent) -> AnswerStrategy
- STRATEGY_REGISTRY (mapping intent → strategy)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

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
)


@dataclass
class AnswerStrategy:
    """Phase 14.3 §3: per-intent answer scaffolding."""

    intent: str
    label: str
    sections: List[str] = field(default_factory=list)
    required_elements: List[str] = field(default_factory=list)
    depth: str = "intermediate"  # surface | intermediate | deep
    formula_required: bool = False
    experiment_required: bool = False
    citation_required: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "label": self.label,
            "sections": list(self.sections),
            "required_elements": list(self.required_elements),
            "depth": self.depth,
            "formula_required": self.formula_required,
            "experiment_required": self.experiment_required,
            "citation_required": self.citation_required,
        }


# ---------------------------------------------------------------------------
# Per-intent strategies — Phase 14.3 §3
# ---------------------------------------------------------------------------
def _strategy_mechanism() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_MECHANISM_ANALYSIS,
        label="机理分析",
        sections=[
            "核心机制",
            "作用路径",
            "数学/物理模型",
            "关键变量",
            "实验验证方法",
            "当前研究空白",
        ],
        required_elements=[
            "mechanism chain",
            "quantitative variables",
            "research gaps",
        ],
        depth="deep",
        formula_required=True,
        experiment_required=True,
        citation_required=True,
    )


def _strategy_experiment_design() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_EXPERIMENT_DESIGN,
        label="实验设计",
        sections=[
            "科学问题",
            "假设",
            "自变量",
            "因变量",
            "控制变量",
            "测试方法",
            "数据分析",
        ],
        required_elements=[
            "DOE structure",
            "control variables",
            "data analysis plan",
        ],
        depth="intermediate",
        formula_required=False,
        experiment_required=True,
        citation_required=False,
    )


def _strategy_literature_review() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_LITERATURE_REVIEW,
        label="文献综述",
        sections=[
            "Research history",
            "Current frontier",
            "Representative papers",
            "Research gaps",
            "Future directions",
        ],
        required_elements=[
            "timeline",
            "research hot-spots",
            "representative citations",
        ],
        depth="intermediate",
        citation_required=True,
    )


def _strategy_engineering_design() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_ENGINEERING_DESIGN,
        label="工程设计",
        sections=[
            "System architecture",
            "Key components",
            "Parameters",
            "Scaling issues",
            "Engineering constraints",
        ],
        required_elements=[
            "process flow",
            "dimensioning",
            "scale-up economics",
        ],
        depth="intermediate",
        formula_required=True,
        experiment_required=False,
        citation_required=False,
    )


def _strategy_paper_writing() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_PAPER_WRITING,
        label="论文写作",
        sections=[
            "Innovation points",
            "Literature positioning",
            "Method advantages",
            "Figure/table suggestions",
            "Submission strategy",
        ],
        required_elements=[
            "novelty statement",
            "comparison table",
            "submission strategy",
        ],
        depth="intermediate",
        citation_required=True,
    )


def _strategy_concept_explanation() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_CONCEPT_EXPLANATION,
        label="基础概念解释",
        sections=["定义", "核心原理", "应用场景", "下一步"],
        required_elements=["definition", "simple example"],
        depth="surface",
        formula_required=False,
        experiment_required=False,
        citation_required=False,
    )


def _strategy_method_comparison() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_METHOD_COMPARISON,
        label="方法对比",
        sections=[
            "对比维度",
            "Method A",
            "Method B",
            "优势劣势",
            "推荐场景",
        ],
        required_elements=[
            "comparison table",
            "scenario recommendation",
        ],
        depth="intermediate",
        citation_required=True,
    )


def _strategy_data_analysis() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_DATA_ANALYSIS,
        label="数据分析",
        sections=[
            "Data summary",
            "Statistical methods",
            "Visualization",
            "Findings",
            "Caveats",
        ],
        required_elements=[
            "summary stats",
            "visualization",
            "uncertainty",
        ],
        depth="deep",
        formula_required=True,
        citation_required=False,
    )


def _strategy_research_planning() -> AnswerStrategy:
    return AnswerStrategy(
        intent=INTENT_RESEARCH_PLANNING,
        label="研究规划",
        sections=[
            "Goals",
            "Milestones",
            "Required resources",
            "Risk analysis",
            "Timeline",
        ],
        required_elements=[
            "milestones",
            "deliverables",
            "contingency plan",
        ],
        depth="intermediate",
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
STRATEGY_REGISTRY: Dict[str, AnswerStrategy] = {
    INTENT_MECHANISM_ANALYSIS: _strategy_mechanism(),
    INTENT_EXPERIMENT_DESIGN: _strategy_experiment_design(),
    INTENT_LITERATURE_REVIEW: _strategy_literature_review(),
    INTENT_ENGINEERING_DESIGN: _strategy_engineering_design(),
    INTENT_PAPER_WRITING: _strategy_paper_writing(),
    INTENT_CONCEPT_EXPLANATION: _strategy_concept_explanation(),
    INTENT_METHOD_COMPARISON: _strategy_method_comparison(),
    INTENT_DATA_ANALYSIS: _strategy_data_analysis(),
    INTENT_RESEARCH_PLANNING: _strategy_research_planning(),
}


def get_strategy(intent: str) -> AnswerStrategy:
    """Phase 14.3 §3: return the strategy for an intent.

    Falls back to a shallow concept-explanation strategy when the intent is
    unknown so callers never crash.
    """
    if intent in STRATEGY_REGISTRY:
        return STRATEGY_REGISTRY[intent]
    return STRATEGY_REGISTRY[INTENT_CONCEPT_EXPLANATION]


__all__ = [
    "AnswerStrategy",
    "STRATEGY_REGISTRY",
    "get_strategy",
]
