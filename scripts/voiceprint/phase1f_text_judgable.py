"""Phase 1f: 产品形态提案的三个工作量数字 + 「台账裁决 vs 簇命名」的优先级与收益上限。

要回答的三个问题
----------------
A. **人工起名的三层工作量** (主指挥第一句: 「这个起名是人来亲自听, 然后判断说话人吗?」)
   答: **不是必须听**, 分三层:
     ① **看文本就判**  —— 把簇的转录连起来读几行 (谁是导师/谁是汇报人/哪个是提问的学生)
     ② **看系统候选名 + 只改错的** —— 系统按簇质心给候选名, 人只改那约 30% 安错的
     ③ **听 10–20 秒音频** —— 只在文本也看不出来时
   ⇒ 本脚本量化: **①需要人改的簇数/场 ②其中光看文本就能改的占比 ③必须听音频的簇数/场**

   做法 (纯代理, 无循环论证):
     - 簇的文本画像 = 该簇内**有台账真值**的段的文本统计 (人工台账, 与声学无关)
     - 成员的文本画像 = 该成员在**其它场**的台账段的文本统计 (留出该簇所在的场 ⇒ 不自证)
     - `text_name` = 文本画像离谁最近
     - 与 `acoustic_name` (簇质心最近成员) 和 `truth` (台账真值主人) 三方对比

B. **台账裁决 vs 簇命名冲突时谁赢**, 以及**簇命名实际能影响多少段**
   - 倾向: **台账 > 簇名** (台账是逐段确认的、更细; 簇名是聚类级推断)
   - ⇒ 必须量: **台账覆盖率**下, 簇命名实际能影响的段数 ⇒ 这决定「人工命名」的**收益上限**

C. **半自动 vs 纯人工的工作量差** (用 A 的三个数折算)

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1f_text_judgable.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1f
"""
import argparse
import collections
import json
import os
import re
import statistics
import sys

import numpy as np

sys.path.insert(0, "/app")

DEV_MEETINGS = [229, 250, 254, 259, 262]
TEST_MEETINGS = [243, 247, 255, 256]
K_FIXED = 6
SEED = 20261031

# ---- 纯文本特征 (只用转录文本本身, 不用任何声学/标签) ----
ASK_RE = re.compile(r"(请教|请指导|请老师|谢谢老师|感谢老师|老师|请问|指导一下|指教)")
REPORT_RE = re.compile(r"(我们|本文|本研究|实验|结果|提出|分析|方法|结论|研究|模型|数据|算法)")
QUESTION_RE = re.compile(r"[?？]")


