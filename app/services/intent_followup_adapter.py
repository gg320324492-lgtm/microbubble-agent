"""Intent-Aware Follow-up Adapter — Phase 14.3 §5.

Generates high-value, intent-specific follow-up questions. Reuses
``FollowUpQuestion`` from Phase 14.1 (no schema changes), but routes
generation through intent-specific templates so a ``MECHANISM_ANALYSIS``
query never produces a generic "了解更多" reply.

Forbidden phrases (per spec §5):
- "了解更多"
- "想深入了解"
- "它主要是什么"
- "它有什么作用"
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

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

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Forbidden phrases — Phase 14.3 §5
# ---------------------------------------------------------------------------
FORBIDDEN_PHRASES: tuple = (
    "了解更多",
    "想深入了解",
    "它主要是什么",
    "它有什么作用",
    "do you want",
    "want to know more",
    "想不想了解更多",
)


def _is_forbidden(text: str) -> bool:
    low = (text or "").lower()
    return any(p.lower() in low for p in FORBIDDEN_PHRASES)


def _safe_subject(text: str) -> str:
    if not text:
        return "当前研究"
    cleaned = (text or "").strip()
    return cleaned if len(cleaned) <= 80 else cleaned[:77] + "..."


# ---------------------------------------------------------------------------
# Per-intent templates — Phase 14.3 §5
# ---------------------------------------------------------------------------
def _mechanism_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=(
                f"微纳米气泡如何通过提高臭氧传质系数(kLa)增强{subject}效率？"
            ),
            category=CATEGORY_EXPLANATION,
            intent="mechanism_kla_oh",
            reason="m+kLa + ·OH 链是机理分析的下一步",
            confidence=0.9,
            priority=0.9,
            metadata={"generator": "intent_aware", "dimension": "mechanism_chain"},
        ),
        make_followup(
            question=(
                f"如何建立O3传质、·OH生成以及{subject}动力学之间的机制链？"
            ),
            category=CATEGORY_EXPLANATION,
            intent="mechanism_chain",
            reason="机制链分析是 MECHANISM_ANALYSIS 的核心",
            confidence=0.88,
            priority=0.88,
            metadata={"generator": "intent_aware", "dimension": "chain"},
        ),
        make_followup(
            question=(
                f"当前{subject}体系中最大的机制研究空白是什么？"
            ),
            category=CATEGORY_KNOWLEDGE_GAP,
            intent="research_gap",
            reason="识别研究空白是研究者的下一步",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "gap"},
        ),
    ]


def _experiment_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"针对{subject}的实验变量设计应包含哪些关键自变量与控制变量？",
            category=CATEGORY_NEXT_ACTION,
            intent="experimental_design_variables",
            reason="实验变量设计是 EXPERIMENT_DESIGN 的关键",
            confidence=0.9,
            priority=0.9,
            metadata={"generator": "intent_aware", "dimension": "experiment"},
        ),
        make_followup(
            question=f"{subject}的反应动力学测试方法应包括哪些测试集？",
            category=CATEGORY_NEXT_ACTION,
            intent="kinetic_testing_plan",
            reason="动力学测试覆盖准一级反应速率常数与活化能",
            confidence=0.88,
            priority=0.88,
            metadata={"generator": "intent_aware", "dimension": "kinetics"},
        ),
        make_followup(
            question=f"如何设计自由基验证方案以证实{subject}中的关键路径？",
            category=CATEGORY_NEXT_ACTION,
            intent="free_radical_verification",
            reason="自由基验证（捕获实验+ESR）支撑机理链",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "validation"},
        ),
    ]


def _literature_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"{subject}近五年的核心文献路线如何演化？",
            category=CATEGORY_KNOWLEDGE_GAP,
            intent="literature_route",
            reason="梳理演化路径是 LITERATURE_REVIEW 的第一步",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "route"},
        ),
        make_followup(
            question=f"{subject}当前的研究热点集中在哪些应用方向？",
            category=CATEGORY_DETAIL,
            intent="research_hotspot",
            reason="热点识别帮助定位可发力的子领域",
            confidence=0.82,
            priority=0.82,
            metadata={"generator": "intent_aware", "dimension": "hotspot"},
        ),
        make_followup(
            question=f"{subject}领域下一步值得突破的研究方向是什么？",
            category=CATEGORY_KNOWLEDGE_GAP,
            intent="future_direction",
            reason="未来方向是综述的收尾必备",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "future"},
        ),
    ]


def _concept_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"{subject}的定义与核心工作原理是什么？",
            category=CATEGORY_EXPLANATION,
            intent="definition",
            reason="基础概念解释需要先建立定义",
            confidence=0.78,
            priority=0.78,
            metadata={"generator": "intent_aware", "dimension": "definition"},
        ),
        make_followup(
            question=f"{subject}的主要应用场景有哪些？分别处于什么研究阶段？",
            category=CATEGORY_DETAIL,
            intent="applications",
            reason="应用场景是基础概念的下一步",
            confidence=0.75,
            priority=0.75,
            metadata={"generator": "intent_aware", "dimension": "applications"},
        ),
    ]


def _engineering_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"将{subject}从实验室放大到工业级，需突破哪些关键工程瓶颈？",
            category=CATEGORY_NEXT_ACTION,
            intent="scale_up_bottleneck",
            reason="工程设计关注 scale-up",
            confidence=0.88,
            priority=0.88,
            metadata={"generator": "intent_aware", "dimension": "scale"},
        ),
        make_followup(
            question=f"针对{subject}的系统架构应包含哪些核心组件？",
            category=CATEGORY_DETAIL,
            intent="system_architecture",
            reason="工程设计需先明确系统架构",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "system"},
        ),
    ]


def _paper_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"{subject}相关的潜在创新点可以从哪些维度切入？",
            category=CATEGORY_KNOWLEDGE_GAP,
            intent="innovation_dimensions",
            reason="论文写作需要先识别创新维度",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "novelty"},
        ),
        make_followup(
            question=f"{subject}的文献定位应如何阐述与对比？",
            category=CATEGORY_COMPARISON,
            intent="literature_positioning",
            reason="文献定位是投稿策略的前置",
            confidence=0.82,
            priority=0.82,
            metadata={"generator": "intent_aware", "dimension": "positioning"},
        ),
    ]


def _comparison_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"{subject}与传统/替代工艺在效率、能耗上的差异如何量化？",
            category=CATEGORY_COMPARISON,
            intent="quantitative_comparison",
            reason="方法对比需要量化指标",
            confidence=0.85,
            priority=0.85,
            metadata={"generator": "intent_aware", "dimension": "compare"},
        ),
        make_followup(
            question=f"{subject}在不同水质/工况下的适用性边界如何？",
            category=CATEGORY_DETAIL,
            intent="applicability_boundary",
            reason="适用边界是 METHOD_COMPARISON 的延伸",
            confidence=0.8,
            priority=0.8,
            metadata={"generator": "intent_aware", "dimension": "boundary"},
        ),
    ]


def _data_analysis_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"针对{subject}的数据应使用哪些统计方法进行差异性检验？",
            category=CATEGORY_DETAIL,
            intent="statistical_methods",
            reason="数据分析需要匹配的统计工具",
            confidence=0.82,
            priority=0.82,
            metadata={"generator": "intent_aware", "dimension": "stats"},
        ),
        make_followup(
            question=f"{subject}的可视化方案应包含哪些关键图(回归/箱线/相关性热图)？",
            category=CATEGORY_DETAIL,
            intent="visualization_plan",
            reason="可视化是数据驱动研究的展现",
            confidence=0.8,
            priority=0.8,
            metadata={"generator": "intent_aware", "dimension": "viz"},
        ),
    ]


def _planning_questions(subject: str) -> List[FollowUpQuestion]:
    return [
        make_followup(
            question=f"针对{subject}的研究里程碑应如何切分（季度/年度）？",
            category=CATEGORY_NEXT_ACTION,
            intent="milestone_breakdown",
            reason="研究规划需先切分里程碑",
            confidence=0.82,
            priority=0.82,
            metadata={"generator": "intent_aware", "dimension": "milestones"},
        ),
        make_followup(
            question=f"{subject}的研究路径上的关键风险与缓解策略是什么？",
            category=CATEGORY_KNOWLEDGE_GAP,
            intent="risk_analysis",
            reason="研究规划必须识别风险",
            confidence=0.8,
            priority=0.8,
            metadata={"generator": "intent_aware", "dimension": "risk"},
        ),
    ]


_PER_INTENT_TEMPLATES: Dict[str, Any] = {
    INTENT_MECHANISM_ANALYSIS: _mechanism_questions,
    INTENT_EXPERIMENT_DESIGN: _experiment_questions,
    INTENT_LITERATURE_REVIEW: _literature_questions,
    INTENT_CONCEPT_EXPLANATION: _concept_questions,
    INTENT_ENGINEERING_DESIGN: _engineering_questions,
    INTENT_PAPER_WRITING: _paper_questions,
    INTENT_METHOD_COMPARISON: _comparison_questions,
    INTENT_DATA_ANALYSIS: _data_analysis_questions,
    INTENT_RESEARCH_PLANNING: _planning_questions,
}


def _build_for_intent(intent: str, subject: str) -> List[FollowUpQuestion]:
    fn = _PER_INTENT_TEMPLATES.get(intent)
    if fn is None:
        return _mechanism_questions(subject)  # safe fallback
    return fn(subject)


def _filter_forbidden(questions: List[FollowUpQuestion]) -> List[FollowUpQuestion]:
    return [q for q in questions if q.question and not _is_forbidden(q.question)]


# ---------------------------------------------------------------------------
# Public API — Phase 14.3 §5
# ---------------------------------------------------------------------------
def generate_intent_followups(
    user_prompt: str,
    *,
    intent: str,
    max_questions: int = 3,
) -> List[FollowUpQuestion]:
    """Phase 14.3 §5: render intent-aware follow-ups.

    Args:
        user_prompt: original question (used only for subject).
        intent: classified intent (one of ``DEFAULT_INTENTS``).
        max_questions: cap (default 3).

    Returns:
        Non-empty list of ``FollowUpQuestion``. Forbidden phrases are
        filtered out and, if the resulting list would be empty, the
        function falls back to a researcher-grade mechanism question.
    """
    subject = _safe_subject(user_prompt or "")
    candidates = _build_for_intent(intent, subject)
    candidates = _filter_forbidden(candidates)
    if not candidates:
        # Last-resort safe fallback (researcher-grade mechanism question).
        candidates = _mechanism_questions(subject)
        candidates = _filter_forbidden(candidates)
        if not candidates:
            # Last-resort Q&D.
            candidates = [
                make_followup(
                    question=(
                        f"如何系统拆解{subject}的关键科学问题与变量？"
                    ),
                    category=CATEGORY_DETAIL,
                    intent="fallback_plan",
                    reason="fallback for empty forbidden filter",
                    confidence=0.6,
                    priority=0.6,
                    metadata={"generator": "intent_aware_fallback"},
                ),
            ]
    return candidates[:max_questions] if max_questions > 0 else candidates


__all__ = [
    "FORBIDDEN_PHRASES",
    "generate_intent_followups",
    "_safe_subject",
]
