"""Celery wrapper for Alembic-080 Drive chunked upload cleanup."""
# ==========================================================================
# 分片上传有四个相关文件, 别误判为重复代码:
#   chunked_upload_service           会议录音边录边传 (本地临时文件 + ffmpeg 合并)
#   generic_chunked_upload_service   通用分片上传 (不持久化会话, 无 resume)
#   drive_chunked_upload_service     网盘分片 (PG 表 + sha256 + resume + 过期清理)
#   drive_chunked_upload_tasks       Celery wrapper, 仅调度 cleanup
# 2026-09-30 已核实"合并四件套"的建议不成立 (存储契约不同), 见
# app/services/CHUNKED_UPLOAD.md
# ==========================================================================


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
