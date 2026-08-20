"""Unified Research Agent Orchestrator — Phase 14.0 §1.

The single entry point for autonomous research. Wires together all
frozen Phase 8-13 modules into a complete pipeline:

    user_prompt
        |
        v
    Research Intent (Phase 8.0)
        |
        v
    Research Plan (Phase 8.1)
        |
        v
    Memory Retrieval (Phase 9.1)
        |
        v
    Tool Execution (Phase 8.2)
        |
        v
    Evaluation (Phase 8.3)
        |
        v
    Reflection (Phase 8.3)
        |
        v
    Scientific Reasoning (Phase 11.0/11.1/11.2)
        |
        v
    Knowledge Update (Phase 9.0/9.1)
        |
        v
    Research Report (Phase 14.0)

This is the V1.0 release orchestrator. All underlying modules are frozen;
this file only composes them.

Public API:
- run_research_agent(user_prompt, *, use_llm=True, enable_memory=True,
                    enable_reasoning=True, enable_reflection=True) -> AgentResult
- AgentResult dataclass: agent_input + steps + final_report + metadata

The orchestrator NEVER modifies any underlying service. It only calls
existing public APIs.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any as TypingAny
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)


# Pipeline step names (for AgentResult.steps tracking)
PIPELINE_STEPS: tuple = (
    "intent_understanding",
    "research_planning",
    "memory_retrieval",
    "tool_execution",
    "evaluation",
    "reflection",
    "scientific_reasoning",
    "knowledge_update",
    "report_generation",
)


@dataclass
class PipelineStep:
    """Phase 14.0 §1: single pipeline step result."""

    name: str
    success: bool
    duration_seconds: float
    output: Any = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "success": self.success,
            "duration_seconds": self.duration_seconds,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class AgentResult:
    """Phase 14.0 §1: complete research agent result."""

    user_prompt: str
    steps: List[PipelineStep] = field(default_factory=list)
    final_report: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_prompt": self.user_prompt,
            "steps": [s.to_dict() for s in self.steps],
            "final_report": (
                self.final_report.to_dict()
                if hasattr(self.final_report, "to_dict")
                else self.final_report
            ),
            "metadata": dict(self.metadata),
            "started_at": (
                self.started_at.isoformat() if self.started_at else None
            ),
            "finished_at": (
                self.finished_at.isoformat() if self.finished_at else None
            ),
        }

    @property
    def success(self) -> bool:
        return all(s.success for s in self.steps)


def _timed_step(name: str, fn) -> PipelineStep:
    """Run a pipeline step and capture timing + success."""
    t0 = time.time()
    try:
        output = fn()
        return PipelineStep(
            name=name, success=True, duration_seconds=time.time() - t0, output=output,
        )
    except Exception as exc:
        return PipelineStep(
            name=name, success=False, duration_seconds=time.time() - t0,
            error=f"{type(exc).__name__}: {str(exc)[:500]}",
        )


def run_research_agent(
    user_prompt: str,
    *,
    use_llm: bool = True,
    enable_memory: bool = True,
    enable_reasoning: bool = True,
    enable_reflection: bool = True,
    max_memory_results: int = 3,
) -> AgentResult:
    """Phase 14.0 §1: run the unified research agent pipeline.

    Composes frozen Phase 8-13 modules. NEVER modifies them. Only calls
    their public APIs.

    Args:
        user_prompt: user's research question
        use_llm: if False, use heuristic/keyword fallbacks (for tests)
        enable_memory: if True, query research memory (Phase 9.1)
        enable_reasoning: if True, run Bayesian reasoning (Phase 11.0+)
        enable_reflection: if True, run reflection + memory update (Phase 8.3/9.0)
        max_memory_results: max memories to retrieve (default 3)

    Returns:
        AgentResult with pipeline steps + final report + metadata
    """
    result = AgentResult(
        user_prompt=user_prompt,
        started_at=datetime.now(timezone.utc),
        metadata={
            "use_llm": use_llm,
            "enable_memory": enable_memory,
            "enable_reasoning": enable_reasoning,
            "enable_reflection": enable_reflection,
        },
    )

    _logger.info(
        "[Phase 14.0 §1] run_research_agent START: prompt=%r",
        user_prompt[:100],
    )

    # 1. Research Intent Understanding (Phase 8.0)
    def _step_intent():
        from app.services.research_intent_parser import parse_research_intent
        return parse_research_intent(user_prompt, use_llm=use_llm)

    intent_step = _timed_step("intent_understanding", _step_intent)
    result.steps.append(intent_step)
    intent = intent_step.output

    # 2. Research Planning (Phase 8.1)
    def _step_plan():
        from app.services.research_planner import generate_execution_plan
        return generate_execution_plan(intent, use_llm=use_llm)

    plan_step = _timed_step("research_planning", _step_plan)
    result.steps.append(plan_step)
    plan = plan_step.output

    # 3. Memory Retrieval (Phase 9.1, optional)
    memory_hits = []
    if enable_memory:
        def _step_memory():
            from app.services.research_memory_storage import save_memory, search_similar
            # Build candidate memories (heuristic: chunk prompt into statements)
            chunks = [
                user_prompt[i : i + 256]
                for i in range(0, len(user_prompt), 256)
            ]
            memories = [
                save_memory(
                    content=chunk,
                    memory_type="insight",
                    importance=0.5,
                )
                for chunk in chunks
            ]
            return search_similar(
                query_text=user_prompt,
                memories=memories,
                top_k=max_memory_results,
            )

        memory_step = _timed_step("memory_retrieval", _step_memory)
        result.steps.append(memory_step)
        memory_hits = memory_step.output or []

        # 3b. Memory-augmented planning (Phase 9.1 §6)
        def _step_memory_plan():
            from app.services.research_memory_planner_upgrade import (
                upgrade_plan_memory,
            )
            return upgrade_plan_memory(
                plan,
                memories=[h.memory for h in memory_hits] if memory_hits else None,
                top_k=max_memory_results,
            )

        memory_plan_step = _timed_step("memory_plan_upgrade", _step_memory_plan)
        result.steps.append(memory_plan_step)
        if memory_plan_step.output is not None:
            plan = memory_plan_step.output.plan

    # 4. Tool Execution (Phase 8.2 + Phase 13.0)
    def _step_tool_exec():
        from app.services.research_executor import execute_plan
        return execute_plan(plan)

    exec_step = _timed_step("tool_execution", _step_tool_exec)
    result.steps.append(exec_step)
    execution_result = exec_step.output

    # 5. Evaluation (Phase 8.3)
    def _step_evaluation():
        from app.services.research_evaluator import evaluate_execution
        return evaluate_execution(execution_result, use_llm=use_llm)

    eval_step = _timed_step("evaluation", _step_evaluation)
    result.steps.append(eval_step)
    evaluation = eval_step.output

    # 6. Reflection (Phase 8.3, optional)
    improvement_plan = None
    if enable_reflection:
        def _step_reflection():
            from app.services.research_reflector import generate_improvement_plan
            return generate_improvement_plan(evaluation, use_llm=use_llm)

        reflection_step = _timed_step("reflection", _step_reflection)
        result.steps.append(reflection_step)
        improvement_plan = reflection_step.output

    # 7. Scientific Reasoning (Phase 11.0/11.1/11.2, optional)
    reasoning_output = None
    if enable_reasoning and improvement_plan is not None:
        def _step_reasoning():
            from app.services.decision_explanation_bayesian import (
                explain_decision_bayesian,
            )
            from app.services.reasoning_graph import ReasoningGraph
            from app.models.research_hypothesis import ResearchHypothesis
            from app.models.research_evidence import ResearchEvidence

            # Build minimal reasoning graph
            graph = ReasoningGraph()
            hyp = ResearchHypothesis(
                id=intent.task_id or 1,
                statement=intent.objective or user_prompt,
                confidence=evaluation.overall_score,
                domain=intent.domain or "other",
            )
            graph.add_hypothesis(hyp)
            # Stub evidence
            stub_ev = ResearchEvidence(
                id=1,
                content=f"Evaluation result for {user_prompt[:50]}",
                source_type="computation",
                polarity="supports",
                reliability=0.5,
            )
            graph.add_evidence(stub_ev)
            graph.link_evidence_to_hypothesis(1, 1, polarity="supports", weight=1.0)

            # Generate a decision
            from app.services.research_decision_engine import (
                Decision,
                DECISION_CONTINUE,
            )
            decision = Decision(
                action=DECISION_CONTINUE,
                reason=f"Overall score: {evaluation.overall_score:.3f}",
                confidence=0.5,
            )
            return explain_decision_bayesian(decision, graph)

        reasoning_step = _timed_step("scientific_reasoning", _step_reasoning)
        result.steps.append(reasoning_step)
        reasoning_output = reasoning_step.output

    # 8. Knowledge Update (Phase 9.0/9.1, optional if memory enabled)
    knowledge_output = None
    if enable_memory and improvement_plan is not None:
        def _step_knowledge_update():
            from app.services.research_memory_reflection_hook import (
                save_reflection_to_memory,
            )
            return save_reflection_to_memory(
                evaluation, improvement_plan,
                intent_id=1,
            )

        knowledge_step = _timed_step("knowledge_update", _step_knowledge_update)
        result.steps.append(knowledge_step)
        knowledge_output = knowledge_step.output

    # 9. Report Generation (Phase 14.0)
    def _step_report():
        from app.services.research_report import generate_research_report
        return generate_research_report(
            user_prompt=user_prompt,
            intent=intent,
            plan=plan,
            execution_result=execution_result,
            evaluation=evaluation,
            improvement_plan=improvement_plan,
            reasoning_output=reasoning_output,
            knowledge_output=knowledge_output,
            memory_hits=memory_hits,
            steps=result.steps,
        )

    report_step = _timed_step("report_generation", _step_report)
    result.steps.append(report_step)
    result.final_report = report_step.output

    result.finished_at = datetime.now(timezone.utc)
    _logger.info(
        "[Phase 14.0 §1] run_research_agent END: success=%s, steps=%d",
        result.success,
        len(result.steps),
    )

    return result