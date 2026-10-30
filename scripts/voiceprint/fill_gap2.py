"""把某场会议的漏抓空档补进转录 + 台账/裁决表(通用版)。

用法:
    python fill_gap2.py <meeting_id> <gap_tag> <windows_json> <assign_json> [speaker]

windows_json: [{"s","e","text","judge","d","margin","second"}, ...]
assign_json : [{"s","e","speaker","note"}, ...]   按时间序, 不重叠
speaker     : assign 里没写 speaker 时用这个默认值

铁律:
- 文本必须过 sanitize_text (SenseVoice 控制 token 会让 quality 判 control_token_leak fail)
- 既有段一字不动 (字段保全自检)
- 写前建备份表
- 补完复算 gap 并报剩余最大 gap
"""
import asyncio
import json
import sys

sys.path.insert(0, "/app")


async def main():
    MID = int(sys.argv[1])
    TAG = sys.argv[2]
    wins = json.load(open(sys.argv[3], encoding="utf-8"))
    assigns = json.load(open(sys.argv[4], encoding="utf-8"))
    default_speaker = sys.argv[5] if len(sys.argv) > 5 else None

    from sqlalchemy import select, text as sqlt
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.services.meeting_quality_service import sanitize_text

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        m = (await db.execute(select(Meeting).where(Meeting.id == MID))).scalar_one()
        raw = list(m.transcript or [])
        pol = list(m.transcript_polished or [])
        mapping = dict(m.speaker_mapping or {})

        def txt_of(a, b, own=None):
            # 裁剪过的窗口自带 text(区间与本段完全一致) ⇒ 直接用
            if own is not None:
                return own
            out = []
            for w in wins:
                if a - 0.6 <= float(w["s"]) < b:
                    t = sanitize_text((w.get("text") or "").strip())
                    if t:
                        out.append(t)
            return "".join(out)

        base = {(round(float(s["start"]), 2), round(float(s["end"]), 2)): s for s in raw}

        new_entries = []
        for k, a in enumerate(assigns):
            st, en = float(a["s"]), float(a["e"])
            spk = a.get("speaker") or default_speaker
            lbl = "gap%s_%d" % (TAG, k)
            new_entries.append({
                "text": txt_of(st, en, a.get("text")),
                "start": round(st, 2),
                "end": round(en, 2),
                "speaker_label": lbl,
                "speaker": spk,
            })
            mapping[lbl] = spk

        merged = sorted(raw + new_entries, key=lambda s: float(s.get("start") or 0))
        mono = all(float(merged[i - 1]["end"]) <= float(merged[i]["start"]) for i in range(1, len(merged)))
        print("[vp] 合并后 %d 段, 时间单调=%s" % (len(merged), mono), flush=True)
        if not mono:
            print("[vp] ✗ 单调性失败, 放弃写入", flush=True)
            return

        pol_final = []
        for s in merged:
            lbl = str(s.get("speaker_label") or "")
            if lbl.startswith("gap"):
                pol_final.append({"speaker": s.get("speaker"), "text": s.get("text", ""),
                                  "ts": s.get("start")})
            else:
                old = next((p for p in pol if abs(float(p.get("ts") or -1) - float(s["start"])) < 0.01), None)
                if old is None:
                    pol_final.append({"speaker": s.get("speaker"), "text": s.get("text", ""),
                                      "ts": s.get("start")})
                else:
                    o = dict(old)
                    o["speaker"] = s.get("speaker")
                    pol_final.append(o)

        bk = "meeting_%d_backup_pre_gapfill_%s" % (MID, TAG)
        await db.execute(sqlt("DROP TABLE IF EXISTS %s" % bk))
        await db.execute(sqlt("CREATE TABLE %s AS SELECT * FROM meetings WITH NO DATA" % bk))
        await db.execute(sqlt("INSERT INTO %s SELECT * FROM meetings WHERE id = :i" % bk), {"i": MID})
        await db.commit()
        print("[vp] 备份表 %s 已写入" % bk, flush=True)

        from app.services.meeting_analysis_service import MeetingAnalysisService
        stats = MeetingAnalysisService().compute_speaker_stats(merged)

        m.transcript = merged
        m.transcript_polished = pol_final
        m.speaker_mapping = mapping
        m.speaker_stats = stats
        await db.commit()
        await db.refresh(m)

        bad = []
        for s in m.transcript:
            k = (round(float(s["start"]), 2), round(float(s["end"]), 2))
            if k in base:
                o = base[k]
                for f in ("text", "start", "end", "speaker_label", "speaker"):
                    if o.get(f) != s.get(f):
                        bad.append((k, f, o.get(f), s.get(f)))
        print("[vp] 既有段字段保全: %s" % ("OK" if not bad else bad[:5]), flush=True)
        print("[vp] polished 长度 %d (raw %d)" % (len(m.transcript_polished), len(m.transcript)), flush=True)

        # 裁决表
        from app.services.speaker_adjudication_service import get_adjudications
        from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication
        adjs = await get_adjudications(db, MID)
        have = {(round(float(a.seg_start), 2), round(float(a.seg_end), 2)) for a in adjs}
        added = 0
        for a in assigns:
            st, en = round(float(a["s"]), 2), round(float(a["e"]), 2)
            if (st, en) in have:
                continue
            db.add(MeetingSpeakerAdjudication(
                meeting_id=MID, seg_start=st, seg_end=en, seg_index=None,
                speaker=a.get("speaker") or default_speaker,
                source="commander-listening-2026-10-30-gapfill-%s" % TAG,
                note=a.get("note", "")))
            added += 1
        await db.commit()
        print("[vp] 裁决表新增 %d 条 (原有 %d)" % (added, len(adjs)), flush=True)

        # 空档复算
        t = m.transcript
        gaps = []
        for i in range(1, len(t)):
            g = float(t[i]["start"]) - float(t[i - 1]["end"])
            if g > 0:
                gaps.append((round(g, 2), i))
        gaps.sort(reverse=True)
        print("[vp] 剩余 gap>5s: %d 个, 最大 %s" % (sum(1 for g in gaps if g[0] > 5), gaps[:3]), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
