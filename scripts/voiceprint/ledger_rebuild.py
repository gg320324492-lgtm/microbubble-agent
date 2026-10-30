"""用**人工确认台账**重建声纹质心, 并做留一验证与锚池污染体检。

⛔ 三条纪律 (CLAUDE.md 类 20.226 / 20.241):
  ① 判「某方案能不能用」必须同时报 **认回率** 与 **抢走率(绝对数)**,
     只报认回率是不够的 (认回 0 段但抢走 9 段是典型的「看着无损失、实则破坏」)。
  ② 留出集必须与建库样本**不相交**, 且**跨环境**(按会议留出, 不按段留出)。
  ③ **不设自造阈值** —— 判据用「离谁更近」的逐段比较, 而不是
     「d <= 0.45」这类自己拍的界。

判「某人本场有没有发言」用**跨场台账重建的真值质心**, 不用库里那个 anchor
(anchor 自己可能被污染过, 拿它当参照 = 循环论证, 类 20.241)。

用法 (容器内):
    python /app/scripts/voiceprint/ledger_rebuild.py --samples /tmp/vp/all.npz
    python /app/scripts/voiceprint/ledger_rebuild.py --samples /tmp/vp/all.npz --apply 刘子煜,蒋芦笛
"""

import argparse
import asyncio
import json
import os
import sys

import numpy as np

sys.path.insert(0, "/app")

MATCH_THRESHOLD = 0.65  # app/services/voiceprint_service.py:27
NEGATIVE_WHO = {"环境声", "人群杂音", "视频", "环境声/人群杂音"}


def centroid(mat: np.ndarray) -> np.ndarray:
    """台账样本的质心: L2 归一化向量的均值, 再归一化。"""
    v = mat.mean(axis=0)
    n = float(np.linalg.norm(v))
    return v / (n + 1e-8)


