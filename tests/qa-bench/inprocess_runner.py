"""In-process qa-bench runner skeleton.

W68 Route B-1 design only. Lives under tests/: no production change. The
real implementation lands in W68 B-2 once the design is approved.
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Mapping, Sequence


@dataclass(slots=True)
class VerdictResult:
    """One benchmark verdict plus enough metadata for report generation."""

    question_id: str
    question: str
    answer: str = ""
    verdict: str = "error"
    score: float | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _question_fields(question: Any, index: int) -> tuple[str, str, dict[str, Any]]:
    if isinstance(question, Mapping):
        text = str(question.get("question") or question.get("prompt") or question.get("text") or "")
        identifier = str(question.get("id") or question.get("question_id") or index)
        return identifier, text, dict(question)
    return str(index), str(question), {}


def _event_text(event: Any) -> str | None:
    """Return the text payload for increment-style delta events."""
    if isinstance(event, Mapping):
        event_type = event.get("type")
        if event_type in {"text_delta", "content_delta"}:
            delta = event.get("text") or event.get("delta")
            if isinstance(delta, str):
                return delta
        if event_type == "done":
            content = event.get("content")
            if isinstance(content, str):
                return content
        return None
    event_type = getattr(event, "type", None)
    if event_type in {"text_delta", "content_delta"}:
        text = getattr(event, "text", None)
        if isinstance(text, str):
            return text
    if event_type == "done":
        content = getattr(event, "content", None)
        if isinstance(content, str):
            return content
    return None


def _is_done(event: Any) -> bool:
    if isinstance(event, Mapping):
        return event.get("type") == "done"
    return getattr(event, "type", None) == "done"


async def _collect_stream(stream: AsyncIterator[Any] | Any) -> str:
    """Collect increment text from a ChatEngine stream without HTTP."""
    if not hasattr(stream, "__aiter__"):
        return ""
    chunks: list[str] = []
    async for event in stream:
        text = _event_text(event)
        if text is not None:
            chunks.append(text)
        if _is_done(event):
            break
    return "".join(chunks)


async def run_inprocess(questions: Sequence[Any], db_url: str) -> list[VerdictResult]:
    """Run benchmark questions through ChatEngine directly.

    The eventual implementation must create one test-scoped async session,
    inject it into ``ChatEngine.synthesize_stream(..., db=session)``, and use
    an AsyncMock LLM/client where network-backed model calls are not desired.
    No TestClient request or uvicorn process belongs in this function.
    ``db_url`` is deliberately explicit so CI can point at its disposable
    PostgreSQL service and never accidentally use a developer database.
    """
    if not db_url:
        raise ValueError("db_url is required for the in-process benchmark")

    # Imports stay inside the coroutine.  This follows the cross-event-loop
    # rule: clients, pools, and sessions must be constructed on this loop.
    try:
        from app.agent.chat_engine import ChatEngine  # noqa: WPS433 (deferred import on purpose)
    except ImportError as exc:  # pragma: no cover - helpful skeleton failure
        raise RuntimeError("qa-bench requires the application dependencies") from exc

    engine = ChatEngine(llm=None)
    results: list[VerdictResult] = []

    # Serial execution is the safe default while DB-session and Redis sharing
    # semantics are measured.  A later batch may add bounded concurrency with
    # one session/client context per worker.
    for index, raw_question in enumerate(questions):
        question_id, text, metadata = _question_fields(raw_question, index)
        result = VerdictResult(
            question_id=question_id,
            question=text,
            metadata=metadata,
        )
        try:
            messages = [{"role": "user", "content": text}]
            stream = engine.synthesize_stream(
                messages=messages,
                system=os.getenv("QA_BENCH_SYSTEM", ""),
                user_id=None,
                db=None,  # replaced with the test-scoped AsyncSession in batch 2
                session_id=f"qa-bench-{question_id}",
            )
            result.answer = await _collect_stream(stream)
            result.verdict = "pass" if result.answer else "empty"
        except asyncio.CancelledError:
            result.error = "CancelledError"
            result.verdict = "error"
            results.append(result)
            raise
        except Exception as exc:  # keep one bad question from hiding others
            result.error = f"{type(exc).__name__}: {exc}"
            result.verdict = "error"
        results.append(result)
    return results


__all__ = ["VerdictResult", "run_inprocess"]
