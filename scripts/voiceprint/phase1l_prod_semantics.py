"""⭐⭐ 回答 teammate 的 prod/strict 语义问题 —— 用**实测**而不是论证。

teammate 的主张: 真实生产里成员质心在 enrollment 时刻固定 ⇒ 不含正在转写的那一场
⇒ prod 档若含目标场材料 ⇒ 对成员侧 in-sample ⇒ 是上界不是生产预期。

⚠️ **这个主张只对「现役质心的素材恰好来自目标场」的那几个 (成员,场) 组合成立**
   (实测: 全库只有 3 个 —— 陈天祥/吴孟铨/韩重阳 × 会议 262)。

本脚本量化:
  ① 剔除那 3 个 in-sample 组合后, prod 档的段级归属变成多少
     ⇒ 「prod 是不是一个被 in-sample 撑起来的数字」有答案
  ② 同时给 strict 档, 以及「strict + prod」两档逐场分布
  ③ ⚠️ **新会议 vs 存量会议**的区分:
     存量会议 = 我们评测的这 9 场 ⇒ 现役质心**可能**含该场素材
     新会议   = 真实生产的日常 ⇒ 质心在 enrollment 时刻固定 ⇒ **结构上不可能**含该场
     ⇒ 「prod 是上界」这句话**只对存量会议成立**, 对新会议不成立。

⚠️ 只读: 不写任何生产表。
"""
import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")

DEV = [229, 250, 254, 259, 262]
TEST = [243, 247, 255, 256]
LEDGER = set(DEV + TEST)

#: 实测: 现役质心素材含这些台账场 ⇒ prod 对这些 (成员,场) 是 in-sample
#: (来源: member_voice_history.notes 抽会议号 —— 陈天祥/吴孟铨/韩重阳 均由「262 报告块建库」)
INSAMPLE_PAIRS = {("陈天祥", 262), ("吴孟铨", 262), ("韩重阳", 262)}


def log(m):
    print("[prod-语义] " + m, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    args = ap.parse_args()

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)

    # ---- 台账真值 ----
    blocks = []
    for p in args.ledgers.split(","):
        p = p.strip()
        if not p:
            continue
        for b in json.load(open(p, encoding="utf-8"))["blocks"]:
            if b.get("_可用") is False or b["who"] in ("视频", "人群杂音", "环境声", "发言人?"):
                continue
            blocks.append(b)
    bm = collections.defaultdict(list)
    for b in blocks:
        bm[b["meeting"]].append(b)
    truth = {}
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        t = (m["start"] + m["end"]) / 2
        for b in bm.get(m["meeting"], []):
            if b["s"] <= t <= b["e"]:
                truth[i] = b["who"]
                break

    per_meeting = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            per_meeting[m["meeting"]].append(i)

    # ---- 现役质心 (prod 候选池) ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member
    engine, Session = create_celery_engine_and_session()
    db_cent = {}
    async with Session() as db:
        for mm in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cent[mm.name] = norm(v)
    await engine.dispose()
    POOL = sorted(db_cent)
    log("现役候选池 %d 人" % len(POOL))

    # ---- strict 档: 留出该场重建 (Phase 1h 的 loo_pool 口径) ----
    segs_by_meeting = collections.defaultdict(list)
    mem_rows = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg" and truth.get(i):
            segs_by_meeting[m["meeting"]].append((truth[i], i))
            mem_rows[(truth[i], m["meeting"])].append(i)
    mem_per_meeting = {k: norm(E[v].mean(0)) for k, v in mem_rows.items()}
    all_people = {w for (w, mid) in mem_rows}

    def loo_pool(mid):
        out = {}
        for q in all_people:
            alts = [mem_per_meeting[(q, m2)] for (ww, m2) in mem_per_meeting
                    if ww == q and m2 != mid]
            if alts and q in POOL:
                out[q] = norm(np.mean(alts, axis=0))
        return out

    def eval_pool(pick_pool, meetings, drop_insample=False):
        """pick_pool(mid) -> {name: centroid}; 返回 (acc, n, per_meeting)"""
        tot = acc = 0
        per_m = {}
        dropped = 0
        for mid in meetings:
            pl = pick_pool(mid)
            if not pl:
                continue
            t = a = 0
            for w, i in segs_by_meeting.get(mid, []):
                if drop_insample and (w, mid) in INSAMPLE_PAIRS:
                    dropped += 1
                    continue
                # 该段的表示: 用该成员在**其它场**的台账段均值 (strict 的成员侧)
                # 与 Phase 1h 的 loo_ref 同构
                alts = [mem_per_meeting[(w, m2)] for (ww, m2) in mem_per_meeting
                        if ww == w and m2 != mid]
                if not alts:
                    continue
                cm = norm(np.mean(alts, axis=0))
                # 候选侧: 段的**簇质心**没有 ⇒ 这里用「成员质心」对比段本身
                # ⇒ 简化为 argmin(成员质心, 段嵌入) ⇒ 即 Phase 1 的 baseline 口径
                v = E[i]
                pred = min(pl, key=lambda q: float(1.0 - np.dot(pl[q], v)))
                t += 1
                a += (pred == w)
            if t:
                per_m[mid] = (a, t, round(a / t, 4))
            tot += t
            acc += a
        return (acc / max(1, tot), tot, per_m, dropped)

    def strict_pool(mid):
        return loo_pool(mid)

    def prod_pool(mid):
        return {q: db_cent[q] for q in POOL if q in db_cent}

    res = {}
    for tag, fn in (("strict", strict_pool), ("prod", prod_pool)):
        for drop in (False, True):
            key = tag + ("_no_insample" if drop else "")
            acc, n, per_m, dropped = eval_pool(fn, sorted(LEDGER), drop)
            res[key] = {"acc": round(acc, 4), "n": n, "dropped_insample_segs": dropped,
                        "per_meeting": {str(k): v for k, v in per_m.items()}}
            log("%-20s 段级 %.4f (n=%d, 剔除 in-sample 段 %d)" % (
                key, acc, n, dropped))

    log("")
    log("逐场 (strict vs prod vs prod剔in-sample):")
    for mid in sorted(LEDGER):
        s = res["strict"]["per_meeting"].get(str(mid))
        p = res["prod"]["per_meeting"].get(str(mid))
        q = res["prod_no_insample"]["per_meeting"].get(str(mid))
        log("   m%-4d strict=%s prod=%s prod_noIS=%s" % (
            mid, s[2] if s else "-", p[2] if p else "-", q[2] if q else "-"))

    out = {"insample_pairs": sorted(INSAMPLE_PAIRS), "results": res}
    with open("/tmp/vp/prod_semantics.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 /tmp/vp/prod_semantics.json")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
