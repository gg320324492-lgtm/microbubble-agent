"""Phase 1h 的 shadow evaluation: 在**真实生产会议**（非台账那 8 场）上跑滑窗聚类,
**只记录、不写任何生产字段**。

为什么必须在「真实会议」上做
--------------------------
台账那 8 场是**选参用**的, 且说话人集合已知; **生产会议说话人更多、台账覆盖更少**
⇒ 台账上的数字不能代表生产分布 (类 20.249 的「候选池/样本集变化会漂移判据」)。
⇒ 本脚本把 12 场滑窗集拆成两组分别报:
    生产组 = 台账之外 (m246 / m257 / m263)
    台账组 = 参照 (其余 9 场)
重点量四件事:

  ① **逐段 diff**: 若启用滑窗聚类, 每个段的标签 vs 现役标签 → 改了多少段
     ⚠️ 拆三档报: 新名**不在候选池**(必然不同, 是"无处可归"不是"归错") /
        双方都在池内但不同 (真正的"改名") / 完全相同
  ② **簇名候选 diff**: 新算的簇名 vs 现役的**人工裁决** (meeting_speaker_adjudications)
  ③ **成本账**: 总嵌入耗时 / 每场窗数 / **每分钟音频 ms**
  ④ ⭐ **簇数分布 + 纯度代理 + 主导簇占比**: 真实会议说话人更多 ⇒
     **固定 k=6 会不会把不同人切进同一簇(簇混)?**
     ⇒ 纯度代理 = 「簇内**现役**标签众数占比」(⚠️ 现役标签本身可能错 ⇒ 只是代理)
     ⇒ 「发言人?/发言人A/B/C」**不算说话人**, 单独统计弃权率

⭐ **零 GPU 成本**: Phase 1h 已把 12 场的滑窗嵌入算好 (/tmp/vp/phase1h/emb_sw.npy)
⇒ 本脚本只做聚类 + 统计。

⛔ 不写生产表; 不改 members; 不改 transcript。

用法 (容器内):
    python /tmp/vp/phase1h_shadow_eval.py --phase1 /tmp/vp/phase1 --sw /tmp/vp/phase1h \
        --out /tmp/vp/phase1h_shadow
"""
import argparse
import asyncio
import collections
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")

SEED = 20261031
K_FIXED = 6
DEV_MEETINGS = [229, 250, 254, 259, 262]     # 选参集
TEST_MEETINGS = [243, 247, 255, 256]          # 验证集
LEDGER_MEETINGS = set(DEV_MEETINGS) | set(TEST_MEETINGS)

# 「发言人?」/「发言人A」这类是**弃权标记**, 不是说话人
NON_SPEAKER = {"", "发言人?", "发言人A", "发言人B", "发言人C", "系统", "未知"}


