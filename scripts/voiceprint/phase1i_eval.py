"""Phase 1i 评测: **2×2 矩阵** —— {ERes2Net(现役), CAM++} × {ASR段聚类, 滑窗聚类}。

⚠️ **跨模型比较必须重建成员质心**（两个空间不相通, 现役质心在 CAM++ 空间不可用）
⚠️ **三档候选池**（类 20.252 的延伸）:
   strict = 该成员的质心**留出该场**、只用别的场重建 (Phase 1b~1h 的口径, 悲观)
   prod   = **库里的现役生产质心** (含被识别场次的素材 ⇒ 最贴近生产形态)
   loose  = 该场自己的 (in-sample, 只作参照)

⭐ 滑窗模式的段→簇映射: 取**覆盖该段中点**的滑窗 (两个空间的滑窗时间轴相同 ⇒ 映射可共用)。

用法 (容器内):
    python /tmp/vp/phase1i_eval.py --phase1 /tmp/vp/phase1 --camp /tmp/vp/phase1i --out /tmp/vp/phase1i
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
POOL13 = ['关小未', '吴孟铨', '周之超', '宋洋', '张宏魁', '杜同贺', '王天志',
          '耿嘉栋', '蒋芦笛', '贾琦', '赵航佳', '陈金薪', '韩重阳']


def log(m):
    print("[phase1i-eval] " + m, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


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
    ap.add_argument("--camp", default="/tmp/vp/phase1i")
    ap.add_argument("--out", default="/tmp/vp/phase1i")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E_ERES_ALL = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    SWM = json.load(open(os.path.join(args.phase1, "sw_meta.json"), encoding="utf-8"))
    SW_ERES_ALL = np.load(os.path.join(args.phase1, "sw_emb.npy")).astype(np.float32)

    camp_seg_meta = json.load(open(os.path.join(args.camp, "meta_camp_seg.json"), encoding="utf-8"))
    E_CAMP_ALL = np.load(os.path.join(args.camp, "emb_camp_seg.npy")).astype(np.float32)
    camp_sw_path = os.path.join(args.camp, "emb_camp_sw.npy")
    SW_CAMP_ALL = (np.load(camp_sw_path).astype(np.float32)
                   if os.path.exists(camp_sw_path) else None)
    log("ERes2Net 段 %s / 滑窗 %s; CAM++ 段 %s / 滑窗 %s" % (
        E_ERES_ALL.shape, SW_ERES_ALL.shape, E_CAMP_ALL.shape,
        SW_CAMP_ALL.shape if SW_CAMP_ALL is not None else "无"))

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

    # ---- 段对齐 (按 meeting/start/end) ----
    eres_index, camp_index = {}, {}
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            eres_index[(m["meeting"], round(float(m["start"]), 3), round(float(m["end"]), 3))] = i
    for k, m in enumerate(camp_seg_meta):
        camp_index[(m["meeting"], round(float(m["start"]), 3), round(float(m["end"]), 3))] = k
    keys = sorted(set(eres_index) & set(camp_index))
    log("段对齐: 交集 %d" % len(keys))
    N = len(keys)
    E_ERES = E_ERES_ALL[[eres_index[k] for k in keys]]
    E_CAMP = E_CAMP_ALL[[camp_index[k] for k in keys]]
    mid_of = [k[0] for k in keys]
    mid_t = [(k[1] + k[2]) / 2.0 for k in keys]
    truth_of = [truth.get(eres_index[k]) for k in keys]

    # ---- 滑窗索引 (两个空间共用时间轴 ⇒ 映射可共用) ----
    sw_by_mid = collections.defaultdict(list)
    for k, m in enumerate(SWM):
        sw_by_mid[m["meeting"]].append(k)
    sw_sorted = {}
    for mid, ks in sw_by_mid.items():
        order = sorted(ks, key=lambda k: float(SWM[k]["start"]))
        sw_sorted[mid] = (np.array([float(SWM[k]["start"]) for k in order]),
                          np.array([float(SWM[k]["end"]) for k in order]), order)

    def win_start(mid):
        return sw_sorted[mid][0]

    def win_index(mid, j):
        return sw_sorted[mid][2][j]

    # 段 → 该场内的**局部**滑窗位置 (O(1); 不能用 list.index ⇒ O(n) 太慢)
    sw_local = {}
    for mid, ks in sw_by_mid.items():
        order = sw_sorted[mid][2]
        sw_local[mid] = {g: k for k, g in enumerate(order)}

    def seg_to_window(mid, r):
        j = int(np.searchsorted(win_start(mid), mid_t[r], side="right")) - 1
        if j < 0:
            j = 0
        return sw_local[mid][win_index(mid, j)]

    # ---- 按会议的段索引 / 真值 ----
    per_meeting_rows = collections.defaultdict(list)
    mem_rows_s = collections.defaultdict(list)
    segs_by_meeting = collections.defaultdict(list)
    for r in range(N):
        mid = mid_of[r]
        per_meeting_rows[mid].append(r)
        w = truth_of[r]
        if w:
            mem_rows_s[(w, mid)].append(r)
            segs_by_meeting[mid].append((w, r))

    # ---- common_MP ----
    run_by_meeting = collections.defaultdict(list)
    for rr in RUNS:
        run_by_meeting[rr["meeting"]].append(rr)
    tpb = collections.defaultdict(set)
    for (w, mid) in mem_rows_s:
        tpb[mid].add(w)

    def unit_set(variant):
        have = set()
        for mid, people in tpb.items():
            for w in people:
                if variant == "seg_old":
                    have.add((mid, w))
                    continue
                rs = [x for x in run_by_meeting.get(mid, []) if x["who"] == w]
                if variant == "whole":
                    rs = [x for x in rs if x.get("speech_sec", 0) <= 300.0]
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

    from sklearn.cluster import KMeans

    def build_space(E):
        mem_pm = {k: norm(E[v].mean(0)) for k, v in mem_rows_s.items()}
        all_people = {w for (w, mid) in mem_rows_s}

        def loo_ref(mid):
            out = {}
            for q in all_people:
                alts = [mem_pm[(q, m2)] for (ww, m2) in mem_pm if ww == q and m2 != mid]
                if alts:
                    out[q] = norm(np.mean(alts, axis=0))
            return out

        def pool_loo(mid):
            ref = loo_ref(mid)
            return {q: ref[q] for q in POOL13 if q in ref}

        return {"mem_pm": mem_pm, "loo_ref": loo_ref, "pool_loo": pool_loo}

    def evaluate(E, space, tag, pool_mode, meetings, cluster_mode, SW):
        loo_ref = space["loo_ref"]
        pool_loo = space["pool_loo"]
        # ⚠️ 只实现 seg 模式: sw 模式的段→簇映射在本轮未验证 ⇒ **不留坏路径**。
        #    (「滑窗 + CAM++」的边际价值也低: CAM++ 在段级已判负。)
        clusters = {}
        if True:
            for mid in meetings:
                rs = per_meeting_rows.get(mid)
                if not rs:
                    continue
                Ek = E[rs]
                lab = KMeans(n_clusters=max(1, min(K_FIXED, len(rs))), n_init=3,
                             random_state=SEED).fit_predict(Ek)
                cents = np.stack([norm(Ek[[r for r in range(len(rs)) if lab[r] == c]].mean(0))
                                  for c in sorted(set(lab.tolist()))])
                clusters[mid] = (rs, lab, cents)
        # EER
        pos, neg = [], []
        for (mid, q) in sorted(common_MP):
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            cm = loo_ref(mid).get(q)
            if cm is None:
                continue
            if True:
                rs, lab, cents = clusters[mid]
                local = {r: k for k, r in enumerate(rs)}
                for w, r in items:
                    d = float(1.0 - cents[lab[local[r]]] @ cm)
                    (pos if w == q else neg).append(d)
        e, far, frr = eer(pos, neg)
        out = {"model": tag, "pool_mode": pool_mode, "cluster_mode": cluster_mode,
               "eer_cross": round(e, 4) if e is not None else None,
               "eer_far": round(far, 4) if far is not None else None,
               "eer_frr": round(frr, 4) if frr is not None else None,
               "n_pos": len(pos), "n_neg": len(neg)}
        for pname in ("strict", "prod", "loose"):
            tot = acc = 0
            ceil_num = ceil_den = 0
            purities = []
            pcc = collections.defaultdict(collections.Counter)
            cpk = {}
            for mid in meetings:
                if mid not in clusters:
                    continue
                if pname == "strict":
                    pl = pool_loo(mid)
                elif pname == "prod":
                    pl = {q: db_cent[q] for q in POOL13 if q in db_cent}
                else:
                    pl = {q: space["mem_pm"][(q, mid)] for q in POOL13
                          if (q, mid) in space["mem_pm"]}
                if not pl:
                    continue
                if True:
                    rs, lab, cents = clusters[mid]
                    names = [min(pl, key=lambda q: dist(c, pl[q])) for c in cents]
                    local = {r: k for k, r in enumerate(rs)}
                    # ⚠️ pmt_local 的 li 一律是**簇号** (不是段/窗的局部索引)
                    pmt_local = [(w, lab[local[r]]) for w, r in segs_by_meeting.get(mid, [])]
                per_cluster = collections.defaultdict(collections.Counter)
                for w, li in pmt_local:
                    per_cluster[li][w] += 1
                for li, mem in per_cluster.items():
                    if not mem:
                        continue
                    top, cnt = mem.most_common(1)[0]
                    purities.append(cnt / sum(mem.values()))
                    cpk[(mid, li)] = cnt / sum(mem.values())
                    for w2, c2 in mem.items():
                        pcc[(w2, mid)][li] = c2
                    ceil_num += cnt
                    ceil_den += sum(mem.values())
                for w, li in pmt_local:
                    tot += 1
                    if names[li] == w:
                        acc += 1
            dom_num = dom_den = 0
            for cc in pcc.values():
                t = sum(cc.values())
                if t:
                    dom_num += max(cc.values())
                    dom_den += t
            dcp_num = dcp_den = 0
            for (w, mid), cc in pcc.items():
                if not cc:
                    continue
                pur = cpk.get((mid, cc.most_common(1)[0][0]))
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

    spaces = {"ERes2Net(现役)": (E_ERES, SW_ERES_ALL, build_space(E_ERES)),
              "CAM++": (E_CAMP, SW_CAMP_ALL, build_space(E_CAMP))}

    res = {}
    for tag, (E, SW, sp) in spaces.items():
        if SW is None:
            continue
        for cmode in ("seg",):
            for pm in ("strict", "prod"):
                r_dev = evaluate(E, sp, tag, pm, DEV_MEETINGS, cmode, SW)
                r_test = evaluate(E, sp, tag, pm, TEST_MEETINGS, cmode, SW)
                r_all = evaluate(E, sp, tag, pm, DEV_MEETINGS + TEST_MEETINGS, cmode, SW)
                key = "%s|%s|%s" % (tag, cmode, pm)
                res[key] = {"dev": r_dev, "test": r_test, "all9": r_all}
                for k, r in (("dev", r_dev), ("test", r_test), ("all9", r_all)):
                    log("  %-28s %-5s | EER %.4f | strict %.4f | prod %.4f | 天花板 %.4f | 簇纯度 %.4f" % (
                        key, k, r["eer_cross"], r["seg_acc_strict"], r["seg_acc_prod"],
                        r["ceiling_strict"], r["cluster_purity_strict"]))

    ref = res["ERes2Net(现役)|seg|strict"]["test"]["seg_acc_strict"]
    log("回归核对: ERes2Net|段|strict 验证集段级 = %.4f (Phase 1g = 0.5970) %s" % (
        ref, "✅" if abs(ref - 0.5970) < 1e-6 else "❌"))
    assert abs(ref - 0.5970) < 1e-6, "口径与 Phase 1g 不一致 ⇒ 数字不可用"

    out = {"common_MP": len(common_MP), "pool13": POOL13,
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "k_fixed": K_FIXED, "results": res}
    outp = os.path.join(args.out, "eval.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
