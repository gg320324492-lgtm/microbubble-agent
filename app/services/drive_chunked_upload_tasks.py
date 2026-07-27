"""Celery wrapper for Alembic-080 Drive chunked upload cleanup."""

import asyncio
import logging

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.services.drive_chunked_upload_service import cleanup_expired_uploads

logger = logging.getLogger("microbubble.drive_chunked_upload_tasks")


@celery_app.task(
    name="app.services.drive_chunked_upload_tasks.cleanup_expired_uploads_task",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_expired_uploads_task(self):
    """Hourly cleanup for 24-hour upload sessions and their MinIO chunks."""

    async def _run():
        engine, session_factory = create_celery_engine_and_session()
        try:
            async with session_factory() as db:
                return await cleanup_expired_uploads(db)
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        logger.info("Drive chunk cleanup finished: %s", result)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error("Drive chunk cleanup failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
