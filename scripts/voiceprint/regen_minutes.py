"""重标发言人后**刷新纪要**, 让 summary/key_points/decisions 与新标签一致。

为什么需要
----------
说话人标签变了, 纪要里的「【某人】」署名就与转录对不上了
(实测: 会议 256 重标后 王天志 1854 → 262 段, 而纪要里大量署名王天志)。

走**生产路径**: `meeting_reprocessing_service.MeetingReprocessingService.execute`
的 `analysis` 阶段 (= `MeetingAnalysisService.analyze_transcript`,
分块分析 + 汇总合并, 支持 3h+ 长会议), 而不是自己另写一套。

用法 (容器内):
    python scripts/voiceprint/regen_minutes.py --meetings 250,255,256
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "/app")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meetings", required=True, help="逗号分隔的会议 id")
    args = ap.parse_args()
    ids = [int(x) for x in args.meetings.split(",") if x.strip()]

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.meeting_reprocessing_service import (
        MeetingReprocessingService, ReprocessRequest,
    )

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        svc = MeetingReprocessingService(db)
        for mid in ids:
            m = (await db.execute(select(Meeting).where(Meeting.id == mid))).scalar_one()
            before = {
                "summary_len": len(m.summary or ""),
                "key_points": len(m.key_points or []),
                "decisions": len(m.decisions or []),
            }
            req = ReprocessRequest(meeting_id=mid, requested_stages=["analysis"],
                                    trigger="voiceprint_relabel_2026-10-30", force=True)
            res = await svc.execute(req)
            await db.refresh(m)
            after = {
                "summary_len": len(m.summary or ""),
                "key_points": len(m.key_points or []),
                "decisions": len(m.decisions or []),
            }
            print("[vp] 会议 %d: 完成阶段=%s 错误=%s 警告=%s" % (
                mid, res.completed_stages, res.errors[:1], res.warnings[:1]), flush=True)
            print("[vp]   纪要规模 %s -> %s" % (before, after), flush=True)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
