"""Phase 1g: **聚类算法本身**的对比 (零 GPU) —— 回答「主导簇难形成」是不是算法问题。

Phase 1b~1f 的结论都指向同一个瓶颈: **聚类要把人分开(主导簇)**。
到 Phase 1f 为止只试过**一条路**: KMeans + 固定 k + maxdist 自适应(失败)。
⇒ 本轮换算法与人数估计方式:

聚类算法
  kmeans          基线 (sklearn, n_init=3, 固定种子)
  ahc_ward        层次聚合 Ward linkage, k 固定
  ahc_avg         层次聚合 average linkage, k 固定
  ahc_dist        层次聚合 average linkage + **距离阈值** ⇒ 不用估人数
  spectral        谱聚类 (余弦相似度预计算), k 固定

人数估计 (替代「固定 k」)
  fixed6          固定 6 (基线)
  eigengap        对余弦相似度矩阵做特征分解, 取**最大特征值间隙** ⇒ 不用估人数
  maxdist         簇质心间最小距离最大 (Phase 1d 测过, 作对照)

⚠️ **VBx 不在本轮范围内**: 它的原生输入是**帧级**的 ARD 权重
   (`BUTSpeechFIT/VBx` 每帧一组), 直接套到「段级 192 维向量」上语义不成立;
   要用得先切帧 ⇒ 那正是 Phase 1h 的滑窗路线 ⇒ 应与 Phase 1h **组合**后再评。

⭐ 口径 (类 20.252: 参照集 ≠ 候选池)
--------------------------------
- **成员侧参照集**(EER 里的成员质心): 固定 = 台账**全部 19 人**的 LOO 质心 (与 Phase 1b/1d/1e 同)
- **候选池**(命名时可选谁): 现役 13 人 (不变)
- EER 只在 common_MP 39 个组合上算; 段级在 ASR 段上算; 同场/跨场**分两栏**

判据 (主会话指定): 跨场 EER[簇质心] + **跨场段级归属准确率** + **簇纯度(主导簇占比)** + 天花板

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1g_cluster_algos.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1g
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
VARIANTS = ["kmeans", "ahc_ward", "ahc_avg", "ahc_dist", "spectral"]
K_MODES = ["fixed6", "eigengap", "maxdist"]


def log(msg):
    print("[phase1g] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def med(xs):
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


import statistics  # noqa: E402


def affinity_of(Eseg):
    """余弦相似度矩阵 (n×n)。"""
    X = Eseg / np.maximum(np.linalg.norm(Eseg, axis=1, keepdims=True), 1e-9)
    return (X @ X.T).astype(np.float32)


def eigengap_k(Eseg, kmin=2, kmax=10):
    """最大特征值间隙法 (NeMo offline_clustering 的思路): 估计说话人数。"""
    from scipy.sparse.linalg import eigsh
    A = affinity_of(Eseg)
    n = A.shape[0]
    kmax = min(kmax, n - 1)
    if kmax < kmin + 1:
        return kmin
    vals = eigsh(A, k=kmax, which="LA", return_eigenvectors=False)
    vals = np.sort(vals)[::-1]
    gaps = vals[:-1] - vals[1:]
    return int(kmin + int(np.argmax(gaps[:kmax - kmin])))


def maxdist_k(Eseg, kmin=2, kmax=8):
    """簇质心间最小距离最大的 k (Phase 1d 测过, 作对照)。"""
    from sklearn.cluster import KMeans
    best_k, best_v = kmin, -1.0
    for k in range(kmin, kmax + 1):
        lab = KMeans(n_clusters=k, n_init=3, random_state=SEED).fit_predict(Eseg)
        cs = np.stack([norm(Eseg[lab == c].mean(0)) for c in sorted(set(lab.tolist()))])
        if len(cs) < 2:
            continue
        dd = np.linalg.norm(cs[:, None, :] - cs[None, :, :], axis=2)
        v = float(dd[~np.eye(len(cs), dtype=bool)].min())
        if v > best_v:
            best_k, best_v = k, v
    return best_k


def do_cluster(algo, k_mode, Eseg):
    """返回 (labels, centroids)。"""
    from sklearn.cluster import AgglomerativeClustering, KMeans, SpectralClustering
    n = len(Eseg)
    if algo == "kmeans":
        if k_mode == "fixed6":
            k = K_FIXED
        elif k_mode == "eigengap":
            k = eigengap_k(Eseg)
        else:
            k = maxdist_k(Eseg)
        k = max(1, min(k, n))
        lab = KMeans(n_clusters=k, n_init=3, random_state=SEED).fit_predict(Eseg)
    elif algo in ("ahc_ward", "ahc_avg"):
        linkage = "ward" if algo == "ahc_ward" else "average"
        k = K_FIXED
        if k_mode == "eigengap":
            k = eigengap_k(Eseg)
        elif k_mode == "maxdist":
            k = maxdist_k(Eseg)
        k = max(1, min(k, n))
        if k == 1:
            lab = np.zeros(n, dtype=int)
        else:
            lab = AgglomerativeClustering(n_clusters=k, linkage=linkage).fit_predict(Eseg)
    elif algo == "ahc_dist":
        # 距离阈值 ⇒ 不用估人数 (阈值在**选参数集**上扫, 验证集沿用)
        th = AH_DIST_THRESHOLD[0]
        lab = AgglomerativeClustering(n_clusters=None, distance_threshold=th,
                                      linkage="average").fit_predict(Eseg)
    elif algo == "spectral":
        k = K_FIXED
        if k_mode == "eigengap":
            k = eigengap_k(Eseg)
        elif k_mode == "maxdist":
            k = maxdist_k(Eseg)
        k = max(1, min(k, n))
        A = affinity_of(Eseg)
        lab = SpectralClustering(n_clusters=k, affinity="precomputed",
                                 assign_labels="kmeans", random_state=SEED).fit_predict(A)
    else:
        raise ValueError(algo)
    cents = []
    for c in sorted(set(lab.tolist())):
        cents.append(norm(Eseg[lab == c].mean(0)))
    return lab, (np.stack(cents) if cents else np.zeros((0, 192), dtype=np.float32))


AH_DIST_THRESHOLD = [0.8]      # 选参数集上选, 验证集沿用


def load_ledger_blocks(paths):
    out = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        for b in json.load(open(p, encoding="utf-8"))["blocks"]:
            if b.get("_可用") is False or b["who"] in ("视频", "人群杂音", "环境声", "发言人?"):
                continue
            out.append(b)
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1g")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))

    blocks = load_ledger_blocks(args.ledgers.split(","))
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

    # ---- common_MP (与 Phase 1b/1d/1e 同) ----
    run_by_meeting = collections.defaultdict(list)
    for r in RUNS:
        run_by_meeting[r["meeting"]].append(r)
    truth_people_by_meeting = collections.defaultdict(set)
    for (w, mid) in mem_rows:
        truth_people_by_meeting[mid].add(w)

    def unit_set(variant):
        have = set()
        for mid, people in truth_people_by_meeting.items():
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

    def loo_ref(mid):
        out = {}
        for q in {w for w in truth_rows_names()}:
            alts = [mem_per_meeting[(q, m2)] for (ww, m2) in mem_per_meeting
                    if ww == q and m2 != mid]
            if alts:
                out[q] = norm(np.mean(alts, axis=0))
        return out

    def truth_rows_names():
        return {w for (w, mid) in mem_rows}

    def loo_pool(mid):
        return {q: v for q, v in loo_ref(mid).items() if q in POOL13}

    def evaluate(algo, k_mode, meetings):
        clusters = {}
        for mid in meetings:
            rows = per_meeting.get(mid)
            if not rows:
                continue
            lab, cents = do_cluster(algo, k_mode, E[rows])
            clusters[mid] = (rows, lab, cents)
        # EER (簇质心表示; 参照集固定 = 台账全部人)
        pos, neg = [], []
        for (mid, q) in sorted(common_MP):
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            rows, lab, cents = clusters[mid]
            row_of = {i: r for r, i in enumerate(rows)}
            cm = loo_ref(mid).get(q)
            if cm is None:
                continue
            cidxs = sorted(set(lab.tolist()))
            lab2cid = {c: n for n, c in enumerate(cidxs)}
            for w, i in items:
                if i not in row_of:
                    continue
                d = float(1.0 - cents[lab2cid[lab[row_of[i]]]] @ cm)
                (pos if w == q else neg).append(d)
        e, far, frr = eer(pos, neg)
        # 段级 (跨场 strict / 同场 loose) + 簇纯度 + 主导簇占比 + 天花板
        out = {"algo": algo, "k_mode": k_mode,
               "eer_cross": round(e, 4) if e is not None else None,
               "eer_far": round(far, 4) if far is not None else None,
               "eer_frr": round(frr, 4) if frr is not None else None}
        for pname in ("strict", "loose"):
            tot = acc = 0
            ceil_num = ceil_den = 0
            purities = []
            dom_num = dom_den = 0
            person_in_cluster = {}
            cluster_purity_key = {}
            person_cluster_counts = collections.defaultdict(collections.Counter)
            for mid in meetings:
                if mid not in clusters:
                    continue
                rows, lab, cents = clusters[mid]
                pl = loo_pool(mid) if pname == "strict" else {
                    q: mem_per_meeting[(q, mid)] for q in POOL13 if (q, mid) in mem_per_meeting}
                if not pl:
                    continue
                names = [min(pl, key=lambda q: dist(c, pl[q])) for c in cents]
                for ci in range(len(cents)):
                    mem = collections.Counter(truth.get(rows[r]) for r in range(len(rows))
                                             if lab[r] == ci and truth.get(rows[r]))
                    if not mem:
                        continue
                    top, cnt = mem.most_common(1)[0]
                    purities.append(cnt / sum(mem.values()))
                    cluster_purity_key[(mid, ci)] = cnt / sum(mem.values())
                    for _w, _c in mem.items():
                        person_cluster_counts[(_w, mid)][ci] = _c
                    ceil_num += cnt
                    ceil_den += sum(mem.values())
                    # 该成员在本簇的段数 (供主导簇占比用)
                    person_in_cluster[(top, ci, mid)] = mem[top]
                for r, i in enumerate(rows):
                    w = truth.get(i)
                    if not w:
                        continue
                    tot += 1
                    if names[lab[r]] == w:
                        acc += 1
            # 主导簇占比: 对每个成员, 他在**各簇**的段数 ⇒ 最多的那个簇占他全部段的比例
            # 主导簇占比: 必须**在 (人, 场) 内**算 —— 簇 id 是**场内**的,
            #   跨场比较 max 会把「簇数少」的人算得更差 (第一版跨场混算 ⇒ ahc_dist
            #   的主导簇占比被算成 0.08, 是伪值)
            per_person_clusters = collections.defaultdict(collections.Counter)
            for mid in meetings:
                if mid not in clusters:
                    continue
                rows, lab, cents = clusters[mid]
                for r, i in enumerate(rows):
                    w = truth.get(i)
                    if w:
                        per_person_clusters[(w, mid)][lab[r]] += 1
            for cc in per_person_clusters.values():
                tot_w = sum(cc.values())
                if tot_w:
                    dom_num += max(cc.values())
                    dom_den += tot_w
            # ⭐ 主导簇的**纯度**: 该成员的主导簇里, 他的段占该簇有真值段的比例
            #   (纯度高但主导簇占比低 = 簇碎; 主导簇占比高但纯度低 = 簇混 ⇒ 两个都要看)
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

    # ---- 扫描 ----
    scan = []
    combos = []
    for algo in VARIANTS:
        if algo == "ahc_dist":
            for th in (0.6, 0.7, 0.8, 0.9):
                combos.append((algo, "dist%.1f" % th, th))
        else:
            for km in K_MODES:
                combos.append((algo, km, None))
    for algo, km, th in combos:
        if th is not None:
            AH_DIST_THRESHOLD[0] = th
        r = evaluate(algo, km, DEV_MEETINGS)
        r["dist_thr"] = th
        scan.append(r)
        log("  %-10s %-8s | EER %.4f | 段级strict %.4f (天花板 %.4f) | 纯度 %.4f | 主导簇占比 %.4f | 主导簇纯度 %.4f" % (
            algo, km, r["eer_cross"], r["seg_acc_strict"], r["ceiling_strict"],
            r["cluster_purity_strict"], r["dominant_cluster_share_strict"], r["dominant_cluster_purity_strict"]))
    # 主判据 = **跨场 EER[簇质心]** (聚类的可分性, 与命名行为无关, 跨会话可比)
    #   ⛔ 单一「簇纯度」/「主导簇纯度」/「主导簇占比」都会选错 —— 各自被「簇碎 / 簇混」污染:
    #   ahc_dist 纯度最高(0.97) 但占比最低(0.11) = 簇极碎; ahc_avg 占比最高(0.99) 但纯度最低(0.49) = 簇混
    best = min(scan, key=lambda r: (r["eer_cross"], -r["seg_acc_strict"]))
    if best.get("dist_thr") is not None:
        AH_DIST_THRESHOLD[0] = best["dist_thr"]
    log("选参数集上最优: %s / %s (段级strict %.4f, EER %.4f)" % (
        best["algo"], best["k_mode"], best["seg_acc_strict"], best["eer_cross"]))
    test_r = evaluate(best["algo"], best["k_mode"], TEST_MEETINGS)
    full_r = evaluate(best["algo"], best["k_mode"], DEV_MEETINGS + TEST_MEETINGS)
    log("=== 验证集 ===")
    log("  %-10s %-8s | EER %.4f | 段级strict %.4f (天花板 %.4f) | 纯度 %.4f | 主导簇占比 %.4f | 主导簇纯度 %.4f" % (
        best["algo"], best["k_mode"], test_r["eer_cross"], test_r["seg_acc_strict"],
        test_r["ceiling_strict"], test_r["cluster_purity_strict"],
        test_r["dominant_cluster_share_strict"], r["dominant_cluster_purity_strict"]))
    log("=== 全 9 场 ===")
    log("  %-10s %-8s | EER %.4f | 段级strict %.4f (天花板 %.4f) | 纯度 %.4f | 主导簇占比 %.4f | 主导簇纯度 %.4f" % (
        best["algo"], best["k_mode"], full_r["eer_cross"], full_r["seg_acc_strict"],
        full_r["ceiling_strict"], full_r["cluster_purity_strict"],
        full_r["dominant_cluster_share_strict"], r["dominant_cluster_purity_strict"]))

    out = {"pool13": POOL13, "common_MP": len(common_MP),
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "scan_dev": scan, "selected": {"algo": best["algo"], "k_mode": best["k_mode"]},
           "dev_best": best, "test_at_best": test_r, "all9_at_best": full_r}
    outp = os.path.join(args.out, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
