"""Persistent de-duplication for Drive combined notifications."""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.drive_notification_dedup import DriveNotificationDedup


def actions_hash(actions: list[str]) -> str:
    canonical = "|".join(sorted(set(actions)))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def should_send(db: AsyncSession, user_id: int, comment_id: int, digest: str) -> bool:
    row = (await db.execute(select(DriveNotificationDedup.id).where(
        DriveNotificationDedup.user_id == user_id,
        DriveNotificationDedup.comment_id == comment_id,
        DriveNotificationDedup.actions_hash == digest,
    ))).first()
    return row is None


async def record_sent(db: AsyncSession, user_id: int, comment_id: int, digest: str) -> None:
    stmt = insert(DriveNotificationDedup).values(
        user_id=user_id, comment_id=comment_id, actions_hash=digest,
    ).on_conflict_do_nothing(index_elements=["user_id", "comment_id", "actions_hash"])
    await db.execute(stmt)
    await db.commit()


async def cleanup_expired(db: AsyncSession, *, now: Optional[datetime] = None) -> int:
    cutoff = (now or datetime.now(timezone.utc)).replace(tzinfo=None) - timedelta(days=7)
    result = await db.execute(delete(DriveNotificationDedup).where(DriveNotificationDedup.sent_at < cutoff))
    await db.commit()
    return result.rowcount or 0
