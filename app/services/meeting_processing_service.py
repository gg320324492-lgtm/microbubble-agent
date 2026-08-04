"""Meeting 处理运行/阶段持久化 service

2026-08-04 Batch B-2:
- 提供 start_run / start_stage / finish_stage / finish_run 接口
- 每个阶段 (download / transcribe / identify / analyze / create_tasks / store / done) 都有持久化记录
- 与 Redis 实时进度协同: Redis 1h TTL 仅供实时 UI, DB 是永久审计
- 提供 list_failures / get_latest_run 给后续管理面板与重跑服务用
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select, and_, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meeting_processing import MeetingProcessingRun, MeetingProcessingStage


PIPELINE_VERSION = "v2026-08-04-batch-A"


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MeetingProcessingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def start_run(
        self,
        meeting_id: int,
        *,
        task_id: Optional[str] = None,
        trigger: str = "initial",
        requested_stages: Optional[list[str]] = None,
    ) -> MeetingProcessingRun:
        run = MeetingProcessingRun(
            meeting_id=meeting_id,
            task_id=task_id,
            trigger=trigger,
            overall_status="running",
            started_at=_now(),
            requested_stages=requested_stages,
            pipeline_version=PIPELINE_VERSION,
        )
        self.db.add(run)
        await self.db.flush()
        return run

    async def start_stage(
        self,
        run: MeetingProcessingRun,
        stage: str,
        attempt: int = 1,
    ) -> MeetingProcessingStage:
        st = MeetingProcessingStage(
            run_id=run.id,
            stage=stage,
            attempt=attempt,
            status="started",
            started_at=_now(),
        )
        self.db.add(st)
        await self.db.flush()
        return st

    async def finish_stage(
        self,
        stage_row: MeetingProcessingStage,
        *,
        status: str,
        error: Optional[BaseException] = None,
        error_code: Optional[str] = None,
        retryable: Optional[bool] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        finished = _now()
        stage_row.finished_at = finished
        stage_row.latency_ms = max(
            0,
            int((finished - stage_row.started_at).total_seconds() * 1000),
        )
        stage_row.status = status
        stage_row.metrics = metrics or stage_row.metrics
        if error is not None:
            stage_row.error_class = type(error).__name__
            stage_row.error_code = error_code
            stage_row.error_message = str(error)[:2000]
        if retryable is not None:
            stage_row.retryable = retryable

    async def finish_run(
        self,
        run: MeetingProcessingRun,
        *,
        overall_status: str,
        warning_count: int = 0,
        error_summary: Optional[str] = None,
        metrics: Optional[dict[str, Any]] = None,
    ) -> None:
        run.overall_status = overall_status
        run.warning_count = warning_count
        run.error_summary = error_summary
        run.metrics = metrics or run.metrics
        run.finished_at = _now()

    async def attach_to_meeting(self, meeting_id: int, run_id: int) -> None:
        """把最新一次运行 ID 回写到 meeting.last_processing_run_id"""
        from sqlalchemy import update
        from app.models.meeting import Meeting
        await self.db.execute(
            update(Meeting)
            .where(Meeting.id == meeting_id)
            .values(last_processing_run_id=run_id)
        )

    async def get_latest_run(self, meeting_id: int) -> Optional[MeetingProcessingRun]:
        result = await self.db.execute(
            select(MeetingProcessingRun)
            .where(MeetingProcessingRun.meeting_id == meeting_id)
            .order_by(desc(MeetingProcessingRun.started_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_failures(self, *, limit: int = 50) -> list[MeetingProcessingRun]:
        result = await self.db.execute(
            select(MeetingProcessingRun)
            .where(MeetingProcessingRun.overall_status.in_(["error", "warning"]))
            .order_by(desc(MeetingProcessingRun.started_at))
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def compute_overall_status(self, run: MeetingProcessingRun) -> str:
        """根据阶段错误数 + warning 数推导 run 整体状态"""
        stages = run.stages or []
        if not stages:
            return run.overall_status
        errors = sum(1 for s in stages if s.status == "error")
        warnings = sum(1 for s in stages if s.status in ("warning", "skipped"))
        if errors:
            return "error"
        if warnings:
            return "warning"
        return "success"