def log(msg):
    print("[phase1f] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def feats_of(texts, durs):
    n = max(1, len(texts))
    ask = sum(1 for t in texts if ASK_RE.search(t)) / n
    rep = sum(1 for t in texts if REPORT_RE.search(t)) / n
    q = sum(1 for t in texts if QUESTION_RE.search(t)) / n
    ml = float(np.mean(durs)) if durs else 0.0
    mc = float(np.mean([len(t) for t in texts])) if texts else 0.0
    return np.array([ask, rep, q, ml, mc], dtype=np.float64)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--out", default="/tmp/vp/phase1f")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
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

    # ---- 从 DB 取转录文本 (meta.json 里没有 text) ----
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.member import Member

    engine, Session = create_celery_engine_and_session()
    texts = {}
    n_prod_seg = collections.Counter()
    mt = {}
    async with Session() as db:
        rows = (await db.execute(select(Meeting))).scalars().all()
        for m in rows:
            segs = sorted(m.transcript or [], key=lambda s: float(s.get("start") or 0))
            mt[m.id] = segs
    await engine.dispose()
    for i, m in enumerate(META):
        if m["kind"] != "seg":
            continue
        segs = mt.get(m["meeting"], [])
        if m["seg_idx"] < len(segs):
            s = segs[m["seg_idx"]]
            texts[i] = (s.get("text") or "")
            n_prod_seg[m["meeting"]] += 1
    log("取到文本 %d 条; 每场生产段数 %s" % (len(texts), dict(sorted(n_prod_seg.items()))))

    # ---- 成员池 (现役 13 人) ----
    async with Session() as db:
        db_cent = {}
        for mm in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cent[mm.name] = norm(v)
    await engine.dispose()
    POOL13 = sorted(db_cent)

    # ---- 聚类 (k=6, 与 Phase 1b/1d/1e 同) ----
    from sklearn.cluster import KMeans
    per_meeting = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            per_meeting[m["meeting"]].append(i)
    clusters = {}
    for mid, rows in per_meeting.items():
        lab = KMeans(n_clusters=max(1, min(K_FIXED, len(rows))), n_init=3,
                     random_state=SEED).fit_predict(E[rows])
        cents = np.stack([norm(E[[rows[r] for r in range(len(rows)) if lab[r] == c]].mean(0))
                          for c in sorted(set(lab.tolist()))])
        clusters[mid] = (rows, lab, cents)

    # ---- 成员文本画像 (留出该簇所在的场 ⇒ 不自证) ----
    member_rows = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg" and truth.get(i):
            member_rows[(truth[i], m["meeting"])].append(i)

    def member_profile(q, exclude_mid):
        rows = [i for (w, mid), rs in member_rows.items() if w == q and mid != exclude_mid
                for i in rs]
        if not rows:
            return None
        return feats_of([texts.get(i, "") for i in rows], [META[i]["dur"] for i in rows])

    # 特征尺度: 用**全体**算 min/max (无标签参与 ⇒ 无泄漏)
    all_prof = []
    for q in POOL13:
        rows = [i for (w, mid), rs in member_rows.items() if w == q for i in rs]
        if rows:
            all_prof.append(feats_of([texts.get(i, "") for i in rows],
                                     [META[i]["dur"] for i in rows]))
    if all_prof:
        A = np.stack(all_prof)
        lo, hi = A.min(axis=0), A.max(axis=0)
        span = np.where(hi - lo < 1e-9, 1.0, hi - lo)
    else:
        lo = hi = span = None

    def z(f):
        return (f - lo) / span

    # ---- 逐簇分析 ----
    per_cluster = []
    for mid, (rows, lab, cents) in sorted(clusters.items()):
        lp = {q: member_profile(q, mid) for q in POOL13}
        lp = {q: v for q, v in lp.items() if v is not None}
        for ci, c in enumerate(cents):
            sel = [r for r in range(len(rows)) if lab[r] == ci]
            idxs = [rows[r] for r in sel]
            # 声学候选名 (系统给的)
            aco = min(db_cent, key=lambda q: dist(c, db_cent[q])) if db_cent else None
            # 真值主人 (台账)
            mem = collections.Counter(truth[i] for i in idxs if truth.get(i))
            tr = mem.most_common(1)[0][0] if mem else None
            # 文本画像: 只用该簇内**有台账真值**的段的文本 (混合, 不区分人) ⇒ 无循环论证
            tidxs = [i for i in idxs if truth.get(i)]
            tp = feats_of([texts.get(i, "") for i in tidxs], [META[i]["dur"] for i in tidxs]) \
                if tidxs else None
            # 文本预测: 离该簇文本画像最近的成员(留出该场)
            txt = None
            if tp is not None and lp:
                zc = z(tp)
                txt = min(lp, key=lambda q: float(np.linalg.norm(zc - z(lp[q]))))
            per_cluster.append({
                "mid": mid, "cid": ci, "size": len(idxs),
                "n_truth_seg": len(tidxs),
                "n_people_truth": len(mem),
                "acoustic_name": aco, "text_name": txt, "truth": tr,
                "text_profile": [round(float(x), 4) for x in tp] if tp is not None else None,
                "acoustic_ok": (aco == tr) if tr else None,
                "text_ok": (txt == tr) if tr else None,
                "acoustic_text_agree": (aco == txt) if (aco and txt) else None,
                "text_fixes": (txt == tr and aco != tr) if (tr and aco and txt) else False,
                "must_listen": (tr is not None and aco != tr and txt != tr),
            })

    # ---- 汇总三个数 ----
    def summarize(clusters_subset):
        n = len(clusters_subset)
        n_need_fix = sum(1 for c in clusters_subset if c["acoustic_ok"] is False)
        n_text_fix = sum(1 for c in clusters_subset if c["text_fixes"])
        n_must_listen = sum(1 for c in clusters_subset if c["must_listen"])
        n_confirm = n - n_need_fix
        return {"n_clusters": n, "need_fix": n_need_fix, "text_can_fix": n_text_fix,
                "must_listen": n_must_listen, "just_confirm": n_confirm,
                "text_can_fix_ratio_of_need": (round(n_text_fix / n_need_fix, 4)
                                               if n_need_fix else None),
                "must_listen_per_cluster": round(n_must_listen / max(1, n), 4)}

    summ_all = summarize(per_cluster)
    by_meeting = {}
    for mid in sorted(clusters):
        by_meeting[mid] = summarize([c for c in per_cluster if c["mid"] == mid])
    log("=== 三个数 (全 9 场, 只统计有台账真值的簇) ===")
    log("  %s" % json.dumps(summ_all, ensure_ascii=False))
    for mid, s in by_meeting.items():
        log("  m%-4d %s" % (mid, json.dumps(s, ensure_ascii=False)))

    # ---- B. 台账覆盖率 + 裁决优先下簇命名能影响多少段 ----
    cov = {}
    for mid in sorted(clusters):
        rows = per_meeting[mid]
        nt = sum(1 for i in rows if truth.get(i))
        cov[mid] = {"prod_segs": len(rows), "ledger_segs": nt,
                    "coverage": round(nt / max(1, len(rows)), 4),
                    "segs_not_covered_by_ledger": len(rows) - nt}
    tot_prod = sum(v["prod_segs"] for v in cov.values())
    tot_led = sum(v["ledger_segs"] for v in cov.values())
    log("=== 台账覆盖率 ===")
    for mid, v in cov.items():
        log("  m%-4d 生产段 %5d | 台账 %4d | 覆盖 %.3f | 裁决优先下簇命名能影响 %5d 段" % (
            mid, v["prod_segs"], v["ledger_segs"], v["coverage"],
            v["segs_not_covered_by_ledger"]))
    log("  合计: 生产段 %d | 台账 %d | 覆盖率 %.3f | 裁决优先下簇命名能影响 %d 段 (%.1f%%)" % (
        tot_prod, tot_led, tot_led / max(1, tot_prod),
        tot_prod - tot_led, 100.0 * (tot_prod - tot_led) / max(1, tot_prod)))

    # ---- C. 联合系统的收益上限 (台账裁决优先 + 簇命名) ----
    # 「台账 > 簇名」: 台账覆盖段由裁决保证(100% 对), 台账外段由簇命名(准确率 = 跨场口径)
    # ⇒ 联合段级准确率 = 覆盖率×1.0 + (1-覆盖率)×纯簇命名准确率
    CROSS_ACC = 0.5604        # Phase 1b/1d/1e 的跨场段级准确率(纯簇命名)
    SEMI_ACC = 0.7054         # Phase 1e: 人工只改错簇后的跨场段级准确率
    CEIL = 0.8252             # 命名天花板(簇名全对)
    covf = tot_led / max(1, tot_prod)
    joint = {
        "ledger_cov": round(covf, 4),
        "pure_cluster_naming": CROSS_ACC,
        "joint_ledger_then_cluster": round(covf * 1.0 + (1 - covf) * CROSS_ACC, 4),
        "joint_ledger_then_semi_auto": round(covf * 1.0 + (1 - covf) * SEMI_ACC, 4),
        "joint_ledger_then_ceiling": round(covf * 1.0 + (1 - covf) * CEIL, 4),
        "new_meeting_no_ledger_cluster_only": CROSS_ACC,
        "new_meeting_no_ledger_semi_auto": SEMI_ACC,
        "gain_vs_pure_cluster_on_ledger_meetings": round(
            (covf * 1.0 + (1 - covf) * SEMI_ACC) - CROSS_ACC, 4),
        "gain_vs_pure_cluster_on_new_meetings": round(SEMI_ACC - CROSS_ACC, 4),
    }
    log("=== 联合系统收益上限 (台账裁决优先) ===")
    for k, v in joint.items():
        log("  %-42s %s" % (k, v))

    # 必须听音频的簇: 段数与分布
    must = [c for c in per_cluster if c["must_listen"]]
    listen_work = {
        "n_clusters": len(must),
        "segs_in_them": sum(c["size"] for c in must),
        "by_meeting": {m: sum(1 for c in must if c["mid"] == m) for m in sorted(clusters)},
        "segs_by_meeting": {m: sum(c["size"] for c in must if c["mid"] == m)
                            for m in sorted(clusters)},
        "text_proxy_upper_bound": {
            "note": "若文本信息足够, 全部需改的簇都能靠文本纠正 ⇒ 上界 = need_fix",
            "need_fix": summ_all["need_fix"], "text_can_fix_measured": summ_all["text_can_fix"],
            "text_proxy_is_lower_bound": True},
    }
    log("=== 必须听音频的簇: %d 个, 涉及 %d 段 (占需改簇段数的比例见 JSON) ===" % (
        listen_work["n_clusters"], listen_work["segs_in_them"]))

    out = {"pool13": POOL13, "k_fixed": K_FIXED,
           "joint_system": joint, "listen_work": listen_work,
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "three_numbers": {"all9": summ_all, "by_meeting": by_meeting},
           "per_cluster": per_cluster,
           "ledger_coverage": {"by_meeting": cov,
                               "total_prod_segs": tot_prod, "total_ledger_segs": tot_led,
                               "coverage": round(tot_led / max(1, tot_prod), 4),
                               "segs_cluster_naming_can_affect": tot_prod - tot_led,
                               "pct": round(100.0 * (tot_prod - tot_led) / max(1, tot_prod), 2)}}
    outp = os.path.join(args.out, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
