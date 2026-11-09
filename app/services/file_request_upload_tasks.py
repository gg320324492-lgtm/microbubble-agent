"""Celery wrapper: 外部收件分片会话的过期清理 (Alembic 150)。

为什么**必须**有这条清理
------------------------
10 GiB 级的 staging 片躺在 MinIO 里，而外部用户**很可能传一半就关页面**。
只靠 complete/abort 两个显式路径回收，留下的就是"用户随手一关 ⇒ 几十 GB
永久占盘"，而这台机器的 Docker 数据盘就是本项目自己的 E 盘。

⚠️ 类 20.219 的硬纪律：本模块定义 @celery_app.task 之后**必须同时**进
`app/core/celery.py` 的 `celery_app.conf.imports` 列表，否则 worker 会以
"Received unregistered task" 静默丢弃 —— 本仓已有 4 例同型事故
（meeting_chunk / drive_index / auto_rag_tasks / rag_eval_runner），
症状都是"功能看起来在、实际从未执行"，而且**不报错**。
"""


import asyncio
import logging

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.services.file_request_upload_service import file_request_upload_service

logger = logging.getLogger("microbubble.file_request_upload_tasks")


@celery_app.task(
    name="app.services.file_request_upload_tasks.cleanup_file_request_uploads_task",
    bind=True,
    max_retries=1,
    default_retry_delay=60,
)
def cleanup_file_request_uploads_task(self):
    """回收过期的匿名收件会话及其 MinIO staging 片。"""

    async def _run():
        engine, session_factory = create_celery_engine_and_session()
        try:
            async with session_factory() as db:
                return await file_request_upload_service.cleanup_expired(db)
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        logger.info("File-request chunk cleanup finished: %s", result)
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error("File-request chunk cleanup failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc)
