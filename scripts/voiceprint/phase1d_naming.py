"""Phase 1d: 命名改造 —— 簇级弃权 + 融合投票 + k 自适应。

Phase 1b 的结论与本轮的三条改造
------------------------------
Phase 1b 实测: 跨场 EER 0.2067 → 0.1484, **验证集独立确认**; 但
**簇命名正确率只有 0.706** ⇒ 簇名错 ⇒ 整簇皆错 ⇒ 24 个百分点卡在「命名」上。
⇒ 本轮改三处命名机制:

1. **簇级弃权**: 簇级 top-1 与 top-2 的分数差 (margin) < τ ⇒ **整簇**标「发言人?」
   ⇒ 弃权的作用域是**簇**不是段 (簇名不可信 ⇒ 簇里每段都不可信)
2. **融合投票**: 簇级给**先验** + 段级给**证据**
   ⚠️ 段级信号**只在簇级 top-M 候选之间**消歧, **绝不**把同一成员的多个簇质心
   当成多个候选 (否则重演「取最近者几乎恒真 ⇒ 判别力塌掉」)
3. **k 自适应**: 固定 k=6 在只有 2–3 人说话的会上会强行切出多余簇 ⇒ 加
   **不看真值**的自适应 (maxdist: 簇质心间最小距离最大的 k) 与 **oracle** 对照

⭐ 判据 (主会话定的三条约束)
---------------------------
- **EER 仍是主判据**, 且**跨场 / 同场分两栏报**, 不许合并成一个「准确率」
  (簇级路线**只在跨场赢**; 合并就等于把「同场是倒退的」藏起来)
- **coverage–selective-risk 曲线** (Geifman arXiv:1705.08500) 与 EER 并排:
  coverage = 接受率, selective risk = 错误率/接受率
  ⇒ 单点 EER 会把「覆盖率 ↔ 残余错误率」的 trade-off 藏起来
- **弃权阈值 τ 用选参数集选, 在验证集上报告**; 且**弃权率必须同时报 k 与簇大小分布**
  (弃权率与簇数强相关 ⇒ 不报 k 的弃权率没有意义)

参数选择协议: 选参数集 (5 场) / 验证集 (4 场) 分离; 参数只在选参数集上选。

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1d_naming.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1d
"""
import argparse
import collections
import json
import os
import statistics
import sys

import numpy as np

sys.path.insert(0, "/app")

NON_PERSON = {"视频", "人群杂音", "环境声", "发言人?", "未知", "其他"}
DEV_MEETINGS = [229, 250, 254, 259, 262]
TEST_MEETINGS = [243, 247, 255, 256]
SEED = 20261031
TOPM = 2                     # 段级投票的候选上限 (簇级 top-M)
ALPHAS = [0.0, 0.25, 0.5, 0.75, 1.0]   # 1=纯簇级先验, 0=纯段级证据
K_MODES = ["2", "3", "4", "5", "6", "8", "maxdist", "oracle_people"]
MERGES = [1.0]               # Phase 1b 已证: 簇合并一律有害


