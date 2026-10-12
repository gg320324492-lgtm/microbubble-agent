r"""
订正一场会议里被误识别的说话人（用库内已有声纹做判别）

2026-10-13 首个使用者 —— 会议 256（2h24m 真实组会）:
  赵航佳（成员 id=2）的论文汇报被**整段**标成「蒋芦笛」，共 209 段。
  补录其声纹后，用本脚本把 dist 足够低的区间订正回来。

⚠️ 为什么"没录声纹"不是完整解释（实测结论）:
  赵航佳**从未录过声纹**，但他的音频与蒋芦笛的声纹 cosine 距离
  **0.59 < MATCH_THRESHOLD 0.7** ⇒ 阈值内，会被**主动判成蒋芦笛**，
  而不是走「发言人?」兜底。所以补录声纹是必要的；但**补录之前**，
  可以先用"已经有声纹的人"去判别那些误识别段落。

⚠️ 判据纪律（都踩过，别改）:
  1. **默认 dry-run**，只有 `--apply` 才写生产数据。
  2. **写前自动备份**到 `meeting_<id>_backup_pre_voiceprint_fix`（可完整回滚）。
  3. **只用 dist < --threshold（默认 0.2）的区间**。0.2 以下是铁证;
     0.2~0.6 只是"相对最像"，实测里那几段其实是别人
     （会议 256 的 136 分那段「重点是我们能从中学会什么」是王天志式的总结，
      dist 0.41~0.58）。**宁可漏改，不可错改。**
  4. 备份/回读一律用 **Python 解析 JSON**，**绝不用 SQL `LIKE` 查 JSON 里的中文**
     —— JSON 存储会把中文转义成 `\uXXXX`，`LIKE '%中文%'` **永远匹配不到**。
     2026-10-13 实测据此漏改了 `transcript_polished`，差点以为无需改。
  5. **备份必须独立提交，并在换新会话后回读确认**。把备份与数据修改放进**同一个事务**
     是危险的 —— 修改阶段一旦回滚，`CREATE TABLE` 会被一起撤销，**备份表凭空消失**，
     而数据可能已被部分改动。等价的坑: 把多条语句塞进一个 `psql -c "A; B; C"`，
     最后一条报错会回滚整串（含 CREATE TABLE）。
     2026-10-13 实测踩过一次 —— 改完数据才发现备份表不存在，
     最后靠本地留的原始 transcript 快照重建才恢复回滚能力。

⚠️ 必须在 **app 容器内**跑（要 modelscope 声纹模型 + MinIO 音频）:
    MSYS_NO_PATHCONV=1 docker cp scripts/voiceprint/fix_meeting_speakers.py \
        microbubble-agent-app-1:/tmp/
    MSYS_NO_PATHCONV=1 docker exec microbubble-agent-app-1 \
        python /tmp/fix_meeting_speakers.py <args>

Usage:
    # 1) 看看哪些区间能改（默认 dry-run，不写库）
    python fix_meeting_speakers.py --meeting 256 --expect 赵航佳 --from-speaker 蒋芦笛

    # 2) 确认后执行：订正 transcript + polished + mapping + 纪要人名
    python fix_meeting_speakers.py --meeting 256 --expect 赵航佳 \
        --from-speaker 蒋芦笛 --rename-in-text 蒋芦笛=赵航佳 --apply

    # 3) 只订正某段时间范围（便于分批）
    python fix_meeting_speakers.py --meeting 256 --expect 赵航佳 \
        --from-speaker 蒋芦笛 --range 0-1200
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys

sys.path.insert(0, "/app")

MERGE_GAP = 2.0   # 相邻段落间隔 <=2s 视为连续发言
MIN_SEG_SEC = 1.0 # 短于此长度的区间不做判别（声纹提取噪声大）


def to_py(v):
    """psycopg/SQLAlchemy 可能已把 json 列解析成对象，别重复 loads。"""
    return v if isinstance(v, (list, dict)) else (json.loads(v) if v else v)


def merge_intervals(spans):
    out = []
    for a, b in sorted(spans):
        if out and a - out[-1][1] <= MERGE_GAP:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def cut_audio(m4a, intervals, workdir):
    """按区间切 16k mono 并拼接。"""
    import numpy as np
    from scipy.io import wavfile

    os.makedirs(workdir, exist_ok=True)
    chunks, durs = [], []
    for i, (a, b) in enumerate(intervals):
        seg = f"{workdir}/s{i:03d}.wav"
        r = subprocess.run(
            ["ffmpeg", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", m4a,
             "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", seg],
            capture_output=True, text=True)
        if r.returncode != 0:
            durs.append(0.0)
            continue
        sr, data = wavfile.read(seg)
        if data.ndim > 1:
            data = data.mean(axis=1)
        chunks.append(data.astype(np.float32) / 32768.0)
        durs.append(len(data) / sr)
    return (np.concatenate(chunks) if chunks else None), durs


def hhmmss(x):
    return f"{int(x)//60:>3}分{int(x)%60:02d}秒"


async def run(args):
    import numpy as np
    from sqlalchemy import text
    from app.core.database import async_session
    from app.models.member import Member
    from app.services.file_service import file_service
    from app.services.voiceprint_service import voiceprint_service

    # ---------- 1. 取段落与区间 ----------
    async with async_session() as db:
        r = await db.execute(text(
            "SELECT transcript, audio_url FROM meetings WHERE id=:i"),
            {"i": args.meeting})
        row = r.one()
        segs = to_py(row[0]) or []
        audio_url = row[1]
        if not audio_url:
            raise SystemExit(f"会议 {args.meeting} 没有 audio_url")

        spans = [(float(s["start"]), float(s["end"]))
                 for s in segs if s.get("speaker") == args.from_speaker]
        if args.range:
            lo, hi = [float(x) for x in args.range.split("-")]
            spans = [sp for sp in spans if lo <= sp[0] <= hi]
    ivs = merge_intervals(spans)
    print(f"  「{args.from_speaker}」{len(spans)} 段 -> {len(ivs)} 区间 / "
          f"{sum(b-a for a,b in ivs):.1f}s"
          + (f"（限定 {args.range}s）" if args.range else ""))
    if not ivs:
        return

    # ---------- 2. 音频 ----------
    os.makedirs("/tmp/fms", exist_ok=True)
    m4a = f"/tmp/fms/m{args.meeting}.m4a"
    if not os.path.exists(m4a):
        with open(m4a, "wb") as f:
            f.write(file_service.download_file_sync(audio_url))
    audio, durs = cut_audio(m4a, ivs, "/tmp/fms/cut")
    if audio is None:
        raise SystemExit("ffmpeg 全部失败，检查音频与区间")

    # ---------- 3. 逐区间判别 ----------
    async with async_session() as db:
        r = await db.execute(text(
            "SELECT id, name, voice_embedding FROM members "
            "WHERE voice_embedding IS NOT NULL AND is_active=true AND voice_sample_count>0"))
        voices = [(mid, name, np.array(to_py(emb), dtype="float32"))
                  for mid, name, emb in r.all()]

    def rank(emb):
        return sorted((1.0 - float(np.dot(emb, v) /
                                   (np.linalg.norm(emb) * np.linalg.norm(v) + 1e-8)), nm, mid)
                      for mid, nm, v in voices)

    print(f"  库内可用声纹 {len(voices)} 个；阈值 {args.threshold}\n")
    results = []
    for i, (a, b) in enumerate(ivs):
        if durs[i] < MIN_SEG_SEC:
            print(f"     区间{i:02d} {hhmmss(a)}-{hhmmss(b)}  {durs[i]:5.1f}s  （太短，跳过）")
            continue
        emb = voiceprint_service.extract_embedding(
            audio if len(ivs) == 1 else cut_audio(m4a, [[a, b]], f"/tmp/fms/one{i}")[0])
        rs = rank(emb)
        d0, n0, _ = rs[0]
        d1, n1, _ = rs[1] if len(rs) > 1 else (float("nan"), "-", 0)
        good = n0 == args.expect and d0 < args.threshold
        print(f"  {'✅' if good else '  '} 区间{i:02d} {hhmmss(a)}-{hhmmss(b)} "
              f"{durs[i]:6.1f}s -> {n0:6}({d0:.3f})  次:{n1}({d1:.3f})")
        results.append({"i": i, "a": a, "b": b, "best": n0, "d": round(d0, 4), "ok": good})

    good_iv = [(x["a"], x["b"]) for x in results if x["ok"]]
    print(f"\n  可订正 {len(good_iv)}/{len(results)} 区间")
    if not args.apply:
        print("  DRY-RUN —— 加 --apply 才写库")
        return

    # ---------- 4. 备份（⚠️ 必须**独立提交**）----------
    # ⚠️⚠️ 2026-10-13 实测踩过: 备份与数据修改放在**同一个事务**里，
    #    一旦修改阶段抛错回滚，**CREATE TABLE 会被一起撤销 —— 备份表凭空消失**，
    #    而数据可能已被部分改动。（另一种触发方式: 把多条语句塞进一个
    #    `psql -c "A; B; C"`，最后一条报错会回滚整串，包括 CREATE TABLE。）
    # ⇒ 备份建完**立刻 commit**，与后续修改彻底分开。
    async with async_session() as db:
        if not args.no_backup:
            await db.execute(text(f"DROP TABLE IF EXISTS "
                                  f"meeting_{args.meeting}_backup_pre_voiceprint_fix"))
            await db.execute(text(
                f"CREATE TABLE meeting_{args.meeting}_backup_pre_voiceprint_fix AS "
                f"SELECT id, transcript, transcript_polished, summary, key_points, "
                f"decisions, speaker_mapping, speaker_stats, related_meeting_ids, "
                f"now() AS snapshot_at FROM meetings WHERE id={args.meeting}"))
            await db.commit()          # ← 独立提交，备份就此固化
            # 换新会话回读确认真的落库了（不信"没报错"）
            await db.close()
        async with async_session() as db2:
            r = await db2.execute(text(
                "SELECT count(*) FROM meeting_%s_backup_pre_voiceprint_fix"
                % args.meeting))
            n = r.scalar()
            if n != 1:
                raise SystemExit(f"❌ 备份表验证失败（{n} 行），已中止，**未做任何修改**")
            print(f"  ✅ 备份已固化并回读确认 -> "
                  f"meeting_{args.meeting}_backup_pre_voiceprint_fix（{n} 行）")

        # ---------- 5. transcript / polished ----------
        # ⚠️ 两列的时间字段名不同: transcript 用 start/end, polished 用 ts
        for field, tkey in (("transcript", "start"), ("transcript_polished", "ts")):
            r = await db.execute(text(
                f"SELECT {field}, speaker_mapping FROM meetings WHERE id=:i"),
                {"i": args.meeting})
            col, smap = r.one()
            col = to_py(col) or []
            smap = to_py(smap) or {}
            before = sum(1 for s in col if s.get("speaker") == args.from_speaker)
            labels = set()
            for s in col:
                if s.get("speaker") != args.from_speaker:
                    continue
                try:
                    st = float(s.get(tkey))
                except (TypeError, ValueError):
                    continue
                if any(lo <= st <= hi for lo, hi in good_iv):
                    s["speaker"] = args.expect
                    labels.add(s.get("speaker_label"))
            after = sum(1 for s in col if s.get("speaker") == args.from_speaker)
            sm_n = sum(1 for lb in labels if smap.get(lb) == args.from_speaker)
            for lb in labels:
                if smap.get(lb) == args.from_speaker:
                    smap[lb] = args.expect

            sets = {"v": json.dumps(col, ensure_ascii=False)}
            if field == "transcript":
                from collections import Counter
                await db.execute(text(
                    "UPDATE meetings SET transcript=CAST(:v AS json), "
                    "speaker_mapping=CAST(:m AS json), speaker_stats=CAST(:t AS json) "
                    "WHERE id=:i"),
                    {"v": json.dumps(col, ensure_ascii=False),
                     "m": json.dumps(smap, ensure_ascii=False),
                     "t": json.dumps({k: {"segments": n} for k, n in
                                     Counter(s.get("speaker") for s in col).items()},
                                    ensure_ascii=False),
                     "i": args.meeting})
                print(f"  {field}: {args.from_speaker} {before} -> {after} 段"
                      f"（改 {before-after}），speaker_mapping 改 {sm_n} 簇")
            else:
                await db.execute(text(
                    f"UPDATE meetings SET {field}=CAST(:v AS json) WHERE id=:i"),
                    {"v": json.dumps(col, ensure_ascii=False), "i": args.meeting})
                print(f"  {field}: {args.from_speaker} {before} -> {after} 段"
                      f"（改 {before-after}）")

        # ---------- 6. 纪要人名替换 ----------
        if args.rename_in_text:
            old, new = args.rename_in_text.split("=", 1)
            r = await db.execute(text(
                "SELECT summary, key_points, decisions FROM meetings WHERE id=:i"),
                {"i": args.meeting})
            summary, kps, decs = r.one()
            n_s = 1 if summary and old in summary else 0
            summary = (summary or "").replace(old, new)
            kps2 = [(k or "").replace(old, new) for k in (kps or [])]
            decs2 = [(d or "").replace(old, new) for d in (decs or [])]
            n_k = sum(1 for a, b in zip(kps or [], kps2) if a != b)
            n_d = sum(1 for a, b in zip(decs or [], decs2) if a != b)
            await db.execute(text(
                "UPDATE meetings SET summary=:s, key_points=CAST(:k AS text[]), "
                "decisions=CAST(:d AS text[]) WHERE id=:i"),
                {"s": summary, "k": kps2, "d": decs2, "i": args.meeting})
            print(f"  纪要「{old}」→「{new}」: summary={n_s} key_points={n_k} decisions={n_d}")

        await db.execute(text("UPDATE meetings SET updated_at=NOW() WHERE id=:i"),
                         {"i": args.meeting})
        await db.commit()

        # ---------- 7. 回读（Python 解析，不用 SQL LIKE）----------
        from collections import Counter
        for field in ("transcript", "transcript_polished"):
            r = await db.execute(text(
                f"SELECT {field} FROM meetings WHERE id=:i"), {"i": args.meeting})
            col = to_py(r.scalar()) or []
            print(f"  [回读] {field}: {dict(Counter(s.get('speaker') for s in col))}")


def main():
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--meeting", type=int, required=True)
    p.add_argument("--from-speaker", required=True, help="待订正的（错误）speaker 名")
    p.add_argument("--expect", required=True, help="期望的目标 speaker 名")
    p.add_argument("--threshold", type=float, default=0.2,
                   help="距离阈值，低于才改（默认 0.2；调高会误改）")
    p.add_argument("--range", help="只处理 START-END 秒内的区间")
    p.add_argument("--rename-in-text", help="纪要人名替换 OLD=NEW")
    p.add_argument("--no-backup", action="store_true", help="跳过备份（不建议）")
    p.add_argument("--apply", action="store_true", help="写库（默认 dry-run）")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
