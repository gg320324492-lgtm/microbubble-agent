"""Phase 1m: 「跨场多条采样」enrollment —— 唯一还没被否掉的 enrollment 杠杆。

## 动机 (两处独立证据)

① Phase 0 机制结论: 决定 enrollment 质量的是**素材条数/声学多样性**, 不是单条多长
   (c10_longest 最差 / c10 中性 ⇒ 单场覆盖度太窄)。
② Phase 1l 实测: prod(现役质心=全部历史素材跨场混合) 比 strict(LOO=只用品台账其它场
   台账段) 高 ~11 点, 且 **in-sample 只贡献 0.3 点** ⇒ 差距来自素材丰富度。
⇒ 若把 enrollment 改成「跨多场、多条短段」, strict 口径(诚实生产预期)应显著改善。

## 变体 (候选质心的采样策略; 全部留出被评场 ⇒ strict)

| 变体 | 质心 = | 权重语义 |
|---|---|---|
| base | 其它**每场**质心的均值 (现 strict LOO 基线) | 每场等权 |
| seg_mean | 其它场**全部台账段**的均值 | 每段等权 (段多的场权重大) |
| sqrt_weighted | 每场质心按 sqrt(段数) 加权 | 折中 |
| prod (参照) | 库里现役质心 (含该场素材 ⇒ in-sample 上界, 只作参照) | — |

⭐ 口径纪律 (类 20.252/20.254):
- 全部变体用**同一 harness / 同一样本集 / 同一候选池规则**(cohort 内有场外素材者),
  数字可横比; **argmin 基线口径**, 不与簇质心口径的 0.5604/0.6350 横比。
- EER: 每变体同协议 (同段/同人/同留出) ⇒ 跨变体可比; 与其它 Phase 的 EER 数字**不横比**。
- 判据 (类 20.226): 净增益 = 认回增益 − 损失 (**绝对数**), 逐人报; 不看单一均值。
- **零 GPU**: 全部复用 phase1 的 seg 嵌入缓存。**生产 members 不动**, 不建表
  (候选质心落 JSON, 采纳与否待主指挥复核)。

用法 (容器内):
    python /tmp/vp/phase1m_cross_meeting_enroll.py --phase1 /tmp/vp/phase1 \
        --ledgers /tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json --out /tmp/vp/phase1m
"""
import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")


