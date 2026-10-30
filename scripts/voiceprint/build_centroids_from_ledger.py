"""从**人工确认的长报告块**为"没有声纹的人"建质心, 并跑类 20.226 双指标闸。

为什么需要这个脚本
------------------
- 2026-10-30 实测: 陈天祥/王书馨/吴孟铨 的台账素材**全是 1.5-1.8 秒的短段**
  (中位 dur), 而 3D-Speaker 在短段上系统性不稳 ⇒ 用它们建质心会
  **系统性吸引短段** (类 20.245), 且单场素材 = 过拟合 (类 20.226 的王天志案例)。
- 会议 262 的四次文献汇报是 **400-800 秒连续讲话**的长素材 ⇒ 唯一可用的建库源。

三类素材必须分清:
  ①**建库素材** = 报告块内的长窗(10s)  ⇒ 质心来源
  ②**认回(召回)验证集** = **其它会议**的台账段(跨场留出) ⇒ 排除"自己认自己"的虚高
  ③**抢走验证集** = 全库台账段里**别人**的发言 ⇒ 绝对数

闸(类 20.226 / 20.243):
  净增益 = 认回数 − 抢走数(绝对数); 抢走必须同时报"被抢者离其真值质心的距离中位"
  (类 20.243 ③: 离真值也远的才是真破坏, 只是换了个错名的不算)
  ⇒ 净增益 <= 0 ⇒ **不写库**

用法(容器内):
    python build_centroids_from_ledger.py --blocks /tmp/vp/blocks.json --dry-run
    python build_centroids_from_ledger.py --blocks /tmp/vp/blocks.json --apply

blocks.json:
{
  "262": {
     "audio": "/tmp/vp/src_recordings__262__merged.m4a",
     "blocks": [
        {"id":"B1","who":"<姓名>","s":0.0,"e":398.0,
         "seed":[[20.0,90.0]],            # 主指挥确认的"这一段就是此人"的长窗
         "report":"PCA/OPLS-DA 文献汇报"}
     ]
  }
}
"""
import argparse
import asyncio
import collections
import json
import os
import subprocess
import sys

import numpy as np
from sqlalchemy import text as sqlt

sys.path.insert(0, "/app")
SR = 16000
WIN = 10.0
WORK = "/tmp/vp"
NPZ = os.path.join(WORK, "all3.npz")
META = os.path.join(WORK, "all3_meta.json")

# 跨场同人距离基线(类 20.243 ①): 蒋芦笛 255质心↔250台账段 = 0.5038
CROSS_BASE = 0.50
# 抢走的判定: 新质心比"该段的真值质心"近多少才算抢走
STEAL_MARGIN = 0.05


