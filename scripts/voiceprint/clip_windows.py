"""按**实际空档区间**裁剪逐窗结果, 生成不与既有段重叠的补录清单。

为什么: 一个"空档聚簇"可能是**多个分散的小空档**(255 的 9425-10049 就是 8 段),
逐窗切块会跨过既有段 ⇒ 时间单调性被破坏 ⇒ 必须按空档区间裁。

用法: python /tmp/vp/clip_windows.py <meeting_id> <windows_json> <out_assign_json> [min_text]
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")


async def main():
    MID = int(sys.argv[1])
    wins = json.load(open(sys.argv[2], encoding="utf-8"))
    out_path = sys.argv[3]
    min_text = int(sys.argv[4]) if len(sys.argv) > 4 else 8

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.meeting_quality_service import sanitize_text

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(select(Meeting).where(Meeting.id == MID))).scalar_one()
        t = m.transcript or []
        gaps = []
        for i in range(1, len(t)):
            g0 = float(t[i - 1].get("end") or 0)
            g1 = float(t[i].get("start") or 0)
            if g1 - g0 > 0.5:
                gaps.append((round(g0, 2), round(g1, 2)))
        # ⚠️ **绝不合并相邻空档**: 两个空档之间若夹着既有段, 合并后的区间会**盖住那段**
        # ⇒ 补录段与既有段重叠 ⇒ 时间单调性被破坏(实测踩中: 255 合并 1505 处时炸了)
        print("[vp] 会议 %d 空档 %d 处(逐个处理, 不合并)" % (MID, len(gaps)))
        merged = gaps

        out = []
        for (g0, g1) in merged:
            for w in wins:
                a = max(float(w["s"]), g0)
                b = min(float(w["e"]), g1)
                if b - a < 1.0:
                    continue
                txt = sanitize_text((w.get("text") or "").strip())
                if len(txt) < min_text:
                    continue
                d = w.get("d")
                mg = w.get("margin")
                confident = (d is not None and d <= 0.55 and mg is not None and mg >= 0.08)
                spk = w.get("judge") if confident else "发言人?"
                out.append({"s": round(a, 2), "e": round(b, 2), "text": txt,
                            "speaker": spk, "d": d, "margin": mg,
                            "note": "空档补录; 声学 margin<0.08 或距离过大 ⇒ 标发言人?"})
        out.sort(key=lambda x: x["s"])
        print("[vp] 裁剪后候选 %d 段" % len(out))
        import collections
        print("[vp] 说话人分布:", dict(collections.Counter(x["speaker"] for x in out)))
        json.dump(out, open(out_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        json.dump(out, open("/tmp/vp/%s_clipped.json" % MID, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)


if __name__ == "__main__":
    asyncio.run(main())