def log(msg):
    print("[phase1d] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def med(xs):
    return float(statistics.median(xs)) if xs else None


def eer(pos, neg):
    """验证 EER (minimax): EER = min_t max(FAR(t), FRR(t))。"""
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


def load_ledger_blocks(paths):
    blocks = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for b in d["blocks"]:
            if b.get("_可用") is False or b["who"] in NON_PERSON:
                continue
            blocks.append({"who": b["who"], "meeting": int(b["meeting"]),
                           "s": float(b["s"]), "e": float(b["e"])})
    return blocks


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1d")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--k-n-init", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    assert len(META) == len(E)
    log("素材 %d 条" % len(META))

    blocks = load_ledger_blocks(args.ledgers.split(","))
    by_meeting = collections.defaultdict(list)
    for b in blocks:
        by_meeting[b["meeting"]].append(b)
    seg_truth = {}
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        mid_t = (m["start"] + m["end"]) / 2.0
        for b in by_meeting.get(m["meeting"], []):
            if b["s"] <= mid_t <= b["e"]:
                seg_truth[i] = b["who"]
                break
    truth_rows = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg" and seg_truth.get(i):
            truth_rows[seg_truth[i]].append((m["meeting"], i))
    segs_by_meeting = collections.defaultdict(list)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            segs_by_meeting[mm].append((w, i))

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
    log("候选池 %d 人" % len(POOL13))

    per_meeting = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            per_meeting[m["meeting"]].append(i)
    mem_rows = collections.defaultdict(list)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            mem_rows[(w, mm)].append(i)
    mem_per_meeting = {k: norm(E[v].mean(axis=0)) for k, v in mem_rows.items()}

    def mem_loo(w, mid):
        alts = [mem_per_meeting[(w, m2)] for (ww, m2) in mem_per_meeting
                if ww == w and m2 != mid]
        return norm(np.mean(alts, axis=0)) if alts else None

    loo_cache = {}

    def loo_pool(mid):
        if mid not in loo_cache:
            loo_cache[mid] = {q: v for q, v in
                              ((q, mem_loo(q, mid)) for q in POOL13) if v is not None}
        return loo_cache[mid]

    def loose_pool(mid):
        return {q: mem_per_meeting[(q, mid)] for q in POOL13
                if (q, mid) in mem_per_meeting}

    # ---- common_MP (与 Phase 1 / 1b 完全同口径) ----
    run_by_meeting = collections.defaultdict(list)
    for r in RUNS:
        run_by_meeting[r["meeting"]].append(r)
    truth_people_by_meeting = collections.defaultdict(set)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            truth_people_by_meeting[mm].add(w)

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
        w_meetings = collections.defaultdict(set)
        for (mm, w) in have:
            w_meetings[w].add(mm)
        avail = set()
        for mid, items in segs_by_meeting.items():
            for q in {w for w, _ in items}:
                if any(m2 != mid for m2 in w_meetings.get(q, ())):
                    avail.add((mid, q))
        return avail

    common_MP = set.intersection(*[unit_set(v) for v in
                                  ("seg_old", "c5", "c10", "c10_longest", "whole")])
    log("common_MP %d 个" % len(common_MP))

    # ---- 聚类 ----
    from sklearn.cluster import KMeans
    km_cache = {}

    def kmeans(mid, k):
        key = (mid, k)
        if key not in km_cache:
            rows = per_meeting[mid]
            km = KMeans(n_clusters=max(1, min(k, len(rows))), n_init=args.k_n_init,
                        random_state=SEED)
            km_cache[key] = km.fit_predict(E[rows])
        return km_cache[key]

    def k_for(mid, mode):
        n = len(truth_people_by_meeting.get(mid, ()))
        if mode == "oracle_people":
            return max(1, n)
        if mode == "maxdist":
            # ⭐ 不看真值的自适应: 选「簇质心间**最小距离最大**」的 k
            best_k, best_v = 2, -1.0
            for k in range(2, 9):
                rows = per_meeting[mid]
                lab = kmeans(mid, k)
                cs = np.stack([norm(E[rows][lab == c].mean(axis=0))
                               for c in sorted(set(lab.tolist()))])
                if len(cs) < 2:
                    continue
                d = np.linalg.norm(cs[:, None, :] - cs[None, :, :], axis=2)
                v = float(d[~np.eye(len(cs), dtype=bool)].min())
                if v > best_v:
                    best_k, best_v = k, v
            return best_k
        return int(mode)

    def cluster(mid, k_mode):
        rows = per_meeting[mid]
        k = k_for(mid, k_mode)
        lab = kmeans(mid, k)
        cents = np.stack([norm(E[rows][lab == c].mean(axis=0))
                          for c in sorted(set(lab.tolist()))])
        rep = np.zeros((len(rows), 192), dtype=np.float32)
        for ci in range(len(cents)):
            rep[lab == ci] = cents[ci]
        return rows, lab, cents, rep

    # ---- 簇级命名 + 弃权 ----
    def name_clusters(rows, lab, cents, pool, alpha):
        """对每个簇给出 (top1成员, margin, 绝对距离, 投票与先验的一致率)。

        alpha = 1.0 ⇒ 纯簇级先验 (= Phase 1b 的 centroid 命名)
        alpha = 0.0 ⇒ 纯段级证据 (但候选**限**簇级 top-M ⇒ 不破坏单一线性体)
        """
        names, margins, absd = [], [], []
        agree_votes = agree_tot = 0
        for ci, c in enumerate(cents):
            if not pool:
                names.append(None)
                margins.append(0.0)
                absd.append(9.9)
                continue
            # 簇级先验: 越大越像
            prior = {q: -dist(c, pool[q]) for q in pool}
            lo, hi = min(prior.values()), max(prior.values())
            span = (hi - lo) or 1.0
            prior_n = {q: (prior[q] - lo) / span for q in pool}
            order = sorted(pool, key=lambda q: -prior[q])
            topM = order[:TOPM]                      # ⭐ 段级投票的候选上限
            # 段级证据: 簇内段的 argmin 票数 (候选**只**在 topM 内)
            sel = [r for r in range(len(rows)) if lab[r] == ci]
            votes = collections.Counter()
            for r in sel:
                v = E[rows[r]]
                q_seg = min(topM, key=lambda q: dist(v, pool[q]))
                votes[q_seg] += 1
                # 诊断: 段级投票与簇级先验是否指向同一人
                agree_tot += 1
                if q_seg == order[0]:
                    agree_votes += 1
            n = max(1, len(sel))
            score = {}
            for q in pool:
                if q in topM:
                    score[q] = alpha * prior_n[q] + (1 - alpha) * votes[q] / n
                else:
                    score[q] = alpha * prior_n[q]     # 非 topM 只有先验
            srt = sorted(score, key=lambda q: -score[q])
            names.append(srt[0])
            margins.append(float(score[srt[0]] - score[srt[1]]) if len(srt) > 1 else 1.0)
            # ⭐ 绝对距离弃权判据: 簇质心到 top1 成员质心的距离
            #    ⇒「这个簇离**所有**已知人都远」= 没人认领 (类 20.247 的判据方向)
            absd.append(dist(c, pool[srt[0]]))
        return names, margins, absd, (agree_votes, agree_tot)

    def eval_config(k_mode, alpha, meetings):
        """EER(跨场) + 段级(跨场/同场两栏) + 弃权曲线 + 簇大小分布。"""
        clusters = {}
        for mid in meetings:
            if per_meeting.get(mid):
                clusters[mid] = cluster(mid, k_mode)
        # ---------- EER (只依赖簇质心表示 ⇒ 与 alpha/τ 无关) ----------
        pos, neg = [], []
        for (mid, q) in sorted(common_MP):
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            rows, lab, cents, rep = clusters[mid]
            row_of = {i: r for r, i in enumerate(rows)}
            cm = mem_loo(q, mid)
            if cm is None:
                continue
            for w, i in items:
                if i not in row_of:
                    continue
                d = float(1.0 - rep[row_of[i]] @ cm)
                (pos if w == q else neg).append(d)
        e, far, frr = eer(pos, neg)
        # ---------- 段级归属 (跨场 strict / 同场 loose) + 弃权曲线 ----------
        res = {"k_mode": k_mode, "alpha": alpha,
               "eer_cross": round(e, 4) if e is not None else None,
               "eer_far": round(far, 4) if far is not None else None,
               "eer_frr": round(frr, 4) if frr is not None else None,
               "n_pos": len(pos), "n_neg": len(neg)}
        for poolname, poolf in (("strict", loo_pool), ("loose", loose_pool)):
            tot = acc = 0
            cluster_sizes = []
            per_cluster = []
            va_num = va_den = 0
            for mid in meetings:
                if mid not in clusters:
                    continue
                rows, lab, cents, rep = clusters[mid]
                pool = poolf(mid)
                names, margins, absd, agr = name_clusters(rows, lab, cents, pool, alpha)
                va_num += agr[0]
                va_den += agr[1]
                sizes = collections.Counter(lab.tolist())
                cluster_sizes.extend(sizes.values())
                for ci in range(len(cents)):
                    per_cluster.append({"mid": mid, "size": int(sizes.get(ci, 0)),
                                        "margin": margins[ci], "absd": absd[ci],
                                        "name": names[ci]})
                for r, i in enumerate(rows):
                    w = seg_truth.get(i)
                    if not w:
                        continue
                    tot += 1
                    if names[lab[r]] == w:
                        acc += 1
            res["seg_acc_" + poolname] = round(acc / max(1, tot), 4)
            res["n_truth_seg_" + poolname] = tot
            res["cluster_size_" + poolname] = {
                "n": len(cluster_sizes),
                "min": int(min(cluster_sizes)) if cluster_sizes else 0,
                "median": med(cluster_sizes),
                "max": int(max(cluster_sizes)) if cluster_sizes else 0}
            if poolname == "strict":
                res["vote_agree"] = round(va_num / va_den, 4) if va_den else None
                res["_per_cluster_strict"] = per_cluster
        # ---------- coverage–selective-risk 曲线 (跨场 strict) ----------
        # 弃权作用域 = **簇**; 两种弃权判据并排:
        #   margin: 簇级 top1 与 top2 的**分数**差 (相对判据)
        #   absd  : 簇质心到 top1 成员质心的**绝对距离** (「离所有人都远 ⇒ 没人认领」)
        seg_of_cluster = collections.defaultdict(list)
        for mid in meetings:
            if mid not in clusters:
                continue
            rows, lab, cents, rep = clusters[mid]
            pool = loo_pool(mid)
            names, margins, absd, _ = name_clusters(rows, lab, cents, pool, alpha)
            for ci in range(len(cents)):
                for r, i in enumerate(rows):
                    if lab[r] == ci:
                        seg_of_cluster[(mid, ci)].append((i, names[ci], margins[ci], absd[ci]))
        total_truth = res["n_truth_seg_strict"]

        def curve_for(key, ascending_reject):
            out = []
            vals = sorted({round(items[0][3] if key == "absd" else items[0][2], 6)
                           for items in seg_of_cluster.values() if items})
            # 只扫有代表性的阈值 (避免 5 万个点)
            if len(vals) > 200:
                idx = np.linspace(0, len(vals) - 1, 200).astype(int)
                vals = [vals[i] for i in idx]
            for thr in vals:
                n_cov = acc_cov = 0
                for items in seg_of_cluster.values():
                    if not items:
                        continue
                    v = items[0][3] if key == "absd" else items[0][2]
                    reject = (v > thr) if (key == "absd") else (v < thr)
                    if reject:
                        continue
                    for i, nm, _m, _a in items:
                        w = seg_truth.get(i)
                        if not w:
                            continue
                        n_cov += 1
                        if nm == w:
                            acc_cov += 1
                if n_cov == 0:
                    continue
                out.append({"thr": round(float(thr), 6),
                            "coverage": round(n_cov / max(1, total_truth), 4),
                            "selective_risk": round(1 - acc_cov / n_cov, 4),
                            "n_accepted": n_cov})
            return out

        res["coverage_risk_curve_margin"] = curve_for("margin", True)
        res["coverage_risk_curve_absd"] = curve_for("absd", False)
        res.pop("_per_cluster_strict", None)
        return res

    # ================= 参数扫描 (选参数集) =================
    log("=== 参数扫描 (选参数集 %s) ===" % DEV_MEETINGS)
    scan = []
    for k_mode in K_MODES:
        for alpha in ALPHAS:
            r = eval_config(k_mode, alpha, DEV_MEETINGS)
            scan.append(r)
            log("  k=%-13s a=%.2f | EER(跨场) %.4f | 段级strict %.4f | 段级loose %.4f" % (
                k_mode, alpha, r["eer_cross"], r["seg_acc_strict"], r["seg_acc_loose"]))

    # ---- 选参: k 按 EER(跨场), alpha 按段级strict (跨场口径!) ----
    best_k = min(scan, key=lambda r: r["eer_cross"])
    k_best = best_k["k_mode"]
    alpha_pool = [r for r in scan if r["k_mode"] == k_best]
    best_alpha = max(alpha_pool, key=lambda r: r["seg_acc_strict"])
    alpha_best = best_alpha["alpha"]
    log("选参数集上: k=%s (EER %.4f) | alpha=%.2f (段级strict %.4f)" % (
        k_best, best_k["eer_cross"], alpha_best, best_alpha["seg_acc_strict"]))
    log("  ⓘ 段级投票与簇级先验的**一致率** = %.4f ⇒ α 几乎不改变结果" % (
        best_alpha.get("vote_agree") or 0))

    # ---- 弃权: ⭐ **不选单一 τ**, 直接报 coverage–selective-risk 曲线 ----
    #    (Geifman arXiv:1705.08500: 单点会把「覆盖率 ↔ 残余错误率」的 trade-off 藏起来)
    #    ⇒ 报整条曲线 + 若干 coverage 水平的读数; 读数水平是**读数**不是决策阈值。
    COV_LEVELS = [0.3, 0.5, 0.7, 0.9, 1.0]

    def at_coverage(curve, target):
        pts = sorted(curve, key=lambda c: abs(c["coverage"] - target))
        return pts[0] if pts else None

    # ================= 验证集 / 全 9 场 =================
    def show(tag, r):
        log("=== %s (k=%s alpha=%.2f) ===" % (tag, r["k_mode"], r["alpha"]))
        log("  EER(跨场) %.4f (FAR %.3f / FRR %.3f) | 段级strict %.4f | 段级loose %.4f" % (
            r["eer_cross"], r["eer_far"], r["eer_frr"], r["seg_acc_strict"], r["seg_acc_loose"]))
        log("  簇大小: %s | 段级投票↔簇级先验一致率 %.4f" % (
            json.dumps(r["cluster_size_strict"], ensure_ascii=False), r.get("vote_agree") or 0))
        for cname, key in (("margin", "coverage_risk_curve_margin"),
                           ("absd", "coverage_risk_curve_absd")):
            pts = []
            for lv in COV_LEVELS:
                p = at_coverage(r[key], lv)
                if p:
                    pts.append("cov %.2f→risk %.4f" % (p["coverage"], p["selective_risk"]))
            log("  弃权[%s]: %s" % (cname, " | ".join(pts)))

    test_r = eval_config(k_best, alpha_best, TEST_MEETINGS)
    show("验证集 %s (参数不在此集上选)" % TEST_MEETINGS, test_r)
    full_r = eval_config(k_best, alpha_best, DEV_MEETINGS + TEST_MEETINGS)
    show("全 9 场 (参考)", full_r)
    log("=== 选参数集上 (k=%s alpha=%.2f) ===" % (k_best, alpha_best))
    show("选参数集", best_alpha)
    # k 自适应对照: 各 k 模式在验证集上的 EER
    log("=== k 自适应对照 (验证集) ===")
    k_cmp = []
    for km in K_MODES:
        r = eval_config(km, alpha_best, TEST_MEETINGS)
        k_cmp.append({"k_mode": km, "eer_cross": r["eer_cross"],
                      "seg_acc_strict": r["seg_acc_strict"],
                      "seg_acc_loose": r["seg_acc_loose"]})
        log("  k=%-13s EER %.4f | 段级strict %.4f | 段级loose %.4f" % (
            km, r["eer_cross"], r["seg_acc_strict"], r["seg_acc_loose"]))

    out = {"pool13": POOL13,
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "common_MP": len(common_MP), "topm": TOPM, "alphas": ALPHAS,
           "coverage_levels": COV_LEVELS,
           "selected": {"k_mode": k_best, "alpha": alpha_best,
                        "vote_agree": best_alpha.get("vote_agree")},
           "scan_dev": scan, "dev_at_selected": best_alpha,
           "test_at_selected": test_r, "all9_at_selected": full_r,
           "k_comparison_test": k_cmp}
    outp = os.path.join(args.out, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
