"""Research Action Recommender — Phase 14.2 §4.

Generates concrete next-step research actions, not just questions. Six
action types mapped to specific scientific verbs. Pure rule-based — no LLM.

Public API:
- ResearchAction (dataclass)
- ACTION_TYPES (the canonical 6 names)
- recommend_research_actions(ctx) -> List[ResearchAction]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Action type taxonomy — Phase 14.2 §4
# ---------------------------------------------------------------------------
ACTION_DEEPEN_MECHANISM = "deepen_mechanism"
ACTION_EXPAND_APPLICATION = "expand_application"
ACTION_COMPARE_METHODS = "compare_methods"
ACTION_VALIDATE_EXPERIMENT = "validate_experiment"
ACTION_LITERATURE_REVIEW = "literature_review"
ACTION_ENGINEERING_DESIGN = "engineering_design"

ACTION_TYPES: tuple = (
    ACTION_DEEPEN_MECHANISM,
    ACTION_EXPAND_APPLICATION,
    ACTION_COMPARE_METHODS,
    ACTION_VALIDATE_EXPERIMENT,
    ACTION_LITERATURE_REVIEW,
    ACTION_ENGINEERING_DESIGN,
)

_ACTION_LABELS: dict = {
    ACTION_DEEPEN_MECHANISM: "深入机理",
    ACTION_EXPAND_APPLICATION: "拓展应用",
    ACTION_COMPARE_METHODS: "方法对比",
    ACTION_VALIDATE_EXPERIMENT: "实验验证",
    ACTION_LITERATURE_REVIEW: "文献分析",
    ACTION_ENGINEERING_DESIGN: "工程设计",
}


@dataclass
class ResearchAction:
    """Phase 14.2 §4: a single next-step research action recommendation."""

    action_type: str
    description: str
    priority: float = 0.5
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.action_type not in ACTION_TYPES:
            # Fall back to deepen_mechanism rather than raising
            self.action_type = ACTION_DEEPEN_MECHANISM
        self.priority = max(0.0, min(1.0, float(self.priority)))

    @property
    def label(self) -> str:
        return _ACTION_LABELS.get(self.action_type, "深入机理")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "label": self.label,
            "description": self.description,
            "priority": self.priority,
            "reason": self.reason,
            "metadata": dict(self.metadata),
        }


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------
def _subject(ctx) -> str:
    """Phase 14.2 §4: pull a short, clean subject from the context."""
    q = (getattr(ctx, "current_question", "") or "").strip()
    if not q:
        return "当前研究主题"
    if len(q) <= 60:
        return q
    return q[:57] + "..."


def _domain_labels(domain: str) -> List[str]:
    """Phase 14.2 §4: domain-specific keyword hints for templates."""
    if domain == "pollution_control_water_treatment":
        return ["kLa", "·OH", "传质系数", "降解率", "污染物", "工艺放大", "臭氧"]
    if domain == "advanced_oxidation_water_treatment":
        return ["·OH 自由基", "臭氧传质", "高级氧化", "·O2-"]
    if domain == "computational_fluid_dynamics":
        return ["速度场", "湍流动能", "压力梯度", "网格"]
    if domain == "membrane_separation":
        return ["膜通量", "截留率", "污染层", "反冲"]
    if domain == "computational_chemistry":
        return ["B3LYP", "6-31G(d)", "基态能量", "过渡态"]
    if domain == "interfacial_phenomena":
        return ["zeta电位", "表面张力", "接触角"]
    return []


def _template_actions(
    subject: str,
    domain: str,
    expertise: str,
    memory_hits: Sequence[Any],
) -> List[ResearchAction]:
    """Phase 14.2 §4: render canonical actions for the user's context."""
    domain_hints = _domain_labels(domain)
    has_memory = bool(memory_hits)
    is_researcher = expertise in ("researcher", "practitioner")

    actions: List[ResearchAction] = []

    # 1. Deepen mechanism
    if domain_hints or is_researcher:
        mechanics = "、".join(domain_hints[:2]) if domain_hints else "传质与反应动力学"
        description = f"分析{subject}中{mechanics}等关键机制及其影响"
        reason = "机制理解是科研深化路径的基础"
        actions.append(ResearchAction(
            action_type=ACTION_DEEPEN_MECHANISM,
            description=description,
            priority=0.85 if is_researcher else 0.55,
            reason=reason,
            metadata={"template": "deepen", "expertise": expertise},
        ))

    # 2. Compare methods
    if expertise in ("researcher", "practitioner"):
        actions.append(ResearchAction(
            action_type=ACTION_COMPARE_METHODS,
            description=f"对比{subject}与传统/替代工艺在效率、能耗、操作性上的差异",
            priority=0.7,
            reason="方法对比可凸显研究价值与适用边界",
            metadata={"template": "compare"},
        ))

    # 3. Literature review
    actions.append(ResearchAction(
        action_type=ACTION_LITERATURE_REVIEW,
        description=f"整理近5年与{subject}相关的CEJ / JHM / WR 等顶刊研究路线",
        priority=0.65 if has_memory else 0.75,
        reason="文献梳理确保下一步不重复造轮子",
        metadata={"template": "review"},
    ))

    # 4. Validate experiment
    if is_researcher:
        actions.append(ResearchAction(
            action_type=ACTION_VALIDATE_EXPERIMENT,
            description=f"设计DOE 实验验证{subject}关键假设并量化不确定度",
            priority=0.7,
            reason="实验验证是 scientific claim 的关键支撑",
            metadata={"template": "experiment"},
        ))

    # 5. Expand application
    if expertise in ("researcher", "practitioner"):
        actions.append(ResearchAction(
            action_type=ACTION_EXPAND_APPLICATION,
            description=f"拓展{subject}在工业级/新场景下的应用潜力（材料、对象、规模）",
            priority=0.55,
            reason="应用拓展为后续课题提供 growth vector",
            metadata={"template": "expand"},
        ))

    # 6. Engineering design (only when domain hints suggest real-world)
    if domain_hints and expertise in ("researcher", "practitioner"):
        actions.append(ResearchAction(
            action_type=ACTION_ENGINEERING_DESIGN,
            description=f"针对{subject}完成工艺放大与反应器工程化设计草案",
            priority=0.5,
            reason="工程化路径是从研究走向落地的桥梁",
            metadata={"template": "engineering"},
        ))

    return actions


