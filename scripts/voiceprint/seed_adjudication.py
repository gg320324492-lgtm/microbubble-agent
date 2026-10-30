"""把人工确认的台账区间播种进 `meeting_speaker_adjudications`。

为什么需要
----------
台账里的"人耳确认的说话人"只存在于**转录字段**里 ⇒ 一旦重跑说话人识别就会被覆盖
(类 20.244 坑②)。而 `meeting_speaker_adjudications` 是**独立表**, 只靠
(meeting_id, 时间区间) 与音频绑定 ⇒ 转录怎么重建都不影响。

⭐ **裁决在最终赋值处优先于聚类投票**(类 20.244 坑① 的修复:
`app/services/post_meeting_tasks.py` 阶段 2.9 会再查一次裁决表) ⇒
人工真值以后重跑也保得住。

⚠️ **区间要按「逐窗切分后」的精确区间给, 不能整块给** ——
整块会把区间内导师的插话也记成汇报人(实测会议 262 的第三次汇报块内
有 40 窗/400 秒是王天志的追问)。

用法(容器内):
    python scripts/voiceprint/seed_adjudication.py --meeting 262 --ranges /tmp/vp/adj.json

ranges.json:
    [{"s": 0.0, "e": 398.0, "speaker": "陈天祥", "note": "..."}]
"""
import argparse
import asyncio
import json
import sys

sys.path.insert(0, "/app")


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--ranges", required=True, help="JSON: [{s,e,speaker,note}]")
    ap.add_argument("--source", default="commander-listening")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ranges = json.load(open(args.ranges, encoding="utf-8"))

    from sqlalchemy import select, text as sqlt
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication
    from app.services.speaker_adjudication_service import get_adjudications

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        have = await get_adjudications(db, args.meeting)
        print("[vp] 会议%d 裁决表原有 %d 条" % (args.meeting, len(have)))
        exist = {(round(float(a.seg_start), 2), round(float(a.seg_end), 2)) for a in have}

        to_add = []
        for r in ranges:
            s, e = round(float(r["s"]), 2), round(float(r["e"]), 2)
            if (s, e) in exist:
                print("[vp]   已存在, 跳过: %s - %s %s" % (s, e, r["speaker"]))
                continue
            to_add.append((s, e, r["speaker"], r.get("note", "")))

        if args.dry_run:
            print("[vp] dry-run: 将新增 %d 条" % len(to_add))
            for s, e, spk, note in to_add:
                print("   %9.2f - %9.2f  %s" % (s, e, spk))
            return

        if to_add:
            bk = "meeting_%d_backup_pre_adjudication_seed" % args.meeting
            await db.execute(sqlt("DROP TABLE IF EXISTS %s" % bk))
            await db.execute(sqlt("CREATE TABLE %s AS SELECT * FROM meeting_speaker_adjudications "
                                 "WITH NO DATA" % bk))
            await db.execute(sqlt("INSERT INTO %s SELECT * FROM meeting_speaker_adjudications "
                                 "WHERE meeting_id = :i" % bk), {"i": args.meeting})
            await db.commit()

        for s, e, spk, note in to_add:
            db.add(MeetingSpeakerAdjudication(
                meeting_id=args.meeting, seg_start=s, seg_end=e, seg_index=None,
                speaker=spk, source=args.source, note=note))
        await db.commit()
        now = await get_adjudications(db, args.meeting)
        print("[vp] 新增 %d 条, 现共 %d 条(备份表 %s)" % (
            len(to_add), len(now), "meeting_%d_backup_pre_adjudication_seed" % args.meeting))
        for a in now:
            print("   %9.2f - %9.2f  %s" % (a.seg_start, a.seg_end, a.speaker))


if __name__ == "__main__":
    asyncio.run(main())
