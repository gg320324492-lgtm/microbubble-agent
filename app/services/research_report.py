"""Research Report Generator — Phase 14.0 §2, Phase 14.1 §4.

Generates a structured research report from the pipeline outputs.

Per spec §2: report contains:
- Executive summary
- Methodology (intent, plan, memory, executor)
- Findings (evaluation, reasoning)
- Next steps (improvement plan, knowledge updates)
- Provenance (steps + metadata)
- Follow-up questions (Phase 14.1 §4 — intent-aware)

Public API:
- ResearchReport dataclass: title, executive_summary, methodology,
  findings, next_steps, provenance, followup_questions
- generate_research_report(...) -> ResearchReport
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any as TypingAny
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)

# Phase 14.1: lightweight import surface so we don't crash if the follow-up
# stack is missing on a frozen checkout. ``generate_followup_questions`` and
# ``rank_followups`` are lazy-imported inside the helper to avoid loading
# optional modules (LLM clients, etc.) at import time.


@dataclass
class ResearchReport:
    """Phase 14.0 §2: structured research report (Phase 14.1 §4 adds follow-up questions)."""

    title: str
    executive_summary: str
    methodology: List[str] = field(default_factory=list)
    findings: List[str] = field(default_factory=list)
    next_steps: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)
    generated_at: Optional[datetime] = None
    user_prompt: str = ""
    # Phase 14.1 §4: intent-aware follow-up questions (additive)
    followup_questions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "executive_summary": self.executive_summary,
            "methodology": list(self.methodology),
            "findings": list(self.findings),
            "next_steps": list(self.next_steps),
            "provenance": dict(self.provenance),
            "generated_at": (
                self.generated_at.isoformat() if self.generated_at else None
            ),
            "user_prompt": self.user_prompt,
            "followup_questions": [dict(q) for q in (self.followup_questions or [])],
        }


def _summarize_intent(intent) -> List[str]:
    """Phase 14.0 §2: summarize intent."""
    if intent is None:
        return []
    parts = []
    if getattr(intent, "objective", None):
        parts.append(f"Objective: {intent.objective[:300]}")
    if getattr(intent, "domain", None):
        parts.append(f"Domain: {intent.domain}")
    if getattr(intent, "task_type", None):
        parts.append(f"Task type: {intent.task_type}")
    return parts


def _summarize_plan(plan) -> List[str]:
    """Phase 14.0 §2: summarize plan."""
    if plan is None:
        return []
    parts = []
    steps = getattr(plan, "steps", []) or []
    if steps:
        parts.append(f"Plan: {len(steps)} steps")
    tools = getattr(plan, "required_tools", []) or []
    if tools:
        parts.append(f"Tools required: {', '.join(str(t) for t in tools[:5])}")
    if getattr(plan, "plan_version", None):
        parts.append(f"Plan version: {plan.plan_version}")
    return parts


def _summarize_execution(execution_result) -> List[str]:
    """Phase 14.0 §2: summarize execution result."""
    if execution_result is None:
        return []
    parts = []
    parts.append(f"Execution success: {execution_result.success}")
    parts.append(f"Total steps: {len(execution_result.steps)}")
    parts.append(f"OK steps: {len(execution_result.ok_steps)}")
    parts.append(f"Error steps: {len(execution_result.error_steps)}")
    parts.append(f"Skipped steps: {len(execution_result.skipped_steps)}")
    duration = getattr(execution_result, "total_duration_seconds", 0.0) or 0.0
    parts.append(f"Duration: {duration:.3f}s")
    return parts


def _summarize_evaluation(evaluation) -> List[str]:
    """Phase 14.0 §2: summarize evaluation."""
    if evaluation is None:
        return []
    parts = []
    overall = getattr(evaluation, "overall_score", 0.0) or 0.0
    quality = getattr(evaluation, "quality_score", 0.0) or 0.0
    completeness = getattr(evaluation, "completeness_score", 0.0) or 0.0
    confidence = getattr(evaluation, "confidence_score", 0.0) or 0.0
    parts.append(f"Overall score: {overall:.3f}")
    parts.append(f"Quality: {quality:.3f}")
    parts.append(f"Completeness: {completeness:.3f}")
    parts.append(f"Confidence: {confidence:.3f}")
    issues = getattr(evaluation, "issues", []) or []
    if issues:
        parts.append(f"Issues: {len(issues)}")
    return parts


def _summarize_reasoning(reasoning_output) -> List[str]:
    """Phase 14.0 §2: summarize reasoning output."""
    if reasoning_output is None:
        return []
    parts = []
    if hasattr(reasoning_output, "summary"):
        parts.append(f"Reasoning summary: {reasoning_output.summary[:300]}")
    if hasattr(reasoning_output, "action"):
        parts.append(f"Recommended action: {reasoning_output.action}")
    if hasattr(reasoning_output, "bayesian_posterior"):
        posterior = reasoning_output.bayesian_posterior
        parts.append(f"Bayesian posterior: {posterior:.3f}")
    return parts


def _summarize_improvement_plan(improvement_plan) -> List[str]:
    """Phase 14.0 §2: summarize improvement plan."""
    if improvement_plan is None:
        return []
    parts = []
    if getattr(improvement_plan, "priority", None):
        parts.append(f"Improvement priority: {improvement_plan.priority}")
    steps = getattr(improvement_plan, "additional_steps", []) or []
    if steps:
        parts.append(f"Additional steps: {len(steps)}")
    if getattr(improvement_plan, "reason", None):
        parts.append(f"Reason: {improvement_plan.reason[:200]}")
    return parts


def _summarize_knowledge(knowledge_output) -> List[str]:
    """Phase 14.0 §2: summarize knowledge update output."""
    if knowledge_output is None:
        return []
    if not isinstance(knowledge_output, list):
        return []
    return [f"Hypotheses generated: {len(knowledge_output)}"]


def _summarize_memory(memory_hits) -> List[str]:
    """Phase 14.0 §2: summarize memory retrieval."""
    if not memory_hits:
        return []
    return [f"Memories retrieved: {len(memory_hits)}"]


def _build_followup_questions(
    user_prompt: str,
    intent,
    memory_hits,
    reasoning_output,
    max_questions: int = 3,
    expected_intent: str = "",
) -> List[Dict[str, Any]]:
    """Phase 14.1 §4: build follow-up questions + rank.

    Lazy import avoids hard-fail if the follow-up stack is missing on a
    frozen checkout.
    """
    try:
        from app.services.followup_generator import generate_followup_questions
        from app.services.followup_ranker import rank_followups
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("Follow-up modules unavailable: %s", exc)
        return []

    answer_excerpt = ""
    try:
        if reasoning_output is not None and getattr(reasoning_output, "summary", None):
            answer_excerpt = str(reasoning_output.summary or "")[:600]
    except Exception:
        answer_excerpt = ""

    try:
        followups = generate_followup_questions(
            user_prompt=user_prompt or "",
            answer=answer_excerpt,
            context=None,
            memory_hits=memory_hits,
            reasoning_output=reasoning_output,
            intent=intent,
            max_questions=max_questions,
        )
    except Exception as exc:  # pragma: no cover - non-critical
        _logger.debug("generate_followup_questions failed: %s", exc)
        return []

    if not followups:
        return []

    try:
        ranked = rank_followups(followups, expected_intent=expected_intent)
    except Exception as exc:  # pragma: no cover
        _logger.debug("rank_followups failed: %s", exc)
        ranked = list(followups)

    return [f.to_dict() for f in (ranked or [])]


def generate_research_report(
    *,
    user_prompt: str,
    intent=None,
    plan=None,
    execution_result=None,
    evaluation=None,
    improvement_plan=None,
    reasoning_output=None,
    knowledge_output=None,
    memory_hits=None,
    steps=None,
) -> ResearchReport:
    """Phase 14.0 §2: generate a structured research report.

    Args:
        user_prompt: original user question
        intent: ResearchIntent from Phase 8.0
        plan: ResearchExecutionPlan from Phase 8.1
        execution_result: ExecutionResult from Phase 8.2
        evaluation: EvaluationResult from Phase 8.3
        improvement_plan: ImprovementPlan from Phase 8.3
        reasoning_output: BayesianDecisionExplanation from Phase 11.0
        knowledge_output: List[ResearchHypothesis] from Phase 9.0
        memory_hits: List[MemoryHit] from Phase 9.0
        steps: List[PipelineStep] (optional, for provenance)

    Returns:
        ResearchReport with all sections populated
    """
    # Title
    title = f"Research Report: {user_prompt[:80]}"
    if title.endswith((".", "?", "!")):
        title = title.rstrip(".?!")
    if not title.endswith("Research Report:"):
        title = "Research Report: " + user_prompt[:80]
    title = title[:200]

    # Executive summary (1-2 paragraphs)
    summary_lines: List[str] = []
    if intent is not None and getattr(intent, "objective", None):
        summary_lines.append(
            f"Objective: {intent.objective}"
        )
    if evaluation is not None:
        overall = float(getattr(evaluation, "overall_score", 0.0) or 0.0)
        summary_lines.append(
            f"Overall evaluation score: {overall:.3f}."
        )
    if execution_result is not None:
        if execution_result.success:
            summary_lines.append(
                f"Execution completed successfully across {len(execution_result.steps)} steps."
            )
        else:
            summary_lines.append(
                f"Execution completed with failures ({len(execution_result.error_steps)} errors of {len(execution_result.steps)} total)."
            )
    if not summary_lines:
        summary_lines.append("No pipeline output available.")
    executive_summary = " ".join(summary_lines)

    # Methodology
    methodology: List[str] = []
    methodology.extend(_summarize_intent(intent))
    methodology.extend(_summarize_plan(plan))
    methodology.extend(_summarize_memory(memory_hits))

    # Findings
    findings: List[str] = []
    findings.extend(_summarize_execution(execution_result))
    findings.extend(_summarize_evaluation(evaluation))
    findings.extend(_summarize_reasoning(reasoning_output))

    # Next steps
    next_steps: List[str] = []
    next_steps.extend(_summarize_improvement_plan(improvement_plan))
    next_steps.extend(_summarize_knowledge(knowledge_output))

    # Provenance
    provenance: Dict[str, Any] = {
        "phases_used": [
            "Phase 8.0 (Intent + Planning + Execution + Evaluation)",
            "Phase 9.0/9.1 (Memory + Decay + Dedup + Adaptive LR)",
            "Phase 8.2 (Tool Execution + Failure Recovery)",
            "Phase 8.3 (Reflection + Improvement Plan)",
            "Phase 11.0/11.1/11.2 (Bayesian Reasoning + Adaptive)",
            "Phase 12.0/13.0 (Experiment Design + Execution)",
            "Phase 14.1 (Follow-up Intelligence Layer)",
        ],
        "step_durations": [
            {"name": s.name, "duration": s.duration_seconds, "success": s.success}
            for s in (steps or [])
        ],
    }

    expected_intent = ""
    if intent is not None:
        expected_intent = (
            getattr(intent, "task_type", "")
            or getattr(intent, "domain", "")
            or ""
        )

    followup_questions: List[Dict[str, Any]] = _build_followup_questions(
        user_prompt=user_prompt,
        intent=intent,
        memory_hits=memory_hits,
        reasoning_output=reasoning_output,
        max_questions=3,
        expected_intent=expected_intent,
    )

    return ResearchReport(
        title=title,
        executive_summary=executive_summary,
        methodology=methodology,
        findings=findings,
        next_steps=next_steps,
        provenance=provenance,
        generated_at=datetime.now(timezone.utc),
        user_prompt=user_prompt,
        followup_questions=followup_questions,
    )