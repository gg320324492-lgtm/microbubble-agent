"""Research Agent Productization Adapter — Phase 15.0 §7.

End-to-end pipeline that integrates the Phase 14.x research agent stack
with the Phase 15.0 productization layer. Does NOT modify
``research_agent.py`` or any Phase 14 frozen module.

Pipeline:

    User Prompt
       ↓
    Load User Profile (memory)
       ↓
    Load Workspace
       ↓
    Intent Detection (Phase 14.3)
       ↓
    Research Agent V1.0 (delegated, Phase 14.0)
       ↓
    Quality Evaluation (Phase 15.0 §6)
       ↓
    Update Workspace (Phase 15.0 §4)
       ↓
    Save Memory (Phase 15.0 §3)
       ↓
    Generate Report (additive Phase 15.0 fields)

Public API:
- ProductizedAgentResult dataclass
- run_product_research_agent(...)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.research_memory_service import (
    CATEGORY_CURRENT_PROBLEM,
    CATEGORY_RESEARCH_TOPIC,
    ResearchMemoryService,
)
from app.services.research_workspace_manager import (
    ResearchWorkspaceManager,
)

_logger = logging.getLogger(__name__)


@dataclass
class ProductizedAgentResult:
    """Phase 15.0 §7: aggregated productized result."""

    user_prompt: str
    user_id: int
    workspace_id: Optional[str]
    profile: Optional[Dict[str, Any]] = None
    classification: Optional[Any] = None
    strategy: Optional[Any] = None
    agent_result: Optional[Any] = None
    final_report: Optional[Any] = None
    quality_score: Optional[Dict[str, Any]] = None
    progress: Optional[Dict[str, Any]] = None
    recommended_next_actions: List[str] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str = ""


def run_product_research_agent(
    user_prompt: str,
    *,
    user_id: int,
    workspace_id: Optional[str] = None,
    memory_service: Optional[ResearchMemoryService] = None,
    workspace_manager: Optional[ResearchWorkspaceManager] = None,
    use_llm: bool = True,
    enable_memory: bool = True,
    enable_reasoning: bool = True,
    enable_reflection: bool = True,
    max_memory_results: int = 3,
    force_intent: Optional[str] = None,
) -> ProductizedAgentResult:
    """Phase 15.0 §7: full productized pipeline."""
    out = ProductizedAgentResult(
        user_prompt=user_prompt,
        user_id=int(user_id),
        workspace_id=workspace_id,
    )
    mem = memory_service or ResearchMemoryService()
    mgr = workspace_manager or ResearchWorkspaceManager()

    # ----- 1. Load / create user profile ---------------------------
    profile = mem.load_profile(int(user_id))
    if profile is None:
        profile = mem.save_profile(
            int(user_id),
            name=f"user_{int(user_id)}",
            research_domain="general",
            expertise_level="researcher",
        )
    out.profile = profile
    out.steps.append({"name": "load_profile", "success": True})

    # ----- 2. Load or create workspace -----------------------------
    ws_snapshot = None
    if workspace_id:
        ws_snapshot = mgr.get_workspace(workspace_id)
    if ws_snapshot is None:
        ws_snapshot = mgr.create_workspace(
            int(user_id),
            title="研究项目",
            domain=str(profile.get("research_domain") or "general"),
            goal="探索用户提出的研究问题",
        )
    out.workspace_id = ws_snapshot.workspace_id
    out.steps.append({
        "name": "load_workspace",
        "workspace_id": ws_snapshot.workspace_id,
    })

    # ----- 3. Intent detection -------------------------------------
    classification = None
    strategy = None
    try:
        from app.services.research_intent_classifier import (
            ResearchIntentClassifier,
            classify_intent,
        )
        from app.services.research_profile import (
            ResearchProfile,
        )
        prof_obj = ResearchProfile(
            domain=profile.get("research_domain", "general"),
            expertise_level=profile.get("expertise_level", "researcher"),
            keywords=profile.get("research_topics", []),
        )
        if force_intent is None:
            classification = classify_intent(
                user_prompt,
                profile=prof_obj,
            )
        else:
            from app.services.research_intent_schema import (
                make_intent_classification,
            )
            classification = make_intent_classification(
                intent=force_intent,
                confidence=1.0,
                reasoning="forced",
            )
        out.classification = classification

        from app.services.research_answer_strategy import get_strategy
        strategy = get_strategy(classification.intent)
        out.strategy = strategy
        out.steps.append({
            "name": "intent_detection",
            "intent": classification.intent,
            "confidence": classification.confidence,
        })
    except Exception as exc:  # pragma: no cover
        _logger.debug("intent detection failed: %s", exc)
        out.steps.append({
            "name": "intent_detection",
            "success": False,
            "error": str(exc),
        })

    # ----- 4. Run Research Agent V1.0 (delegated, Phase 14.0) ------
    try:
        from app.services.research_agent import run_research_agent
        agent_result = run_research_agent(
            user_prompt=user_prompt,
            use_llm=use_llm,
            enable_memory=enable_memory,
            enable_reasoning=enable_reasoning,
            enable_reflection=enable_reflection,
            max_memory_results=max_memory_results,
        )
        out.agent_result = agent_result
        final_report = getattr(agent_result, "final_report", None)
        out.final_report = final_report
        out.steps.append({
            "name": "research_agent_v1",
            "success": bool(getattr(agent_result, "success", False)),
        })
    except Exception as exc:
        out.success = False
        out.error = f"v1_agent_failed: {exc}"
        out.steps.append({
            "name": "research_agent_v1",
            "success": False,
            "error": str(exc),
        })
        return out

    # ----- 5. Quality evaluation -----------------------------------
    try:
        from app.services.research_quality_evaluator import (
            ResearchQualityEvaluator,
        )
        answer_text = (
            getattr(final_report, "executive_summary", "")
            or user_prompt
        )
        qe = ResearchQualityEvaluator()
        qs = qe.evaluate_answer(
            answer_text,
            intent=classification.intent if classification else "",
        )
        out.quality_score = qs.to_dict()
        # Surface top suggestions as recommended_next_actions
        out.recommended_next_actions = list(qs.suggestions or [])
        out.steps.append({
            "name": "quality_evaluation",
            "overall_score": qs.overall_score,
        })
    except Exception as exc:  # pragma: no cover
        _logger.debug("quality evaluation failed: %s", exc)
        out.steps.append({
            "name": "quality_evaluation",
            "success": False,
            "error": str(exc),
        })

    # ----- 6. Update workspace + tracker ---------------------------
    try:
        # Add a hypothesis automatically when intent is mechanism_analysis
        if classification is not None and classification.intent == "mechanism_analysis":
            mgr.add_hypothesis(
                ws_snapshot.workspace_id,
                hypothesis_id="H_AUTO_1",
                text=f"基于本次提问的机制假设: {user_prompt[:160]}",
            )
        # Always update progress payload
        mgr.update_progress(
            ws_snapshot.workspace_id,
            {
                "last_intent": (
                    classification.intent if classification else ""
                ),
                "last_quality_score": (
                    out.quality_score.get("overall_score")
                    if out.quality_score else None
                ),
            },
        )
        from app.services.research_progress_tracker import (
            ResearchProgressTracker,
        )
        tracker = ResearchProgressTracker()
        progress = tracker.evaluate_workspace(ws_snapshot)
        out.progress = progress.to_dict()
        out.recommended_next_actions.append(progress.next_action)
        out.steps.append({
            "name": "progress_update",
            "overall_score": progress.overall_score,
        })
    except Exception as exc:  # pragma: no cover
        _logger.debug("workspace update failed: %s", exc)
        out.steps.append({
            "name": "progress_update",
            "success": False,
            "error": str(exc),
        })

    # ----- 7. Save memory ------------------------------------------
    try:
        if classification is not None:
            mem.save_project_memory(
                int(user_id),
                workspace_id=ws_snapshot.workspace_id,
                category=CATEGORY_RESEARCH_TOPIC,
                content=user_prompt[:300],
                metadata={
                    "intent": classification.intent,
                    "confidence": classification.confidence,
                },
            )
            if out.quality_score:
                mem.save_project_memory(
                    int(user_id),
                    workspace_id=ws_snapshot.workspace_id,
                    category=CATEGORY_CURRENT_PROBLEM,
                    content="当前质量评估缺失项",
                    metadata={
                        "missing": list(
                            (out.quality_score.get("missing_elements") or [])
                        ),
                    },
                )
        out.steps.append({"name": "save_memory", "success": True})
    except Exception as exc:  # pragma: no cover
        _logger.debug("save memory failed: %s", exc)
        out.steps.append({
            "name": "save_memory",
            "success": False,
            "error": str(exc),
        })

    # ----- 8. Attach Phase 15.0 metadata on report (additive) ------
    try:
        if final_report is not None:
            attach_payload = {
                "research_status": out.progress,
                "quality_score": out.quality_score,
                "workspace_summary": mgr.get_research_status(
                    ws_snapshot.workspace_id
                ),
                "recommended_next_actions": list(
                    out.recommended_next_actions or []
                ),
            }
            for key, value in attach_payload.items():
                if hasattr(final_report, key):
                    setattr(final_report, key, value)
    except Exception as exc:  # pragma: no cover
        _logger.debug("attach Phase 15.0 metadata failed: %s", exc)

    return out


__all__ = [
    "ProductizedAgentResult",
    "run_product_research_agent",
]
