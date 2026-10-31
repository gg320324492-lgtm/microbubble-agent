"""Phase 1h: **1.5s/50% 重叠滑窗**簇的评测 (官方 3D-Speaker recipe 的窗口形态)。

⭐ 评测口径**与 Phase 1b/1d/1e 完全一致** ⇒ 数字可直接横比
------------------------------------------------------------------
- **聚类的输入单元** = 滑窗 (1.5s, 0.75s shift)
- **评测的输入单元** = **生产 ASR 段** (1.5–8s, 不变) ⇒ 段级归属准确率/天花板/真值映射全部不变
- 段 → 簇: 取**覆盖该段中点**的滑窗 ⇒ 唯一归属
- 簇质心 = 该簇所有**滑窗**嵌入的均值 (不是 ASR 段嵌入的均值)
- EER[簇质心]: 被验证段的表示 = 簇质心
- 参照集 = 台账**全部 19 人**的 LOO 质心 (固定); 候选池 = 现役 13 人 (类 20.252)

同时跑一遍**同代码的 ASR 段聚类基线** ⇒ 滑窗 vs 段的差异只来自「聚类的输入单元」。

用法 (容器内):
    python /tmp/vp/phase1h_eval.py --phase1 /tmp/vp/phase1 --sw /tmp/vp/phase1h --out /tmp/vp/phase1h
"""
import argparse
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")

DEV_MEETINGS = [229, 250, 254, 259, 262]
TEST_MEETINGS = [243, 247, 255, 256]
SEED = 20261031
K_FIXED = 6