def log(m):
    print("[phase1m] " + m, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def eer_minimax(pos, neg):
    """minimax EER = min_t max(FAR(t), FRR(t)) (与 Phase 1 同形式)"""
    if not pos or not neg:
        return None
    pos = np.sort(np.asarray(pos, dtype=np.float64))
    neg = np.sort(np.asarray(neg, dtype=np.float64))
    cand = np.unique(np.concatenate([pos, neg]))
    far = np.searchsorted(neg, cand, side="left") / len(neg)
    frr = (len(pos) - np.searchsorted(pos, cand, side="left")) / len(pos)
    j = int(np.argmin(np.maximum(far, frr)))
    return float(max(far[j], frr[j]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--out", default="/tmp/vp/phase1m")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

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

    segs_by_meeting = collections.defaultdict(list)       # mid -> [(who, row)]
    mem_rows = collections.defaultdict(list)              # (who, mid) -> [row]
    for i, m in enumerate(META):
        if m["kind"] == "seg" and truth.get(i):
            segs_by_meeting[m["meeting"]].append((truth[i], i))
            mem_rows[(truth[i], m["meeting"])].append(i)
    mem_per_meeting = {k: norm(E[v].mean(0)) for k, v in mem_rows.items()}
    all_people = sorted({w for (w, _mid) in mem_rows})
    meetings_all = sorted(segs_by_meeting)

    # ---- cohort: 有 ≥2 场台账素材的人 ----
    person_meetings = collections.defaultdict(list)
    for (w, mid) in mem_rows:
        person_meetings[w].append(mid)
    person_meetings = {w: sorted(ms) for w, ms in person_meetings.items()}
    cohort = sorted(w for w, ms in person_meetings.items() if len(ms) >= 2)
    log("台账人数 %d; cohort (≥2 场) %d 人: %s" % (len(all_people), len(cohort), cohort))

    # ---- 现役 prod 质心 ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member
    engine, Session = create_celery_engine_and_session()
    db_cent = {}

    async def _load():
        async with Session() as db:
            for mm in (await db.execute(
                    select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
                v = np.asarray(mm.voice_embedding, dtype=np.float32)
                if np.linalg.norm(v) > 0:
                    db_cent[mm.name] = norm(v)
    import asyncio
    asyncio.run(_load())
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(engine.dispose())
    finally:
        loop.close()
    POOL = sorted(db_cent)
    log("现役池 %d 人" % len(POOL))

    # ---- 变体质心 (q, mid) -> 向量; 全部留出 mid ----
    def cent_base(q, mid):
        alts = [mem_per_meeting[(q, m2)] for m2 in person_meetings[q] if m2 != mid]
        return norm(np.mean(alts, axis=0)) if alts else None

    def cent_segmean(q, mid):
        rows = [r for m2 in person_meetings[q] if m2 != mid for r in mem_rows[(q, m2)]]
        return norm(E[rows].mean(0)) if rows else None

    def cent_sqrt(q, mid):
        alts = [(m2, mem_per_meeting[(q, m2)], len(mem_rows[(q, m2)]))
                for m2 in person_meetings[q] if m2 != mid]
        if not alts:
            return None
        w = np.array([np.sqrt(n) for _, _, n in alts], dtype=np.float64)
        V = np.stack([c for _, c, _ in alts])
        return norm((V * w[:, None]).sum(0) / w.sum())

    VARIANTS = [("base(每场等权=现基线)", cent_base),
                ("seg_mean(每段等权)", cent_segmean),
                ("sqrt_weighted(按√段数)", cent_sqrt)]

    # ---- 评测: argmin 段级归属 (strict) ----
    def eval_variant(cfunc, pool_names):
        """pool_names: 候选池规则。返回 (acc, n, per_meeting, preds)"""
        per_meeting = {}
        preds = {}
        tot = acc = 0
        for mid in meetings_all:
            pool = {}
            for q in pool_names:
                c = cfunc(q, mid)
                if c is not None:
                    pool[q] = c
            if not pool:
                continue
            t = a = 0
            names = sorted(pool)
            C = np.stack([pool[q] for q in names])
            for w, i in segs_by_meeting.get(mid, []):
                if w not in {p for p in names}:
                    pass
                d = 1.0 - C @ E[i]
                pred = names[int(np.argmin(d))]
                preds[i] = pred
                t += 1
                a += (pred == w)
            if t:
                per_meeting[mid] = (a, t, round(a / t, 4))
            tot += t
            acc += a
        return (acc / max(1, tot), tot, per_meeting, preds)

    results = {}
    pred_by_variant = {}
    for tag, fn in VARIANTS:
        acc, n, per_m, preds = eval_variant(fn, cohort)
        results[tag] = {"acc": round(acc, 4), "n": n,
                        "per_meeting": {str(k): v for k, v in sorted(per_m.items())}}
        pred_by_variant[tag] = preds
        log("strict %-26s 段级 %.4f (n=%d)" % (tag, acc, n))
    # prod 参照 (in-sample 上界): 池 = 现役全部 13 人
    acc_p, n_p, per_mp, preds_p = eval_variant(lambda q, mid: db_cent.get(q), POOL)
    results["prod(现役,含该场素材)"] = {"acc": round(acc_p, 4), "n": n_p,
                                   "per_meeting": {str(k): v for k, v in sorted(per_mp.items())}}
    pred_by_variant["prod"] = preds_p
    log("参照 prod(现役,含该场素材)   段级 %.4f (n=%d) ⚠️ in-sample 上界" % (acc_p, n_p))

    log("")
    log("逐场 (base → seg_mean → sqrt → prod):")
    for mid in meetings_all:
        row = [results[t]["per_meeting"].get(str(mid), ("-","-","-"))[2]
               for t, _ in VARIANTS]
        row.append(results["prod(现役,含该场素材)"]["per_meeting"].get(str(mid), ("-","-","-"))[2])
        log("   m%-4d %s | prod %s" % (mid, " → ".join(str(x) for x in row), row[-1]))

    # ---- 认回/抢走 vs base (绝对数, 类 20.226) ----
    log("")
    log("逐人净增益 vs base (认回+ / 抢走- / 净; 只统计 base 与变体都覆盖的段):")
    base_preds = pred_by_variant[VARIANTS[0][0]]
    for tag, _ in VARIANTS[1:]:
        new_preds = pred_by_variant[tag]
        common = [i for i in base_preds if i in new_preds]
        gains = [i for i in common
                 if new_preds[i] == truth[i] and base_preds[i] != truth[i]]
        losses = [i for i in common
                  if base_preds[i] == truth[i] and new_preds[i] != truth[i]]
        per_person = {}
        for i in gains:
            per_person.setdefault(truth[i], [0, 0])[0] += 1
        for i in losses:
            per_person.setdefault(truth[i], [0, 0])[1] += 1
        net = len(gains) - len(losses)
        results[tag]["vs_base"] = {"n_common": len(common), "gains": len(gains),
                                   "losses": len(losses), "net": net,
                                   "per_person": {k: v for k, v in sorted(per_person.items())}}
        log("   %-26s 认回+%d / 损失-%d / 净 %+d" % (tag, len(gains), len(losses), net))
        for w, (g, l) in sorted(per_person.items()):
            log("        %-8s +%d/-%d" % (w, g, l))

    # ---- 选择性采纳 A/B: 把干净赢家替换进现役 prod 池 ----
    # 类 20.226 ⑧ 的正确形态: 不是全域换质心, 而是「只换净增益显著为正且损失有界的人」。
    # 替换者用 sqrt 跨场 LOO 质心 (评其自己的场时留出 ⇒ 对替换者略严, prod 对其余人是
    # in-sample ⇒ 本对照**低估**替换收益, 方向保守)。
    def eval_mixed(replace_map, cfunc):
        per_meeting = {}
        preds = {}
        tot = acc = 0
        for mid in meetings_all:
            pool = {}
            for q in POOL:
                if q in replace_map:
                    c = cfunc(q, mid)
                    if c is not None:
                        pool[q] = c
                        continue
                if q in db_cent:
                    pool[q] = db_cent[q]
            if not pool:
                continue
            names = sorted(pool)
            C = np.stack([pool[q] for q in names])
            t = a = 0
            for w, i in segs_by_meeting.get(mid, []):
                d = 1.0 - C @ E[i]
                pred = names[int(np.argmin(d))]
                preds[i] = pred
                t += 1
                a += (pred == w)
            if t:
                per_meeting[mid] = (a, t, round(a / t, 4))
            tot += t
            acc += a
        return (acc / max(1, tot), tot, per_meeting, preds)

    winners = [w for w in cohort
               if (r := results["sqrt_weighted(按√段数)"]["vs_base"]["per_person"].get(w))
               and (r[0] - r[1]) >= 5 and r[1] <= 2]
    log("")
    log("选择性采纳候选 (净≥+5 且损失≤2): %s" % winners)
    if winners:
        acc_s, n_s, per_ms, preds_s = eval_mixed(set(winners), cent_sqrt)
        results["selective_sqrt(替换%s进prod池)" % "+".join(winners)] = {
            "acc": round(acc_s, 4), "n": n_s, "replaced": winners,
            "per_meeting": {str(k): v for k, v in sorted(per_ms.items())}}
        pred_prod = pred_by_variant["prod"]
        common = [i for i in pred_prod if i in preds_s]
        gains = [i for i in common if preds_s[i] == truth[i] and pred_prod[i] != truth[i]]
        losses = [i for i in common if pred_prod[i] == truth[i] and preds_s[i] != truth[i]]
        pp = collections.defaultdict(lambda: [0, 0])
        for i in gains:
            pp[truth[i]][0] += 1
        for i in losses:
            pp[truth[i]][1] += 1
        results["selective_sqrt(替换%s进prod池)" % "+".join(winners)]["vs_prod"] = {
            "n_common": len(common), "gains": len(gains), "losses": len(losses),
            "net": len(gains) - len(losses),
            "per_person": {k: v for k, v in sorted(pp.items())}}
        log("selective 替换后: strict/pool混合口径 %.4f (n=%d) vs prod %.4f"
            % (acc_s, n_s, acc_p))
        log("   vs prod: 认回+%d / 损失-%d / 净 %+d" % (len(gains), len(losses),
                                                      len(gains) - len(losses)))
        for w, (g, l) in sorted(pp.items()):
            log("      %-8s +%d/-%d" % (w, g, l))

    # ---- EER (同协议跨变体可比; 不与其它 Phase 横比) ----    log("")
    log("EER (cohort 质心 ↔ 台账段; 每变体同协议):")
    for tag, fn in list(VARIANTS) + [("prod", lambda q, mid: db_cent.get(q))]:
        pos, neg = [], []
        for mid in meetings_all:
            cents = {q: fn(q, mid) for q in cohort}
            cents = {q: c for q, c in cents.items() if c is not None}
            names = sorted(cents)
            if len(names) < 2:
                continue
            C = np.stack([cents[q] for q in names])
            for w, i in segs_by_meeting.get(mid, []):
                if w not in cents:
                    continue
                d = 1.0 - C @ E[i]
                for q, dq in zip(names, d):
                    (pos if q == w else neg).append(float(dq))
        e = eer_minimax(pos, neg)
        results.setdefault(tag, {})["eer_cohort"] = round(e, 4) if e else None
        log("   %-26s EER %.4f (pos=%d neg=%d)" % (tag, e, len(pos), len(neg)))

    # ---- cohort 素材表 (解释 prod−strict 缺口) ----
    log("")
    log("cohort 素材 (人: 场数 [段数/场]):")
    cohort_tbl = {}
    for w in cohort:
        tbl = {str(m2): len(mem_rows[(w, m2)]) for m2 in person_meetings[w]}
        cohort_tbl[w] = {"n_meetings": len(person_meetings[w]), "segs_per_meeting": tbl}
        log("   %-8s %d 场 %s" % (w, len(person_meetings[w]), tbl))

    out = {"cohort": cohort, "cohort_material": cohort_tbl,
           "results": results,
           "note": "argmin 基线口径; EER 同协议跨变体可比, 不与其它 Phase 横比"}
    outp = os.path.join(args.out, "enroll_multi.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    main()
