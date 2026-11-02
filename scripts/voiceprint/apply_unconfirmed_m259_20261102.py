"""把主指挥 2026-11-02 对「会议 259 未确认片段」16 个区段的听辨真值写进段级裁决表。

主指挥原话（按区段号）:
  1、4、5、20、24、26、27、33、34、39 = 王天志
  17 = 肖佐林 与 其他一个人听不清
  18 = 人群声
  25、42 = 前面王天志 后面赵航佳
  43 = 赵航佳
  44 = 前面赵航佳 后面王天志

⚠️ 混合段的切分依据：主指挥给的「前面/后面」与逐段声学判定**独立一致**
   （25: idx238/239=王天志, idx240/241=赵航佳；42: idx336=王天志, idx337=赵航佳；
     44: idx344=赵航佳, idx345+=王天志；17: idx178=肖佐林, idx179=听不清）
   ⇒ 两个独立来源一致 ⇒ 按该切分逐段写（类 20.244）。

默认 dry-run；--apply 才写库。写库前自动备份到 meeting_259_adjud_backup_pre_20261102。
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

BASE = "/tmp/vp/未确认片段"
MEETING = 259
SOURCE = "commander-listening-2026-11-02"
NOTE = "会议259 未确认片段听辨真值 (主指挥 2026-11-02 亲耳判定)"

# 区段号 -> 处理规则
WHOLE_WANG = [1, 4, 5, 20, 24, 26, 27, 33, 34, 39]
WHOLE_CROWD = [18]
WHOLE_ZHAO = [43]
# 混合段 -> {idx: speaker}
MIXED = {
    17: {178: "肖佐林", 179: "发言人?"},
    25: {238: "王天志", 239: "王天志", 240: "赵航佳", 241: "赵航佳"},
    42: {336: "王天志", 337: "赵航佳"},
}
# 44 是「前面赵航佳 后面王天志」—— 只有 idx344 是赵航佳，其余王天志
MIXED_44 = {344: "赵航佳"}


def log(m):
    print("[m259-20261102] " + m, flush=True)


def build_plan():
    d = {r["no"]: r for r in json.load(open(os.path.join(BASE, "我的判定.json"), encoding="utf-8"))}
    plan = {}
    for no in WHOLE_WANG:
        for it in d[no]["items"]:
            plan[(it["idx"], round(it["s"], 2), round(it["e"], 2))] = "王天志"
    for no in WHOLE_CROWD:
        for it in d[no]["items"]:
            plan[(it["idx"], round(it["s"], 2), round(it["e"], 2))] = "发言人?"
    for no in WHOLE_ZHAO:
        for it in d[no]["items"]:
            if it["e"] - it["s"] >= 1.0:      # 0.4s 的「好的。」不硬判
                plan[(it["idx"], round(it["s"], 2), round(it["e"], 2))] = "赵航佳"
    for no, mapping in MIXED.items():
        for it in d[no]["items"]:
            if it["idx"] in mapping:
                plan[(it["idx"], round(it["s"], 2), round(it["e"], 2))] = mapping[it["idx"]]
    for it in d[44]["items"]:
        plan[(it["idx"], round(it["s"], 2), round(it["e"], 2))] = MIXED_44.get(it["idx"], "王天志")
    return plan


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    plan = build_plan()
    log("计划写入 %d 段" % len(plan))
    from collections import Counter
    log("分布: %s" % dict(Counter(plan.values())))

    from sqlalchemy import text
    from app.core.celery_db import create_celery_engine_and_session
    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        rows = (await db.execute(text(
            "SELECT id, seg_index, seg_start, seg_end, coalesce(speaker,'') "
            "FROM meeting_speaker_adjudications WHERE meeting_id=:m"), {"m": MEETING})).fetchall()
        existing = {(round(float(r[2]), 2), round(float(r[3]), 2)): (r[0], r[4]) for r in rows}
        log("现有裁决 %d 行" % len(rows))

        conflict = [(k, existing[(round(k[1], 2), round(k[2], 2))][1]) for k in plan
                    if (round(k[1], 2), round(k[2], 2)) in existing]
        log("与现有裁决重叠 %d 段%s" % (
            len(conflict), (": " + str(Counter(v for _, v in conflict))) if conflict else ""))

        # 当前 transcript 中这些段实际是什么
        tr = (await db.execute(text("SELECT transcript FROM meetings WHERE id=:m"), {"m": MEETING})).scalar_one()
        cur = {}
        for s in (tr or []):
            cur[(round(float(s.get("start") or 0), 2), round(float(s.get("end") or 0), 2))] = s.get("speaker") or ""
        missing = [k for k in plan if (round(k[1], 2), round(k[2], 2)) not in cur]
        log("在转录里找不到的段: %d %s" % (len(missing), missing[:5]))

        changed = [(k, cur.get((round(k[1], 2), round(k[2], 2)), "?"), v) for k, v in plan.items()
                   if cur.get((round(k[1], 2), round(k[2], 2)), "?") != v]
        log("会改判 %d 段: %s" % (len(changed), dict(Counter("%s->%s" % (a, b) for _, a, b in changed))))

        if not args.apply:
            log("DRY-RUN 结束（未写库）")
            await engine.dispose()
            return

        # 备份
        await db.execute(text("DROP TABLE IF EXISTS meeting_259_adjud_backup_pre_20261102"))
        await db.execute(text("CREATE TABLE meeting_259_adjud_backup_pre_20261102 AS "
                              "SELECT * FROM meeting_speaker_adjudications WHERE meeting_id=:m"), {"m": MEETING})
        # 幂等：先删同 source
        n = (await db.execute(text("DELETE FROM meeting_speaker_adjudications "
                                   "WHERE meeting_id=:m AND source=:s"), {"m": MEETING, "s": SOURCE})).rowcount
        log("清旧同 source 行: %d" % n)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for (idx, s, e), spk in plan.items():
            await db.execute(text(
                "INSERT INTO meeting_speaker_adjudications "
                "(meeting_id, seg_index, seg_start, seg_end, speaker, source, note, created_at, updated_at) "
                "VALUES (:m, :i, :s, :e, :sp, :src, :n, :t, :t)"),
                {"m": MEETING, "i": idx, "s": s, "e": e, "sp": spk, "src": SOURCE, "n": NOTE, "t": now})
        await db.commit()
        log("✅ 已写 %d 段" % len(plan))

        # ⚠️ 清掉被本次取代的旧裁决（同段多行 ⇒ resolver 胜负不确定，类 20.220）
        #    删除前先验证：每条旧行只覆盖本次新行中的一个中点（不波及邻段）
        old_overlap = (await db.execute(text(
            "SELECT a.id, a.seg_start, a.seg_end, a.speaker, a.source, "
            "  (SELECT count(*) FROM meeting_speaker_adjudications r "
            "    WHERE r.meeting_id=:m AND r.source=:s "
            "      AND (r.seg_start+r.seg_end)/2 BETWEEN a.seg_start AND a.seg_end) AS hits "
            "FROM meeting_speaker_adjudications a "
            "WHERE a.meeting_id=:m AND a.source <> :s"), {"m": MEETING, "s": SOURCE})).fetchall()
        to_del = [r for r in old_overlap if r[5] == 1]
        unsafe = [r for r in old_overlap if r[5] > 1]
        log("待删被取代旧行: %d 条 (覆盖多个新行中点数>1 的不删: %d 条)" % (len(to_del), len(unsafe)))
        for r in to_del:
            await db.execute(text("DELETE FROM meeting_speaker_adjudications WHERE id=:i"), {"i": r[0]})
        await db.commit()
        log("已删旧行 %d 条" % len(to_del))
        back = (await db.execute(text(
            "SELECT speaker, count(*) FROM meeting_speaker_adjudications "
            "WHERE meeting_id=:m AND source=:s GROUP BY 1 ORDER BY 2 DESC"),
            {"m": MEETING, "s": SOURCE})).fetchall()
        log("回读: %s" % [(r[0], r[1]) for r in back])
    await engine.dispose()


asyncio.run(main())
