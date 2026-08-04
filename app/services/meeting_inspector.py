"""会议健康巡检任务

2026-08-04 Batch D-4: 扫会议表找假成功/卡住/孤儿, 仅报告不擅自修复
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, or_, func

from app.core.celery import celery_app
from app.core.celery_db import create_celery_engine_and_session
from app.models.meeting import Meeting

logger = logging.getLogger("microbubble.meeting_inspector")


@celery_app.task(name="app.services.meeting_inspector.scan_meeting_health")
def scan_meeting_health(window_days: int = 7):
    import asyncio
    return asyncio.run(_async_scan(window_days))


async def _async_scan(window_days: int):
    engine, session_factory = create_celery_engine_and_session()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=window_days)
    report = {
        "window_days": window_days,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "findings": {},
    }
    try:
        async with session_factory() as db:
            empty_minutes = (await db.execute(
                select(func.count(Meeting.id))
                .where(
                    Meeting.start_time >= cutoff,
                    Meeting.status == "completed",
                    or_(Meeting.summary.is_(None), Meeting.summary == "", Meeting.key_points.is_(None)),
                )
            )).scalar() or 0
            report["findings"]["completed_but_minutes_empty"] = int(empty_minutes)

            stuck_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
            stuck_processing = (await db.execute(
                select(func.count(Meeting.id))
                .where(Meeting.status == "processing", Meeting.start_time <= stuck_cutoff)
            )).scalar() or 0
            report["findings"]["processing_stuck_over_2h"] = int(stuck_processing)

            quality_fail = (await db.execute(
                select(func.count(Meeting.id))
                .where(
                    Meeting.start_time >= cutoff,
                    Meeting.quality_status == "fail",
                    Meeting.status == "completed",
                )
            )).scalar() or 0
            report["findings"]["quality_fail_but_status_completed"] = int(quality_fail)

            err_but_done = (await db.execute(
                select(func.count(Meeting.id))
                .where(
                    Meeting.start_time >= cutoff,
                    Meeting.error_reason.isnot(None),
                    Meeting.status == "completed",
                )
            )).scalar() or 0
            report["findings"]["error_reason_but_completed"] = int(err_but_done)

            orphan = (await db.execute(
                select(func.count(Meeting.id))
                .where(
                    Meeting.start_time >= cutoff,
                    Meeting.audio_url.is_(None),
                    Meeting.status.in_(["processing", "completed"]),
                )
            )).scalar() or 0
            report["findings"]["orphan_no_audio_url"] = int(orphan)
    finally:
        await engine.dispose()

    if any(v > 0 for v in report["findings"].values()):
        logger.warning(f"meeting inspector: {report}")
    else:
        logger.info(f"meeting inspector clean: {report}")
    return report