"""Personalized Research Agent — Phase 14.2 §6.

Phase 14.2 adapter that layers personalization on top of Phase 14.0's
``run_research_agent``. This module does **not** modify
``research_agent.py``; it delegates the core V1.0 pipeline to it and
adds Phase 14.2 enrichment steps:

    user question
        ↓ intent
        ↓ memory retrieval
        ↓ profile extraction (Phase 14.2 §2)
        ↓ Research Agent V1.0 (delegated, Phase 14.0)
        ↓ citation guard (Phase 14.2 §5)
        ↓ personalized follow-up (Phase 14.2 §3)
        ↓ research action recommendation (Phase 14.2 §4)
        ↓ final report

Public API:
- PersonalizedAgentResult dataclass
- run_personalized_research_agent(...) -> PersonalizedAgentResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class PersonalizedAgentResult:
    """Phase 14.2 §6: result of a personalized research run."""

    user_prompt: str
    profile: Optional[Any]
    v1_result: Optional[Any] = None
    final_report: Optional[Any] = None
    personalized_followups: List[Dict[str, Any]] = field(default_factory=list)
    recommended_actions: List[Dict[str, Any]] = field(default_factory=list)
    citation_status: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str = ""


def run_personalized_research_agent(
    user_prompt: str,
    *,
    use_llm: bool = True,
    enable_memory: bool = True,
    enable_reasoning: bool = True,
    enable_reflection: bool = True,
    max_memory_results: int = 3,
    memory_hits: Optional[List[Any]] = None,
    historical_projects: Optional[List[Dict[str, Any]]] = None,
    user_expertise_level: str = "general",
    research_goal: str = "",
    allowed_sources: Optional[List[Dict[str, Any]]] = None,
) -> PersonalizedAgentResult:
    """Phase 14.2 §6: end-to-end personalised research pipeline.

    The core V1.0 ``research_agent.run_research_agent`` is invoked as a
    black box; Phase 14.2 enrichment runs **before and after** it without
    modifying that module.
    """
    result = PersonalizedAgentResult(
        user_prompt=user_prompt,
        profile=None,
    )

    # ----- 1. Memory retrieval (Phase 9.x style — local placeholder) -----
    # Phase 14.2 does not call the V1.0 memory retrieval directly; it
    # accepts pre-fetched memory and stores it on the result. The caller can
    # bypass this and supply memory directly.
    mem_hits: List[Any] = list(memory_hits or [])
    result.steps.append({
        "name": "memory_retrieval",
        "success": True,
        "count": len(mem_hits),
    })

    # ----- 2. Profile extraction (Phase 14.2 §2) -----
    try:
        from app.services.research_profile import (
            extract_profile_from_memory,
            extract_profile_from_history,
            merge_profiles,
            ResearchProfile,
        )
        p_mem = extract_profile_from_memory(mem_hits)
        p_hist = extract_profile_from_history(historical_projects or [])
        profile = merge_profiles(p_mem, p_hist)
        # If the caller specified an expertise level, prefer it
        if user_expertise_level in ("general", "practitioner", "researcher"):
            # Demote only if the rule-based profile didn't find a signal
            if not profile.expertise_level or profile.expertise_level == "general":
                profile.expertise_level = user_expertise_level
        result.profile = profile
        result.steps.append({
            "name": "profile_extraction",
            "success": True,
            "domain": profile.domain,
            "expertise_level": profile.expertise_level,
        })
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("profile extraction failed: %s", exc)
        result.profile = None
        result.steps.append({
            "name": "profile_extraction",
            "success": False,
            "error": str(exc),
        })

    # ----- 3. Run Research Agent V1.0 (delegated, Phase 14.0) -----
    v1_result = None
    final_report = None
    try:
        from app.services.research_agent import run_research_agent
        v1_result = run_research_agent(
            user_prompt=user_prompt,
            use_llm=use_llm,
            enable_memory=enable_memory,
            enable_reasoning=enable_reasoning,
            enable_reflection=enable_reflection,
            max_memory_results=max_memory_results,
        )
        result.v1_result = v1_result
        final_report = getattr(v1_result, "final_report", None)
        result.steps.append({
            "name": "research_agent_v1",
            "success": bool(getattr(v1_result, "success", False)),
        })
    except Exception as exc:  # pragma: no cover - critical path
        result.success = False
        result.error = f"v1_agent_failed: {exc}"
        result.steps.append({
            "name": "research_agent_v1",
            "success": False,
            "error": str(exc),
        })
        return result

    # ----- 4. Citation Guard (Phase 14.2 §5) -----
    try:
        from app.services.citation_guard import (
            validate_answer_citations,
            summarize_citation_status,
        )
        answer_text = ""
        if final_report is not None:
            answer_text = getattr(final_report, "executive_summary", "") or ""

        _cleaned, records = validate_answer_citations(
            answer_text, allowed_sources=allowed_sources or []
        )
        result.citation_status = [r.to_dict() for r in records]
        # Attach summary on report
        if final_report is not None:
            summary = summarize_citation_status(records)
            if not hasattr(final_report, "citation_status"):
                # shouldn't happen on Phase 14.2 reports, but guard anyway
                pass
            else:
                final_report.citation_status_summary = summary
        result.steps.append({
            "name": "citation_guard",
            "success": True,
            "citation_count": len(records),
        })
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("citation guard failed: %s", exc)
        result.steps.append({
            "name": "citation_guard",
            "success": False,
            "error": str(exc),
        })

    # ----- 5. Personalized follow-ups (Phase 14.2 §3) -----
    try:
        from app.services.followup_context import build_followup_context
        from app.services.personalized_followup_generator import (
            generate_personalized_followups,
        )
        ctx = build_followup_context(
            user_prompt=user_prompt,
            answer=getattr(final_report, "executive_summary", "")
            if final_report is not None
            else "",
            context=None,
            memory_hits=mem_hits,
            reasoning_output=(
                getattr(v1_result, "metadata", {}).get("scientific_reasoning")
                if v1_result is not None
                else None
            ),
            intent=None,
            user_profile=result.profile,
            research_domain=(getattr(result.profile, "domain", "") if result.profile else ""),
            user_expertise_level=(
                getattr(result.profile, "expertise_level", user_expertise_level)
                if result.profile is not None
                else user_expertise_level
            ),
            historical_projects=historical_projects,
            research_goal=research_goal,
        )
        followups = generate_personalized_followups(ctx, max_questions=3)
        result.personalized_followups = [f.to_dict() for f in followups]
        if final_report is not None and hasattr(final_report, "personalized_followups"):
            final_report.personalized_followups = result.personalized_followups
        result.steps.append({
            "name": "personalized_followup",
            "success": True,
            "count": len(followups),
        })
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("personalized follow-up failed: %s", exc)
        result.steps.append({
            "name": "personalized_followup",
            "success": False,
            "error": str(exc),
        })

    # ----- 6. Research Action Recommendations (Phase 14.2 §4) -----
    try:
        from app.services.followup_context import build_followup_context
        from app.services.research_action_recommender import (
            recommend_research_actions,
        )
        ctx = build_followup_context(
            user_prompt=user_prompt,
            answer=getattr(final_report, "executive_summary", "")
            if final_report is not None
            else "",
            memory_hits=mem_hits,
            user_profile=result.profile,
            research_domain=(getattr(result.profile, "domain", "") if result.profile else ""),
            user_expertise_level=(
                getattr(result.profile, "expertise_level", user_expertise_level)
                if result.profile is not None
                else user_expertise_level
            ),
            historical_projects=historical_projects,
            research_goal=research_goal,
        )
        actions = recommend_research_actions(ctx, max_actions=4)
        result.recommended_actions = [a.to_dict() for a in actions]
        if final_report is not None and hasattr(final_report, "recommended_actions"):
            final_report.recommended_actions = result.recommended_actions
        result.steps.append({
            "name": "research_action_recommendation",
            "success": True,
            "count": len(actions),
        })
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("research action recommendation failed: %s", exc)
        result.steps.append({
            "name": "research_action_recommendation",
            "success": False,
            "error": str(exc),
        })

    result.final_report = final_report
    return result


__all__ = [
    "PersonalizedAgentResult",
    "run_personalized_research_agent",
]
