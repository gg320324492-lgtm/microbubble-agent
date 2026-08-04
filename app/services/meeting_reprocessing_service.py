"""会议分阶段重跑 service

2026-08-04 Batch C-1: 把脚本里可复用阶段抽到 service
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, desc

from app.models.meeting import Meeting
from app.models.meeting_processing import MeetingProcessingRun, MeetingProcessingStage

logger = logging.getLogger("microbubble.reprocessing")


SUPPORTED_STAGES = {
    "title", "polish", "analysis", "speaker_assignment",
    "transcription", "quality",
}


@dataclass
class ReprocessRequest:
    meeting_id: int
    requested_stages: List[str]
    trigger: str = "admin_reprocess"
    force: bool = False
    initiated_by: Optional[int] = None

    def __post_init__(self):
        unknown = [s for s in self.requested_stages if s not in SUPPORTED_STAGES]
        if unknown:
            raise ValueError(f"unsupported stages: {unknown}")


@dataclass
class ReprocessResult:
    meeting_id: int
    run_id: int
    reused: bool
    skipped_stages: List[str] = field(default_factory=list)
    completed_stages: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    snapshot_path: Optional[str] = None


class MeetingReprocessingService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        result = await self.db.execute(select(Meeting).where(Meeting.id == meeting_id))
        return result.scalar_one_or_none()

    def idempotency_key(self, meeting_id: int, stages: List[str]) -> str:
        from app.services.meeting_processing_service import PIPELINE_VERSION
        payload = f"{meeting_id}|{PIPELINE_VERSION}|{','.join(sorted(stages))}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    async def find_recent_successful_run(
        self, meeting_id: int, stages: List[str], max_age_minutes: int = 60,
    ) -> Optional[MeetingProcessingRun]:
        key = self.idempotency_key(meeting_id, stages)
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=max_age_minutes)
        result = await self.db.execute(
            select(MeetingProcessingRun)
            .where(
                and_(
                    MeetingProcessingRun.meeting_id == meeting_id,
                    MeetingProcessingRun.started_at >= cutoff,
                    MeetingProcessingRun.overall_status.in_(["success", "warning"]),
                )
            )
            .order_by(desc(MeetingProcessingRun.started_at))
            .limit(5)
        )
        for run in result.scalars().unique().all():
            metrics = run.metrics or {}
            if metrics.get("idempotency_key") == key:
                return run
        return None

    async def snapshot_derived_fields(self, meeting: Meeting) -> Dict[str, Any]:
        return {
            "title": meeting.title,
            "summary": meeting.summary,
            "key_points": list(meeting.key_points or []),
            "decisions": list(meeting.decisions or []),
            "transcript_polished": meeting.transcript_polished,
            "speaker_mapping": meeting.speaker_mapping,
            "speaker_stats": meeting.speaker_stats,
            "error_reason": meeting.error_reason,
        }

    def _pipeline_version(self) -> str:
        from app.services.meeting_processing_service import PIPELINE_VERSION
        return PIPELINE_VERSION

    async def start_reprocess_run(self, req: ReprocessRequest) -> tuple[MeetingProcessingRun, bool]:
        existing = await self.find_recent_successful_run(req.meeting_id, req.requested_stages)
        if existing and not req.force:
            return existing, True
        run = MeetingProcessingRun(
            meeting_id=req.meeting_id,
            trigger=req.trigger,
            overall_status="running",
            started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            requested_stages=req.requested_stages,
            pipeline_version=self._pipeline_version(),
            metrics={"idempotency_key": self.idempotency_key(req.meeting_id, req.requested_stages)},
        )
        self.db.add(run)
        await self.db.flush()
        return run, False

    async def execute(self, req: ReprocessRequest) -> ReprocessResult:
        meeting = await self.get_meeting(req.meeting_id)
        if meeting is None:
            return ReprocessResult(
                meeting_id=req.meeting_id, run_id=0, reused=False,
                errors=[f"meeting {req.meeting_id} not found"],
            )
        if "transcription" in req.requested_stages and not req.force:
            return ReprocessResult(
                meeting_id=req.meeting_id, run_id=0, reused=False,
                errors=[
                    "transcription 重跑必须显式 force=true, 否则会破坏原始录音数据; "
                    "推荐先在 audio 备份后单独运行 transcribe_only 工具."
                ],
            )
        run, reused = await self.start_reprocess_run(req)
        if reused:
            return ReprocessResult(
                meeting_id=req.meeting_id, run_id=run.id, reused=True,
                completed_stages=req.requested_stages,
                warnings=[f"reused run {run.id} from {run.started_at.isoformat()}"],
            )
        snapshot = await self.snapshot_derived_fields(meeting)
        run.metrics = {**(run.metrics or {}), "snapshot": snapshot}
        await self.db.commit()

        result = ReprocessResult(
            meeting_id=req.meeting_id, run_id=run.id, reused=False,
            snapshot_path=f"meeting_processing_runs.metrics[{run.id}].snapshot",
        )
        order = ["title", "polish", "speaker_assignment", "analysis", "transcription", "quality"]
        for stage in order:
            if stage not in req.requested_stages:
                continue
            stage_row = MeetingProcessingStage(
                run_id=run.id, stage=stage, attempt=1, status="started",
                started_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            self.db.add(stage_row)
            await self.db.flush()
            try:
                await self._run_stage(stage, meeting, run, stage_row)
                result.completed_stages.append(stage)
            except Exception as e:
                stage_row.status = "error"
                stage_row.error_class = type(e).__name__
                stage_row.error_message = str(e)[:2000]
                stage_row.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
                result.errors.append(f"{stage}: {e}")
                break
            finally:
                await self.db.commit()
        try:
            from app.services.meeting_quality_service import evaluate_meeting
            meeting_dict = {
                "audio_url": meeting.audio_url,
                "audio_duration": meeting.audio_duration,
                "media_duration_seconds": getattr(meeting, "media_duration_seconds", None),
                "transcript": meeting.transcript,
                "transcript_polished": meeting.transcript_polished,
                "summary": meeting.summary,
                "key_points": meeting.key_points,
                "decisions": meeting.decisions,
            }
            qa = evaluate_meeting(meeting_dict)
            meeting.quality_status = qa["status"]
            run.metrics = {**(run.metrics or {}), "quality": qa}
        except Exception as e:
            result.warnings.append(f"quality_evaluate_failed: {e}")
        if result.errors:
            run.overall_status = "error"
        elif result.warnings:
            run.overall_status = "warning"
        else:
            run.overall_status = "success"
        run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        meeting.last_processing_run_id = run.id
        await self.db.commit()
        return result

    async def _run_stage(
        self, stage: str, meeting: Meeting, run: MeetingProcessingRun, stage_row: MeetingProcessingStage,
    ) -> None:
        started = datetime.now(timezone.utc).replace(tzinfo=None)
        if stage == "title":
            await self._stage_title(meeting)
        elif stage == "polish":
            await self._stage_polish(meeting)
        elif stage == "analysis":
            await self._stage_analysis(meeting)
        elif stage == "speaker_assignment":
            await self._stage_speaker(meeting)
        elif stage == "transcription":
            raise NotImplementedError(
                "transcription stage 尚未在 reprocess service 中实现; "
                "请直接调用 scripts/reprocess_meeting.py --stage transcribe"
            )
        elif stage == "quality":
            return
        else:
            raise ValueError(f"unknown stage {stage}")
        stage_row.status = "success"
        stage_row.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
        stage_row.latency_ms = int((stage_row.finished_at - started).total_seconds() * 1000)

    async def _stage_title(self, meeting: Meeting) -> None:
        from app.services.meeting_analysis_service import MeetingAnalysisService
        polished = meeting.transcript_polished or []
        if not polished:
            return
        text = "\n".join(
            f"{seg.get('speaker', '未知')}: {seg.get('text', '')}" for seg in polished[:200]
        )
        svc = MeetingAnalysisService()
        new_title = await svc.generate_title(text)
        if new_title and new_title != "未命名会议":
            meeting.title = new_title

    async def _stage_polish(self, meeting: Meeting) -> None:
        from app.services.meeting_ai_polish import polish_segments_with_lock
        transcript = meeting.transcript or []
        if not transcript:
            return
        segments = [
            {"speaker": s.get("speaker", "未知"), "text": s.get("text", ""), "ts": s.get("start", 0)}
            for s in transcript
        ]
        result = await polish_segments_with_lock(
            meeting.id, segments,
            {"title": meeting.title or "未命名会议", "participants": [], "topic": None, "context": []},
        )
        polished = result.get("polished", []) if isinstance(result, dict) else []
        for i, seg in enumerate(polished):
            if i < len(transcript):
                transcript[i]["text_polished"] = seg.get("text", transcript[i].get("text", ""))
        meeting.transcript_polished = [
            {"speaker": t.get("speaker", "未知"), "text": t.get("text_polished", t.get("text", "")), "ts": t.get("start", 0)}
            for t in transcript
        ]

    async def _stage_analysis(self, meeting: Meeting) -> None:
        from app.services.meeting_analysis_service import MeetingAnalysisService
        polished = meeting.transcript_polished or []
        if not polished:
            return
        text = "\n".join(f"{seg.get('speaker', '未知')}: {seg.get('text', '')}" for seg in polished)
        svc = MeetingAnalysisService()
        result = await svc.analyze_transcript(text)
        meeting.summary = result.get("summary")
        meeting.key_points = result.get("key_points", [])
        meeting.decisions = result.get("decisions", [])
        if result.get("failure"):
            meeting.status = "error"
            meeting.error_reason = f"reprocess analysis failure: {result.get('errors', [{}])[0].get('message', '')[:300]}"
        elif result.get("warning"):
            meeting.status = "completed_with_warnings"
            first_err = (result.get("errors") or [{}])[0]
            meeting.error_reason = f"reprocess analysis partial: {first_err.get('error_class', '?')}: {first_err.get('message', '')[:200]}"
        else:
            meeting.status = "completed"
            meeting.error_reason = None

    async def _stage_speaker(self, meeting: Meeting) -> None:
        from app.services.meeting_analysis_service import MeetingAnalysisService
        polished = meeting.transcript_polished or meeting.transcript or []
        if not polished:
            return
        svc = MeetingAnalysisService()
        try:
            stats = svc.compute_speaker_stats(polished)
            meeting.speaker_stats = stats
        except Exception:
            pass