"""Celery heartbeat for analytics data-source health monitoring.

W86 mini-11 B: production clients stopped producing ``search_logs`` rows for
28 days.  This heartbeat makes the ingestion path observable without counting
synthetic rows in retrieval-quality metrics.
"""
import asyncio
import logging
from datetime import datetime, timezone

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.search_log import SearchLog

logger = logging.getLogger("microbubble.analytics_heartbeat")


@celery_app.task(name="app.services.analytics_tasks.analytics_heartbeat")
def analytics_heartbeat():
    """Write one ``system_metrics`` heartbeat every five minutes."""

    async def _write():
        engine, session_factory = create_celery_engine_and_session()
        try:
            async with session_factory() as db:
                log = SearchLog(
                    user_id=1,
                    query="system_health_check",
                    top_ids=[],
                    clicked_id=None,
                    click_position=None,
                    embedding_model="Qwen/Qwen3-Embedding-0.6B",
                    source="system_metrics",
                    created_at=datetime.now(timezone.utc),
                )
                db.add(log)
                await db.commit()
                logger.info("analytics system_metrics heartbeat written")
                return {"status": "ok", "source": "system_metrics"}
        finally:
            await engine.dispose()

    try:
        return asyncio.run(_write())
    except Exception as exc:
        logger.error("analytics heartbeat failed: %s", exc, exc_info=True)
        return {"status": "error", "error": str(exc)}