def log(m):
    print("[shadow] " + m, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


async def load_db():
    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.member import Member
    from app.models.meeting_speaker_adjudication import MeetingSpeakerAdjudication

    engine, Session = create_celery_engine_and_session()
    mt, db_cent, adj = {}, {}, collections.defaultdict(list)
    async with Session() as db:
        for m in (await db.execute(select(Meeting))).scalars().all():
            mt[m.id] = {"audio_url": m.audio_url,
                        "segs": sorted(m.transcript or [],
                                       key=lambda s: float(s.get("start") or 0))}
        for mm in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            v = np.asarray(mm.voice_embedding, dtype=np.float32)
            if np.linalg.norm(v) > 0:
                db_cent[mm.name] = norm(v)
        for a in (await db.execute(select(MeetingSpeakerAdjudication))).scalars().all():
            adj[a.meeting_id].append({"s": a.seg_start, "e": a.seg_end, "sp": a.speaker,
                                      "src": a.source})
    await engine.dispose()
    return mt, db_cent, adj


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase1", default="/tmp/vp/phase1")
    ap.add_argument("--sw", default="/tmp/vp/phase1h")
    ap.add_argument("--out", default="/tmp/vp/phase1h_shadow")
    ap.add_argument("--k", type=int, default=K_FIXED,
                    help="簇数; 配合 --ksweep 可扫多档")
    ap.add_argument("--ksweep", default="",
                    help="逗号分隔的 k 列表, 例 '4,6,8,10,12'; 空=只跑 --k")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    from sklearn.cluster import KMeans

    SWM = json.load(open(os.path.join(args.sw, "meta_sw.json"), encoding="utf-8"))
    SW = np.load(os.path.join(args.sw, "emb_sw.npy")).astype(np.float32)
    ident = json.load(open(os.path.join(args.sw, "identity_check.json"), encoding="utf-8"))
    elapsed = float(ident.get("elapsed_sec") or 0)
    log("滑窗 %d 条; 上一轮嵌入总耗时 %.0fs" % (len(SWM), elapsed))

    mt, db_cent, adj = asyncio.run(load_db())
    POOL = sorted(db_cent)
    log("现役质心 %d 人: %s" % (len(POOL), POOL))
    log("有人工裁决的会议 %d 个: %s" % (len(adj), sorted(adj)))

    sw_by_mid = collections.defaultdict(list)
    for k, m in enumerate(SWM):
        sw_by_mid[m["meeting"]].append(k)

    # ---- k 扫描模式: 生产会议上「固定 k=6 会不会簇混/簇碎」----
    if args.ksweep.strip():
        ks = [int(x) for x in args.ksweep.split(",") if x.strip()]
        sweep = []
        for kk in ks:
            rows_k = []
            for mid in sorted(sw_by_mid):
                wk = sw_by_mid[mid]
                if len(wk) < 10:
                    continue
                rows_k.append(eval_meeting(mid, wk, SW, SWM, mt, db_cent, POOL,
                                           adj, kk))
            pk = [r for r in rows_k if not r["in_ledger_set"]]
            lk = [r for r in rows_k if r["in_ledger_set"]]
            agg_k = {}
            for tag, rs in (("prod", pk), ("ledger", lk)):
                def m_(key):
                    xs = [r[key] for r in rs if r.get(key) is not None]
                    return round(float(np.mean(xs)), 4) if xs else None
                agg_k[tag] = {
                    "purity_proxy_mean": m_("cluster_label_purity_proxy"),
                    "purity_proxy_min": m_("cluster_purity_proxy_min"),
                    "dominant_cluster_share": m_("dominant_cluster_share"),
                    "diff_in_pool_rate": m_("seg_diff_in_pool_rate"),
                }
            sweep.append({"k": kk, "per_meeting": rows_k, "agg": agg_k})
            log("k=%-3d | 生产组: 纯度代理%.3f(最低%.3f) 主导簇占比%.3f 改名率%.1f%% | "
                "台账组: 纯度代理%.3f(最低%.3f) 主导簇占比%.3f" % (
                    kk,
                    agg_k["prod"]["purity_proxy_mean"] or 0,
                    agg_k["prod"]["purity_proxy_min"] or 0,
                    agg_k["prod"]["dominant_cluster_share"] or 0,
                    100 * (agg_k["prod"]["diff_in_pool_rate"] or 0),
                    agg_k["ledger"]["purity_proxy_mean"] or 0,
                    agg_k["ledger"]["purity_proxy_min"] or 0,
                    agg_k["ledger"]["dominant_cluster_share"] or 0))
        outp = os.path.join(args.out, "shadow_ksweep.json")
        with open(outp, "w", encoding="utf-8") as fh:
            json.dump({"k_list": ks, "sweep": sweep}, fh, ensure_ascii=False, indent=1)
        log("已写出 %s" % outp)
        return

    rows_out = []
    for mid in sorted(sw_by_mid):
        wk = sw_by_mid[mid]
        if len(wk) < 10:
            continue
        rows_out.append(eval_meeting(mid, wk, SW, SWM, mt, db_cent, POOL, adj, args.k))

    led = [r for r in rows_out if r["in_ledger_set"]]
    prod = [r for r in rows_out if not r["in_ledger_set"]]
    hdr = ("  m%-4s 窗%6d 簇%d 现役说话人%2d | 段%5d 同%5d 改名%5d 无处可归%5d (改名率%.1f%%) | "
           "弃权率%.1f%% | 纯度代理%.3f(最低%.3f) | 主导簇占比%.3f | 裁决diff %s")
    log("=== 生产会议(台账之外) %d 场 ===" % len(prod))
    for r in prod:
        log(hdr % (r["meeting"], r["n_windows"], r["n_clusters"], r["n_current_speakers"],
                   r["n_segments_compared"], r["seg_same"], r["seg_diff_in_pool"],
                   r["seg_diff_not_in_pool"], 100 * (r["seg_diff_in_pool_rate"] or 0),
                   100 * (r["current_abstain_rate"] or 0),
                   r["cluster_label_purity_proxy"] or 0, r["cluster_purity_proxy_min"] or 0,
                   r["dominant_cluster_share"],
                   json.dumps(r["adjudication_diff"], ensure_ascii=False) if r["adjudication_diff"] else "-"))
    log("=== 台账那 9 场(参照) ===")
    for r in led:
        log(hdr % (r["meeting"], r["n_windows"], r["n_clusters"], r["n_current_speakers"],
                   r["n_segments_compared"], r["seg_same"], r["seg_diff_in_pool"],
                   r["seg_diff_not_in_pool"], 100 * (r["seg_diff_in_pool_rate"] or 0),
                   100 * (r["current_abstain_rate"] or 0),
                   r["cluster_label_purity_proxy"] or 0, r["cluster_purity_proxy_min"] or 0,
                   r["dominant_cluster_share"],
                   json.dumps(r["adjudication_diff"], ensure_ascii=False) if r["adjudication_diff"] else "-"))
    def agg(rs, key):
        xs = [r[key] for r in rs if r.get(key) is not None]
        return {"n": len(xs),
                "mean": round(float(np.mean(xs)), 4) if xs else None,
                "median": round(float(np.median(xs)), 4) if xs else None,
                "min": round(float(np.min(xs)), 4) if xs else None,
                "max": round(float(np.max(xs)), 4) if xs else None}

    tot_audio_sec = sum(r["audio_sec"] for r in rows_out)
    cost = {
        "embed_elapsed_sec_total": elapsed,
        "n_windows_total": len(SWM),
        "audio_sec_total": round(tot_audio_sec, 1),
        "ms_per_audio_minute": round(elapsed / max(tot_audio_sec, 1) * 60000, 1),
        "windows_per_audio_minute": round(len(SWM) / max(tot_audio_sec, 1) * 60, 1),
        "sec_per_window": round(elapsed / max(len(SWM), 1), 4),
    }
    log("成本账: %s" % json.dumps(cost, ensure_ascii=False))

    out = {"k_fixed": args.k,
           "ledger_meetings": sorted(LEDGER_MEETINGS),
           "production_meetings": [r["meeting"] for r in prod],
           "cost": cost,
           "per_meeting": rows_out,
           "agg_production": {
               "seg_label_diff_rate": agg(prod, "seg_label_diff_rate"),
               "seg_diff_in_pool_rate": agg(prod, "seg_diff_in_pool_rate"),
               "cluster_label_purity_proxy": agg(prod, "cluster_label_purity_proxy"),
               "cluster_purity_proxy_min": agg(prod, "cluster_purity_proxy_min"),
               "dominant_cluster_share": agg(prod, "dominant_cluster_share"),
               "n_clusters": agg(prod, "n_clusters"),
               "n_current_speakers": agg(prod, "n_current_speakers"),
           },
           "agg_ledger": {
               "seg_label_diff_rate": agg(led, "seg_label_diff_rate"),
               "seg_diff_in_pool_rate": agg(led, "seg_diff_in_pool_rate"),
               "cluster_label_purity_proxy": agg(led, "cluster_label_purity_proxy"),
               "cluster_purity_proxy_min": agg(led, "cluster_purity_proxy_min"),
               "dominant_cluster_share": agg(led, "dominant_cluster_share"),
           }}
    outp = os.path.join(args.out, "shadow.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


def eval_meeting(mid, wk, SW, SWM, mt, db_cent, POOL, adj, k_fixed):
    """对一场会议做滑窗聚类 + 统计 (k 由调用方给)。"""
    from sklearn.cluster import KMeans

    Ek = SW[wk]
    k = min(k_fixed, len(wk))
    lab = KMeans(n_clusters=k, n_init=3, random_state=SEED).fit_predict(Ek)
    cids = sorted(set(lab.tolist()))
    cents = np.stack([norm(Ek[lab == c].mean(0)) for c in cids])
    names = [min(POOL, key=lambda q: float(1.0 - np.dot(c, db_cent[q]))) for c in cents]
    sw_start = np.array([float(SWM[i]["start"]) for i in wk])
    sw_end = np.array([float(SWM[i]["end"]) for i in wk])

    segs = [s for s in mt.get(mid, {}).get("segs", [])
            if float(s.get("end") or 0) - float(s.get("start") or 0) >= 0.5]
    n_same = n_diff_inpool = n_diff_notpool = n_seg = n_abstain = 0
    cur_names = set()
    per_cluster = collections.defaultdict(collections.Counter)
    for s in segs:
        a, b = float(s.get("start") or 0), float(s.get("end") or 0)
        t = (a + b) / 2.0
        j = int(np.searchsorted(sw_start, t, side="right")) - 1
        if j < 0 or t > sw_end[j]:
            continue
        ci = int(lab[j])
        new_label = names[ci]
        cur_label = (s.get("speaker") or "").strip()
        n_seg += 1
        if cur_label in NON_SPEAKER:
            n_abstain += 1
        else:
            cur_names.add(cur_label)
        if new_label == cur_label:
            n_same += 1
        elif cur_label in NON_SPEAKER or new_label not in POOL:
            # 现役是弃权, 或新名压根不在候选池(无处可归) —— 不是"改名"
            n_diff_notpool += 1
        else:
            n_diff_inpool += 1
        if cur_label not in NON_SPEAKER:
            per_cluster[ci][cur_label] += 1
    # 纯度代理: 簇内**现役实名**标签的众数占比 (弃权段不计入)
    purities, dom_share, cluster_sizes = [], [], []
    for c in cids:
        sz = int((lab == c).sum())
        cluster_sizes.append(sz)
        dom_share.append(sz / len(wk))
        hist = per_cluster.get(c)
        if hist:
            tot = sum(hist.values())
            purities.append(hist.most_common(1)[0][1] / tot)
    audio_sec = max([float(s.get("end") or 0) for s in mt.get(mid, {}).get("segs", [])]
                    + [0])

    # 簇名候选 vs 现役人工裁决
    adj_diff = None
    if adj.get(mid):
        a_list = adj[mid]
        same = compared = 0
        for ci in cids:
            # ⚠️ lab 是**场内局部下标**, wk 是**全局下标** ⇒ 必须先转
            local_pos = np.flatnonzero(lab == ci)
            if len(local_pos) == 0:
                continue
            ci_rows = [wk[p] for p in local_pos]
            t = float(np.median([(float(SWM[i]["start"]) + float(SWM[i]["end"])) / 2
                                 for i in ci_rows]))
            hit = None
            for a in a_list:
                if a["s"] <= t <= a["e"]:
                    hit = a["sp"]
                    break
            if hit is None:
                continue
            compared += 1
            if hit == names[ci]:
                same += 1
        adj_diff = {"adjudication_rows": len(a_list),
                    "clusters_compared": compared,
                    "same_name_clusters": same}

    return {
        "meeting": mid,
        "in_ledger_set": mid in LEDGER_MEETINGS,
        "k": k,
        "n_windows": len(wk),
        "n_clusters": len(cids),
        "cluster_sizes": sorted(cluster_sizes, reverse=True),
        "dominant_cluster_share": round(max(dom_share), 4),
        "n_current_speakers": len(cur_names),
        "current_speakers": sorted(cur_names),
        "audio_sec": round(audio_sec, 1),
        "n_segments_compared": n_seg,
        "seg_same": n_same,
        "seg_diff_in_pool": n_diff_inpool,
        "seg_diff_not_in_pool": n_diff_notpool,
        "seg_label_diff_rate": round((n_diff_inpool + n_diff_notpool) / n_seg, 4) if n_seg else None,
        "seg_diff_in_pool_rate": round(n_diff_inpool / n_seg, 4) if n_seg else None,
        "current_abstain_rate": round(n_abstain / n_seg, 4) if n_seg else None,
        "cluster_label_purity_proxy": round(float(np.mean(purities)), 4) if purities else None,
        "cluster_purity_proxy_min": round(float(np.min(purities)), 4) if purities else None,
        "cluster_names": names,
        "adjudication_diff": adj_diff,
    }


if __name__ == "__main__":
    main()
