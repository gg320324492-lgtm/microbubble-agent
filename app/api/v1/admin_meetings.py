"""会议处理管理 API (管理员)

2026-08-04 Batch C-2: 重跑 + runs + failures + health 端点
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin
from app.models.member import Member
from app.models.meeting import Meeting
from app.models.meeting_processing import MeetingProcessingRun, MeetingProcessingStage
from app.services.meeting_reprocessing_service import (
    MeetingReprocessingService,
    ReprocessRequest,
)

logger = logging.getLogger("microbubble.meeting_admin")
router = APIRouter(prefix="/admin/meetings", tags=["admin-meetings"])


class ReprocessBody(BaseModel):
    stages: List[str]
    force: bool = False
    trigger: Optional[str] = None


@router.post("/{meeting_id}/reprocess")
async def start_reprocess(
    meeting_id: int,
    body: ReprocessBody,
    current_admin: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    try:
        req = ReprocessRequest(
            meeting_id=meeting_id,
            requested_stages=body.stages,
            trigger=body.trigger or f"admin:{current_admin.id}",
            force=body.force,
            initiated_by=current_admin.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    service = MeetingReprocessingService(db)
    result = await service.execute(req)
    return {
        "meeting_id": result.meeting_id,
        "run_id": result.run_id,
        "reused": result.reused,
        "completed_stages": result.completed_stages,
        "skipped_stages": result.skipped_stages,
        "warnings": result.warnings,
        "errors": result.errors,
    }


@router.get("/{meeting_id}/runs")
async def list_runs(
    meeting_id: int,
    limit: int = Query(20, ge=1, le=100),
    _admin: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MeetingProcessingRun)
        .where(MeetingProcessingRun.meeting_id == meeting_id)
        .order_by(desc(MeetingProcessingRun.started_at))
        .limit(limit)
    )
    runs = list(result.scalars().unique().all())
    out = []
    for run in runs:
        stages_out = []
        for stage in run.stages:
            stages_out.append({
                "stage": stage.stage,
                "attempt": stage.attempt,
                "status": stage.status,
                "started_at": stage.started_at.isoformat() if stage.started_at else None,
                "finished_at": stage.finished_at.isoformat() if stage.finished_at else None,
                "latency_ms": stage.latency_ms,
                "error_class": stage.error_class,
                "error_message": stage.error_message,
            })
        out.append({
            "id": run.id,
            "trigger": run.trigger,
            "overall_status": run.overall_status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "warning_count": run.warning_count,
            "error_summary": run.error_summary,
            "pipeline_version": run.pipeline_version,
            "stages": stages_out,
        })
    return {"items": out, "total": len(out)}


@router.get("/failures")
async def list_failures(
    limit: int = Query(50, ge=1, le=200),
    _admin: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(MeetingProcessingRun)
        .where(MeetingProcessingRun.overall_status.in_(["error", "warning"]))
        .order_by(desc(MeetingProcessingRun.started_at))
        .limit(limit)
    )
    runs = list(result.scalars().unique().all())
    items = []
    for run in runs:
        items.append({
            "id": run.id,
            "meeting_id": run.meeting_id,
            "trigger": run.trigger,
            "overall_status": run.overall_status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "warning_count": run.warning_count,
            "error_summary": run.error_summary,
            "pipeline_version": run.pipeline_version,
        })
    return {"items": items, "total": len(items)}


@router.get("/health")
async def health(
    days: int = Query(7, ge=1, le=90),
    _admin: Member = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    cache_key = f"admin:meetings:health:{days}"
    try:
        import redis.asyncio as aioredis
        from app.config import settings
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        cached = await r.get(cache_key)
        if cached:
            await r.aclose()
            return json.loads(cached)
    except Exception as e:
        logger.warning(f"admin meetings health cache read failed: {e}")

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    total = int((await db.execute(
        select(func.count(Meeting.id)).where(Meeting.start_time >= cutoff)
    )).scalar() or 0)
    status_rows = (await db.execute(
        select(Meeting.status, func.count(Meeting.id))
        .where(Meeting.start_time >= cutoff)
        .group_by(Meeting.status)
    )).all()
    by_status = {row[0]: int(row[1]) for row in status_rows}
    quality_rows = (await db.execute(
        select(Meeting.quality_status, func.count(Meeting.id))
        .where(Meeting.start_time >= cutoff, Meeting.quality_status.isnot(None))
        .group_by(Meeting.quality_status)
    )).all()
    by_quality = {row[0]: int(row[1]) for row in quality_rows}
    run_rows = (await db.execute(
        select(MeetingProcessingRun.overall_status, func.count(MeetingProcessingRun.id))
        .where(MeetingProcessingRun.started_at >= cutoff)
        .group_by(MeetingProcessingRun.overall_status)
    )).all()
    by_run_status = {row[0]: int(row[1]) for row in run_rows}
    success_runs = by_run_status.get("success", 0) + by_run_status.get("warning", 0)
    total_runs = sum(by_run_status.values())
    success_rate = round(success_runs / total_runs, 4) if total_runs else 0
    payload = {
        "window_days": days,
        "meetings_total": total,
        "by_status": by_status,
        "by_quality_status": by_quality,
        "processing_runs_total": total_runs,
        "by_run_status": by_run_status,
        "run_success_rate": success_rate,
    }
    try:
        await r.set(cache_key, json.dumps(payload), ex=60)
        await r.aclose()
    except Exception as e:
        logger.warning(f"admin meetings health cache write failed: {e}")
    return payload