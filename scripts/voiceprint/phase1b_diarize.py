"""Phase 1b: diarization 聚类 → 簇质心 → 成员质心命名。

要回答的问题
------------
Phase 1 测出**跨场 EER 20.7% / 同场 11.6%** ⇒ 近一半误差来自「声学环境变化」。
换模型、换 enrollment 长度这两条杠杆都被实测否掉了 ⇒ 剩下没被否掉的杠杆是
**「让命名对象本身带上环境信息」** —— 也就是 diarization: 先在会议内把说话人聚成簇,
用**簇质心**（几十上百个段的均值, 与成员质心同一表征空间）去命名。

⭐ 本脚本的评测口径**与 Phase 1 完全一致** ⇒ 数字可直接横比
------------------------------------------------------------------
- 被验证对象: **同一批**台账真值段 (2866 条), 同一批 (会议,成员) 组合
- 成员质心: 同一个「留出该场」(LOO) 构造 —— 与 Phase 1 的 EER 完全同源
- EER: minimax 形式, 阈值扫描向量化
- ⛔ **唯一变的**: 被验证段的「表示」从**段嵌入**换成**它所属簇的簇质心**
  ⇒ 正负样本**集合完全相同**, 只是表示变了 ⇒ EER 下降才说明聚类真的有用
- ✅ **回归核对**: 不聚类(rep=段嵌入)时, 全 9 场的 EER 必须等于 Phase 1 的
  `seg_old` = **0.2067**; 不等 ⇒ 口径错了, 中止 (类 20.220)

⚠️ **参数选择协议** (类 20.226 ⑤: 阈值不能自造)
------------------------------------------------
按会议把 9 场分成**选参数集**与**验证集**:
  选参数集 (5 场): 229 / 250 / 254 / 259 / 262
  验证集   (4 场): 243 / 247 / 255 / 256
⇒ 参数 **只在选参数集上选**, 然后在验证集上汇报最终数字
⇒ 杜绝「扫一遍挑个最好看的报出来」。

⚠️ **聚类实现**: modelscope 的 `SpectralCluster` 对本输入不可行
   (它要先算 n×n 相似度矩阵再做**特征分解** ⇒ O(n³); 我们一场最多 3361 段)
   ⇒ 用 **KMeans + 3D-Speaker recipe 的 `merge_by_cos`** (簇质心余弦 > 阈值就合并)。
   ⚠️ 这是与官方 recipe 的一处**已知差异** (官方是帧级 spectral 聚类 + 1.5s/50% 重叠滑窗),
   本脚本用**生产 ASR 段**当窗 ⇒ 好处是与生产完全同源、且零 GPU 成本。

产出:
  /tmp/vp/phase1b/analysis.json     全部数字

⛔ 不写生产表; 不改 members。

用法 (容器内):
    python /tmp/vp/phase1b_diarize.py --phase1 /tmp/vp/phase1 --out /tmp/vp/phase1b
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
DEV_MEETINGS = [229, 250, 254, 259, 262]      # 选参数集
TEST_MEETINGS = [243, 247, 255, 256]           # 验证集
RANDOM_SEED = 20261031
PHASE1_EER_SEGOLD = 0.2067                      # 回归核对基准 (Phase 1 实测)


def log(msg):
    print("[phase1b] " + msg, flush=True)


def norm(v):
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def dist(a, b):
    return float(1.0 - np.dot(a, b))


def med(xs):
    return float(statistics.median(xs)) if xs else None


def eer(pos, neg):
    """验证 EER (minimax 形式): EER = min_t max(FAR(t), FRR(t))。"""
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


def merge_by_cos(Eseg, labels, threshold):
    """3D-Speaker recipe 的簇合并: 簇质心余弦相似度 > threshold 就合并, 反复迭代。

    ⚠️ 合并后的质心按**成员段数**加权 (不是簇数) —— 否则大簇小簇权重相同, 结果失真。
    """
    if threshold >= 1.0:
        return labels
    groups = {c: [c] for c in set(labels.tolist())}
    cent = {c: norm(Eseg[labels == c].mean(axis=0)) for c in groups}
    changed = True
    while changed:
        changed = False
        ks = sorted(cent)
        for i in range(len(ks)):
            for j in range(i + 1, len(ks)):
                a, b = ks[i], ks[j]
                if b not in cent:
                    continue
                if float(np.dot(norm(cent[a]), norm(cent[b]))) > threshold:
                    na = len(groups[a])
                    nb = len(groups[b])
                    cent[a] = norm((cent[a] * na + cent[b] * nb) / (na + nb))
                    groups[a] = groups[a] + groups[b]
                    del cent[b]
                    del groups[b]
                    changed = True
                    break
            if changed:
                break
    out = labels.copy()
    for new_id, (old, members) in enumerate(sorted(groups.items())):
        for m in members:
            out[labels == old] = new_id
    # ⚠️ 重映射后的标签值域必须与「簇质心列表的顺序」严格一致
    #    (cents 是按 sorted(set(labels)) 建的 ⇒ 标签值 0..n-1)
    uniq = sorted(set(out.tolist()))
    if uniq != list(range(len(uniq))):
        remap = {old: new for new, old in enumerate(uniq)}
        out = np.array([remap[int(v)] for v in out], dtype=out.dtype)
    return out


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
    ap.add_argument("--out", default="/tmp/vp/phase1b")
    ap.add_argument("--ledgers", default="/tmp/vp/ledger_13.json,/tmp/vp/ledger_30.json")
    ap.add_argument("--k-n-init", type=int, default=3)
    ap.add_argument("--emb", default="",
                    help="覆盖嵌入来源 (相对 phase1 目录, 如 emb_denoised.npz); "
                         "用于「同一套评测口径」下做 A/B 对照 (Phase 1c 降噪)。"
                         "⚠️ 只能换**嵌入**, common_MP / 候选池 / 台账真值全部不变 ⇒ EER 可比。")
    ap.add_argument("--meetings", default="",
                    help="限定评测的会议 (逗号分隔)。用于「只有部分场被改动」的 A/B 对照: "
                         "降噪只做了几场时, 必须把 common_MP 与评测集合都限到那几场, "
                         "否则未降噪的场会稀释对比。")
    ap.add_argument("--fixed-params", default="",
                    help="固定参数模式, 形如 '6,1.0' ⇒ 跳过参数扫描, 直接用给定参数评测。"
                         "A/B 对照时用 (只换嵌入, 不重选参数)。")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    META = json.load(open(os.path.join(args.phase1, "meta.json"), encoding="utf-8"))
    emb_path = os.path.join(args.phase1, args.emb) if args.emb else \
        os.path.join(args.phase1, "emb_eres.npz")
    E = np.load(emb_path)["emb"].astype(np.float32)
    assert len(META) == len(E)
    log("素材 %d 条 (嵌入: %s)" % (len(META), emb_path))
    ONLY = set(int(x) for x in args.meetings.split(",") if x.strip()) if args.meetings else None
    if ONLY:
        log("⚠️ 评测限定在会议 %s" % sorted(ONLY))

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
    log("台账真值段 %d" % len(seg_truth))

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
    log("候选池 %d 人: %s" % (len(POOL13), POOL13))

    per_meeting = collections.defaultdict(list)
    for i, m in enumerate(META):
        if m["kind"] == "seg":
            per_meeting[m["meeting"]].append(i)
    segs_by_meeting = collections.defaultdict(list)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            segs_by_meeting[mm].append((w, i))

    # 成员质心: 逐场 (该人该场的短段均值) → 重建池(全量) 与 LOO(留出该场)
    mem_rows = collections.defaultdict(list)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            mem_rows[(w, mm)].append(i)
    mem_per_meeting = {k: norm(E[v].mean(axis=0)) for k, v in mem_rows.items()}
    mem_full = {}
    for w in POOL13:
        rows = [i for mm, i in truth_rows.get(w, [])]
        if rows:
            mem_full[w] = norm(E[rows].mean(axis=0))

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

    # ---- ⭐ 复现 Phase 1 的 common_MP (39 个 (会议,成员) 组合) ----
    # Phase 1 的 EER 只在「5 个变体都有 (成员,场) 质心」的组合上算 ⇒ 样本集是锁死的。
    # ⚠️ 不复现这个限制 ⇒ 样本集不同 ⇒ EER 数字不可横比 (本轮真的踩到了: 0.2172 vs 0.2067)
    runs = json.load(open(os.path.join(args.phase1, "runs.json"), encoding="utf-8"))
    run_by_meeting = collections.defaultdict(list)
    for r in runs:
        run_by_meeting[r["meeting"]].append(r)
    truth_people_by_meeting = collections.defaultdict(set)
    for w, rows in truth_rows.items():
        for mm, i in rows:
            truth_people_by_meeting[mm].add(w)

    def unit_set(variant):
        """Phase 1 的 `avail` 构造 (三段式, 顺序不能错):
          ① 该变体的质心存在于哪些 (人, 场)         → have
          ② 可参与 EER 的组合 (会议, 成员): 成员在**该场有真值段**
             且该成员在**别的场**有该变体质心 (否则 LOO 质心不存在) → avail
          ⚠️ ② 的「该场有真值段」**不需要**该场有该变体质心 ——
             这一点曾经让本脚本算出 common_MP=29 而 Phase 1 是 39 (EER 0.2085 vs 0.2067)。
        """
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

    variants = ["seg_old", "c5", "c10", "c10_longest", "whole"]
    sets = {v: unit_set(v) for v in variants}
    common_MP = set.intersection(*sets.values())
    if ONLY:
        common_MP = {mp for mp in common_MP if mp[0] in ONLY}
    log("common_MP (5 变体共有组合): %d 个; 各变体可用 %s" % (
        len(common_MP), {v: len(s) for v, s in sets.items()}))

    # ---- KMeans 缓存 (同一 k 只算一次) ----
    from sklearn.cluster import KMeans
    km_cache = {}

    def kmeans_labels(mid, k):
        key = (mid, k)
        if key not in km_cache:
            rows = per_meeting[mid]
            kk = max(1, min(k, len(rows)))
            km = KMeans(n_clusters=kk, n_init=args.k_n_init, random_state=RANDOM_SEED)
            km_cache[key] = km.fit_predict(E[rows])
        return km_cache[key]

    # ---- k 的候选规则 ----
    n_people_by_meeting = {mid: len({w for w, _ in items})
                           for mid, items in segs_by_meeting.items()}

    def k_for(mid, mode):
        n = n_people_by_meeting.get(mid, 2)
        if mode == "oracle":
            return n
        if mode == "oracle+1":
            return n + 1
        if mode == "oracle+2":
            return n + 2
        return int(mode)

    K_MODES = ["oracle", "oracle+1", "oracle+2", "2", "3", "4", "6"]
    MERGES = [1.0, 0.85, 0.75]

    def build(mid, k_mode, merge_thr):
        rows = per_meeting[mid]
        labels = kmeans_labels(mid, k_for(mid, k_mode))
        labels = merge_by_cos(E[rows], labels, merge_thr)
        cents = []
        for c in sorted(set(labels.tolist())):
            cents.append(norm(E[rows][labels == c].mean(axis=0)))
        cents = np.stack(cents) if cents else np.zeros((0, 192), dtype=np.float32)
        rep = np.zeros((len(rows), 192), dtype=np.float32)
        for c_i in range(len(cents)):
            rep[labels == c_i] = cents[c_i]
        return rows, labels, cents, rep

    def evaluate(k_mode, merge_thr, meetings):
        if ONLY:
            meetings = [m for m in meetings if m in ONLY]
        clusters = {}
        for mid in meetings:
            if per_meeting.get(mid):
                clusters[mid] = build(mid, k_mode, merge_thr)
        # ⭐ 变体 B: **成员侧也用簇质心** (队友要求的「两侧都用长段/簇级对象」)
        #   成员 P 的簇级质心 = P 在**其它场**里、**含 P 的段**的那些簇的质心
        #   ⇒ 命名时取最近的那个
        member_cluster_pool = collections.defaultdict(list)   # (P, mid) -> [簇质心...]
        for mid in meetings:
            if mid not in clusters:
                continue
            rows, labels, cents, rep = clusters[mid]
            row_of = {i: r for r, i in enumerate(rows)}
            for w, i in [(w, i) for w, i in segs_by_meeting.get(mid, [])]:
                r = row_of.get(i)
                if r is not None:
                    member_cluster_pool[(w, mid)].append(cents[labels[r]])

        def mem_cluster_loo(w, mid):
            """成员 P 在**其它场**的簇质心集合 (P 在该场也要有段 ⇒ 否则无参照)。"""
            out = []
            for (ww, mm), cs in member_cluster_pool.items():
                if ww != w or mm == mid:
                    continue
                out.extend(cs)
            return out

        # 段级归属准确率: 两种命名口径
        #  strict = LOO 成员质心 (该人的质心来自**其它场**) ⇒ 跨场口径, 与 EER 同源
        #  loose  = 该场自己的成员质心 (in-sample for that meeting) ⇒ 与 Phase 1 的 argmin 同口径
        # 命名方式: cluster_centroid (簇质心距离) / cluster_median (簇内段距离中位数)
        #           / cluster_vs_cluster (簇质心 ↔ 成员**簇**质心)
        acc = {k: 0 for k in ("direct_strict", "clus_strict", "clus_median_strict",
                               "direct_loose", "clus_loose", "clus_median_loose",
                               "clus_clus_strict")}
        n_tot = 0
        for mid in meetings:
            if mid not in clusters:
                continue
            rows, labels, cents, rep = clusters[mid]
            pool_s = loo_pool(mid)
            pool_l = {}
            for q in POOL13:
                c = mem_per_meeting.get((q, mid))
                if c is not None:
                    pool_l[q] = c
            mc_s = {q: mem_cluster_loo(q, mid) for q in POOL13}
            mc_s = {q: v for q, v in mc_s.items() if v}
            name_s, name_l, name_ms, name_ml, name_cs = [], [], [], [], []
            for c_i, c in enumerate(cents):
                sel = [r for r in range(len(rows)) if labels[r] == c_i]
                name_s.append(min(pool_s, key=lambda q: dist(c, pool_s[q])) if pool_s else None)
                name_l.append(min(pool_l, key=lambda q: dist(c, pool_l[q])) if pool_l else None)
                if pool_s:
                    md = {q: float(np.median([dist(E[rows[r]], pool_s[q]) for r in sel]))
                          for q in pool_s}
                    name_ms.append(min(md, key=lambda q: md[q]))
                else:
                    name_ms.append(None)
                if pool_l:
                    md = {q: float(np.median([dist(E[rows[r]], pool_l[q]) for r in sel]))
                          for q in pool_l}
                    name_ml.append(min(md, key=lambda q: md[q]))
                else:
                    name_ml.append(None)
                if mc_s:
                    name_cs.append(min(mc_s, key=lambda q: min(dist(c, x) for x in mc_s[q])))
                else:
                    name_cs.append(None)
            for r, i in enumerate(rows):
                w = seg_truth.get(i)
                if not w:
                    continue
                n_tot += 1
                if pool_s and min(pool_s, key=lambda q: dist(E[i], pool_s[q])) == w:
                    acc["direct_strict"] += 1
                if name_s[labels[r]] == w:
                    acc["clus_strict"] += 1
                if name_ms[labels[r]] == w:
                    acc["clus_median_strict"] += 1
                if name_cs[labels[r]] == w:
                    acc["clus_clus_strict"] += 1
                if pool_l:
                    if min(pool_l, key=lambda q: dist(E[i], pool_l[q])) == w:
                        acc["direct_loose"] += 1
                if name_l[labels[r]] == w:
                    acc["clus_loose"] += 1
                if name_ml[labels[r]] == w:
                    acc["clus_median_loose"] += 1
        # 同口径 EER (⛔ 只在 common_MP 上算 —— 与 Phase 1 完全同一样本集)
        def eer_with(rep_mode):
            pos, neg = [], []
            for (mid, q) in sorted(common_MP):
                items = segs_by_meeting.get(mid)
                if not items or mid not in clusters:
                    continue
                rows, labels, cents, rep = clusters[mid]
                row_of = {i: r for r, i in enumerate(rows)}
                cm = mem_loo(q, mid)
                if cm is None:
                    continue
                for w, i in items:
                    if i not in row_of:
                        continue
                    vec = E[i] if rep_mode == "direct" else rep[row_of[i]]
                    d = float(1.0 - vec @ cm)
                    (pos if w == q else neg).append(d)
            return eer(pos, neg)

        e_direct, _, _ = eer_with("direct")
        e_cluster, _, _ = eer_with("cluster")
        # 簇纯度 / 簇命名正确率 / **命名天花板**
        purities, n_clu, n_ok = [], 0, 0
        oracle_named = 0        # ⭐ 若簇命名全对, 段级准确率能到多少 (瓶颈定位)
        oracle_tot = 0
        for mid in meetings:
            if mid not in clusters:
                continue
            rows, labels, cents, rep = clusters[mid]
            pool = loo_pool(mid)
            for c_i, c in enumerate(cents):
                members = collections.Counter()
                seg_n = 0
                for r, i in enumerate(rows):
                    if labels[r] == c_i:
                        if seg_truth.get(i):
                            members[seg_truth[i]] += 1
                            seg_n += 1
                if not members:
                    continue
                n_clu += 1
                top, cnt = members.most_common(1)[0]
                purities.append(cnt / sum(members.values()))
                # ⭐ 天花板的分母只能算**有真值的段** (无真值的段没有"正确"可言)
                oracle_named += cnt
                oracle_tot += seg_n
                if pool and min(pool, key=lambda q: dist(c, pool[q])) == top:
                    n_ok += 1
        return {
            "k_mode": k_mode, "merge_thr": merge_thr,
            "n_truth_seg": n_tot,
            "seg_acc_direct_strict": round(acc["direct_strict"] / max(1, n_tot), 4),
            "seg_acc_cluster_strict": round(acc["clus_strict"] / max(1, n_tot), 4),
            "seg_acc_cluster_median_strict": round(acc["clus_median_strict"] / max(1, n_tot), 4),
            "seg_acc_direct_loose": round(acc["direct_loose"] / max(1, n_tot), 4),
            "seg_acc_cluster_loose": round(acc["clus_loose"] / max(1, n_tot), 4),
            "seg_acc_cluster_median_loose": round(acc["clus_median_loose"] / max(1, n_tot), 4),
            "seg_acc_cluster_cluster_strict": round(acc["clus_clus_strict"] / max(1, n_tot), 4),
            "seg_acc_delta_strict": round((acc["clus_strict"] - acc["direct_strict"]) / max(1, n_tot), 4),
            "seg_acc_delta_loose": round((acc["clus_loose"] - acc["direct_loose"]) / max(1, n_tot), 4),
            "eer_direct": round(e_direct, 4) if e_direct is not None else None,
            "eer_cluster": round(e_cluster, 4) if e_cluster is not None else None,
            "eer_delta": (round(e_cluster - e_direct, 4)
                          if (e_direct is not None and e_cluster is not None) else None),
            "cluster_purity_mean": round(float(np.mean(purities)), 4) if purities else None,
            "n_clusters_with_truth": n_clu,
            "cluster_naming_acc": round(n_ok / max(1, n_clu), 4) if n_clu else None,
            # ⭐ 命名天花板: 若每个簇都命名成它的真值主人, 段级准确率会是多少
            #   ⇒ 段级准确率的上界由**纯度**决定 ⇒ 定位瓶颈在「命名」还是「聚类」
            "seg_acc_naming_ceiling": round(oracle_named / max(1, oracle_tot), 4) if oracle_tot else None,
        }

    ALL9 = DEV_MEETINGS + TEST_MEETINGS
    # ---- 回归核对: 不聚类时全 9 场的 EER 必须 = Phase 1 的 0.2067 ----
    # ⛔ 只在「未换嵌入」且「未限定会议」时做 —— A/B 对照(换嵌入/限会议)下样本集或输入都变了,
    #    基线值不再是 0.2067 ⇒ 此时核对无意义, 但**仍要报出实测值**供人工比对。
    if args.emb or ONLY:
        log("回归核对: 跳过 (A/B 对照模式: emb=%s meetings=%s) ⇒ "
            "下面报的 EER 只在**本次对照内部**可比" % (args.emb or "无", ONLY or "无"))
        base = evaluate("oracle", 1.0, ALL9)
    else:
        base = evaluate("oracle", 1.0, ALL9)      # merge 1.0 ⇒ 不合并
        log("回归核对: 不聚类(直接表示) 全 9 场 EER = %.4f (Phase 1 的 seg_old = %.4f) %s" % (
            base["eer_direct"], PHASE1_EER_SEGOLD,
            "✅" if abs(base["eer_direct"] - PHASE1_EER_SEGOLD) < 1e-6 else "❌ 口径不一致"))
        if abs(base["eer_direct"] - PHASE1_EER_SEGOLD) >= 1e-6:
            raise RuntimeError("EER 口径与 Phase 1 不一致 ⇒ 中止 (类 20.220)")

    log("=== 参数扫描 (选参数集 %s) ===" % DEV_MEETINGS)
    results = []
    best_oracle = None
    if args.fixed_params:
        # A/B 对照模式: 沿用**已选定的**参数, 不重扫 (只换嵌入)
        km, mt_ = args.fixed_params.split(",")
        best = evaluate(km.strip(), float(mt_), DEV_MEETINGS)
        results = [dict(best, split="dev_fixed")]
        log("固定参数模式: k=%s merge=%s (不重扫)" % (km.strip(), mt_))
    else:
        for k_mode in K_MODES:
            for m in MERGES:
                r = evaluate(k_mode, m, DEV_MEETINGS)
                results.append(dict(r, split="dev"))
                log("  k=%-9s merge=%.2f | EER %.4f → %.4f (%+.4f) | 段级strict %.4f → %.4f (%+.4f) | 段级loose %.4f → %.4f | 纯度 %.3f | 簇命名 %.3f" % (
                    r["k_mode"], r["merge_thr"], r["eer_direct"], r["eer_cluster"], r["eer_delta"],
                    r["seg_acc_direct_strict"], r["seg_acc_cluster_strict"], r["seg_acc_delta_strict"],
                    r["seg_acc_direct_loose"], r["seg_acc_cluster_loose"],
                    r["cluster_purity_mean"], r["cluster_naming_acc"]))

        dev = [r for r in results if r["split"] == "dev"]
        # ⛔ **只在「固定 k」里选参数** —— oracle 族的 k 来自台账真值给出的「该场人数」,
        #    生产系统拿不到 ⇒ 用它选参数就是自欺 (类 20.226 ⑤)。
        deployable = [r for r in dev if r["k_mode"] not in ("oracle", "oracle+1", "oracle+2")]
        best = min(deployable, key=lambda r: (r["eer_cluster"] if r["eer_cluster"] is not None else 9,
                                              -r["seg_acc_cluster_strict"]))
        oracle_rows = [r for r in dev if r["k_mode"].startswith("oracle")]
        best_oracle = min(oracle_rows, key=lambda r: (r["eer_cluster"] if r["eer_cluster"] is not None else 9,
                                                     -r["seg_acc_cluster_strict"])) if oracle_rows else None
        log("选参数集上最优(可部署, 固定k): k=%s merge=%.2f (EER %.4f, 段级strict %.4f)" % (
            best["k_mode"], best["merge_thr"], best["eer_cluster"], best["seg_acc_cluster_strict"]))
        if best_oracle:
            log("  (参考, 不可部署) 最优 oracle 族: k=%s merge=%.2f (EER %.4f)" % (
                best_oracle["k_mode"], best_oracle["merge_thr"], best_oracle["eer_cluster"]))

    def show(tag, r):
        log("=== %s ===" % tag)
        log("  k=%s merge=%.2f | EER %.4f → %.4f (%+.4f) | 段级strict %.4f → %.4f (%+.4f) [median %.4f | 簇↔簇 %.4f] | 段级loose %.4f → %.4f (%+.4f) | 纯度 %.3f | 簇命名 %.3f | 天花板 %.4f" % (
            r["k_mode"], r["merge_thr"], r["eer_direct"], r["eer_cluster"], r["eer_delta"],
            r["seg_acc_direct_strict"], r["seg_acc_cluster_strict"], r["seg_acc_delta_strict"],
            r["seg_acc_cluster_median_strict"], r["seg_acc_cluster_cluster_strict"],
            r["seg_acc_direct_loose"], r["seg_acc_cluster_loose"], r["seg_acc_delta_loose"],
            r["cluster_purity_mean"], r["cluster_naming_acc"],
            r["seg_acc_naming_ceiling"]))

    test = evaluate(best["k_mode"], best["merge_thr"], TEST_MEETINGS)
    show("验证集 %s (参数不在此集上选)" % TEST_MEETINGS, test)
    full = evaluate(best["k_mode"], best["merge_thr"], ALL9)
    show("全 9 场 (参考, 非选参数依据)", full)
    if best_oracle:
        show("验证集 · oracle 族最优 (参考, 不可部署)", evaluate(best_oracle["k_mode"],
                                                                best_oracle["merge_thr"],
                                                                TEST_MEETINGS))

    out = {"pool13": POOL13,
           "dev_meetings": DEV_MEETINGS, "test_meetings": TEST_MEETINGS,
           "regression_eer_direct_all9": base["eer_direct"],
           "regression_phase1_eer_segold": PHASE1_EER_SEGOLD,
           "best_params_deployable": {"k_mode": best["k_mode"], "merge_thr": best["merge_thr"]},
           "best_params_oracle_reference": ({"k_mode": best_oracle["k_mode"],
                                            "merge_thr": best_oracle["merge_thr"]}
                                           if best_oracle else None),
           "scan": results,
           "dev_best": best, "test_at_best": test, "all9_at_best": full}
    outp = os.path.join(args.out, "analysis.json")
    with open(outp, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    log("已写出 %s" % outp)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
