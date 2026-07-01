"""thumbnail_tasks — v2 网盘 PR5 Celery 缩略图生成任务

异步调用模式 (避免阻塞上传链路):
- POST /upload 完成 → 写 Knowledge 行 → 立刻 fire-and-forget 调 generate_thumbnail_task.delay(...)
- Celery worker 跑缩略图 (Pillow/PyMuPDF/ffmpeg CPU 密集) → 写 thumbnail_path/status
- 前端轮询 /api/v1/drive/files/{id} → 看 thumbnail_status='ready' → 显示 <img>

失败模式:
- Celery 任务抛异常 → 写入 thumbnail_status='failed'
- UI fallback 到 type icon (FileCard 的 fallback 逻辑)
"""
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery import celery_app
from app.config import settings
from app.models.knowledge import Knowledge
from app.services.thumbnail_service import generate_thumbnail, delete_thumbnail

logger = logging.getLogger(__name__)


def _create_session_factory():
    """独立引擎 + NullPool (Celery 跨事件循环范式, 与 chat_history_tasks 同模式)"""
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(name="thumbnail.generate", bind=True, max_retries=2, default_retry_delay=60)
def generate_thumbnail_task(self, file_id: int):
    """Celery 异步生成缩略图

    Args:
        file_id: Knowledge.id (storage_mode='drive')

    流程:
    1. 查 Knowledge 行 (拿 file_path + file_name)
    2. 调 generate_thumbnail (download → PIL → upload thumbnail)
    3. 成功 → update Knowledge.thumbnail_path='thumbnails/{file_id}.jpg', status='ready'
    4. 失败 → update status='failed', retry 最多 2 次
    """
    import asyncio
    from datetime import datetime

    async def _run():
        session_factory = _create_session_factory()
        async with session_factory() as db:
            try:
                stmt = select(Knowledge).where(
                    Knowledge.id == file_id,
                    Knowledge.storage_mode == "drive",
                    Knowledge.deleted_at.is_(None),
                )
                k = (await db.execute(stmt)).scalar_one_or_none()
                if not k:
                    logger.warning(f"[ThumbnailTask] 文件不存在/已删: id={file_id}")
                    return

                if not k.file_path:
                    logger.warning(f"[ThumbnailTask] 文件无 MinIO path: id={file_id}")
                    k.thumbnail_status = "failed"
                    await db.commit()
                    return

                # 已生成过 → 跳过 (幂等)
                if k.thumbnail_status == "ready" and k.thumbnail_path:
                    logger.debug(f"[ThumbnailTask] 已有缩略图: id={file_id}")
                    return

                k.thumbnail_status = "pending"
                await db.commit()

                thumb_obj = await generate_thumbnail(
                    file_id=file_id,
                    source_object_name=k.file_path,
                    file_name=k.file_name or "",
                )

                if thumb_obj:
                    k.thumbnail_path = thumb_obj
                    k.thumbnail_status = "ready"
                    k.thumbnail_generated_at = datetime.utcnow()
                else:
                    k.thumbnail_status = "failed"
                await db.commit()

            except Exception as e:
                logger.error(f"[ThumbnailTask] 异常 file_id={file_id}: {e}", exc_info=True)
                try:
                    await db.rollback()
                    stmt2 = select(Knowledge).where(Knowledge.id == file_id)
                    k2 = (await db.execute(stmt2)).scalar_one_or_none()
                    if k2:
                        k2.thumbnail_status = "failed"
                        await db.commit()
                except Exception:
                    await db.rollback()
                raise

    asyncio.run(_run())


@celery_app.task(name="thumbnail.delete", bind=True, max_retries=1, default_retry_delay=30)
def delete_thumbnail_task(self, thumb_object_name: str):
    """删除缩略图 (文件物理删除时调用)"""
    import asyncio
    asyncio.run(delete_thumbnail(thumb_object_name))