def log(msg):
    print("[phase1h-eval] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def med(xs):
    import statistics
    return float(statistics.median(xs)) if xs else None


def eer(pos, neg):
    if not pos or not neg:
        return None, None, None
    pos = np.sort(np.asarray(pos, dtype=np.float64))
    neg = np.sort(np.asarray(neg, dtype=np.float64))
    npos, nneg = len(pos), len(neg)
    cand = np.unique(np.concatenate([pos, neg]))
    far = np.searchsorted(neg, cand, side="left") / nneg
    frr = (npos - np.searchsorted(pos, cand, side="left")) / npos
    mx = np.maximum(far, frr)
    j = int(np.argmin(mx))
    return float(mx[j]), float(far[j]), float(frr[j])


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--sw", default="/tmp/vp/phase1h")
    ap.add_argument("--out", default="/tmp/vp/phase1h")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    SW = np.load(os.path.join(args.sw, "emb_sw.npy")).astype(np.float32)
    SWMETA = json.load(open(os.path.join(args.sw, "meta_sw.json"), encoding="utf-8"))
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    log("ASR 段 %d; 滑窗 %d" % (len(META), len(SWMETA)))

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
    segs_by_meeting = collections.defaultdict(list)
    mem_rows = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg" and truth.get(i):
            segs_by_meeting[m["meeting"]].append((truth[i], i))
            mem_rows[(truth[i], m["meeting"])].append(i)
    mem_per_meeting = {k: norm(E[v].mean(0)) for k, v in mem_rows.items()}

    # common_MP (与 Phase 1b/1d/1e 同)
    run_by_meeting = collections.defaultdict(list)
    for r in RUNS:
        run_by_meeting[r["meeting"]].append(r)
    tpb = collections.defaultdict(set)
    for (w, mid) in mem_rows:
        tpb[mid].add(w)

    def unit_set(variant):
        have = set()
        for mid, people in tpb.items():
            for w in people:
                if variant == "seg_old":
                    have.add((mid, w))
                    continue
                rs = [r for r in run_by_meeting.get(mid, []) if r["who"] == w]
                if variant == "whole":
                    rs = [r for r in rs if r.get("speech_sec", 0) <= 300.0]
                if rs:
                    have.add((mid, w))
        wm = collections.defaultdict(set)
        for (mm, w) in have:
            wm[w].add(mm)
        avail = set()
        for mid, items in segs_by_meeting.items():
            for q in {w for w, _ in items}:
                if any(m2 != mid for m2 in wm.get(q, ())):
                    avail.add((mid, q))
        return avail

    common_MP = set.intersection(*[unit_set(v) for v in
                                  ("seg_old", "c5", "c10", "c10_longest", "whole")])
    log("common_MP %d" % len(common_MP))

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
    POOL13 = sorted(db_cent)

    all_people = {w for (w, mid) in mem_rows}

    def loo_ref(mid):
        out = {}
        for q in all_people:
            alts = [mem_per_meeting[(q, m2)] for (ww, m2) in mem_per_meeting
                    if ww == q and m2 != mid]
            if alts:
                out[q] = norm(np.mean(alts, axis=0))
        return out

    def loo_pool(mid):
        return {q: v for q, v in loo_ref(mid).items() if q in POOL13}

    # ---- 两种聚类输入: ASR 段 / 滑窗 ----
    from sklearn.cluster import KMeans

    sw_by_meeting = collections.defaultdict(list)
    for i, m in enumerate(SWMETA):
        sw_by_meeting[m["meeting"]].append(i)

    def cluster_seg(mid):
        rows = per_meeting[mid]
        lab = KMeans(n_clusters=max(1, min(K_FIXED, len(rows))), n_init=3,
                     random_state=SEED).fit_predict(E[rows])
        cents = np.stack([norm(E[[rows[r] for r in range(len(rows)) if lab[r] == c]].mean(0))
                          for c in sorted(set(lab.tolist()))])
        # 段 → 簇 (只存簇号; 与滑窗聚类口径一致)
        seg2c = {}
        for r, i in enumerate(rows):
            seg2c[i] = int(lab[r])
        return {"cents": cents, "seg2c": seg2c, "rows": rows}

    def cluster_sw(mid):
        """滑窗聚类 ⇒ 段(按中点) → 簇"""
        wrows = sw_by_meeting.get(mid)
        if not wrows:
            return None
        lab = KMeans(n_clusters=max(1, min(K_FIXED, len(wrows))), n_init=3,
                     random_state=SEED).fit_predict(SW[wrows])
        cents = np.stack([
            norm(SW[[wrows[r] for r in range(len(wrows)) if lab[r] == c]].mean(0))
            for c in sorted(set(lab.tolist()))])
        # 段 → 滑窗: 取覆盖段中点的滑窗 (二分)
        starts = np.array([SWMETA[wrows[r]]["start"] for r in range(len(wrows))])
        order = np.argsort(starts)
        s_sorted = starts[order]
        e_sorted = np.array([SWMETA[wrows[order[k]]]["end"] for k in range(len(wrows))])
        l_sorted = lab[order]
        seg2c = {}
        for i in per_meeting[mid]:
            mid_t = (META[i]["start"] + META[i]["end"]) / 2.0
            j = int(np.searchsorted(s_sorted, mid_t, side="right")) - 1
            if j < 0:
                # 段中点早于第一个窗 ⇒ 归到第一个窗的簇
                j = 0
            if mid_t > e_sorted[j]:
                # 中点在窗的右边 ⇒ 找下一个包含它的窗 (窗可能不重叠覆盖)
                j2 = int(np.searchsorted(s_sorted, mid_t, side="right"))
                if j2 < len(s_sorted) and mid_t <= e_sorted[j2]:
                    j = j2
            seg2c[i] = int(l_sorted[j])
        return {"cents": cents, "seg2c": seg2c}

    def evaluate(clusterer, tag, meetings):
        clusters = {}
        for mid in meetings:
            if not per_meeting.get(mid):
                continue
            c = clusterer(mid)
            if c:
                clusters[mid] = c
        # EER[簇质心]
        pos, neg = [], []
        for (mid, q) in sorted(common_MP):
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            cm = loo_ref(mid).get(q)
            if cm is None:
                continue
            cents = clusters[mid]["cents"]
            for w, i in items:
                ci = clusters[mid]["seg2c"].get(i)
                if ci is None or ci >= len(cents):
                    continue
                d = float(1.0 - cents[ci] @ cm)
                (pos if w == q else neg).append(d)
        e, far, frr = eer(pos, neg)
        out = {"mode": tag, "eer_cross": round(e, 4) if e is not None else None,
               "eer_far": round(far, 4) if far is not None else None,
               "eer_frr": round(frr, 4) if frr is not None else None,
               "n_pos": len(pos), "n_neg": len(neg)}
        for pname in ("strict", "loose", "prod"):
            tot = acc = 0
            ceil_num = ceil_den = 0
            purities = []
            person_cluster_counts = collections.defaultdict(collections.Counter)
            cluster_purity_key = {}
            for mid in meetings:
                if mid not in clusters:
                    continue
                cents = clusters[mid]["cents"]
                seg2c = clusters[mid]["seg2c"]
                # 三档候选池:
                #  strict = 留出该场重建 (Phase 1b/1g/1h 的口径, **悲观**: 生产质心其实含本场素材)
                #  loose  = 该场自己的 (in-sample, 只作参照)
                #  prod   = **库里的现役生产质心** ⇒ 最贴近生产形态 (含该场素材)
                if pname == "strict":
                    pl = loo_pool(mid)
                elif pname == "loose":
                    pl = {q: mem_per_meeting[(q, mid)] for q in POOL13
                          if (q, mid) in mem_per_meeting}
                else:
                    pl = {q: db_cent[q] for q in POOL13 if q in db_cent}
                if not pl:
                    continue
                names = [min(pl, key=lambda q: dist(c, pl[q])) for c in cents]
                per_cluster_members = collections.defaultdict(collections.Counter)
                for i in per_meeting.get(mid, []):
                    ci = seg2c.get(i)
                    if ci is None:
                        continue
                    w = truth.get(i)
                    if w:
                        per_cluster_members[ci][w] += 1
                for ci, mem in per_cluster_members.items():
                    if not mem:
                        continue
                    top, cnt = mem.most_common(1)[0]
                    # ⭐ 天花板口径与 Phase 1g 一致: Σ(簇众数段数) / Σ(簇内有真值段数)
                    #   (=「若每个簇都命名成它的真值主人」时能到的段级准确率)
                    ceil_num += cnt
                    ceil_den += sum(mem.values())
                    purities.append(cnt / sum(mem.values()))
                    cluster_purity_key[(mid, ci)] = cnt / sum(mem.values())
                    for w2, c2 in mem.items():
                        person_cluster_counts[(w2, mid)][ci] = c2
                for i in per_meeting.get(mid, []):
                    w = truth.get(i)
                    if not w:
                        continue
                    ci = seg2c.get(i)
                    if ci is None:
                        continue
                    tot += 1
                    if names[ci] == w:
                        acc += 1
            dom_num = dom_den = 0
            for cc in person_cluster_counts.values():
                tot_w = sum(cc.values())
                if tot_w:
                    dom_num += max(cc.values())
                    dom_den += tot_w
            dcp_num = dcp_den = 0
            for (w, mid), cc in person_cluster_counts.items():
                if not cc:
                    continue
                ci_dom = cc.most_common(1)[0][0]
                pur = cluster_purity_key.get((mid, ci_dom))
                if pur is not None:
                    dcp_num += pur
                    dcp_den += 1
            out["seg_acc_" + pname] = round(acc / max(1, tot), 4)
            out["n_truth_seg_" + pname] = tot
            out["ceiling_" + pname] = round(ceil_num / max(1, ceil_den), 4) if ceil_den else None
            out["cluster_purity_" + pname] = round(float(np.mean(purities)), 4) if purities else None
            out["dominant_cluster_share_" + pname] = round(dom_num / max(1, dom_den), 4) if dom_den else None
            out["dominant_cluster_purity_" + pname] = round(dcp_num / max(1, dcp_den), 4) if dcp_den else None
        return out

    res = {}
    for tag, clusterer in (("ASR段聚类(基线)", cluster_seg), ("滑窗聚类(1.5s/50%)", cluster_sw)):
        r_dev = evaluate(clusterer, tag, DEV_MEETINGS)
        r_test = evaluate(clusterer, tag, TEST_MEETINGS)
        r_all = evaluate(clusterer, tag, DEV_MEETINGS + TEST_MEETINGS)
        res[tag] = {"dev": r_dev, "test": r_test, "all9": r_all}
        for k, r in (("dev", r_dev), ("test", r_test), ("all9", r_all)):
            log("  %-22s %-5s | EER %.4f | 段级strict %.4f | **段级prod(现役池) %.4f** (天花板 %.4f) | 簇纯度 %.4f | 主导簇占比 %.4f" % (
                tag, k, r["eer_cross"], r["seg_acc_strict"], r.get("seg_acc_prod", -1),
                r["ceiling_strict"], r["cluster_purity_strict"],
                r["dominant_cluster_share_strict"]))

    out = {"pool13": POOL13, "common_MP": len(common_MP),
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "k_fixed": K_FIXED, "modes": res}
    outp = os.path.join(args.out, "eval.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