def _filter_generic(actions: List[ResearchAction], subject: str) -> List[ResearchAction]:
    """Phase 14.2 §4: ban generic "需要了解更多吗？" patterns.

    Drops descriptions that look generic or under-specified.
    """
    banned_substrings = (
        "了解更多",
        "想了解更多",
        "do you want to know",
        "want to know more",
        "进一步了解",
        "have questions",
    )
    out: List[ResearchAction] = []
    for a in actions:
        low = (a.description or "").lower()
        if any(b.lower() in low for b in banned_substrings):
            continue
        out.append(a)
    return out


def recommend_research_actions(
    ctx,
    *,
    max_actions: int = 4,
) -> List[ResearchAction]:
    """Phase 14.2 §4: produce ranked research actions for the user context.

    Args:
        ctx: a ``FollowUpContext``-like object (duck-typed).
        max_actions: how many actions to return (default 4).

    Returns:
        Sorted list of ``ResearchAction`` (highest priority first).
    """
    subject = _subject(ctx)
    domain = getattr(ctx, "research_domain", "") or ""
    expertise = getattr(ctx, "user_expertise_level", "") or "general"
    memory_hits = getattr(ctx, "memory_hits", None) or []

    actions = _template_actions(subject, domain, expertise, memory_hits)
    actions = _filter_generic(actions, subject)

    # De-duplicate by (type, description-prefix)
    seen = set()
    deduped: List[ResearchAction] = []
    for a in actions:
        key = (a.action_type, (a.description or "")[:40])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(a)

    deduped.sort(key=lambda a: (-a.priority,))
    return deduped[:max_actions] if max_actions > 0 else deduped


__all__ = [
    "ResearchAction",
    "ACTION_TYPES",
    "ACTION_DEEPEN_MECHANISM",
    "ACTION_EXPAND_APPLICATION",
    "ACTION_COMPARE_METHODS",
    "ACTION_VALIDATE_EXPERIMENT",
    "ACTION_LITERATURE_REVIEW",
    "ACTION_ENGINEERING_DESIGN",
    "recommend_research_actions",
]