def simulate(pool: dict, emb: np.ndarray, thr: float = MATCH_THRESHOLD):
    """复刻生产语义 (identify_speaker_anchored): 最近 anchor 且 dist < thr 才认。"""
    names = list(pool.keys())
    if not names:
        return None, 1.0
    P = np.stack([pool[n] for n in names])
    P = P / (np.linalg.norm(P, axis=1, keepdims=True) + 1e-8)
    d = 1.0 - P @ emb
    j = int(np.argmin(d))
    return (names[j], float(d[j])) if d[j] < thr else (None, float(d[j]))


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--apply", default="", help="逗号分隔的成员名; 空 = 只报告")
    ap.add_argument("--out", default="/tmp/vp/rebuild_report.json")
    args = ap.parse_args()

    d = np.load(args.samples)
    E = d["emb"].astype(np.float32)
    M = json.load(open(args.samples.replace(".npz", "_meta.json"), encoding="utf-8"))
    assert len(E) == len(M), (len(E), len(M))

    # ---------- 1. 当前 anchor 池 ----------
    from sqlalchemy import select

    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        rows = (await db.execute(
            select(Member).where(Member.voice_embedding.isnot(None),
                                 Member.voice_confirmed_at.isnot(None),
                                 Member.is_active == True))).scalars().all()
        cur_pool, cur_ids = {}, {}
        for m in rows:
            cur_pool[m.name] = np.asarray(m.voice_embedding, dtype=np.float32)
            cur_ids[m.name] = m.id
        all_members = (await db.execute(select(Member))).scalars().all()
        member_by_name = {m.name: m for m in all_members}
    await engine.dispose()

    # ---------- 2. 台账索引 ----------
    idx = []
    for i, m in enumerate(M):
        m["_i"] = i
        if m["in_ledger"] and m["who"] and m["who"] not in NEGATIVE_WHO:
            idx.append(i)
    ledger_idx = np.array(idx, dtype=int)
    # 负样本 (环境声/人群杂音)
    neg_idx = np.array([m["_i"] for m in M if m["in_ledger"] and m["who"] in NEGATIVE_WHO], dtype=int)

    people = sorted({M[i]["who"] for i in ledger_idx})
    report = {"threshold": MATCH_THRESHOLD, "n_segments": len(M),
              "n_ledger_speech": len(ledger_idx), "n_ledger_negative": len(neg_idx),
              "current_anchors": sorted(cur_pool.keys()), "people": {}}

    # 每人的台账样本按会议分组
    by_person = {}
    for i in ledger_idx:
        by_person.setdefault(M[i]["who"], {}).setdefault(M[i]["meeting"], []).append(i)

    # ---------- 3. 当前状态基线: 谁吸走了谁 ----------
    steal = {a: {} for a in cur_pool}
    cur_pred = {}
    for i in ledger_idx:
        who = M[i]["who"]
        pred, dist = simulate(cur_pool, E[i])
        cur_pred[i] = (pred, dist)
        if pred is not None and pred != who:
            steal.setdefault(pred, {}).setdefault(who, []).append(
                {"seg": M[i]["seg_idx"], "mid": M[i]["meeting"], "d": round(dist, 4),
                 "dur": M[i]["dur"], "text": M[i]["text"][:60]})
    report["baseline_current_anchors"] = {
        a: {w: len(v) for w, v in sorted(d_.items(), key=lambda kv: -len(kv[1]))}
        for a, d_ in steal.items() if d_}

    # ---------- 3.5 每场对齐诊断 (cohesion) ----------
    # 若某场音频与转录时间轴错位, 该场同一人的人工块会互不相似 ⇒ cohesion 会塌。
    # 判据是**相对量**(同人间最大距离 vs 人人间最小距离), 不设自造阈值。
    cohesion = {}
    for mid in sorted({M[i]["meeting"] for i in ledger_idx}):
        same, diff = [], []
        loc = [i for i in ledger_idx if M[i]["meeting"] == mid]
        for a in range(len(loc)):
            for b in range(a + 1, len(loc)):
                ia, ib = loc[a], loc[b]
                dd = float(1.0 - E[ia] @ E[ib])
                if M[ia]["who"] == M[ib]["who"]:
                    same.append(dd)
                else:
                    diff.append(dd)
        if same and diff:
            cohesion[mid] = {
                "n_same_pairs": len(same), "n_diff_pairs": len(diff),
                "same_max": round(max(same), 4), "same_median": round(float(np.median(same)), 4),
                "diff_min": round(min(diff), 4), "diff_median": round(float(np.median(diff)), 4),
                "separable": bool(max(same) < min(diff)),
            }
    report["alignment_cohesion"] = cohesion

    # ---------- 4. 台账重建质心 + 留一验证 ----------
    # 训练样本时长变体: 短段 embedding 不稳 (类 20.226「按时长降权」),
    # 但**不预设哪个对** —— 每个变体都跑一遍留一, 由**留一结果**选, 不是我拍。
    MIN_DUR_VARIANTS = [0.0, 1.0, 2.0]

    def centroid_for(p, min_dur, held_out=None):
        rows = []
        for m2, lst in by_person[p].items():
            if held_out is not None and m2 == held_out:
                continue
            rows.extend(lst)
        sel = [i for i in rows if M[i]["dur"] >= min_dur]
        if not sel:
            sel = rows
        return centroid(E[sel]), len(sel)

    cand = {}
    for p in by_person:
        cand[p] = {"min_dur=%.1f" % v: centroid_for(p, v)[0] for v in MIN_DUR_VARIANTS}

    loo = {}
    for p, per_meeting in by_person.items():
        if len(per_meeting) < 2:
            loo[p] = {"note": "只有 %d 场台账, 不做留一 (类 20.226: 单场会过拟合)" % len(per_meeting)}
            continue
        rec = {"meetings": sorted(per_meeting.keys()), "variants": {}}
        for v in MIN_DUR_VARIANTS:
            folds, tot_rec = [], 0
            tot_ok = tot_steal = 0
            for held in sorted(per_meeting):
                c, n_train = centroid_for(p, v, held_out=held)
                test_i = per_meeting[held]
                others = [i for i in ledger_idx if M[i]["meeting"] == held and M[i]["who"] != p]
                base_pool = {k: val for k, val in cur_pool.items()}
                base_pool.pop(p, None)
                rec_n = steal_n = 0
                for i in test_i:
                    pred_new, dn = simulate({**base_pool, p: c}, E[i])
                    if pred_new == p:
                        rec_n += 1
                for i in others:
                    pred_new, dn = simulate({**base_pool, p: c}, E[i])
                    pred_old, do = simulate(base_pool, E[i])
                    if pred_new == p and pred_old is not None and pred_old != p:
                        steal_n += 1
                folds.append({
                    "held_out_meeting": held, "n_train": n_train,
                    "n_test": len(test_i), "n_others": len(others),
                    "认回": rec_n, "抢走": steal_n,
                    "认回率": round(rec_n / max(1, len(test_i)), 3),
                    "抢走率": round(steal_n / max(1, len(others)), 3),
                })
                tot_ok += rec_n
                tot_steal += steal_n
                tot_rec += len(test_i)
            rec["variants"]["min_dur=%.1f" % v] = {
                "folds": folds,
                "totals": {"认回": tot_ok, "认回率": round(tot_ok / max(1, tot_rec), 3),
                           "抢走": tot_steal,
                           "净增益": tot_ok - tot_steal},
            }
        # 由留一净增益选变体 (验证集选型, 不是在测试集上调)
        best = max(rec["variants"].items(), key=lambda kv: (kv[1]["totals"]["净增益"],
                                                           kv[1]["totals"]["认回率"]))
        rec["selected"] = best[0]
        rec["selected_totals"] = best[1]["totals"]
        loo[p] = rec
    report["loo"] = loo

    def sel_of(p: str) -> str:
        """该人选定的训练样本时长变体 (由留一结果选, 见 loo[p]['selected'])。"""
        e = loo.get(p, {})
        return e.get("selected", "min_dur=0.0")

    # ---------- 5. 候选池整体对比 (当前池 vs 候选池) ----------
    def evaluate(pool: dict, label: str):
        correct = wrong = unknown = 0
        wrong_detail = {}
        for i in ledger_idx:
            who = M[i]["who"]
            pred, dist = simulate(pool, E[i])
            if pred == who:
                correct += 1
            elif pred is None:
                unknown += 1
            else:
                wrong += 1
                wrong_detail.setdefault(pred, {}).setdefault(who, []).append(
                    {"mid": M[i]["meeting"], "seg": M[i]["seg_idx"], "d": round(dist, 4)})
        # 负样本被误认的比例
        neg_stolen = 0
        for i in neg_idx:
            pred, dist = simulate(pool, E[i])
            if pred is not None:
                neg_stolen += 1
        return {"label": label, "n": len(ledger_idx), "correct": correct, "wrong": wrong,
                "unknown": unknown,
                "acc": round(correct / max(1, len(ledger_idx)), 3),
                "neg_stolen": neg_stolen, "n_neg": len(neg_idx),
                "wrong_detail": {k: {w: len(v) for w, v in vv.items()}
                                 for k, vv in wrong_detail.items()}}

    report["eval"] = [evaluate(cur_pool, "当前库")]
    for p in people:
        if p in cur_ids:
            continue
        report["eval"].append(evaluate({**cur_pool, p: cand[p][sel_of(p)]},
                                       "当前库 + 台账质心[%s | %s]" % (p, sel_of(p))))

    # ---------- 6. 已有 anchor 的纯重建对比 (尤其蒋芦笛) ----------
    rebuild_cmp = {}
    for p in people:
        if p not in cur_ids:
            continue
        pool_new = {**cur_pool, p: cand[p][sel_of(p)]}
        before = evaluate(cur_pool, "before")
        after = evaluate(pool_new, "after")
        rebuild_cmp[p] = {
            "current_sample_count": member_by_name[p].voice_sample_count,
            "ledger_blocks": sum(len(v) for v in by_person[p].values()),
            "ledger_meetings": sorted(by_person[p].keys()),
            "selected_variant": sel_of(p),
            "acc_before": before["acc"], "acc_after": after["acc"],
            "correct_before": before["correct"], "correct_after": after["correct"],
            "wrong_before": before["wrong"], "wrong_after": after["wrong"],
            "neg_stolen_before": before["neg_stolen"], "neg_stolen_after": after["neg_stolen"],
            "wrong_detail_after": after["wrong_detail"],
        }
    report["rebuild_existing"] = rebuild_cmp

    # ---------- 7. 刘子煜专项: 259 整场汇报归属 ----------
    special = {}
    if "刘子煜" in cand:
        lz_pool = {**cur_pool, "刘子煜": cand["刘子煜"][sel_of("刘子煜")]}
        pres = [i for i in range(len(M))
                if M[i]["meeting"] == 259 and 455.0 <= M[i]["start"] <= 1870.0]
        cnt = {}
        for i in pres:
            pred, dist = simulate(lz_pool, E[i])
            cnt[str(pred)] = cnt.get(str(pred), 0) + 1
        special["meeting259_presentation"] = {
            "n": len(pres),
            "with_lizi_centroid": cnt,
            "note": "455-1870s = 整场汇报区间 (87 段, 现标刘子煜)",
        }
        # 只用当前库 (无刘子煜质心) 时这段被谁吸走
        cnt2 = {}
        for i in pres:
            pred, dist = simulate(cur_pool, E[i])
            cnt2[str(pred)] = cnt2.get(str(pred), 0) + 1
        special["meeting259_presentation"]["current_pool_only"] = cnt2

    # ---------- 7b. 259 全场逐 30s 窗口归属 (诊断用) ----------
    win = {}
    for i in range(len(M)):
        if M[i]["meeting"] != 259:
            continue
        b = int(M[i]["start"] // 30) * 30
        w = win.setdefault(b, {"n": 0, "db": {}, "new": {}, "d_lizi": [], "d_wang": []})
        w["n"] += 1
        w["db"][M[i]["db_speaker"]] = w["db"].get(M[i]["db_speaker"], 0) + 1
        if "刘子煜" in cand:
            pool2 = {**cur_pool, "刘子煜": cand["刘子煜"][sel_of("刘子煜")]}
            pred, dist = simulate(pool2, E[i])
            w["new"][str(pred)] = w["new"].get(str(pred), 0) + 1
            w["d_lizi"].append(round(float(1.0 - E[i] @ cand["刘子煜"][sel_of("刘子煜")]), 4))
            if "王天志" in cur_pool:
                w["d_wang"].append(round(float(1.0 - E[i] @ cur_pool["王天志"]), 4))
    for b, w in sorted(win.items()):
        w["d_lizi_med"] = round(float(np.median(w["d_lizi"])), 4) if w["d_lizi"] else None
        w["d_wang_med"] = round(float(np.median(w["d_wang"])), 4) if w["d_wang"] else None
        w["d_lizi"] = w["d_lizi"][:0]
        w["d_wang"] = w["d_wang"][:0]
    special["meeting259_windows_30s"] = {str(k): v for k, v in sorted(win.items())}

    # 转移矩阵: 现库预测 -> 加新质心后预测 (只对 259)
    trans = {}
    for p in people:
        if p in cur_ids:
            continue
        pool2 = {**cur_pool, p: cand[p][sel_of(p)]}
        for i in range(len(M)):
            if M[i]["meeting"] != 259:
                continue
            a, _ = simulate(cur_pool, E[i])
            b, _ = simulate(pool2, E[i])
            if a != b:
                k = "%s -> %s" % (a, b)
                trans.setdefault(k, []).append(
                    {"seg": M[i]["seg_idx"], "s": M[i]["start"], "dur": M[i]["dur"],
                     "db": M[i]["db_speaker"], "text": M[i]["text"][:50]})
    special["meeting259_transitions"] = {
        k: {"n": len(v), "samples": v[:8]} for k, v in sorted(trans.items(), key=lambda kv: -len(kv[1]))}
    report["special"] = special

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)
    print("[vp] 报告已写出", args.out, flush=True)

    # ---------- 8. 应用 ----------
    if args.apply.strip():
        names = [x.strip() for x in args.apply.split(",") if x.strip()]
        from sqlalchemy import text as sql_text
        engine, Session = create_celery_engine_and_session()
        async with Session() as db:
            for p in names:
                if p not in cand:
                    print("[vp] 跳过 %s (台账里没有)" % p, flush=True)
                    continue
                m = member_by_name.get(p)
                if m is None:
                    print("[vp] 跳过 %s (无此成员)" % p, flush=True)
                    continue
                old = list(m.voice_embedding) if m.voice_embedding is not None else None
                old_count = m.voice_sample_count or 0
                sel = sel_of(p)
                vec = cand[p][sel]
                n_samples = sum(len(v) for v in by_person[p].values())
                m.voice_embedding = vec.tolist()
                m.voice_sample_count = n_samples
                m.voice_enrolled_at = sql_text("NOW()")
                m.voice_confirmed_at = sql_text("NOW()")
                m.voice_confirmed_by = "rebuild-2026-10-30"
                m.voice_confirmed_meeting_id = None
                await db.execute(sql_text(
                    "INSERT INTO member_voice_history (member_id, source, old_embedding, new_embedding, "
                    "sample_count_before, sample_count_after, notes) VALUES (:m, 'rebuild_2026_10_30', "
                    ":old, :new, :sb, :sa, :notes)"), {
                        "m": m.id, "old": old, "new": vec.tolist(),
                        "sb": old_count, "sa": n_samples,
                        "notes": "台账重建: %d 块 / %d 场 (人耳确认), 变体 %s, 留一净增益 %s" % (
                            n_samples, len(by_person[p]), sel,
                            loo.get(p, {}).get("selected_totals", {}).get("净增益", "n/a"))})
                print("[vp] 已写库: %s (id=%d, %d 块, %d 场, %s)" % (
                    p, m.id, n_samples, len(by_person[p]), sel), flush=True)
            await db.commit()
        await engine.dispose()
        print("[vp] 写库完成", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
