"""Phase 1 (声纹换代) —— 步骤 2: ERes2Net(现役) vs ERes2NetV2 的同口径对比。

⚠️ **跨模型不可横比的东西**
--------------------------
两个模型的嵌入空间互不相通 ⇒ **余弦距离的绝对值不可跨模型比较**
("0.35 比 0.40 好" 在两个空间里没有意义)。
⇒ 本脚本只用**空间无关**的指标做跨模型结论:
  ① **argmin 正确率** (无阈值: 真主人的质心是不是候选池里最近的) —— 主指标
  ② **双指标**: 认回 / 真抢走 / 净增益 (计数) —— 主指标
  ③ **验证 EER** (跨场留出的正负对距离分布) —— 主指标
  ④ 同空间内的距离分布 —— **只作参考**, 不用于跨模型结论

⚠️ **候选池必须与被测嵌入同空间** (本脚本第一版的 bug)
-------------------------------------------------------
Phase 0 的双指标拿「库内现役质心」当候选池 —— 那在 ERes2Net 空间成立,
但在 V2 空间**拿 ERes2Net 的向量去比 V2 的向量 = 纯噪声**。
⇒ 本脚本的候选池**可插拔**, 且强制与被测空间一致:
  - `pool_db`      : 库内现役质心 (只在 ERes2Net 空间合法) ⇒ 生产现状参照
  - `pool_rebuilt` : 用**同一空间**里该成员的台账段均值重建的成员级质心
                     ⇒ **跨模型比较只用这个** (构造相同, 只差模型)

产出: /tmp/vp/phase1/analysis.json

用法 (容器内):
    python /tmp/vp/enroll_phase1_analyze.py --phase0 /tmp/vp/phase0 --phase1 /tmp/vp/phase1
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
VARIANTS = ("seg_old", "c5", "c10", "c10_longest", "whole")


def log(msg):
    print("[phase1-analyze] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def med(xs):
    return float(statistics.median(xs)) if xs else None


def pct(xs, p):
    if not xs:
        return None
    s = sorted(xs)
    k = (len(s) - 1) * p
    lo, hi = int(np.floor(k)), int(np.ceil(k))
    if lo == hi:
        return float(s[lo])
    return float(s[lo] + (s[hi] - s[lo]) * (k - lo))


def eer(pos, neg):
    """验证 EER: 正样本距离应小于负样本距离。返回 (EER, FAR@EER, FRR@EER)。

    ⚠️ **用 minimax 形式** (EER = min_t max(FAR(t), FRR(t))), 不用「两条曲线交点插值」。
       交点插值在曲线跳变/退化时会返回 0 或 None —— 那是**状态字段在说谎**
       (类 20.220): 上一版就出现过 EER=0.0 的退化值。
    ⚠️ 必须**向量化**: 朴素写法对每个候选阈值扫一遍全部样本 ⇒ O(n²) 的 Python 循环
       (本项目 n≈1e4 ⇒ 会跑几十分钟)。这里用排序 + searchsorted ⇒ O(n log n)。
    """
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
    ap.add_argument("--phase0", default="/tmp/vp/phase0")
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--write-candidates", action="store_true",
                    help="把 V2 候选质心写进新表 member_enrollment_candidates_eres2netv2_phase1_20261031 "
                         "(**不改 members**); 默认不写")
    args = ap.parse_args()

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    RUNS = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    E_ERES = np.load(os.path.join(args.phase1, "emb_eres.npz"))["emb"].astype(np.float32)
    E_V2 = np.load(os.path.join(args.phase1, "emb_v2.npz"))["emb"].astype(np.float32)
    log("素材 %d 条; ERes2Net %s / V2 %s" % (len(META), E_ERES.shape, E_V2.shape))
    assert len(META) == len(E_ERES) == len(E_V2), "行数不一致"

    # ---- 台账真值 ----
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
    log("台账真值段 %d / 生产段 %d" % (
        len(seg_truth), sum(1 for m in META if m["kind"] == "seg")))

    chunk_rows = collections.defaultdict(list)
    whole_rows = {}
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            continue
        if m["kind"] in ("chunk10", "chunk5"):
            chunk_rows[(m["kind"], m["run"])].append(i)
        elif m["kind"] == "whole":
            whole_rows[m["run"]] = i
    run_by_rid = {r["rid"]: r for r in RUNS}

    truth_rows = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        w = seg_truth.get(i)
        if w:
            truth_rows[w].append((m["meeting"], i))

    # ---- 库内生产质心 (只对 ERes2Net 空间合法) ----
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
    log("库内生产质心 %d 人: %s" % (len(POOL13), POOL13))

    def build_variants(E):
        """按 Phase 0 的口径建 5 种变体 + 一个成员级「重建池」。"""
        cents = collections.defaultdict(dict)
        agg = collections.defaultdict(list)
        for i, m in enumerate(META):
            if m["kind"] != "seg":
                continue
            w = seg_truth.get(i)
            if w:
                agg[(w, m["meeting"])].append(i)
        for (w, mid), rows in agg.items():
            cents["seg_old"][(w, mid)] = norm(np.mean([E[i] for i in rows], axis=0))
        for kind, name in (("chunk10", "c10"), ("chunk5", "c5")):
            g = collections.defaultdict(list)
            for (k, rid), rows in chunk_rows.items():
                if k != kind:
                    continue
                r = run_by_rid.get(rid)
                if r:
                    g[(r["who"], r["meeting"])].extend(rows)
            for key, rows in g.items():
                cents[name][key] = norm(np.mean([E[i] for i in rows], axis=0))
        gw = collections.defaultdict(list)
        for rid, i in whole_rows.items():
            r = run_by_rid.get(rid)
            if r:
                gw[(r["who"], r["meeting"])].append(i)
        for key, rows in gw.items():
            cents["whole"][key] = norm(np.mean([E[i] for i in rows], axis=0))
        best = {}
        for r in RUNS:
            k = (r["who"], r["meeting"])
            if k not in best or (r["e"] - r["s"]) > (best[k]["e"] - best[k]["s"]):
                best[k] = r
        for k, r in best.items():
            rows = chunk_rows.get(("chunk10", r["rid"]))
            if rows:
                cents["c10_longest"][k] = norm(np.mean([E[i] for i in rows], axis=0))
        # 成员级「重建池」: 该成员**全部**台账段的均值 (与库内生产质心同构, 但在本空间)
        pool_rebuilt = {}
        for w in POOL13:
            rows = [i for mm, i in truth_rows.get(w, [])]
            if rows:
                pool_rebuilt[w] = norm(np.mean([E[i] for i in rows], axis=0))
        return cents, pool_rebuilt

    def evaluate(E, cents, pool, name, pool_name):
        res = {}
        common = set(cents["seg_old"])
        for v in VARIANTS:
            if v != "seg_old":
                common &= set(cents[v])

        # ---- argmin 正确率 (无阈值; 用变体自己的质心集) ----
        # ⚠️ 热点: 11358 段 × 47 质心 ⇒ 质心先堆成矩阵, 一次矩阵乘算全部
        truth_idx = [i for i, m in enumerate(META)
                     if m["kind"] == "seg" and seg_truth.get(i)]
        truth_who = [seg_truth[i] for i in truth_idx]
        truth_meet = [META[i]["meeting"] for i in truth_idx]
        truth_mat = E[truth_idx] if truth_idx else np.zeros((0, 192), dtype=np.float32)
        for v in VARIANTS:
            cmap = cents[v]
            keys = sorted(cmap)
            C = np.stack([cmap[k] for k in keys]) if keys else np.zeros((0, 192), dtype=np.float32)
            owner = np.array([k[0] for k in keys])
            people = sorted(set(owner.tolist()))
            ok = tot = 0
            ds, dd = [], []
            if C.shape[0]:
                D = 1.0 - truth_mat @ C.T          # (n_truth, n_centroids)
                for r in range(len(truth_idx)):
                    q = truth_who[r]
                    if q not in people:
                        continue
                    same_mask = owner == q
                    if not same_mask.any():
                        continue
                    # 本人本场有质心 ⇒ 用它; 否则取本人其它场里最近的一个
                    hit_key = None
                    for kk in keys:
                        if kk[0] == q and kk[1] == truth_meet[r]:
                            hit_key = kk
                            break
                    if hit_key is not None:
                        j = keys.index(hit_key)
                        d_same = float(D[r, j])
                    else:
                        d_same = float(D[r, same_mask].min())
                    d_diff = float(D[r, ~same_mask].min()) if (~same_mask).any() else None
                    if d_diff is None:
                        continue
                    tot += 1
                    ds.append(d_same)
                    dd.append(d_diff)
                    if d_same < d_diff:
                        ok += 1
            res.setdefault(v, {})["argmin"] = {
                "n": tot, "correct": ok, "rate": round(ok / tot, 4) if tot else None,
                "d_same_median": round(med(ds), 4) if ds else None,
                "d_diff_median": round(med(dd), 4) if dd else None}

        # ---- 双指标 (候选池与被测空间一致) ----
        # ⚠️ 抢走循环是热点 (单元数 × 真值段数 × 池大小) ⇒ 池向量先堆成矩阵, 一次矩阵乘算全部
        pool_names = sorted(pool)
        pool_mat = (np.stack([pool[q] for q in pool_names]) if pool_names
                    else np.zeros((0, 192), dtype=np.float32))
        for v in VARIANTS:
            cmap = cents[v]
            hit = steal_real = steal_mis = steal_no = 0
            seg_total = 0
            d_new_all, d_comp_all = [], []
            for (w, mid), cen in sorted(cmap.items()):
                if (w, mid) not in common:
                    continue
                own = [(mm, i) for mm, i in truth_rows.get(w, []) if mm != mid]
                if not own:
                    continue
                others = [q for q in pool_names if q != w]
                seg_total += len(own)
                if pool_mat.shape[0]:
                    comp_idx = [pool_names.index(q) for q in others]
                    for mm, i in own:
                        vv = E[i]
                        d_all = 1.0 - pool_mat @ vv
                        d_comp = float(d_all[comp_idx].min()) if comp_idx else 9.9
                        d_comp_all.append(d_comp)
                        d_new = dist(vv, cen)
                        d_new_all.append(d_new)
                        if d_new < d_comp:
                            hit += 1
                else:
                    for mm, i in own:
                        d_new = dist(E[i], cen)
                        d_new_all.append(d_new)
                        if d_new < 9.9:
                            hit += 1
                # 抢走 (全部有台账的会议)
                for q, rows in truth_rows.items():
                    if q == w:
                        continue
                    c_true = pool.get(q)
                    qi = pool_names.index(q) if c_true is not None else None
                    for mm, i in rows:
                        vv = E[i]
                        d_c = dist(vv, cen)
                        if pool_mat.shape[0]:
                            d_all = 1.0 - pool_mat @ vv
                            dmin = float(d_all.min())
                            argmin = pool_names[int(d_all.argmin())]
                        else:
                            dmin, argmin = 9.9, None
                        if c_true is None:
                            if d_c < dmin:
                                steal_no += 1
                        else:
                            d_true = float(d_all[qi])
                            if d_c < d_true:
                                if argmin == q:
                                    steal_real += 1
                                else:
                                    steal_mis += 1
            res.setdefault(v, {})["dual"] = {
                "pool_name": pool_name, "units": len(common),
                "recall_segments": seg_total, "recall": hit,
                "recall_rate": round(hit / max(1, seg_total), 4),
                "stolen_real": steal_real, "stolen_misnamed": steal_mis,
                "stolen_noowner": steal_no, "net_gain": hit - steal_real,
                "d_new_median": round(med(d_new_all), 4) if d_new_all else None,
                "d_comp_median": round(med(d_comp_all), 4) if d_comp_all else None}

        # ---- 验证 EER: 只在**所有变体共有**的 (会议, 成员) 组合上算 ----
        # ⚠️ 各变体覆盖的 (人,场) 单元数不同 (seg_old 47 / whole 37) ⇒ 留出质心可得性不同
        #    ⇒ EER 的样本集也不同 ⇒ **必须锁死共同样本**, 否则是在不同难度子集上横比
        #    (类 20.249 ⑧: 「两次不一致」的第一嫌疑是输入变了)
        segs_by_meeting = collections.defaultdict(list)
        for w, rows in truth_rows.items():
            for mm, i in rows:
                segs_by_meeting[mm].append((w, i))
        avail = {}
        for v in VARIANTS:
            cmap = cents[v]
            s = set()
            for mid, items in segs_by_meeting.items():
                for q in {w for w, _ in items}:
                    alts = [cmap[(q, m2)] for (ww, m2) in cmap
                            if ww == q and m2 != mid]
                    if alts:
                        s.add((mid, q))
            avail[v] = s
        common_MP = set.intersection(*avail.values()) if avail else set()
        res["_avail"] = {v: len(s) for v, s in avail.items()}
        res["_common_MP"] = len(common_MP)
        for v in VARIANTS:
            cmap = cents[v]
            pos, neg = [], []
            for (mid, q) in sorted(common_MP):
                items = segs_by_meeting[mid]
                alts = [cmap[(q, m2)] for (ww, m2) in cmap if ww == q and m2 != mid]
                if not alts:
                    continue
                cen = norm(np.mean(alts, axis=0))
                for w, i in items:
                    d = float(1.0 - E[i] @ cen)
                    if w == q:
                        pos.append(d)
                    else:
                        neg.append(d)
            e, far, frr = eer(pos, neg)
            res.setdefault(v, {})["eer"] = {
                "n_pos": len(pos), "n_neg": len(neg),
                "eer": round(e, 4) if e is not None else None,
                "far_at_eer": round(far, 4) if far is not None else None,
                "frr_at_eer": round(frr, 4) if frr is not None else None,
                "pos_median": round(med(pos), 4) if pos else None,
                "neg_median": round(med(neg), 4) if neg else None}

            # ---- 诊断: **同场** EER (质心就用该场自己的段建的) ----
            # 用途: 这是**最容易**的验证任务。若 V2 在这里明显优于现役 ⇒ V2 实现有效,
            #       跨场差距是**场景难度**主导而非模型弱; 若这里也打平 ⇒ 警惕实现问题。
            spos, sneg = [], []
            for (mid, q) in sorted(common_MP):
                cen = cmap.get((q, mid))
                if cen is None:
                    continue
                for w, i in segs_by_meeting[mid]:
                    d = float(1.0 - E[i] @ cen)
                    (spos if w == q else sneg).append(d)
            se, sfar, sfrr = eer(spos, sneg)
            res.setdefault(v, {})["eer_same_meeting"] = {
                "n_pos": len(spos), "n_neg": len(sneg),
                "eer": round(se, 4) if se is not None else None,
                "far_at_eer": round(sfar, 4) if sfar is not None else None,
                "frr_at_eer": round(sfrr, 4) if sfrr is not None else None}

        # ---- 同空间内的距离分布 (只作参考) ----
        for v in VARIANTS:
            cmap = cents[v]
            wm = collections.defaultdict(list)
            for (w, mid) in cmap:
                if (w, mid) in common:
                    wm[w].append(mid)
            cc = []
            for w, mids in wm.items():
                mids = sorted(mids)
                for a in range(len(mids)):
                    for b in range(a + 1, len(mids)):
                        cc.append(dist(cmap[(w, mids[a])], cmap[(w, mids[b])]))
            keys = sorted(k for k in cmap if k in common)
            ddf = [dist(cmap[keys[a]], cmap[keys[b]])
                   for a in range(len(keys)) for b in range(a + 1, len(keys))
                   if keys[a][0] != keys[b][0]]
            res.setdefault(v, {})["within_space"] = {
                "same_person_cross_median": round(med(cc), 4) if cc else None,
                "same_person_cross_n": len(cc),
                "diff_person_median": round(med(ddf), 4) if ddf else None,
                "diff_person_n": len(ddf)}
        res["_common_units"] = len(common)
        return res

    cents_e, pool_e_rebuilt = build_variants(E_ERES)
    cents_v, pool_v_rebuilt = build_variants(E_V2)

    # ERes2Net 用「库内现役池」(生产现状参照) + 「重建池」(模型效应对照)
    res_eres_db = evaluate(E_ERES, cents_e, db_cent, "ERes2Net", "pool_db")
    res_eres = evaluate(E_ERES, cents_e, pool_e_rebuilt, "ERes2Net", "pool_rebuilt")
    res_v2 = evaluate(E_V2, cents_v, pool_v_rebuilt, "ERes2NetV2", "pool_rebuilt")

    # ---- EER 的样本集必须**跨模型也一致** (可用性只取决于素材, 与空间无关) ----
    assert res_eres["_common_MP"] == res_v2["_common_MP"], \
        "两模型的 EER 样本集不一致 ⇒ 输入漂移 (类 20.249 ⑧)"
    log("EER 共同样本: (会议,成员) 组合 %d 个; 各变体可用组合数 %s" % (
        res_eres["_common_MP"], res_eres["_avail"]))

    # ---- 回归核对: ERes2Net + pool_db + seg_old 必须复现 Phase 0 的数 ----
    p0 = json.load(open(os.path.join(args.phase0, "analysis.json"), encoding="utf-8"))
    checks = []
    for v in ("seg_old", "c10", "whole", "c10_longest"):
        for metric, key in (("argmin", "rate"), ("recall", "recall"),
                            ("steal", "stolen_real"), ("net", "net_gain")):
            if metric == "argmin":
                a = res_eres_db[v]["argmin"][key]
                b = p0["variants"][v]["argmin_accuracy"]["rate"]
            else:
                a = res_eres_db[v]["dual"][key]
                b = p0["variants"][v]["dual"]["totals"][
                    {"recall": "recall_new", "steal": "stolen_real",
                     "net": "net_gain"}[metric]]
            checks.append({"variant": v, "metric": metric, "phase1": a, "phase0": b,
                           "match": a == b})
    log("回归核对 (Phase1 的 ERes2Net+pool_db 必须复现 Phase 0):")
    for c in checks:
        log("   %-12s %-7s phase1=%s phase0=%s %s" % (
            c["variant"], c["metric"], c["phase1"], c["phase0"],
            "✅" if c["match"] else "❌"))
    all_match = all(c["match"] for c in checks)

    # ---- 跨模型对照表 (只用空间无关指标) ----
    cmp_rows = []
    for v in VARIANTS:
        row = {"variant": v,
               "argmin_eres": res_eres[v]["argmin"]["rate"],
               "argmin_v2": res_v2[v]["argmin"]["rate"],
               "eer_eres": res_eres[v]["eer"]["eer"],
               "eer_v2": res_v2[v]["eer"]["eer"],
               "recall_eres": res_eres[v]["dual"]["recall"],
               "recall_v2": res_v2[v]["dual"]["recall"],
               "steal_eres": res_eres[v]["dual"]["stolen_real"],
               "steal_v2": res_v2[v]["dual"]["stolen_real"],
               "net_eres": res_eres[v]["dual"]["net_gain"],
               "net_v2": res_v2[v]["dual"]["net_gain"]}
        row["argmin_delta_pts"] = (round(100 * (row["argmin_v2"] - row["argmin_eres"]), 2)
                                   if row["argmin_eres"] is not None else None)
        row["net_delta"] = row["net_v2"] - row["net_eres"]
        row["eer_same_meeting_eres"] = res_eres[v]["eer_same_meeting"]["eer"]
        row["eer_same_meeting_v2"] = res_v2[v]["eer_same_meeting"]["eer"]
        cmp_rows.append(row)
        log("对照 %-12s argmin %.1f%% → %.1f%% (%+.1f 点) | EER(跨场) %s → %s | EER(同场) %s → %s | 认回 %d → %d | 真抢走 %d → %d | 净增益 %d → %d (%+d)" % (
            v, 100 * row["argmin_eres"], 100 * row["argmin_v2"],
            row["argmin_delta_pts"], row["eer_eres"], row["eer_v2"],
            row["eer_same_meeting_eres"], row["eer_same_meeting_v2"],
            row["recall_eres"], row["recall_v2"], row["steal_eres"], row["steal_v2"],
            row["net_eres"], row["net_v2"], row["net_delta"]))

    out = {"pool13": POOL13,
           "common_units": res_eres["_common_units"],
           "models": {"ERes2Net": {"pool_db": res_eres_db, "pool_rebuilt": res_eres},
                      "ERes2NetV2": {"pool_rebuilt": res_v2}},
           "cross_model_table": cmp_rows,
           "phase0_regression": {"checks": checks, "all_match": all_match}}
    outp = os.path.join(args.phase1, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s (Phase0 回归核对全过 = %s)" % (outp, all_match))

    # ================================================================
    # 候选质心落库 (新表, **不改 members**)
    # ⚠️ **必须单开一张表**: ERes2Net 与 ERes2NetV2 的向量在**不同空间**,
    #    放进同一张表而不带 model 列 ⇒ 同名不同物 (类 20.242 / 20.225)
    # ================================================================
    if args.write_candidates:
        from sqlalchemy import text as sqlt
        engine, Session = create_celery_engine_and_session()
        async with Session() as db:
            await db.execute(sqlt(
                "CREATE TABLE IF NOT EXISTS member_enrollment_candidates_eres2netv2_phase1_20261031 ("
                "model text, variant text, member_name text, meeting_id int,"
                " centroid halfvec(192), n_windows int, speech_sec numeric, run_secs numeric,"
                " argmin_rate numeric, eer numeric, net_gain int, created_at timestamptz default now())"))
            await db.execute(sqlt(
                "DELETE FROM member_enrollment_candidates_eres2netv2_phase1_20261031"))
            n_rows = 0
            for variant, cmap in cents_v.items():
                for (w, mid), vec in sorted(cmap.items()):
                    rs = [r for r in RUNS if r["who"] == w and r["meeting"] == mid]
                    speech = sum(r.get("speech_sec", 0) for r in rs)
                    rsec = sum(r["e"] - r["s"] for r in rs)
                    nwin = sum(len(chunk_rows.get(("chunk10", r["rid"]), [])) for r in rs) or len(rs)
                    await db.execute(sqlt(
                        "INSERT INTO member_enrollment_candidates_eres2netv2_phase1_20261031 "
                        "(model, variant, member_name, meeting_id, centroid, n_windows, "
                        " speech_sec, run_secs, argmin_rate, eer, net_gain) VALUES "
                        "('ERes2NetV2',:v,:w,:m,CAST(:c AS halfvec),:n,:s,:r,:a,:e,:g)"), {
                        "v": variant, "w": w, "m": mid,
                        # ⛔ pgvector 列必须收**文本** '[f1,f2,...]' (类 20.248 ⑤)
                        "c": "[" + ",".join("%.9g" % float(x) for x in vec) + "]",
                        "n": nwin, "s": speech, "r": rsec,
                        "a": res_v2[variant]["argmin"]["rate"],
                        "e": res_v2[variant]["eer"]["eer"],
                        "g": res_v2[variant]["dual"]["net_gain"]})
                    n_rows += 1
            await db.commit()
        log("V2 候选质心已落 member_enrollment_candidates_eres2netv2_phase1_20261031 "
            "(%d 行, **members 未改**)" % n_rows)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
