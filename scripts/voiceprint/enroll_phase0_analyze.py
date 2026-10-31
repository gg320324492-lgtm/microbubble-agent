"""Phase 0 (声纹换代) —— 步骤 2: 距离矩阵 + 类 20.226 双指标 + Phase 0 判定。

读步骤 1 的产出 (/tmp/vp/phase0/{emb.npz,meta.json,runs.json}) 与库内生产质心,
输出:
  /tmp/vp/phase0/analysis.json    全部数字(机器可读)
  /tmp/vp/phase0/analysis.md     表格(人可读)

⛔ **只读生产表, 不写任何生产数据**。
⛔ 纪律: 类 20.226(双指标+不设自造阈值) / 20.243(先量基线、报候选池名单) /
   20.220(基线要能复现) / 20.242(缓存键用完整对象键) / 20.249(候选池变化会漂移判据)

用法 (容器内):
    python /tmp/vp/enroll_phase0_analyze.py --phase0 /tmp/vp/phase0
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
# 类 20.243: 本项目跨场同人距离基线(现役, 蒋芦笛 255质心↔250台账段)
PUBLISHED_CROSS_BASE = 0.5038


def log(msg):
    print("[phase0-analyze] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def d(a, b):
    """余弦距离 (输入已归一化)。"""
    return float(1.0 - np.dot(a, b))


def median(xs):
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


def boot_ci(xs, n=4000, seed=20261031):
    """中位数的 bootstrap 95% CI (固定种子 ⇒ 可复现)。"""
    if not xs:
        return (None, None)
    rng = np.random.default_rng(seed)
    a = np.asarray(xs, dtype=np.float64)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    meds = np.median(a[idx], axis=1)
    return float(np.percentile(meds, 2.5)), float(np.percentile(meds, 97.5))


def load_ledger_blocks(paths):
    blocks = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        with open(p, encoding="utf-8") as fh:
            d0 = json.load(fh)
        for b in d0["blocks"]:
            if b.get("_可用") is False or b["who"] in NON_PERSON:
                continue
            blocks.append({"who": b["who"], "meeting": int(b["meeting"]),
                           "s": float(b["s"]), "e": float(b["e"])})
    return blocks


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase0", default="/tmp/vp/phase0")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--write-candidates", action="store_true",
                    help="把候选质心写进新表 member_enrollment_candidates_phase0_20261031 "
                         "(**不改 members**); 默认不写")
    args = ap.parse_args()

    E = np.load(os.path.join(args.phase0, "emb.npz"))["emb"].astype(np.float32)
    META = json.load(open(os.path.join(args.phase0, "meta.json"), encoding="utf-8"))
    RUNS = json.load(open(os.path.join(args.phase0, "runs.json"), encoding="utf-8"))
    log("嵌入 %d 条, 连续段 %d 条" % (len(E), len(RUNS)))
    assert len(E) == len(META), "emb 与 meta 行数不一致"

    # ---- 台账真值: 给每个生产段打上「这段是谁」的标签 ----
    blocks = load_ledger_blocks(args.ledgers.split(","))
    by_meeting = collections.defaultdict(list)
    for b in blocks:
        by_meeting[b["meeting"]].append(b)
    seg_truth = {}          # (meeting, seg_idx) -> who
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        mid_t = (m["start"] + m["end"]) / 2.0
        for b in by_meeting.get(m["meeting"], []):
            if b["s"] <= mid_t <= b["e"]:
                seg_truth[i] = b["who"]
                break
    log("台账真值段 %d / 生产段 %d" % (len(seg_truth), sum(1 for m in META if m["kind"] == "seg")))

    # ---- 索引 ----
    seg_idx = {}            # (meeting, seg_idx) -> 行号
    chunk_rows = collections.defaultdict(list)   # (kind, rid) -> 行号
    whole_rows = {}
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            seg_idx[(m["meeting"], m["seg_idx"])] = i
        elif m["kind"] in ("chunk10", "chunk5"):
            chunk_rows[(m["kind"], m["run"])].append(i)
        elif m["kind"] == "whole":
            whole_rows[m["run"]] = i
    run_by_rid = {r["rid"]: r for r in RUNS}

    # ---- 建质心 (多种口径) ----
    # V_seg   : 旧口径 —— 该人在该场的**短段**均值 (生产质心的建法)
    # V_c5/c10: 长段切 5s/10s 窗后取均值
    # V_whole : 长段整段嵌入
    # V_c10L  : 只用该场**最长**的那条连续段的 10s 窗均值
    def mean_rows(rows):
        if not rows:
            return None
        return norm(np.mean([E[i] for i in rows], axis=0))

    cents = collections.defaultdict(dict)     # variant -> (who, meeting) -> vec
    seg_rows_of = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        w = seg_truth.get(i)
        if w:
            seg_rows_of[(w, m["meeting"])].append(i)
    for (w, mid), rows in seg_rows_of.items():
        v = mean_rows(rows)
        if v is not None:
            cents["seg_old"][(w, mid)] = v

    for kind, name in (("chunk10", "c10"), ("chunk5", "c5")):
        # ⛔ 必须**累加**同一人同场的**所有**连续段的窗, 不能"后写覆盖前写"
        #    (一个人在一场里常有多条连续段 ⇒ 覆盖等于只用其中一条 ⇒ 结果不可比)
        agg = collections.defaultdict(list)
        for (k, rid), rows in chunk_rows.items():
            if k != kind:
                continue
            r = run_by_rid.get(rid)
            if r is None:
                continue
            agg[(r["who"], r["meeting"])].extend(rows)
        for key, rows in agg.items():
            v = mean_rows(rows)
            if v is not None:
                cents[name][key] = v

    # whole: 同一人同场有多条连续段 ⇒ 取「各条整段嵌入」的均值
    agg_whole = collections.defaultdict(list)
    for rid, i in whole_rows.items():
        r = run_by_rid.get(rid)
        if r is None:
            continue
        agg_whole[(r["who"], r["meeting"])].append(i)
    for key, rows in agg_whole.items():
        cents["whole"][key] = mean_rows(rows)

    # 只用最长连续段的 10s 窗
    best_run = {}
    for r in RUNS:
        k = (r["who"], r["meeting"])
        if k not in best_run or (r["e"] - r["s"]) > (best_run[k]["e"] - best_run[k]["s"]):
            best_run[k] = r
    for k, r in best_run.items():
        rows = chunk_rows.get(("chunk10", r["rid"]))
        v = mean_rows(rows) if rows else None
        if v is not None:
            cents["c10_longest"][k] = v

    # ---- 库内生产质心 (对照组) ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member

    engine, Session = create_celery_engine_and_session()
    db_cent, db_meta = {}, {}
    async with Session() as db:
        for mm in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cent[mm.name] = norm(v)
                db_meta[mm.name] = {"id": mm.id, "count": mm.voice_sample_count,
                                    "anchor": mm.voice_confirmed_at is not None}
    await engine.dispose()
    log("库内生产质心 %d 人: %s" % (len(db_cent), sorted(db_cent)))

    # ================================================================
    # ① 基线复现: 能不能重现已发表的 0.5038?
    # ================================================================
    # 已发表: 蒋芦笛 **库内质心**(据 provenance 来自 255) ↔ 250 的台账段 = 0.5038
    base = {}
    for who in ("蒋芦笛", "王天志", "韩重阳", "赵航佳", "张宏魁", "吴孟铨",
                "陈天祥", "王书馨", "肖佐林", "刘子煜", "胡小琪", "宋洋",
                "陈金薪", "刘莫菲", "吴怡霏", "李胜景", "杜同贺", "关小未", "耿嘉栋"):
        if who not in db_cent:
            continue
        rows = [i for i, m in enumerate(META)
                if m["kind"] == "seg" and seg_truth.get(i) == who]
        if not rows:
            continue
        ds = [d(E[i], db_cent[who]) for i in rows]
        base[who] = {"n_seg": len(rows), "median": median(ds),
                     "p25": pct(ds, 0.25), "p75": pct(ds, 0.75)}
    log("基线复现 (库内质心 ↔ 本人全部台账段):")
    for w, v in sorted(base.items(), key=lambda kv: kv[1]["median"] or 9):
        log("   %-8s n=%4d 中位 %.4f (P25 %.3f / P75 %.3f)" % (
            w, v["n_seg"], v["median"], v["p25"], v["p75"]))

    # 蒋芦笛 255质心 ↔ 250台账段 (已发表值) 的精确复现
    # ⛔ 已发表的 0.5038 是用「**255 场**建的旧口径质心」量的, 而库内现役质心是
    #    2026-10-13 用 250/254/255 三场台账块重建的 ⇒ 两者**不是同一个向量**。
    #    ⇒ 必须**重建**一个 255-only 的旧口径质心来复现, 否则就是拿两个东西比 (类 20.220)。
    jl_250 = [i for i, m in enumerate(META)
              if m["kind"] == "seg" and m["meeting"] == 250 and seg_truth.get(i) == "蒋芦笛"]
    if jl_250 and "蒋芦笛" in db_cent:
        ds = [d(E[i], db_cent["蒋芦笛"]) for i in jl_250]
        log("   [库内现役质心] 蒋芦笛 ↔ 250台账段 n=%d 中位 %.4f" % (len(jl_250), median(ds)))
        base["_repro_蒋芦笛_dblive_vs_250segs"] = {"n": len(jl_250), "median": median(ds)}
    c255 = cents["seg_old"].get(("蒋芦笛", 255))
    if c255 is not None and jl_250:
        ds = [d(E[i], c255) for i in jl_250]
        log("   [重建255旧口径质心] 蒋芦笛 ↔ 250台账段 n=%d 中位 %.4f  (已发表 0.5038)" % (
            len(jl_250), median(ds)))
        base["_repro_蒋芦笛_255rebuilt_vs_250segs"] = {"n": len(jl_250), "median": median(ds)}
        base["_published_0.5038"] = PUBLISHED_CROSS_BASE

    # ================================================================
    # ② 同一人跨场距离
    # ================================================================
    report = {"baseline_repro": base, "variants": {}}

    for variant, cmap in cents.items():
        wm = collections.defaultdict(list)
        for (w, mid) in cmap:
            wm[w].append(mid)
        cc, cs = [], []       # centroid↔centroid / centroid↔segments
        detail = {}
        for w, mids in wm.items():
            mids = sorted(mids)
            pairs = []
            for a in range(len(mids)):
                for b in range(a + 1, len(mids)):
                    dd = d(cmap[(w, mids[a])], cmap[(w, mids[b])])
                    cc.append(dd)
                    pairs.append({"m1": mids[a], "m2": mids[b], "d": round(dd, 4)})
            # centroid(M1) ↔ 该人在 M2 的真值段
            segpairs = []
            for m1 in mids:
                for m2 in mids:
                    if m1 == m2:
                        continue
                    rows = [i for i, mm in enumerate(META)
                            if mm["kind"] == "seg" and mm["meeting"] == m2 and seg_truth.get(i) == w]
                    if not rows:
                        continue
                    ds = [d(E[i], cmap[(w, m1)]) for i in rows]
                    segpairs.append({"m1": m1, "m2": m2, "n": len(rows),
                                     "median": round(median(ds), 4)})
                    cs.extend(ds)
            if pairs or segpairs:
                detail[w] = {"centroid_pairs": pairs, "centroid_to_segments": segpairs}
        report["variants"][variant] = {
            "n_centroids": len(cmap),
            "same_person_centroid_centroid": {
                "n": len(cc), "median": median(cc), "min": min(cc) if cc else None,
                "max": max(cc) if cc else None,
                "p25": pct(cc, 0.25), "p75": pct(cc, 0.75)},
            "same_person_centroid_to_segments": {
                "n": len(cs), "median": median(cs), "min": min(cs) if cs else None,
                "max": max(cs) if cs else None,
                "p25": pct(cs, 0.25), "p75": pct(cs, 0.75)},
            "detail": detail}
        log("变体 %-11s 质心 %3d | 同人质心↔质心 n=%2d 中位 %s | 质心↔段 n=%5d 中位 %s" % (
            variant, len(cmap), len(cc), ("%.4f" % median(cc)) if cc else "-",
            len(cs), ("%.4f" % median(cs)) if cs else "-"))

    # 异人互距
    for variant, cmap in cents.items():
        keys = sorted(cmap)
        dd = []
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                if keys[a][0] == keys[b][0]:
                    continue
                dd.append(d(cmap[keys[a]], cmap[keys[b]]))
        report["variants"][variant]["diff_person"] = {
            "n": len(dd), "median": median(dd), "min": min(dd) if dd else None,
            "max": max(dd) if dd else None, "p25": pct(dd, 0.25), "p75": pct(dd, 0.75)}
    # 库内质心之间的异人互距 (对照)
    dk = sorted(db_cent)
    ddk = [d(db_cent[dk[a]], db_cent[dk[b]]) for a in range(len(dk)) for b in range(a + 1, len(dk))]
    report["db_centroid_diff_person"] = {
        "n": len(ddk), "median": median(ddk), "min": min(ddk), "max": max(ddk),
        "p25": pct(ddk, 0.25), "p75": pct(ddk, 0.75)}
    log("库内质心异人互距: n=%d 中位 %.4f" % (len(ddk), median(ddk)))

    # ================================================================
    # ③ 类 20.226 双指标: 留一认回 + 抢走(绝对数) + 被抢者离真值距离中位
    # ================================================================
    pool = sorted(db_cent)                    # 候选池 = 库内 enrolled 池
    log("候选池 (%d 人): %s" % (len(pool), pool))

    truth_rows = collections.defaultdict(list)  # who -> [(meeting, row)]
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        w = seg_truth.get(i)
        if w:
            truth_rows[w].append((m["meeting"], i))

    def run_dual(variant, cmap, units=None):
        """类 20.226 双指标: 留一(按场)认回 + 抢走(绝对数) + 被抢者离真值距离中位。

        ⛔ **三方严格配对** (同一批测试段、同一批建库场):
          新     = cmap[(P, M)]          —— 本变体的质心
          旧配对 = cents['seg_old'][(P, M)] —— **同样素材同样场**的旧口径质心
          旧生产 = db_cent[P]            —— 库内现役质心 (可能有 in-sample 偏乐观)
        ⇒ 三者的分母完全相同, 差异只能来自「质心怎么建」。

        units: 限定参与评测的 (人, 场) 单元 —— 用于把不同变体拉到同一分母上比较。
        """
        old_cmap = cents["seg_old"]
        per = {}
        for (w, mid), cen in sorted(cmap.items()):
            if units is not None and (w, mid) not in units:
                continue
            others = [q for q in pool if q != w]
            # ① 认回: 本人**其它场**的真值段, 新质心是否是候选池里最近的
            own = [(mm, i) for mm, i in truth_rows.get(w, []) if mm != mid]
            if not own:
                continue
            c_old_m = old_cmap.get((w, mid))
            c_prod = db_cent.get(w)
            hit_new = hit_oldm = hit_prod = 0
            d_new_all, d_oldm_all, d_prod_all, d_comp_all = [], [], [], []
            for mm, i in own:
                v = E[i]
                comp = [d(v, db_cent[q]) for q in others]
                d_comp = min(comp) if comp else 9.9
                d_comp_all.append(d_comp)
                d_new = d(v, cen)
                d_new_all.append(d_new)
                if d_new < d_comp:
                    hit_new += 1
                if c_old_m is not None:
                    d_oldm = d(v, c_old_m)
                    d_oldm_all.append(d_oldm)
                    if d_oldm < d_comp:
                        hit_oldm += 1
                if c_prod is not None:
                    d_prod = d(v, c_prod)
                    d_prod_all.append(d_prod)
                    if d_prod < d_comp:
                        hit_prod += 1
            # ② 抢走: **全部有台账的会议**里别人的真值段
            #    ⛔ 必须区分三类 (类 20.243 ③ / 类 20.226 ⑧):
            #      真抢走   = 该段原本**正确**归给真主人, 新质心把它抢走 ⇒ 真破坏
            #      错名改判 = 该段原本就**错**归给别人, 新质心只是换了个错名 ⇒ 不算破坏
            #      无主改判 = 真主人**本来就没有质心**, 没人认领 ⇒ 不算破坏
            def count_steal(cand):
                s_real = s_mis = s_no = 0
                s_true_d = []
                for q, rows in truth_rows.items():
                    if q == w:
                        continue
                    c_true = db_cent.get(q)
                    for mm, i in rows:
                        v = E[i]
                        d_c = d(v, cand)
                        if pool:
                            dmin, argmin = min((d(v, db_cent[q2]), q2) for q2 in pool)
                        else:
                            dmin, argmin = 9.9, None
                        if c_true is None:
                            if d_c < dmin:
                                s_no += 1
                        else:
                            d_true = d(v, c_true)
                            if d_c < d_true:
                                s_true_d.append(d_true)
                                if argmin == q:
                                    s_real += 1
                                else:
                                    s_mis += 1
                return s_real, s_mis, s_no, s_true_d

            s_real, s_mis, s_no, s_true_d = count_steal(cen)
            if c_old_m is not None:
                om_real, om_mis, om_no, _ = count_steal(c_old_m)
            else:
                om_real = om_mis = om_no = None
            if c_prod is not None:
                pr_real, pr_mis, pr_no, _ = count_steal(c_prod)
            else:
                pr_real = pr_mis = pr_no = None
            per[w + "|" + str(mid)] = {
                "who": w, "build_meeting": mid,
                "recall_n": len(own),
                "recall_new": hit_new,
                "recall_new_rate": round(hit_new / len(own), 4),
                "recall_old_matched": hit_oldm if c_old_m is not None else None,
                "recall_old_matched_rate": (round(hit_oldm / len(own), 4)
                                            if c_old_m is not None else None),
                "recall_prod": hit_prod if c_prod is not None else None,
                "recall_prod_rate": (round(hit_prod / len(own), 4)
                                     if c_prod is not None else None),
                "d_new_median": round(median(d_new_all), 4) if d_new_all else None,
                "d_old_matched_median": round(median(d_oldm_all), 4) if d_oldm_all else None,
                "d_prod_median": round(median(d_prod_all), 4) if d_prod_all else None,
                "d_competitor_median": round(median(d_comp_all), 4) if d_comp_all else None,
                "stolen_real": s_real, "stolen_misnamed": s_mis, "stolen_noowner": s_no,
                "stolen_true_dist_median": round(median(s_true_d), 4) if s_true_d else None,
                "stolen_real_old_matched": om_real,
                "stolen_real_prod": pr_real,
                "net_gain": hit_new - s_real,
                # ⛔ 正确的对照 = (新认回 − 新真抢走) − (旧配对认回 − 旧配对真抢走)
                #    (不能写成 "新认回 − 旧真抢走" —— 那是把两条不同的量混着比)
                "net_gain_vs_old_matched": ((hit_new - s_real) - (hit_oldm - om_real)
                                            if om_real is not None else None),
                "pool": pool,
            }
        return per

    # 共同单元 = 各变体与 seg_old 都有的 (人, 场) ⇒ 所有变体在同一分母上比较
    common_units = set(cents["seg_old"])
    for v in cents:
        if v != "seg_old":
            common_units &= set(cents[v])
    log("共同单元 (人,场) %d 个: %s" % (
        len(common_units), sorted("%s@%d" % (w, m) for w, m in common_units)))

    for variant, cmap in cents.items():
        # ⛔ 所有变体都只用**共同单元** ⇒ 各变体的分母完全相同 (类 20.249 ⑧:
        #    「两次跑不一致」的第一嫌疑是输入变了 ⇒ 变体之间也必须锁死输入)
        units = common_units
        per = run_dual(variant, cmap, units)
        tot_new = sum(v["recall_new"] for v in per.values())
        tot_oldm = sum(v["recall_old_matched"] or 0 for v in per.values())
        tot_prod = sum(v["recall_prod"] or 0 for v in per.values())
        tot_steal = sum(v["stolen_real"] for v in per.values())
        tot_mis = sum(v["stolen_misnamed"] for v in per.values())
        tot_noowner = sum(v["stolen_noowner"] for v in per.values())
        tot_steal_oldm = sum(v["stolen_real_old_matched"] or 0 for v in per.values())
        tot_steal_prod = sum(v["stolen_real_prod"] or 0 for v in per.values())
        seg_total = sum(v["recall_n"] for v in per.values())
        ng_new = tot_new - tot_steal
        ng_old = tot_oldm - tot_steal_oldm
        report["variants"][variant]["dual"] = {
            "units": sorted("%s@%d" % (w, m) for w, m in units),
            "per_person": per,
            "totals": {
                "people": len(per), "units": len(units),
                "recall_segments": seg_total,
                "recall_new": tot_new,
                "recall_old_matched": tot_oldm, "recall_prod": tot_prod,
                "recall_new_rate": round(tot_new / max(1, seg_total), 4),
                "recall_old_matched_rate": round(tot_oldm / max(1, seg_total), 4),
                "recall_prod_rate": round(tot_prod / max(1, seg_total), 4),
                "stolen_real": tot_steal, "stolen_misnamed": tot_mis,
                "stolen_noowner": tot_noowner,
                "stolen_real_old_matched": tot_steal_oldm,
                "stolen_real_prod": tot_steal_prod,
                "net_gain": ng_new,
                "net_gain_old_matched": ng_old,
                "net_gain_vs_old_matched": ng_new - ng_old}}
        log("变体 %-11s 双指标(共同分母 %d 段): 认回 新 %d / 旧配对 %d / 现役 %d | "
            "真抢走 新 %d / 旧配对 %d / 现役 %d | 净增益 新 %d vs 旧配对 %d ⇒ Δ%s" % (
                variant, seg_total, tot_new, tot_oldm, tot_prod,
                tot_steal, tot_steal_oldm, tot_steal_prod,
                ng_new, ng_old, ng_new - ng_old))

    # ================================================================
    # ③c 生产相关口径的**逐段配对比较**: 质心(场A) ↔ 该人台账段(场B)
    #     —— 这才是生产里真正发生的比较 (生产用短段, 质心是成员级)
    # ================================================================
    old_cmap = cents["seg_old"]
    for variant, cmap in cents.items():
        if variant == "seg_old":
            continue
        diffs = []
        for (w, m1), cen in cmap.items():
            c_old = old_cmap.get((w, m1))
            if c_old is None:
                continue
            rows = [i for i, m in enumerate(META)
                    if m["kind"] == "seg" and m["meeting"] != m1 and seg_truth.get(i) == w]
            for i in rows:
                diffs.append(d(E[i], cen) - d(E[i], c_old))
        wins = sum(1 for x in diffs if x < -1e-9)
        losses = sum(1 for x in diffs if x > 1e-9)
        ci2 = boot_ci(diffs)
        report["variants"][variant]["paired_centroid_to_segments"] = {
            "n": len(diffs), "wins": wins, "losses": losses,
            "median_diff": median(diffs) if diffs else None,
            "ci95": list(ci2),
            "note": "负值 = 新质心更靠近本人台账段 (生产口径更好)"}
        log("变体 %-11s 生产口径逐段配对 (质心↔台账段): n=%d 胜%d/负%d 中位差 %+.4f CI[%+.4f,%+.4f]" % (
            variant, len(diffs), wins, losses,
            median(diffs) if diffs else 0, ci2[0] or 0, ci2[1] or 0))

    # ================================================================
    # ③b 无阈值的判别力: 「argmin 正确率」—— 真主人的质心是不是该段最近的
    #    (不设任何自造阈值; 类 20.226 ⑤ / 类 20.243 ①)
    # ================================================================
    all_truth = [(m["meeting"], i) for i, m in enumerate(META)
                 if m["kind"] == "seg" and seg_truth.get(i)]
    for variant, cmap in cents.items():
        people = sorted({k[0] for k in cmap})
        ok = tot = 0
        d_same_all, d_diff_all = [], []
        for mm, i in all_truth:
            q = seg_truth[i]
            if q not in people:
                continue
            v = E[i]
            d_same = d(v, cmap[(q, mm)]) if (q, mm) in cmap else None
            if d_same is None:
                # 该人该场没有这个口径的质心 ⇒ 用该人**其它场**的质心(跨场口径)
                alts = [cmap[(q, m2)] for m2 in {m2 for (ww, m2) in cmap if ww == q}]
                if not alts:
                    continue
                d_same = min(d(v, a) for a in alts)
            d_diff = min((d(v, cmap[(q2, m2)]) for (q2, m2) in cmap if q2 != q),
                         default=None)
            if d_diff is None:
                continue
            tot += 1
            d_same_all.append(d_same)
            d_diff_all.append(d_diff)
            if d_same < d_diff:
                ok += 1
        report["variants"][variant]["argmin_accuracy"] = {
            "n": tot, "correct": ok,
            "rate": round(ok / tot, 4) if tot else None,
            "d_same_median": round(median(d_same_all), 4) if d_same_all else None,
            "d_diff_median": round(median(d_diff_all), 4) if d_diff_all else None,
            "gap": (round(median(d_diff_all) - median(d_same_all), 4)
                    if d_same_all and d_diff_all else None)}
        log("变体 %-11s argmin 正确率: %d/%d = %s | 同人 %s / 异人 %s | 间隔 %s" % (
            variant, ok, tot, ("%.1f%%" % (100.0 * ok / tot)) if tot else "-",
            ("%.4f" % median(d_same_all)) if d_same_all else "-",
            ("%.4f" % median(d_diff_all)) if d_diff_all else "-",
            ("%.4f" % (median(d_diff_all) - median(d_same_all))) if d_same_all else "-"))

    # ================================================================
    # ④ 长度混淆控制: 同一素材, 只改「窗长」与「整段」
    # ================================================================
    # 对每条连续段, 用同一批真值段做测试集, 比较 seg_old / c5 / c10 / whole 四种口径
    # ⇒ 分离「素材更多」与「窗更长」两个因素
    ctrl = {}
    for rid, r in sorted(run_by_rid.items()):
        rows_c5 = chunk_rows.get(("chunk5", rid))
        rows_c10 = chunk_rows.get(("chunk10", rid))
        if not rows_c10:
            continue
        # 该连续段覆盖的生产段(它自己范围内的)
        covered = [i for i, m in enumerate(META)
                   if m["kind"] == "seg" and rid in (m.get("runs") or [])]
        if len(covered) < 3:
            continue
        v_old = mean_rows(covered)
        v_c5 = mean_rows(rows_c5)
        v_c10 = mean_rows(rows_c10)
        v_wh = E[whole_rows[rid]] if rid in whole_rows else None
        ent = {"who": r["who"], "meeting": r["meeting"],
               "run_sec": round(r["e"] - r["s"], 1),
               "speech_sec": r.get("speech_sec"),
               "n_seg": len(covered)}
        for nm, v in (("seg_old", v_old), ("c5", v_c5), ("c10", v_c10), ("whole", v_wh)):
            if v is None:
                continue
            ent["d_" + nm] = round(median([d(E[i], v) for i in covered]), 4)
        ctrl["%s|m%d|%.0f-%.0f" % (r["who"], r["meeting"], r["s"], r["e"])] = ent
    report["length_control"] = ctrl
    for nm in ("d_seg_old", "d_c5", "d_c10", "d_whole"):
        xs = [v[nm] for v in ctrl.values() if nm in v]
        log("长度控制 %-10s n=%3d 中位 %s" % (
            nm, len(xs), ("%.4f" % median(xs)) if xs else "-"))

    # ================================================================
    # ⑤ 逐人明细 (跨场表)
    # ================================================================
    per_person = {}
    for w in sorted({k[0] for k in cents["c10"]} | set(db_cent)):
        ent = {"db_centroid": w in db_cent,
               "db_meta": db_meta.get(w),
               "meetings_new": sorted({m for (ww, m) in cents["c10"] if ww == w}),
               "meetings_old": sorted({m for (ww, m) in cents["seg_old"] if ww == w})}
        for variant in ("seg_old", "c5", "c10", "c10_longest", "whole"):
            cmap = cents[variant]
            rows = []
            for (ww, m1) in sorted(cmap):
                if ww != w:
                    continue
                for (ww2, m2) in sorted(cmap):
                    if ww2 != w or m2 <= m1:
                        continue
                    rows.append({"m1": m1, "m2": m2,
                                 "d": round(d(cmap[(ww, m1)], cmap[(ww2, m2)]), 4)})
            if rows:
                ent[variant + "_cross"] = rows
                ent[variant + "_cross_median"] = round(median([x["d"] for x in rows]), 4)
        per_person[w] = ent
    report["per_person"] = per_person

    # ================================================================
    # ⑥ 配对比较 + Phase 0 判定
    # ================================================================
    def cross_pairs(cmap, units=None):
        """(person, m1, m2) -> 质心↔质心 距离 (m1 < m2)。"""
        wm = collections.defaultdict(list)
        for (w, mid) in cmap:
            if units is not None and (w, mid) not in units:
                continue
            wm[w].append(mid)
        out = {}
        for w, mids in wm.items():
            mids = sorted(mids)
            for a in range(len(mids)):
                for b in range(a + 1, len(mids)):
                    if (w, mids[a]) in units and (w, mids[b]) in units:
                        out[(w, mids[a], mids[b])] = d(cmap[(w, mids[a])], cmap[(w, mids[b])])
        return out

    def diff_pairs(cmap, units=None):
        """异人质心互距 (按 (personA,meetingA,personB,meetingB) 记)。"""
        keys = sorted(k for k in cmap if units is None or k in units)
        out = {}
        for a in range(len(keys)):
            for b in range(a + 1, len(keys)):
                if keys[a][0] == keys[b][0]:
                    continue
                out[(keys[a], keys[b])] = d(cmap[keys[a]], cmap[keys[b]])
        return out

    old_cross = cross_pairs(cents["seg_old"], common_units)
    old_diff = diff_pairs(cents["seg_old"], common_units)
    # 「严格」子集: 两侧会议里这个人都有 **≥30s 的连续长段** ⇒ 素材量对等,
    # 排除「一场长一段短」造成的素材量混淆
    long_units = set()
    for r in RUNS:
        if (r["e"] - r["s"]) >= 30.0:
            long_units.add((r["who"], r["meeting"]))
    strict_units = set(common_units) & long_units
    old_cross_strict = cross_pairs(cents["seg_old"], strict_units)
    verdict = {"published_cross_base": PUBLISHED_CROSS_BASE,
               "common_units": sorted("%s@%d" % (w, m) for w, m in common_units),
               "strict_long_units": sorted("%s@%d" % (w, m) for w, m in strict_units),
               "variants": {}}

    for variant, cmap in cents.items():
        if variant == "seg_old":
            continue
        new_cross = cross_pairs(cmap, common_units)
        new_diff = diff_pairs(cmap, common_units)
        common = sorted(set(old_cross) & set(new_cross))
        diffs = [new_cross[k] - old_cross[k] for k in common]
        wins = sum(1 for x in diffs if x < -1e-9)
        losses = sum(1 for x in diffs if x > 1e-9)
        ci = boot_ci(diffs)
        # 异人互距的配对比较 (只看两边都有的对)
        dcommon = sorted(set(old_diff) & set(new_diff))
        ddiffs = [new_diff[k] - old_diff[k] for k in dcommon]
        dci = boot_ci(ddiffs)
        dwins = sum(1 for x in ddiffs if x > 1e-9)     # 异人更远 = 更好
        dlosses = sum(1 for x in ddiffs if x < -1e-9)
        sp_new = median(list(new_cross.values()))
        sp_old = median(list(old_cross.values()))
        # 严格子集 (两侧都有 ≥30s 长段)
        nc_s = cross_pairs(cmap, strict_units)
        com_s = sorted(set(old_cross_strict) & set(nc_s))
        sp_new_s = median([nc_s[k] for k in com_s]) if com_s else None
        sp_old_s = median([old_cross_strict[k] for k in com_s]) if com_s else None
        diffs_s = [nc_s[k] - old_cross_strict[k] for k in com_s]
        wins_s = sum(1 for x in diffs_s if x < -1e-9)
        losses_s = sum(1 for x in diffs_s if x > 1e-9)
        ci_s = boot_ci(diffs_s)
        df_new = median(list(new_diff.values()))
        df_old = median(list(old_diff.values()))
        gap_new = df_new - sp_new
        gap_old = df_old - sp_old
        arg_new = report["variants"][variant].get("argmin_accuracy", {})
        arg_old = report["variants"]["seg_old"].get("argmin_accuracy", {})
        dual = report["variants"][variant]["dual"]["totals"]
        dual_old = report["variants"]["seg_old"]["dual"]["totals"]

        # ---- 判定 (四条都要过) ----
        c1 = (sp_new is not None and sp_old is not None
              and sp_new < PUBLISHED_CROSS_BASE
              and wins > losses and ci[0] is not None and ci[0] < 0)
        c2 = (df_new is not None and df_old is not None and df_new >= df_old
              and dwins >= dlosses)
        c3 = (arg_new.get("rate") is not None and arg_old.get("rate") is not None
              and arg_new["rate"] > arg_old["rate"])
        c4 = dual.get("net_gain_vs_old_matched") is not None and dual["net_gain_vs_old_matched"] > 0
        verdict["variants"][variant] = {
            "same_person_cross_median_old": sp_old,
            "same_person_cross_median_new": sp_new,
            "same_person_cross_median_drop": (sp_old - sp_new) if sp_old and sp_new else None,
            "matched_units": len(common), "wins": wins, "losses": losses,
            "paired_median_diff": median(diffs) if diffs else None,
            "paired_median_diff_ci95": list(ci),
            "diff_person_median_old": df_old,
            "diff_person_median_new": df_new,
            "diff_person_paired_units": len(dcommon),
            "diff_person_wins_farther": dwins, "diff_person_losses_closer": dlosses,
            "diff_person_paired_median_diff": median(ddiffs) if ddiffs else None,
            "diff_person_paired_median_diff_ci95": list(dci),
            "separation_gap_old": gap_old, "separation_gap_new": gap_new,
            "strict_long": {
                "units": len(com_s),
                "same_person_cross_median_old": sp_old_s,
                "same_person_cross_median_new": sp_new_s,
                "wins": wins_s, "losses": losses_s,
                "paired_median_diff": median(diffs_s) if diffs_s else None,
                "paired_median_diff_ci95": list(ci_s)},
            "argmin_acc_old": arg_old.get("rate"), "argmin_acc_new": arg_new.get("rate"),
            "dual_new": dual, "dual_old": dual_old,
            "criteria": {
                "C1_same_person_below_0.5038_and_paired_better": bool(c1),
                "C2_diff_person_not_worse": bool(c2),
                "C3_argmin_accuracy_up": bool(c3),
                "C4_net_gain_vs_old_matched_positive": bool(c4)},
            "verdict": "PASS" if (c1 and c2 and c3 and c4) else "FAIL"}
        v = verdict["variants"][variant]
        log("判定 %-11s 同人跨场 %.4f→%.4f (配对 %d: 胜%d/负%d, 中位差 %.4f CI[%.4f,%.4f]) | "
            "异人 %.4f→%.4f | 间隔 %.4f→%.4f | argmin %s→%s | 净增益 %d (vs旧配对 %s) → %s" % (
                variant, sp_old or -1, sp_new or -1, len(common), wins, losses,
                v["paired_median_diff"] or 0, ci[0] or 0, ci[1] or 0,
                df_old or -1, df_new or -1, gap_old or 0, gap_new or 0,
                arg_old.get("rate"), arg_new.get("rate"),
                dual["net_gain"], dual.get("net_gain_vs_old_matched"), v["verdict"]))
        log("     [严格子集 两侧都有≥30s长段] 配对 %d: 同人跨场 %.4f→%.4f (胜%d/负%d, 中位差 %.4f CI[%.4f,%.4f])" % (
            len(com_s), sp_old_s or -1, sp_new_s or -1, wins_s, losses_s,
            v["strict_long"]["paired_median_diff"] or 0, ci_s[0] or 0, ci_s[1] or 0))

    report["verdict"] = verdict
    out = os.path.join(args.phase0, "analysis.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % out)

    # ================================================================
    # ⑦ 候选质心落库 (新表, **不改 members**) —— 供主指挥审阅
    # ================================================================
    if args.write_candidates:
        from sqlalchemy import text as sqlt
        engine, Session = create_celery_engine_and_session()
        async with Session() as db:
            await db.execute(sqlt(
                "CREATE TABLE IF NOT EXISTS member_enrollment_candidates_phase0_20261031 ("
                "variant text, member_name text, meeting_id int, centroid halfvec(192),"
                " n_windows int, speech_sec numeric, run_secs numeric,"
                " cross_median numeric, argmin_rate numeric, net_gain_vs_old int,"
                " created_at timestamptz default now())"))
            await db.execute(sqlt("DELETE FROM member_enrollment_candidates_phase0_20261031"))
            dual_by_variant = {v: report["variants"][v]["dual"]["per_person"]
                               for v in report["variants"]}
            n_rows = 0
            for variant, cmap in cents.items():
                for (w, mid), vec in sorted(cmap.items()):
                    rs = [r for r in RUNS if r["who"] == w and r["meeting"] == mid]
                    speech = sum(r.get("speech_sec", 0) for r in rs)
                    rsec = sum(r["e"] - r["s"] for r in rs)
                    nwin = sum(len(chunk_rows.get(("chunk10", r["rid"]), [])) for r in rs)
                    if not nwin:
                        nwin = len(rs)
                    cross = None
                    per = dual_by_variant.get(variant, {})
                    kg = "%s|%d" % (w, mid)
                    if kg in per:
                        cross = per[kg].get("d_new_median")
                    await db.execute(sqlt(
                        "INSERT INTO member_enrollment_candidates_phase0_20261031 "
                        "(variant, member_name, meeting_id, centroid, n_windows, speech_sec, "
                        " run_secs, cross_median, net_gain_vs_old) VALUES "
                        "(:v,:w,:m,CAST(:c AS halfvec),:n,:s,:r,:x,:g)"), {
                        "v": variant, "w": w, "m": mid,
                        # ⛔ pgvector 列必须收**文本** `'[f1,f2,...]'`, 直接传 list 会
                        #    DataError: expected str, got list (类 20.248 ⑤)
                        "c": "[" + ",".join("%.9g" % float(x) for x in vec) + "]",
                        "n": nwin, "s": speech, "r": rsec,
                        "x": cross,
                        "g": (per[kg].get("net_gain_vs_old_matched")
                              if kg in per else None)})
                    n_rows += 1
            await db.commit()
        log("候选质心已落 member_enrollment_candidates_phase0_20261031 (%d 行, **members 未改**)" % n_rows)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
