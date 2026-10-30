"""全库会议转录空档体检 —— 找出会漏抓「整段发言」的会议。

判据(与 app/services/meeting_quality_service.py 的 max_gap 同口径):
  gap = transcript[i].start - transcript[i-1].end, 逐段(数组序)算, 取最大与累计。
阈值: max_gap_fail_sec=180(fail) / max_gap_warn_sec=60(warn) / 统计 >5s 的个数。

输出: 会议 id / 标题 / 段数 / 媒体时长 / 最长 gap / >5s 个数 / >5s 累计秒
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")


async def main():
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting

    engine, Session = create_celery_engine_and_session()
    rows = []
    async with Session() as db:
        ms = (await db.execute(select(Meeting).order_by(Meeting.id))).scalars().all()
        for m in ms:
            t = m.transcript or []
            if len(t) < 2:
                rows.append((m.id, m.title, len(t), m.media_duration_seconds, 0.0, 0, 0.0))
                continue
            gaps = []
            for i in range(1, len(t)):
                g = float(t[i].get("start") or 0) - float(t[i - 1].get("end") or 0)
                if g > 0:
                    gaps.append(g)
            mx = max(gaps) if gaps else 0.0
            g5 = [g for g in gaps if g > 5]
            rows.append((m.id, m.title, len(t), m.media_duration_seconds, mx,
                         len(g5), sum(g5)))

    print("%-5s %-46s %6s %8s %9s %5s %9s" % (
        "id", "title", "段数", "媒体秒", "最长gap", "gap>5s", "累计秒"))
    flagged = []
    for r in rows:
        flag = ""
        if r[4] > 180:
            flag = "  <<< fail"
        elif r[4] > 60:
            flag = "  << warn"
        print("%-5s %-46s %6s %8s %9.2f %5d %9.1f%s" % (
            r[0], (r[1] or "")[:44], r[2], r[3] or 0, r[4], r[5], r[6], flag))
        if r[4] > 60:
            flagged.append(r)

    print("\n合计: %d 场会议, %d 场 gap>60s" % (len(rows), len(flagged)))
    tot = sum(r[6] for r in rows)
    print("全库 gap>5s 累计: %.1f 秒" % tot)


if __name__ == "__main__":
    asyncio.run(main())
