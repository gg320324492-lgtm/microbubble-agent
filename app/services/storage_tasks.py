"""storage_tasks — v2 网盘 PR5 Celery 配额重算 + 分片 session 清理

2 个任务:
1. recalc_user_storage_task — 重算用户 drive_used_bytes (sum file_size WHERE storage_mode='drive' AND deleted_at IS NULL)
2. recalc_all_storage_task — 扫所有用户重算 (Celery beat hourly)
3. cleanup_expired_chunked_sessions_task — 清理 24h 未完成 / aborted 残留 session

触发:
- recalc_user_storage: upload complete / soft-delete / restore 之后 fire-and-forget
- recalc_all_storage: Celery beat 每小时 (防 on-demand 漏算)
- cleanup_expired: Celery beat 每 6h
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy import select, update, func, delete, and_
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.celery import celery_app
from app.config import settings
from app.models.knowledge import Knowledge, ChunkedUploadSession
from app.models.member import Member

logger = logging.getLogger(__name__)


def _create_session_factory():
    """独立引擎 + NullPool (Celery 跨事件循环范式)"""
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@celery_app.task(name="storage.recalc_user", bind=True, max_retries=2, default_retry_delay=30)
def recalc_user_storage_task(self, user_id: int):
    """重算单个用户配额 (PR5)

    流程:
    1. 查 Member (拿 drive_quota_bytes 留作对照, 不改)
    2. SUM(file_size) WHERE created_by=user_id AND storage_mode='drive' AND deleted_at IS NULL
    3. UPDATE members SET drive_used_bytes=sum, drive_quota_updated_at=now()
    """
    import asyncio

    async def _run():
        session_factory = _create_session_factory()
        async with session_factory() as db:
            try:
                user = (await db.execute(select(Member).where(Member.id == user_id))).scalar_one_or_none()
                if not user:
                    logger.warning(f"[StorageTask] 用户不存在: id={user_id}")
                    return

                stmt = select(func.coalesce(func.sum(Knowledge.file_size), 0)).where(
                    and_(
                        Knowledge.created_by == user_id,
                        Knowledge.storage_mode == "drive",
                        Knowledge.deleted_at.is_(None),
                    )
                )
                used = (await db.execute(stmt)).scalar() or 0

                user.drive_used_bytes = int(used)
                user.drive_quota_updated_at = datetime.utcnow()
                await db.commit()

                logger.debug(
                    f"[StorageTask] user_id={user_id} used={used}/{user.drive_quota_bytes}"
                )

            except Exception as e:
                logger.error(f"[StorageTask] 异常 user_id={user_id}: {e}", exc_info=True)
                await db.rollback()
                raise

    asyncio.run(_run())


@celery_app.task(name="storage.recalc_all", bind=True, max_retries=1, default_retry_delay=60)
def recalc_all_storage_task(self):
    """Celery beat: 扫所有用户重算 (防 on-demand 漏算, hourly)"""
    import asyncio

    async def _run():
        session_factory = _create_session_factory()
        async with session_factory() as db:
            try:
                users = (await db.execute(select(Member.id))).scalars().all()
                logger.info(f"[StorageTask] recalc_all {len(users)} users")

                stmt = (
                    select(
                        Knowledge.created_by,
                        func.coalesce(func.sum(Knowledge.file_size), 0).label("used"),
                    )
                    .where(
                        and_(
                            Knowledge.storage_mode == "drive",
                            Knowledge.deleted_at.is_(None),
                            Knowledge.created_by.isnot(None),
                        )
                    )
                    .group_by(Knowledge.created_by)
                )
                rows = (await db.execute(stmt)).all()
                used_map = {row.created_by: int(row.used) for row in rows}

                now = datetime.utcnow()
                for uid, used in used_map.items():
                    await db.execute(
                        update(Member)
                        .where(Member.id == uid)
                        .values(drive_used_bytes=used, drive_quota_updated_at=now)
                    )

                zero_users = [u for u in users if u not in used_map]
                if zero_users:
                    await db.execute(
                        update(Member)
                        .where(Member.id.in_(zero_users))
                        .values(drive_used_bytes=0, drive_quota_updated_at=now)
                    )

                await db.commit()
                logger.info(f"[StorageTask] recalc_all done, {len(used_map)} non-zero users")

            except Exception as e:
                logger.error(f"[StorageTask] recalc_all 异常: {e}", exc_info=True)
                await db.rollback()
                raise

    asyncio.run(_run())


@celery_app.task(name="storage.cleanup_chunked_sessions", bind=True, max_retries=1)
def cleanup_expired_chunked_sessions_task(self):
    """Celery beat: 清理 24h+ 未完成 / aborted 的 chunked_upload_sessions"""
    import asyncio

    async def _run():
        session_factory = _create_session_factory()
        async with session_factory() as db:
            try:
                now = datetime.utcnow()
                stmt = select(ChunkedUploadSession).where(
                    and_(
                        ChunkedUploadSession.status.in_(["active", "aborted"]),
                        ChunkedUploadSession.expires_at < now,
                    )
                )
                expired = (await db.execute(stmt)).scalars().all()
                if not expired:
                    logger.debug("[StorageTask] no expired sessions")
                    return

                logger.info(f"[StorageTask] cleaning {len(expired)} expired sessions")
                ids = [s.id for s in expired]
                await db.execute(
                    delete(ChunkedUploadSession).where(ChunkedUploadSession.id.in_(ids))
                )
                await db.commit()

                from app.services.file_service import file_service
                for s in expired:
                    try:
                        objects = await file_service.list_objects(f"drive-uploads/{s.id}/")
                        for obj in objects:
                            await asyncio.to_thread(file_service.delete_file, obj.object_name)
                    except Exception as e:
                        logger.warning(f"[StorageTask] MinIO cleanup {s.id}: {e}")

                logger.info(f"[StorageTask] cleaned {len(expired)} sessions")

            except Exception as e:
                logger.error(f"[StorageTask] cleanup 异常: {e}", exc_info=True)
                await db.rollback()

    asyncio.run(_run())