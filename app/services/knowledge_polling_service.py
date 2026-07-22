"""Periodic processor for knowledge rows left in ``analysis_status='pending'``.

The processor deliberately claims only a small ordered batch.  A failed item is
rolled back and kept pending so a later Celery beat run can retry it.  Celery
uses a dedicated NullPool engine because its ``asyncio.run`` loop must not
reuse FastAPI's async database connections.
"""
import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.knowledge import Knowledge
from app.services.llm_analysis_service import llm_analysis_service

logger = logging.getLogger("microbubble.knowledge_polling")

DEFAULT_LIMIT = 50
MAX_LIMIT = 50
MAX_ATTEMPTS = 3
BACKOFF_BASE_SECONDS = 0.25


def _bounded_limit(limit: int) -> int:
    """Apply the hard safety cap while rejecting meaningless limits."""
    if limit <= 0:
        return 0
    return min(limit, MAX_LIMIT)


def _quality_score(analysis: Dict[str, Any]) -> float:
    """Derive a stable 0..1 completeness score from the analysis payload."""
    signals = (
        bool(analysis.get("summary")),
        bool(analysis.get("category")),
        bool(analysis.get("tags")),
        bool(analysis.get("key_concepts")),
        bool(analysis.get("related_topics")),
    )
    return sum(signals) / len(signals)


def _apply_analysis(knowledge: Knowledge, analysis: Dict[str, Any]) -> None:
    """Copy supported analysis fields without overwriting useful values."""
    for field in (
        "summary",
        "category",
        "topic",
        "tags",
        "key_concepts",
        "entities",
        "related_topics",
        "knowledge_type",
    ):
        value = analysis.get(field)
        if value:
            setattr(knowledge, field, value)
    knowledge.quality_score = _quality_score(analysis)
    knowledge.analysis_status = "done"


async def _analyze_with_backoff(
    knowledge: Knowledge,
    *,
    sleep=asyncio.sleep,
) -> Dict[str, Any]:
    """Analyze one row, retrying transient failures with exponential backoff."""
    last_error: Optional[Exception] = None
    for attempt in range(MAX_ATTEMPTS):
        try:
            analysis = await llm_analysis_service.analyze_content(
                knowledge.title, knowledge.content
            )
            if not isinstance(analysis, dict) or not analysis.get("summary"):
                raise ValueError("knowledge analysis returned no summary")
            return analysis
        except Exception as exc:  # retry boundary intentionally broad
            last_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                await sleep(BACKOFF_BASE_SECONDS * (2 ** attempt))
    assert last_error is not None
    raise last_error


async def process_pending_knowledge(
    limit: int = DEFAULT_LIMIT,
    *,
    db: Optional[AsyncSession] = None,
    sleep=asyncio.sleep,
) -> dict:
    """Process up to 50 pending knowledge rows and return queue statistics.

    ``db`` is injectable for unit tests and callers that already own a session.
    Without it, a dedicated Celery-safe engine/session is created and disposed.
    Failed rows remain pending; successful rows are committed individually so a
    later failure cannot undo earlier work.
    """
    bounded = _bounded_limit(limit)
    owns_session = db is None
    engine = None
    if owns_session:
        engine, session_factory = create_celery_engine_and_session()
        db = session_factory()

    processed = succeeded = failed = 0
    try:
        if bounded:
            result = await db.execute(
                select(Knowledge)
                .where(Knowledge.analysis_status == "pending")
                .order_by(Knowledge.created_at.asc(), Knowledge.id.asc())
                .limit(bounded)
            )
            pending = list(result.scalars().all())
        else:
            pending = []

        for knowledge in pending:
            # Defensive against stale/mock query results and concurrent updates.
            if knowledge.analysis_status != "pending":
                continue
            processed += 1
            try:
                analysis = await _analyze_with_backoff(knowledge, sleep=sleep)
                _apply_analysis(knowledge, analysis)
                await db.commit()
                succeeded += 1
            except Exception as exc:
                failed += 1
                await db.rollback()
                knowledge.analysis_status = "pending"
                logger.warning(
                    "pending knowledge analysis failed id=%s: %s",
                    knowledge.id,
                    exc,
                )

        remaining_result = await db.execute(
            select(func.count(Knowledge.id)).where(
                Knowledge.analysis_status == "pending"
            )
        )
        remaining = int(remaining_result.scalar_one() or 0)
        return {
            "processed": processed,
            "succeeded": succeeded,
            "failed": failed,
            "remaining": remaining,
        }
    finally:
        if owns_session:
            await db.close()
            await engine.dispose()


@celery_app.task(name="app.services.knowledge_polling_service.process_pending_knowledge_task")
def process_pending_knowledge_task(limit: int = DEFAULT_LIMIT) -> dict:
    """Celery wrapper; individual item failures are reported in returned stats."""
    return asyncio.run(process_pending_knowledge(limit=limit))
