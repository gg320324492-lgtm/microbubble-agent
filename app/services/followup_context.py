"""Follow-up Context — Phase 14.2 §1.

Wraps everything the personalized generator needs in one dataclass. Where
Phase 14.1's generator received ``(user_prompt, answer, memory_hits,
reasoning_output)``, Phase 14.2 receives a single ``FollowUpContext`` that
carries user profile + domain + history + memory + answer in one place.

Public API:
- FollowUpContext (dataclass)
- build_followup_context(...) factory
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class FollowUpContext:
    """Phase 14.2 §1: rich context object for follow-up intelligence.

    Additive by design — fills with empty defaults so existing callers that
    haven't migrated to Phase 14.2 can keep passing kwargs.
    """

    # Original inputs (kept verbatim)
    current_question: str = ""
    generated_answer: str = ""

    # User + research background
    user_profile: Optional[Any] = None  # a ResearchProfile if available
    research_domain: str = ""
    user_expertise_level: str = "general"  # general | practitioner | researcher
    historical_projects: List[Dict[str, Any]] = field(default_factory=list)
    research_goal: str = ""

    # Retrieval
    memory_hits: List[Any] = field(default_factory=list)

    # Reasoning context
    reasoning_summary: str = ""
    reasoning_output: Optional[Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_question": self.current_question,
            "generated_answer": self.generated_answer,
            "user_profile": (
                self.user_profile.to_dict()
                if self.user_profile is not None
                and hasattr(self.user_profile, "to_dict")
                else None
            ),
            "research_domain": self.research_domain,
            "user_expertise_level": self.user_expertise_level,
            "historical_projects": list(self.historical_projects),
            "research_goal": self.research_goal,
            "memory_hits_count": len(self.memory_hits or []),
            "reasoning_summary": self.reasoning_summary,
        }


def build_followup_context(
    *,
    user_prompt: str = "",
    answer: str = "",
    context: Optional[Dict[str, Any]] = None,
    memory_hits: Optional[List[Any]] = None,
    reasoning_output: Optional[Any] = None,
    intent: Optional[Any] = None,
    user_profile: Optional[Any] = None,
    research_domain: str = "",
    user_expertise_level: str = "general",
    historical_projects: Optional[List[Dict[str, Any]]] = None,
    research_goal: str = "",
) -> FollowUpContext:
    """Phase 14.2 §1: build a fully-populated ``FollowUpContext``.

    Accepts the same signature as Phase 14.1's generator so existing call
    sites keep working. Anything missing falls back to safe defaults.
    """
    ctx = context or {}
    domain = research_domain or (
        getattr(intent, "domain", "") if intent is not None else ""
    ) or ctx.get("research_domain", "")
    if not domain:
        # Quick heuristic from the question
        lower = (user_prompt or "").lower()
        domain = "general"
        if any(k in lower for k in ("微纳米气泡", "纳米气泡", "microbubble", "nanobubble")):
            domain = "pollution_control_water_treatment"
        elif any(k in lower for k in ("污染", "水处理", "wastewater")):
            domain = "environmental_engineering"
        elif any(k in lower for k in ("df ", "密度泛函", "gaussian", "molecular")):
            domain = "computational_chemistry"

    expertise = user_expertise_level or ctx.get("user_expertise_level", "general")

    rs = reasoning_output
    rs_summary = ""
    if rs is not None and hasattr(rs, "summary"):
        try:
            rs_summary = str(getattr(rs, "summary", "") or "")
        except Exception:
            rs_summary = ""

    return FollowUpContext(
        current_question=user_prompt or "",
        generated_answer=answer or "",
        user_profile=user_profile,
        research_domain=domain,
        user_expertise_level=expertise,
        historical_projects=list(historical_projects or []),
        research_goal=research_goal or ctx.get("research_goal", ""),
        memory_hits=list(memory_hits or []),
        reasoning_summary=rs_summary,
        reasoning_output=rs,
    )


__all__ = ["FollowUpContext", "build_followup_context"]
