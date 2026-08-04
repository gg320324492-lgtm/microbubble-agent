#!/usr/bin/env python3
"""会议 242 受控恢复脚本

2026-08-04 Batch C-4: 默认 dry-run, 不擅自放宽声纹阈值, 354s gap 仅记录 evidence
"""
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.meeting import Meeting
from app.services.meeting_quality_service import evaluate_meeting, sanitize_text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("recover_meeting_242")


async def _export_snapshot(meeting):
    return {
        "id": meeting.id, "title": meeting.title, "summary": meeting.summary,
        "key_points": list(meeting.key_points or []), "decisions": list(meeting.decisions or []),
        "speaker_stats": meeting.speaker_stats,
        "transcript_segments_count": len(meeting.transcript or []),
        "transcript_polished_count": len(meeting.transcript_polished or []),
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


async def _sanitize_transcript_in_place(meeting):
    cleaned = 0
    for seg in meeting.transcript or []:
        text = seg.get("text", "")
        new_text = sanitize_text(text)
        if new_text != text:
            cleaned += 1
            seg["text"] = new_text
        ptext = seg.get("text_polished", "")
        new_ptext = sanitize_text(ptext)
        if new_ptext != ptext:
            cleaned += 1
            seg["text_polished"] = new_ptext
    for seg in meeting.transcript_polished or []:
        text = seg.get("text", "")
        new_text = sanitize_text(text)
        if new_text != text:
            cleaned += 1
            seg["text"] = new_text
    return cleaned


async def _recompute_speaker_stats(meeting):
    from app.services.meeting_analysis_service import MeetingAnalysisService
    polished = meeting.transcript_polished or meeting.transcript or []
    if not polished:
        return None
    return MeetingAnalysisService().compute_speaker_stats(polished)


async def _evaluate_quality(meeting):
    return evaluate_meeting({
        "audio_url": meeting.audio_url, "audio_duration": meeting.audio_duration,
        "media_duration_seconds": getattr(meeting, "media_duration_seconds", None),
        "transcript": meeting.transcript, "transcript_polished": meeting.transcript_polished,
        "summary": meeting.summary, "key_points": meeting.key_points, "decisions": meeting.decisions,
    })


async def _recompute_title_and_analysis(meeting):
    from app.services.meeting_analysis_service import MeetingAnalysisService
    polished = meeting.transcript_polished or meeting.transcript or []
    text = "\n".join(f"{seg.get('speaker', '未知')}: {seg.get('text', '')}" for seg in polished)
    if not text.strip():
        return {"title": None, "summary": None, "key_points": [], "decisions": [], "errors": ["no transcript text"]}
    svc = MeetingAnalysisService()
    new_title = await svc.generate_title(text)
    result = await svc.analyze_transcript(text, speaker_mapping=meeting.speaker_mapping)
    return {
        "title": new_title if new_title != "未命名会议" else None,
        "summary": result.get("summary"), "key_points": result.get("key_points", []),
        "decisions": result.get("decisions", []),
        "success": result.get("success"), "failure": result.get("failure"),
        "warning": result.get("warning"), "errors": result.get("errors", []),
    }


async def run(args):
    db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
    engine = create_async_engine(db_url, poolclass=NullPool)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        meeting = (await db.execute(select(Meeting).where(Meeting.id == args.meeting))).scalar_one_or_none()
        if meeting is None:
            log.error("meeting %s not found", args.meeting)
            return 1

        snapshot = await _export_snapshot(meeting)
        snap_path = f"logs/meeting-{args.meeting}-snapshot-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        os.makedirs("logs", exist_ok=True)
        with open(snap_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        log.info("snapshot exported: %s", snap_path)

        cleaned = await _sanitize_transcript_in_place(meeting)
        log.info("control token segments cleaned: %s", cleaned)

        new_stats = await _recompute_speaker_stats(meeting)
        log.info("speaker_stats recomputed: %s entries", len(new_stats or []))

        if not args.skip_llm:
            analysis = await _recompute_title_and_analysis(meeting)
            log.info("title/analysis: success=%s failure=%s warning=%s",
                     analysis.get("success"), analysis.get("failure"), analysis.get("warning"))
        else:
            analysis = {"title": None, "summary": None, "key_points": [], "decisions": [], "errors": ["--skip-llm"]}

        meeting.speaker_stats = new_stats or meeting.speaker_stats
        qa = await _evaluate_quality(meeting)
        log.info("quality: %s", qa["status"])

        print(json.dumps({
            "meeting_id": meeting.id, "snapshot_path": snap_path,
            "cleaned_segments": cleaned,
            "new_title": analysis.get("title"),
            "new_summary": analysis.get("summary"),
            "new_key_points": analysis.get("key_points"),
            "new_decisions": analysis.get("decisions"),
            "analysis_success": analysis.get("success"),
            "analysis_failure": analysis.get("failure"),
            "analysis_warning": analysis.get("warning"),
            "analysis_errors": analysis.get("errors"),
            "quality_status": qa["status"],
            "quality_issues": qa["issues"],
            "dry_run": args.dry_run,
        }, ensure_ascii=False, indent=2))

        if args.dry_run:
            log.info("--dry-run, nothing written")
            await db.rollback()
        else:
            if analysis.get("title"):
                meeting.title = analysis["title"]
            meeting.summary = analysis.get("summary")
            meeting.key_points = analysis.get("key_points", [])
            meeting.decisions = analysis.get("decisions", [])
            meeting.quality_status = qa["status"]
            if analysis.get("failure"):
                meeting.status = "error"
                meeting.error_reason = f"recover-242 analysis failure: {analysis.get('errors', [{}])[0].get('message', '')[:300]}"
            elif analysis.get("warning"):
                meeting.status = "completed_with_warnings"
            else:
                meeting.status = "completed"
                meeting.error_reason = None
            await db.commit()
            log.info("meeting %s updated: status=%s quality_status=%s",
                     meeting.id, meeting.status, meeting.quality_status)

    await engine.dispose()
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, default=242)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", dest="dry_run", action="store_false")
    parser.add_argument("--skip-llm", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args)))


if __name__ == "__main__":
    main()