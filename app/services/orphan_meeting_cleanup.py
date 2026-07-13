"""孤儿会议清理任务（2026-06-12 防御机制）

解决问题：会议状态卡在 recording，但音频数据已物理丢失（前端刷新/断网），
且用户不再回来点 stop-recording。会议永久占着 ID，Celery 也不会触发后处理。

触发条件（每 10 分钟一次）：
- status = 'recording'
- recording_started_at < NOW() - 1h（启动超过 1h）
- last_chunk_index IS NULL OR last_chunk_index < 0（未收到任何 chunk）

动作：
- 标 status='error', error_reason='录音超时未收到任何音频'
- 推 WS 进度通知（让前端能显示）
- 删 MinIO 上的相关 chunk 文件（如果有）
"""

import asyncio
import logging
from datetime import datetime, timedelta

from app.core.celery_db import create_celery_engine_and_session
from app.core.celery import celery_app

logger = logging.getLogger("microbubble.orphan_cleanup")


@celery_app.task(name="app.services.orphan_meeting_cleanup.cleanup_orphan_meetings")
def cleanup_orphan_meetings():
    """
    Celery beat 调度：每 10 分钟扫一次
    """
    logger.info("开始扫描孤儿会议")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(_scan_and_cleanup())
        logger.info(f"孤儿会议清理完成: {result}")
        return result
    finally:
        loop.close()


async def _scan_and_cleanup() -> dict:
    """异步执行清理逻辑"""
    from sqlalchemy import select
    from app.config import settings
    from app.models.meeting import Meeting
    from app.services.chunked_upload_service import chunked_upload_service
    from app.services.progress_service import update_progress, ProgressStage
    import redis.asyncio as aioredis
    engine, session_factory = create_celery_engine_and_session()
    redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    threshold = datetime.utcnow() - timedelta(hours=1)
    cleaned = []
    errors = []

    try:
        async with session_factory() as db:
            # 找孤儿会议
            r = await db.execute(
                select(Meeting).where(
                    Meeting.status == "recording",
                    Meeting.recording_started_at < threshold,
                    (Meeting.last_chunk_index.is_(None)) | (Meeting.last_chunk_index < 0)
                )
            )
            orphans = r.scalars().all()

            for m in orphans:
                try:
                    # 标 error
                    m.status = "error"
                    m.error_reason = (
                        f"录音超过 1h 未收到任何音频 chunk（last_chunk_index={m.last_chunk_index}），"
                        f"已自动清理"
                    )
                    # 顺手清 MinIO（防孤儿文件）
                    try:
                        deleted = await chunked_upload_service.delete_chunks(m.id)
                        if deleted:
                            logger.info(f"会议 {m.id} 清理 {deleted} 个 chunk")
                    except Exception as e:
                        logger.warning(f"清理会议 {m.id} chunks 失败: {e}")

                    # 推 WS 通知
                    try:
                        await update_progress(
                            m.id, ProgressStage.DONE,
                            detail=f"录音超时已清理: {m.error_reason[:80]}",
                            status="error",
                            redis_override=redis_client,
                        )
                    except Exception as e:
                        logger.warning(f"推 WS 失败: {e}")

                    cleaned.append(m.id)
                except Exception as e:
                    errors.append(f"{m.id}: {e}")

            if cleaned:
                await db.commit()
    finally:
        await redis_client.aclose()
        await engine.dispose()

    return {"cleaned": cleaned, "errors": errors, "count": len(cleaned)}
