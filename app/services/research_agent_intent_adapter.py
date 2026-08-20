"""Research Agent Intent Adapter — Phase 14.3 §4.

Adapter that wraps the Phase 14.0 ``run_research_agent`` with intent
classification + answer strategy selection + intent-aware follow-ups.

The adapter does **not** modify ``research_agent.py``, the existing
``followup_generator.py``, or any other frozen module. It invokes them
through their public API.

Pipeline (per spec §4):

    User Prompt
        ↓
        Intent Classifier       (research_intent_classifier.py)
        ↓
        Answer Strategy         (research_answer_strategy.py)
        ↓
        Existing Research Agent (research_agent.run_research_agent, Phase 14.0)
        ↓
        Research Report         (existing fields + additive intent metadata)
        ↓
        Intent-aware Follow-up  (intent_followup_adapter.py)

Public API:
- IntentAwareResult dataclass
- run_with_intent_detection(...) -> IntentAwareResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


@dataclass
class IntentAwareResult:
    """Phase 14.3 §4: aggregated result of an intent-aware research run."""

    user_prompt: str
    classification: Optional[Any] = None
    strategy: Optional[Any] = None
    agent_result: Optional[Any] = None
    final_report: Optional[Any] = None
    intent_followups: List[Dict[str, Any]] = field(default_factory=list)
    steps: List[Dict[str, Any]] = field(default_factory=list)
    success: bool = True
    error: str = ""


def _classify_step(name: str, **payload) -> Dict[str, Any]:
    return {"name": name, **payload}


def run_with_intent_detection(
    user_prompt: str,
    *,
    use_llm: bool = True,
    enable_memory: bool = True,
    enable_reasoning: bool = True,
    enable_reflection: bool = True,
    max_memory_results: int = 3,
    profile: Optional[Any] = None,
    memory_context: Optional[Any] = None,
    force_intent: Optional[str] = None,
) -> IntentAwareResult:
    """Phase 14.3 §4: end-to-end intent-aware research pipeline.

    Wraps ``run_research_agent`` without modifying it.
    """
    out = IntentAwareResult(user_prompt=user_prompt)

    # ----- 1. Intent classification -----------------------------------------
    classification = None
    try:
        from app.services.research_intent_classifier import (
            ResearchIntentClassifier,
            classify_intent,
        )
        classifier = ResearchIntentClassifier()
        classification = (
            classify_intent(
                user_prompt=user_prompt,
                profile=profile,
                memory_context=memory_context,
            )
            if force_intent is None
            else _force_classification(user_prompt, force_intent)
        )
        out.classification = classification
        out.steps.append(_classify_step(
            "intent_classification",
            intent=classification.intent,
            confidence=classification.confidence,
            domain=classification.domain,
        ))
    except Exception as exc:  # pragma: no cover
        _logger.debug("intent classification failed: %s", exc)
        out.steps.append(_classify_step(
            "intent_classification",
            success=False,
            error=str(exc),
        ))

    # ----- 2. Answer strategy ------------------------------------------------
    strategy = None
    try:
        from app.services.research_answer_strategy import get_strategy
        intent_name = (
            classification.intent
            if classification is not None
            else "concept_explanation"
        )
        strategy = get_strategy(intent_name)
        out.strategy = strategy
        out.steps.append(_classify_step(
            "answer_strategy",
            intent=strategy.intent,
            sections=len(strategy.sections),
        ))
    except Exception as exc:  # pragma: no cover
        _logger.debug("answer strategy lookup failed: %s", exc)
        out.steps.append(_classify_step(
            "answer_strategy",
            success=False,
            error=str(exc),
        ))

    # ----- 3. Existing Research Agent V1.0 (delegated) --------------------
    agent_result = None
    final_report = None
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
        out.steps.append(_classify_step(
            "research_agent_v1",
            success=bool(getattr(agent_result, "success", False)),
        ))
    except Exception as exc:
        out.success = False
        out.error = f"v1_agent_failed: {exc}"
        out.steps.append(_classify_step(
            "research_agent_v1",
            success=False,
            error=str(exc),
        ))
        return out

    # Attach classification + strategy on the report as additive metadata.
    if final_report is not None and hasattr(final_report, "metadata"):
        try:
            md = final_report.metadata or {}
            md["phase14_3_intent"] = (
                classification.to_dict()
                if classification is not None and hasattr(classification, "to_dict")
                else None
            )
            md["phase14_3_strategy"] = (
                strategy.to_dict()
                if strategy is not None and hasattr(strategy, "to_dict")
                else None
            )
            final_report.metadata = md
        except Exception:
            # If the existing dataclass doesn't accept metadata, skip
            pass

    # ----- 4. Intent-aware follow-ups ---------------------------------------
    try:
        from app.services.intent_followup_adapter import generate_intent_followups
        intent_name = (
            classification.intent
            if classification is not None
            else "concept_explanation"
        )
        intent_followups = generate_intent_followups(
            user_prompt,
            intent=intent_name,
            max_questions=3,
        )
        serialized = [f.to_dict() for f in intent_followups]
        out.intent_followups = serialized
        if final_report is not None and hasattr(final_report, "intent_followups"):
            final_report.intent_followups = serialized
        out.steps.append(_classify_step(
            "intent_followup",
            count=len(intent_followups),
        ))
    except Exception as exc:
        _logger.debug("intent follow-up adapter failed: %s", exc)
        out.steps.append(_classify_step(
            "intent_followup",
            success=False,
            error=str(exc),
        ))

    out.final_report = final_report
    return out


def _force_classification(user_prompt: str, intent: str) -> Any:
    """Build an ``IntentClassification`` directly when callers override intent."""
    from app.services.research_intent_schema import make_intent_classification

    return make_intent_classification(
        intent=intent,
        confidence=1.0,
        reasoning="force_intent override",
        matched_keywords=["forced"],
    )


__all__ = [
    "IntentAwareResult",
    "run_with_intent_detection",
]
