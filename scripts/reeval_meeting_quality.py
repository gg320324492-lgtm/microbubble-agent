#!/usr/bin/env python
"""重算存量会议的 `meetings.quality_status` 并回写(带备份)。

为什么需要
----------
`quality_status` 是**落库那一刻**的质量评估结果 —— 之后任何人手工改过转录
(补空档 / 清控制 token / 重标发言人 / 修时长字段), **这个字段都不会跟着变**
⇒ 它开始说谎(类 20.220)。

实测(2026-10-30): 会议 259 的转录空档已补齐、质量门重算是 pass,
但库里 `quality_status` 仍是 fail ⇒ 用户在列表里看到的仍是"失败"。

判据与生产一致
--------------
复刻 `post_meeting_tasks.py` 的调用形状:
  - `audio_gap_evidence` 从**该会议最近一次 processing run** 的
    `downloading_audio` 阶段 metrics 里取(音频证据是音频的事实, 转录改了它也不变);
  - `ai_polish_skipped = not settings.MEETING_AI_POLISH_ENABLED`;
  - 结果写 `meetings.quality_status`, 并把 metrics/issues 写回 run.metrics
    (生产里 issue_codes 也只存在 run.metrics 里)。

用法 (容器内):
    python scripts/reeval_meeting_quality.py --dry-run
    python scripts/reeval_meeting_quality.py --write --meetings 250,256
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", default="", help="逗号分隔; 留空 = 全部有转录的会议")
    ap.add_argument("--write", action="store_true", help="真写库(默认只报告)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    from sqlalchemy import select, text as sqlt
    from app.config import settings
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.meeting_processing import MeetingProcessingRun, MeetingProcessingStage
    from app.services.meeting_quality_service import evaluate_meeting

    ids = [int(x) for x in args.meetings.split(",") if x.strip()]
    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        stmt = select(Meeting).where(Meeting.transcript.isnot(None)).order_by(Meeting.id)
        if ids:
            stmt = stmt.where(Meeting.id.in_(ids))
        meetings = (await db.execute(stmt)).scalars().all()

        changed = 0
        for m in meetings:
            # 最近一次 run + 其 audio_gap_evidence
            run = (await db.execute(
                select(MeetingProcessingRun)
                .where(MeetingProcessingRun.meeting_id == m.id)
                .order_by(MeetingProcessingRun.started_at.desc(), MeetingProcessingRun.id.desc())
                .limit(1))).scalars().first()
            gap_ev = {}
            if run is not None:
                gap_ev = dict((run.metrics or {}).get("audio_gap_evidence") or {})
                if not gap_ev:
                    stage = (await db.execute(
                        select(MeetingProcessingStage)
                        .where(MeetingProcessingStage.run_id == run.id,
                               MeetingProcessingStage.stage == "downloading_audio")
                        .order_by(MeetingProcessingStage.started_at.desc())
                        .limit(1))).scalars().first()
                    if stage is not None:
                        gap_ev = dict((stage.metrics or {}).get("audio_gap_evidence") or {})

            md = {
                "audio_url": m.audio_url,
                "audio_duration": m.audio_duration,
                "media_duration_seconds": getattr(m, "media_duration_seconds", None),
                "transcript": m.transcript,
                "transcript_polished": m.transcript_polished,
                "ai_polish_skipped": not settings.MEETING_AI_POLISH_ENABLED,
                "summary": m.summary,
                "key_points": m.key_points,
                "decisions": m.decisions,
                "audio_gap_evidence": gap_ev,
            }
            qa = evaluate_meeting(md)
            old = m.quality_status
            # ⚠️ **老会议的老转录没有 start/end** ⇒ 转录总时长恒为 0 ⇒ 覆盖率恒为 0%
            #   ⇒ `transcript_low_coverage` 是**假警报**(实测 64/68/70/71/83/95/120/121/135
            #   九场全是这一种, 类 20.220: 指标在说谎)。
            #   ⇒ 这类**不写库**, 只报告 —— 宁可留着旧的 pass, 也不要写一个假的 fail。
            has_ts = any(
                (float(s.get("end") or 0) - float(s.get("start") or 0)) > 0
                for s in (m.transcript or []))
            fake_coverage = ("transcript_low_coverage" in qa["issue_codes"] and not has_ts)
            if fake_coverage:
                print("[q] 会议%-5d %s → %s   **跳过**: 转录无 start/end ⇒ 覆盖率假警报"
                      % (m.id, old, qa["status"]), flush=True)
                continue
            if old != qa["status"]:
                changed += 1
                print("[q] 会议%-5d %s → %s   issue=%s" % (
                    m.id, old, qa["status"], qa["issue_codes"]), flush=True)
            else:
                print("[q] 会议%-5d %s (不变)  issue=%s" % (
                    m.id, old, qa["issue_codes"]), flush=True)

            if args.write and old != qa["status"]:
                bk = "meeting_%d_backup_pre_quality_reeval" % m.id
                await db.execute(sqlt("DROP TABLE IF EXISTS %s" % bk))
                await db.execute(sqlt("CREATE TABLE %s AS SELECT * FROM meetings WITH NO DATA" % bk))
                await db.execute(sqlt("INSERT INTO %s SELECT * FROM meetings WHERE id = :i" % bk),
                                 {"i": m.id})
                m.quality_status = qa["status"]
                if run is not None:
                    run.metrics = {**(run.metrics or {}),
                                   "quality": qa["metrics"],
                                   "quality_issues": qa["issues"]}
                await db.commit()
        print("[q] 共 %d 场, 状态会变 %d 场%s" % (
            len(meetings), changed, " (已写库)" if args.write else " (仅报告)"))


if __name__ == "__main__":
    asyncio.run(main())