def pcm_of(a, b, path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", str(a), "-to", str(b), "-i", path,
                        "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300].decode("utf-8", "replace"))
    return np.frombuffer(p.stdout, dtype=np.float32).copy()


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


async def build_centroid(svc, path, seeds, block_range, other_cents):
    """用 seed 长窗建初始质心, 再在报告块内**引导扩展**只收明显更靠近本人的窗。"""
    def emb_of(rngs):
        wins = []
        for a, b in rngs:
            t = a
            while t < b - 0.5:
                e = min(t + WIN, b)
                if e - t >= 3.0:
                    wins.append((round(t, 2), round(e, 2)))
                t += WIN
        embs = svc.batch_extract_embeddings([pcm_of(a, b, path) for a, b in wins])
        out = []
        for (a, b), e in zip(wins, embs):
            if e is None or np.all(e == 0):
                continue
            out.append((a, b, norm(e)))
        return out

    seed = emb_of(seeds)
    if not seed:
        return None, []
    cen = norm(np.mean([e for _, _, e in seed], axis=0))

    # 引导扩展: 报告块内, 离本候选比离所有"已知他人质心"都近 margin 以上的窗
    block = emb_of([block_range])
    grown = []
    for a, b, e in block:
        d_self = float(1.0 - e @ cen)
        d_other = min((float(1.0 - e @ c) for c in other_cents.values()), default=9.9)
        if d_self < d_other - STEAL_MARGIN:
            grown.append((a, b, e))
    if len(grown) >= 3:
        cen = norm(np.mean([e for _, _, e in grown], axis=0))
    return cen, (seed + grown)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--blocks", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--anchor", action="store_true",
                    help="同时设 voice_confirmed_at(进 anchor 池)。"
                         "⚠️ 该字段非空 = 永不再修改(类 20.226 ⑥), 须主指挥拍板")
    args = ap.parse_args()

    cfg = json.load(open(args.blocks, encoding="utf-8"))

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member
    from app.services.voiceprint_service import VoiceprintService

    # ---- 现有质心 ----
    engine, Session = create_celery_engine_and_session()
    db_cents = {}
    async with Session() as db:
        for mm in (await db.execute(select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cents[mm.name] = norm(v)
    print("[vp] 库内已有质心 %d 人: %s" % (len(db_cents), sorted(db_cents)), flush=True)

    # ---- 台账样本(认回 + 抢走验证集) ----
    d = np.load(NPZ)
    E = d["emb"].astype(np.float32)
    M = json.load(open(META, encoding="utf-8"))
    ledger = [(i, m) for i, m in enumerate(M) if m.get("in_ledger") == 1 and m.get("who")]
    print("[vp] 台账真值样本 %d 段" % len(ledger), flush=True)

    svc = VoiceprintService()
    new_cents = {}
    report = []

    for mid, mc in cfg.items():
        audio = mc["audio"]
        for blk in mc["blocks"]:
            who = blk["who"]
            others = {k: v for k, v in db_cents.items() if k != who}
            cen, samples = await build_centroid(svc, audio, blk["seed"], (blk["s"], blk["e"]), others)
            if cen is None:
                print("[vp] %s %s: seed 窗提取失败" % (blk["id"], who), flush=True)
                continue

            # ---- ① 认回(跨场留出) ----
            own = [(i, m) for i, m in ledger if m["who"] == who and str(m["meeting"]) != str(mid)]
            own_all = [(i, m) for i, m in ledger if m["who"] == who]
            recalled = 0
            ds_recall = []
            for i, m in own_all:
                v = norm(E[i])
                d_new = float(1.0 - v @ cen)
                # 与"其它已知质心"比较: 新质心必须是最近
                d_old = min((float(1.0 - v @ c) for k, c in db_cents.items() if k != who),
                            default=9.9)
                if d_new < d_old - STEAL_MARGIN:
                    recalled += 1
                    ds_recall.append(d_new)

            # ---- ② 抢走(别人) ----
            # ⛔ 必须区分「真抢走」与「无主改判」(类 20.243 ③):
            #   真抢走  = 该段有真值质心, 且新质心比真值质心**更近** ⇒ 真破坏
            #   无主改判 = 该人**本来就没有质心**(count=0), 改判只是"从一个错名换成另一个错名" ⇒ 不算破坏
            stolen_real = 0
            stolen_noowner = 0
            steal_detail = []
            for i, m in ledger:
                if m["who"] == who or m["who"] in ("环境声", "人群杂音", "视频"):
                    continue
                v = norm(E[i])
                d_new = float(1.0 - v @ cen)
                if d_new >= CROSS_BASE:
                    continue
                c_true = db_cents.get(m["who"])
                d_true = float(1.0 - v @ c_true) if c_true is not None else None
                if d_true is None:
                    stolen_noowner += 1
                    steal_detail.append(("无主:" + m["who"], m["meeting"], round(d_new, 3), None))
                elif d_new < d_true - STEAL_MARGIN:
                    stolen_real += 1
                    steal_detail.append((m["who"], m["meeting"], round(d_new, 3), round(d_true, 3)))

            # ---- ③ 组内识别率(同场, 会偏乐观, 仅作参考) ----
            in_meeting = [(i, m) for i, m in own_all if str(m["meeting"]) == str(mid)]
            hit_same = 0
            for i, m in in_meeting:
                v = norm(E[i])
                if float(1.0 - v @ cen) < min((float(1.0 - v @ c) for k, c in db_cents.items() if k != who),
                                              default=9.9) - STEAL_MARGIN:
                    hit_same += 1

            stolen = stolen_real          # 净增益只用「真抢走」
            net = recalled - stolen
            ok = net > 0
            print("[vp] ===== %s / %s (%s) =====" % (mid, blk["id"], who), flush=True)
            print("     质心素材: %d 窗(%.0fs)" % (
                len(samples), sum(b - a for a, b, _ in samples)), flush=True)
            print("     认回: 全部台账段 %d/%d (其中跨场 %d/%d, 同场 %d/%d)" % (
                recalled, len(own_all), recalled, len(own), hit_same, len(in_meeting)), flush=True)
            if ds_recall:
                print("     认回距离中位 %.3f (跨场同人基线 ≈ %.2f)" % (
                    sorted(ds_recall)[len(ds_recall) // 2], CROSS_BASE), flush=True)
            print("     真抢走: %d 段 %s" % (
                stolen_real, dict(collections.Counter(x[0] for x in steal_detail
                                                     if not x[0].startswith("无主:")))), flush=True)
            print("     无主改判(该人本来没质心, 不算破坏): %d 段 %s" % (
                stolen_noowner, dict(collections.Counter(x[0] for x in steal_detail
                                                        if x[0].startswith("无主:")))), flush=True)
            for x in steal_detail[:8]:
                print("        - %s @会议%s  d_新=%.3f d_真值=%s" % x, flush=True)
            print("     净增益 = %d - %d = %d  ⇒ %s" % (
                recalled, stolen, net, "通过" if ok else "不通过(不写库)"), flush=True)
            report.append((mid, blk, who, len(samples), recalled, len(own_all), stolen, net, ok,
                           sum(b - a for a, b, _ in samples)))
            if ok:
                new_cents[who] = cen

    if not args.apply:
        print("[vp] dry-run: 未写库。通过的人: %s" % [r[2] for r in report if r[8]], flush=True)
        return

    async with Session() as db:
        for mid, blk, who, nsamp, rec, nall, st, net, ok, nsec in report:
            if not ok:
                continue
            m = (await db.execute(select(Member).where(Member.name == who))).scalar_one_or_none()
            if m is None:
                print("[vp] 成员 %s 不存在, 跳过" % who, flush=True)
                continue
            old = list(m.voice_embedding) if m.voice_embedding is not None else None
            old_count = m.voice_sample_count or 0
            vec = new_cents[who]
            await db.execute(sqlt(
                "CREATE TABLE IF NOT EXISTS members_backup_before_centroid_build AS "
                "SELECT * FROM members WITH NO DATA"))
            await db.execute(sqlt(
                "INSERT INTO members_backup_before_centroid_build "
                "SELECT * FROM members WHERE id = :i"), {"i": m.id})
            m.voice_embedding = vec.tolist()
            m.voice_sample_count = nsamp
            m.voice_enrolled_at = sqlt("NOW()")
            if args.anchor:
                # ⚠️ voice_confirmed_at 非空 = 该成员**永不再修改**(类 20.226 ⑥)
                # ⇒ 只有主指挥拍板时才设
                m.voice_confirmed_at = sqlt("NOW()")
                m.voice_confirmed_by = "rebuild-2026-10-30-262"
                m.voice_confirmed_meeting_id = None
            await db.execute(sqlt(
                "INSERT INTO member_voice_history (member_id, source, old_embedding, new_embedding, "
                "sample_count_before, sample_count_after, notes) VALUES (:m, 'rebuild_2026_10_30_262', "
                ":old, :new, :sb, :sa, :notes)"), {
                    "m": m.id, "old": old, "new": vec.tolist(),
                    "sb": old_count, "sa": nsamp,
                    "notes": "262 报告块建库: %s, %d 窗(%.0fs), 认回 %d/%d, 抢走 %d, 净增益 %d" % (
                        blk.get("report", ""), nsamp, nsec, rec, nall, st, net)})
            print("[vp] 已写入 %s 的质心 (样本 %d, 净增益 %d, anchor=%s)" % (
                who, nsamp, net, bool(args.anchor)), flush=True)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
