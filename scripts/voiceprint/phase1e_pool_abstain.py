"""Phase 1e: ① 弃权判据按簇大小归一化 + 迁移性量化 ② 给台账里没有可用质心的人建质心(扩池)。

两个问题
--------
① **簇级弃权的阈值不可跨会议迁移** (Phase 1d 实测: 选参数集 coverage 0.69 → risk 0.250,
   验证集同 coverage 只有 0.44) ⇒ 机制是**簇大小分布跨会议差异巨大**
   (选参数集最小簇 25 段 / 验证集有只有 1 段的簇) ⇒ 弃权粒度=簇 ⇒ 同一阈值对应的
   覆盖率天差地别。
   ⇒ 本轮把弃权判据**按簇自身尺度归一化**, 并给出**可迁移性的量化判据**:
   在选参数集上选一个阈值, **在验证集上用同一个阈值** ⇒ 验证集 coverage 是否仍接近目标。
   ⇒ 三条曲线并排: margin (相对量纲) / absd (绝对距离) / absd_norm (绝对距离÷簇内段尺度)

② **台账里有 6 个人没有可用的质心** ⇒ 他们的段永远被兜底给池内的人。
   ⚠️ **两类要分开**:
     - 陈天祥 / 王书馨 / 刘莫菲 / 吴怡霏 / 李胜景: **从来没建过**
     - 关小未: **有列但不可用** —— 她的质心是蒋芦笛的声音(2026-10-30 已停用)
   ⇒ 「兜底是确定的错, 短质心至少有机会对」是**待验证的假设**, 本轮**去量**, 不假设。

⭐ 扩池要连带报「阈值重标」(VoxWatch 式 false-alarm problem):
   候选池变大 ⇒ 簇的 top1 更容易落到**不对**的人身上 ⇒ 同阈值下的 FAR 会涨
   ⇒ 报扩池前后的 EER / FAR / FRR 与**同一阈值**下的对比。

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1e_pool_abstain.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1e
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
K_FIXED = 6
NEW_POOL = ["陈天祥", "王书馨", "刘莫菲", "吴怡霏", "李胜景"]   # 从没建过
BLOCKED_POOL = ["关小未"]                                     # 有列但不可用(声音是蒋芦笛的)


def log(msg):
    print("[phase1e] " + msg, flush=True)


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


def load_ledger_blocks(paths):
    out = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        for b in d["blocks"]:
            if b.get("_可用") is False or b["who"] in NON_PERSON:
                continue
            out.append({"who": b["who"], "meeting": int(b["meeting"]),
                        "s": float(b["s"]), "e": float(b["e"])})
    return out


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1e")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--k-n-init", type=int, default=3)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    E = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    assert len(META) == len(E)

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
    log("现役池 %d 人: %s" % (len(POOL13), POOL13))

    # ---- 成员质心 (逐场 + 成员级重建池) ----
    per_meeting = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            per_meeting[m["meeting"]].append(i)
    mem_rows = collections.defaultdict(list)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            mem_rows[(w, mm)].append(i)
    mem_per_meeting = {k: norm(E[v].mean(axis=0)) for k, v in mem_rows.items()}

    def member_full_centroid(w):
        """成员级重建质心 = 该成员**全部**台账段的均值 (与 Phase 1b 的重建池同构)。"""
        rows = [i for mm, i in truth_rows.get(w, [])]
        return norm(E[rows].mean(axis=0)) if rows else None

    # ================================================================
    # ②-0 诊断: 关小未的台账段是不是蒋芦笛的声音?
    # ================================================================
    diag = {}
    if "关小未" in truth_rows:
        gx_rows = [i for mm, i in truth_rows["关小未"]]
        gx = norm(E[gx_rows].mean(axis=0))
        jl = db_cent.get("蒋芦笛")
        diag["关小未"] = {
            "n_seg": len(gx_rows),
            "d_to_蒋芦笛_现役质心": round(dist(gx, jl), 4) if jl is not None else None,
            "d_to_关小未_现役质心": (round(dist(gx, db_cent["关小未"]), 4)
                                if "关小未" in db_cent else None),
            "d_to_自己台账段的均值": 0.0,
        }
        # 蒋芦笛的台账段到关小未质心的距离 vs 到自己质心的距离
        jl_rows = [i for mm, i in truth_rows["蒋芦笛"]]
        if jl_rows:
            jlc = norm(E[jl_rows].mean(axis=0))
            diag["关小未"]["蒋芦笛台账段→关小未新建质心_中位"] = round(
                med([dist(E[i], gx) for i in jl_rows]), 4)
            diag["关小未"]["蒋芦笛台账段→蒋芦笛现役质心_中位"] = round(
                med([dist(E[i], jl) for i in jl_rows]), 4) if jl is not None else None
        # 反过来: 关小未的台账段到蒋芦笛质心 vs 到自己新建质心
        diag["关小未"]["关小未台账段→自己新建质心_中位"] = round(
            med([dist(E[i], gx) for i in gx_rows]), 4)
        diag["关小未"]["关小未台账段→蒋芦笛现役质心_中位"] = round(
            med([dist(E[i], jl) for i in gx_rows]), 4) if jl is not None else None
        log("=== 诊断: 关小未的台账段是谁的声音 ===")
        for k, v in diag["关小未"].items():
            log("   %s = %s" % (k, v))

    # ================================================================
    # 候选池构建
    # ================================================================
    def build_pool(extra_names):
        """extra_names 里的成员, 若在 members 表有行则用**现役**质心, 否则用台账重建。"""
        pool = dict(db_cent)
        added = []
        for w in extra_names:
            if w in pool:
                continue
            c = member_full_centroid(w)
            if c is not None:
                pool[w] = c
                added.append(w)
        return pool, added

    pool_a, _ = build_pool([])                                  # 现役 13
    pool_b, added_b = build_pool(NEW_POOL)                      # +5 从没建过的
    pool_c, added_c = build_pool(NEW_POOL + BLOCKED_POOL)        # +关小未(现役坏质心, 对照)
    # 池 D: 关小未**用台账重建**的质心 (替换掉现役那个被污染的) ⇒ 验证「台账素材是干净的」
    pool_d = dict(pool_b)
    _gx = member_full_centroid("关小未")
    if _gx is not None:
        pool_d["关小未"] = _gx
    log("池A 现役 %d | 池B 扩池 %d (新增 %s) | 池C +关小未(现役坏质心) %d | 池D +关小未(台账重建) %d" % (
        len(pool_a), len(pool_b), added_b, len(pool_c), len(pool_d)))
    for w in NEW_POOL + BLOCKED_POOL:
        rows = [i for mm, i in truth_rows.get(w, [])]
        log("   %-6s 台账段 %4d (%d 场) ⇒ %s" % (
            w, len(rows), len({mm for mm, _ in truth_rows.get(w, [])}),
            "可建质心" if rows else "无素材"))

    # ================================================================
    # common_MP (与 Phase 1b / 1d **逐字一致**的三段式判据)
    # ⚠️ 不加这一段 ⇒ EER 的样本集变了 ⇒ 与 Phase 1b/1d 的数字**不可横比**
    #    (本脚本第一版就踩了: 池 A 的 EER 算出 0..2132 而 Phase 1b 是 0.1484)
    # ================================================================
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
    log("common_MP %d 个 (与 Phase 1b/1d 同口径)" % len(common_MP))

    # ================================================================
    # 聚类 (k 固定 6, 与 Phase 1b 相同)
    # ================================================================
    from sklearn.cluster import KMeans
    km_cache = {}

    def cluster(mid):
        if mid not in km_cache:
            rows = per_meeting[mid]
            kk = max(1, min(K_FIXED, len(rows)))
            km = KMeans(n_clusters=kk, n_init=args.k_n_init, random_state=SEED)
            lab = km.fit_predict(E[rows])
            cents = np.stack([norm(E[rows][lab == c].mean(axis=0))
                              for c in sorted(set(lab.tolist()))])
            km_cache[mid] = (rows, lab, cents)
        return km_cache[mid]

    def loo_pool(pool, mid):
        out = {}
        for q in pool:
            alts = [mem_per_meeting[(q, m2)] for (ww, m2) in mem_per_meeting
                    if ww == q and m2 != mid]
            if alts:
                out[q] = norm(np.mean(alts, axis=0))
        return out

    # ⚠️⚠️ **「成员侧参照集」与「候选池」是两个不同的东西, 混用会让 EER 不可横比**
    #   参照集 (EER 里成员侧那个质心用谁) ⇒ 决定 EER 的样本难度 ⇒ **必须固定**
    #   候选池 (命名时可选哪些成员)       ⇒ 决定命名行为 ⇒ **这才是本轮要变的**
    # Phase 1b / 1d 的 EER 用的是「台账**全部**人」的 LOO 质心 (19 人) ⇐ 固定为这个
    def loo_pool_ref(mid):
        out = {}
        for q in {w for w in truth_rows}:
            alts = [mem_per_meeting[(q, m2)] for (ww, m2) in mem_per_meeting
                    if ww == q and m2 != mid]
            if alts:
                out[q] = norm(np.mean(alts, axis=0))
        return out

    def loose_pool(pool, mid):
        return {q: mem_per_meeting[(q, mid)] for q in pool if (q, mid) in mem_per_meeting}

    def cluster_names(rows, lab, cents, pool):
        """簇命名 + 三种弃权判据。"""
        names, margin, absd, absd_norm = [], [], [], []
        for ci, c in enumerate(cents):
            if not pool:
                names.append(None); margin.append(0.0); absd.append(9.9); absd_norm.append(9.9)
                continue
            ds = {q: dist(c, pool[q]) for q in pool}
            order = sorted(pool, key=lambda q: ds[q])
            top1 = order[0]
            names.append(top1)
            margin.append(ds[order[1]] - ds[order[0]] if len(order) > 1 else 1.0)
            absd.append(ds[top1])
            # ⭐ 归一化: 簇质心到 top1 的距离 ÷ 簇内段到同一 top1 的距离中位数
            sel = [r for r in range(len(rows)) if lab[r] == ci]
            inner = med([dist(E[rows[r]], pool[top1]) for r in sel]) if sel else None
            absd_norm.append(ds[top1] / inner if inner and inner > 1e-9 else 9.9)
        return names, margin, absd, absd_norm

    def eval_pool(pool, meetings):
        clusters = {mid: cluster(mid) for mid in meetings if per_meeting.get(mid)}
        # ---- EER (跨场, LOO 成员质心; ⛔ 只在 common_MP 上算 ⇒ 与 Phase 1b/1d 同口径) ----
        # ⚠️ **两种「被验证段的表示」都要算**:
        #    direct  = 段嵌入 (Phase 1b 的 `eer_direct`, 0.2067 ⇒ 回归基准)
        #    cluster = 簇质心 (Phase 1b 的 `eer_cluster`, 0.1484 ⇒ **生产形态**)
        #    第一版只算 direct 却拿去跟 Phase 1b 的 0.1484 比 ⇒ 差了一整个表示层 (已修)
        pos_d, neg_d, pos_c, neg_c = [], [], [], []
        for (mid, q) in sorted(common_MP):
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            rows, lab, cents = clusters[mid]
            row_of = {i: r for r, i in enumerate(rows)}
            cm = loo_pool_ref(mid).get(q)      # ⭐ 参照集固定(台账全部人), 与 Phase 1b 同
            if cm is None:
                continue
            cidxs = sorted(set(lab.tolist()))
            lab2cid = {c: n for n, c in enumerate(cidxs)}
            for w, i in items:
                if i not in row_of:
                    continue
                r = row_of[i]
                d_seg = float(1.0 - E[rows[r]] @ cm)
                d_clu = float(1.0 - cents[lab2cid[lab[r]]] @ cm)
                if w == q:
                    pos_d.append(d_seg)
                    pos_c.append(d_clu)
                else:
                    neg_d.append(d_seg)
                    neg_c.append(d_clu)
        e, far, frr = eer(pos_d, neg_d)
        e_c, far_c, frr_c = eer(pos_c, neg_c)
        # ---- 段级 (跨场 strict / 同场 loose) + 天花板 + 这 6 人被谁认领 ----
        out = {"pool_size": len(pool),
               "eer_cross": round(e, 4) if e is not None else None,
               "eer_far": round(far, 4) if far is not None else None,
               "eer_frr": round(frr, 4) if frr is not None else None,
               "eer_cluster": round(e_c, 4) if e_c is not None else None,
               "eer_cluster_far": round(far_c, 4) if far_c is not None else None,
               "eer_cluster_frr": round(frr_c, 4) if frr_c is not None else None,
               "n_pos": len(pos_d), "n_neg": len(neg_d)}
        for pname, poolf in (("strict", loo_pool), ("loose", loose_pool)):
            tot = acc = 0
            ceil_num = ceil_den = 0
            by_person = collections.defaultdict(lambda: [0, 0])
            claimed = collections.Counter()
            per_cluster = []
            for mid in meetings:
                if mid not in clusters:
                    continue
                rows, lab, cents = clusters[mid]
                pl = poolf(pool, mid)
                names, margin, absd, absdn = cluster_names(rows, lab, cents, pl)
                sizes = collections.Counter(lab.tolist())
                for ci in range(len(cents)):
                    members = collections.Counter()
                    for r, i in enumerate(rows):
                        if lab[r] == ci and seg_truth.get(i):
                            members[seg_truth[i]] += 1
                    top = members.most_common(1)[0][0] if members else None
                    if top:
                        ceil_num += members[top]
                        ceil_den += sum(members.values())
                        claimed[names[ci]] += int(sizes.get(ci, 0))
                    per_cluster.append({"mid": mid, "size": int(sizes.get(ci, 0)),
                                        "name": names[ci], "true_top": top,
                                        "margin": margin[ci], "absd": absd[ci],
                                        "absd_norm": absdn[ci]})
                for r, i in enumerate(rows):
                    w = seg_truth.get(i)
                    if not w:
                        continue
                    tot += 1
                    if names[lab[r]] == w:
                        acc += 1
                        by_person[w][0] += 1
                    by_person[w][1] += 1
            out["seg_acc_" + pname] = round(acc / max(1, tot), 4)
            out["n_truth_seg_" + pname] = tot
            out["ceiling_" + pname] = round(ceil_num / max(1, ceil_den), 4) if ceil_den else None
            out["by_person_" + pname] = {
                w: {"correct": c, "n": n, "rate": (round(c / n, 4) if n else None)}
                for w, (c, n) in sorted(by_person.items())}
            if pname == "strict":
                out["_per_cluster"] = per_cluster
                out["claimed_by"] = dict(claimed)
        return out

    def eval_curves(pool, meetings):
        """三种弃权判据的 coverage–selective-risk 曲线 + 每场的簇信息。"""
        clusters = {mid: cluster(mid) for mid in meetings if per_meeting.get(mid)}
        seg_of_cluster = collections.defaultdict(list)
        cluster_info = []
        total_truth = 0
        for mid in meetings:
            items = segs_by_meeting.get(mid)
            if not items or mid not in clusters:
                continue
            rows, lab, cents = clusters[mid]
            pl = loo_pool(pool, mid)
            names, margin, absd, absdn = cluster_names(rows, lab, cents, pl)
            sizes = collections.Counter(lab.tolist())
            for ci in range(len(cents)):
                true_top = None
                members = collections.Counter()
                for r, i in enumerate(rows):
                    if lab[r] == ci and seg_truth.get(i):
                        members[seg_truth[i]] += 1
                if members:
                    true_top = members.most_common(1)[0][0]
                cluster_info.append({"mid": mid, "size": int(sizes.get(ci, 0)),
                                     "name": names[ci], "true_top": true_top,
                                     "margin": margin[ci], "absd": absd[ci],
                                     "absd_norm": absdn[ci],
                                     "named_ok": (names[ci] == true_top) if true_top else None})
                for r, i in enumerate(rows):
                    if lab[r] == ci:
                        seg_of_cluster[(mid, ci)].append(
                            (i, names[ci], margin[ci], absd[ci], absdn[ci]))
            total_truth += sum(1 for w, i in items)

        def curve(idx, mode):
            vals = sorted({round(items[0][idx], 6) for items in seg_of_cluster.values() if items})
            if len(vals) > 250:
                sel = np.linspace(0, len(vals) - 1, 250).astype(int)
                vals = [vals[i] for i in sel]
            out = []
            for thr in vals:
                n_cov = acc_cov = 0
                for items in seg_of_cluster.values():
                    if not items:
                        continue
                    v = items[0][idx]
                    reject = (v > thr) if mode == "gt" else (v < thr)
                    if reject:
                        continue
                    for i, nm, *_ in items:
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

        return {"margin": curve(2, "lt"), "absd": curve(3, "gt"),
                "absd_norm": curve(4, "gt")}, cluster_info, total_truth

    # ================================================================
    # 评测
    # ================================================================
    report = {"pool13": POOL13, "diag_关小未": diag,
              "new_pool": NEW_POOL, "blocked_pool": BLOCKED_POOL,
              "k_fixed": K_FIXED, "dev_meetings": DEV_MEETINGS,
              "test_meetings": TEST_MEETINGS}

    for pname, pool in (("A_现役13", pool_a), ("B_扩池+5", pool_b),
                        ("C_扩池+5+关小未(现役坏质心)", pool_c),
                        ("D_扩池+5+关小未(台账重建)", pool_d)):
        log("=== 池 %s (%d 人) ===" % (pname, len(pool)))
        for tag, meetings in (("dev", DEV_MEETINGS), ("test", TEST_MEETINGS),
                              ("all9", DEV_MEETINGS + TEST_MEETINGS)):
            r = eval_pool(pool, meetings)
            report.setdefault("pools", {}).setdefault(pname, {})[tag] = r
            log("  %-5s EER[段] %.4f | EER[簇质心] %.4f (FAR %.3f/FRR %.3f) | 段级strict %.4f (天花板 %.4f) | loose %.4f" % (
                tag, r["eer_cross"], r["eer_cluster"], r["eer_cluster_far"], r["eer_cluster_frr"],
                r["seg_acc_strict"], r["ceiling_strict"], r["seg_acc_loose"]))
        # 这 6 人的段当前被判给了谁
        r = report["pools"][pname]["all9"]
        who_claims = {}
        for w in NEW_POOL + BLOCKED_POOL:
            rows = [i for mm, i in truth_rows.get(w, [])]
            who_claims[w] = {"n_truth_seg": len(rows),
                              "meetings": sorted({mm for mm, _ in truth_rows.get(w, [])})}
        report.setdefault("six_people", {})[pname] = who_claims

    # ---- ① 归一化弃权 + 迁移性 (池 A, 固定 k=6) ----
    log("=== ① 归一化弃权 + 迁移性 (池 A) ===")
    cur_dev, ci_dev, tot_dev = eval_curves(pool_a, DEV_MEETINGS)
    cur_test, ci_test, tot_test = eval_curves(pool_a, TEST_MEETINGS)
    cur_all, ci_all, tot_all = eval_curves(pool_a, DEV_MEETINGS + TEST_MEETINGS)
    migration = {}
    for cname in ("margin", "absd", "absd_norm"):
        cd = cur_dev[cname]
        # 在**选参数集**上选使 coverage≈0.5 的阈值
        tgt = min(cd, key=lambda x: abs(x["coverage"] - 0.5)) if cd else None
        thr = tgt["thr"] if tgt else None
        ct = cur_test[cname]
        if thr is not None:
            # 在验证集上用**同一个**阈值
            cand = min(ct, key=lambda x: abs(x["thr"] - thr)) if ct else None
        else:
            cand = None
        migration[cname] = {
            "dev_at_cov0.5": tgt,
            "test_same_thr": cand,
            "test_coverage_drift": (round(cand["coverage"] - tgt["coverage"], 4)
                                    if (cand and tgt) else None),
            "test_selective_risk_at_same_thr": (cand["selective_risk"] if cand else None),
            "dev_selective_risk_at_cov0.5": (tgt["selective_risk"] if tgt else None),
        }
        log("  判据 %-10s 选参集 cov %.3f risk %.4f (thr %.4f) ⇒ 验证集同 thr: cov %.3f risk %.4f | 覆盖漂移 %s" % (
            cname, tgt["coverage"], tgt["selective_risk"], thr,
            cand["coverage"], cand["selective_risk"],
            migration[cname]["test_coverage_drift"]))
    report["abstain_curves"] = {"dev": cur_dev, "test": cur_test, "all9": cur_all}
    report["abstain_migration"] = migration

    # ---- ③ 产品形态数字 ----
    log("=== ③ 产品形态数字 ===")
    prod = {}
    prod["per_meeting_clusters"] = {}
    tot_clusters = 0
    tot_wrong = 0
    tot_segs = 0
    tot_segs_fixed = 0
    for ci in ci_all:
        mid = ci["mid"]
        d = prod["per_meeting_clusters"].setdefault(mid, {"n_clusters": 0, "n_wrong": 0,
                                                         "segs": 0, "segs_in_wrong": 0})
        d["n_clusters"] += 1
        d["segs"] += ci["size"]
        tot_clusters += 1
        tot_segs += ci["size"]
        if ci["named_ok"] is False:
            d["n_wrong"] += 1
            d["segs_in_wrong"] += ci["size"]
            tot_wrong += 1
            tot_segs_fixed += ci["size"]
        elif ci["named_ok"] is None:
            d["n_unknown"] = d.get("n_unknown", 0) + 1
    prod["total_clusters"] = tot_clusters
    prod["total_wrong_clusters"] = tot_wrong
    prod["total_segments"] = tot_segs
    prod["segments_in_wrong_clusters"] = tot_segs_fixed
    prod["human_edits_needed"] = tot_wrong
    prod["seg_acc_if_human_fixes_wrong"] = round(1 - tot_segs_fixed / max(1, tot_segs), 4)
    prod["seg_acc_auto"] = report["pools"]["A_现役13"]["all9"]["seg_acc_strict"]
    prod["seg_acc_ceiling"] = report["pools"]["A_现役13"]["all9"]["ceiling_strict"]
    for mid, d in sorted(prod["per_meeting_clusters"].items()):
        log("  m%-4d 簇 %2d (其中自动命名错 %d) | 段 %5d (在错簇里 %5d)" % (
            mid, d["n_clusters"], d["n_wrong"], d["segs"], d["segs_in_wrong"]))
    log("  合计: %d 簇 / 人工要改 %d 个 / 段 %d (改完准确率 %.4f, 自动 %.4f, 天花板 %.4f)" % (
        tot_clusters, tot_wrong, tot_segs, prod["seg_acc_if_human_fixes_wrong"],
        prod["seg_acc_auto"], prod["seg_acc_ceiling"]))
    report["product_shape"] = prod

    outp = os.path.join(args.out, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
