#!/usr/bin/env python
"""闸 C: 新增姓名的**声学交叉验证**(类 20.244 ③)。

背景: 闸 A(台账真值不降) / 闸 B(台账外成员不得占大段) 已在
`scripts/voiceprint/relabel_by_margin.py` 实装; 本脚本补第三道:
**某成员新拿到的那批段, 声学上是否与该成员的人耳确认段同源**。

⚠️ **必须用新鲜提取的嵌入**(与 relabel_by_margin.py 同一条路径: 同音频、同 MIN_SEC=0.5、
同 `batch_extract_embeddings`) —— 之前用缓存 `all3.npz` 重算时, 因为缓存的 MIN_SEC 不同
(少了 128 段) 导致聚类改变, 重算结果 573 未识别 vs relabel 的 334 ⇒ **缓存不能替代新鲜提取**。

判据(全部是相对量, 不设自造阈值 —— 类 20.226 ⑤):
  1. `newly` 段到该成员 anchor 的距离中位 vs `confirmed` 段(台账人耳确认)到同一 anchor 的
     距离中位 —— 同量级 ⇒ 声学一致; 若 newly **明显更近** ⇒ 该 anchor 在「吸走别人」,
     这批新名字不可信。
  2. `newly` 段到该成员的**跨场真值质心**(用台账确认块重建, 类 20.241)的距离中位 vs
     `confirmed` 段到同一质心的距离中位 —— 跨场基线 ≈ 0.50, 异人量级 > 0.55。
     ⚠️ 真值质心**只用台账确认段**重建, 不用 anchor(anchor 本身可能是污染的)。

用法:
    python gate_c_check.py --meeting 250
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from relabel_by_margin import SR, MIN_SEC, decode_audio, fetch_audio  # noqa: E402

NEGATIVE = {"环境声", "人群杂音", "视频"}


def _median(xs):
    return round(float(np.median(xs)), 4) if xs else None


def _pct(xs, q):
    return round(float(np.percentile(xs, q)), 4) if xs else None


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--cache", default="/tmp/vp/all3.npz")
    ap.add_argument("--meta", default="/tmp/vp/all_meta3.json")
    ap.add_argument("--margin", type=float, default=None)
    args = ap.parse_args()
    mid = args.meeting

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.member import Member
    from app.services.voiceprint_service import VoiceprintService
    from app.services.voiceprint_voting import (
        get_min_margin, smart_select_k, vote_with_quality_gates,
    )
    from app.services.speaker_adjudication_service import build_resolver

    # ---- 跨场真值质心: 用缓存里**台账确认段**的嵌入重建(其它会议) ----
    truth_centroid = {}
    confirmed_rows = defaultdict(list)     # name -> [(meeting, row_idx)]
    cache_emb = None
    if os.path.exists(args.cache) and os.path.exists(args.meta):
        cache_emb = np.load(args.cache, allow_pickle=True)["emb"]
        cmeta = json.load(open(args.meta, encoding="utf-8"))
        for i, mm in enumerate(cmeta):
            w = mm.get("who")
            if w and w not in NEGATIVE:
                confirmed_rows[w].append(i)
        for w, idxs in confirmed_rows.items():
            if len(idxs) >= 3:
                v = np.mean([cache_emb[i] for i in idxs], axis=0)
                truth_centroid[w] = v / (np.linalg.norm(v) + 1e-9)

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        mrow = (await db.execute(select(Meeting).where(Meeting.id == mid))).scalar_one()
        raw = list(mrow.transcript or [])
        segs = sorted(raw, key=lambda s: float(s.get("start") or 0))

        # ---- 1. 新鲜提取嵌入(与 relabel 同一条路径) ----
        pcm = decode_audio(fetch_audio(mrow.audio_url))
        need = max((float(s.get("end") or 0) for s in segs), default=0.0)
        if len(pcm) / SR < need * 0.95:
            raise RuntimeError("音频长度不足: %.1fs < 转录 %.1fs" % (len(pcm) / SR, need))
        idxs, clips = [], []
        for i, s in enumerate(segs):
            st, en = float(s.get("start") or 0), float(s.get("end") or 0)
            if en - st < MIN_SEC:
                continue
            a = pcm[int(st * SR):int(en * SR)]
            if len(a) < SR * MIN_SEC:
                continue
            idxs.append(i)
            clips.append(a)
        svc = VoiceprintService()
        embs = svc.batch_extract_embeddings(clips)
        seg_embs = [None] * len(segs)
        for i, e in zip(idxs, embs):
            if e is not None and not np.all(e == 0):
                seg_embs[i] = np.asarray(e, dtype=np.float32)

        # ---- 2. enrolled 池 ----
        rows = (await db.execute(
            select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all()
        enrolled = [(r.id, r.name, np.array(r.voice_embedding, dtype=np.float32),
                      r.voice_sample_count or 1) for r in rows]
        anchor = {name: vec for (_i, name, vec, _c) in enrolled}

        # ---- 2b. context 过滤(与 relabel 同参; **不做这一步结果会与 relabel 不同**) ----
        ctx_names = set()
        try:
            from app.services.voiceprint_voting import (
                extract_context_speakers, get_recent_meeting_speakers,
                resolve_context_to_names,
            )
            ctx_raw = extract_context_speakers(mrow)
            ctx_names = await resolve_context_to_names(ctx_raw, db) if ctx_raw else set()
            hist = await get_recent_meeting_speakers(mid, db, lookback_count=10, lookback_days=90)
            if hist:
                ctx_names = ctx_names | hist
        except Exception as e:
            print("[vp] context 解析失败(不启用过滤): %r" % (e,), flush=True)
        if ctx_names:
            filt = [e for e in enrolled if e[1] in ctx_names]
            if filt:
                enrolled = filt
        print("[vp] context 过滤后 enrolled 池 %d 人 (ctx=%d)" % (len(enrolled), len(ctx_names)),
              flush=True)

        # ---- 3. 生产投票 + 裁决(与 relabel 同参) ----
        labels, k, score, _ = smart_select_k(seg_embs=seg_embs, n_expected=3, min_k=2, max_k=8)
        margin = args.margin if args.margin is not None else get_min_margin()
        cluster_names = vote_with_quality_gates(
            seg_embs, list(labels), enrolled, context_names=None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
        )
        resolver = await build_resolver(db, mid)

        proposed = []
        for i, s in enumerate(segs):
            decided = resolver.lookup(s.get("start"), s.get("end"))
            if decided:
                proposed.append(decided)
                continue
            cid = labels[i] if i < len(labels) else -1
            entry = cluster_names.get(cid) if (cid is not None and cid >= 0) else None
            proposed.append((entry[0] if entry and entry[0] else "发言人?"))

        old = [s.get("speaker") or "发言人?" for s in segs]

        # ---- 4. 报告 ----
        report = []
        report.append("=== 会议 %d: %d 段 (有效嵌入 %d), margin=%.2f, 聚类 K=%d ===" % (
            mid, len(segs), sum(1 for e in seg_embs if e is not None), margin, k))
        report.append("簇命名: %s" % {c: (v[0], round(v[1], 3), v[2], v[3])
                                      for c, v in cluster_names.items()})
        report.append("库内 before: %s" % dict(sorted(Counter(old).items())))
        report.append("重算 after : %s" % dict(sorted(Counter(proposed).items())))

        # 逐段 dump(供与 relabel 的 after 计数对账)
        with open("/tmp/gate_c_%d_segs.json" % mid, "w", encoding="utf-8") as f:
            json.dump([{"i": i, "start": segs[i].get("start"), "end": segs[i].get("end"),
                        "old": old[i], "new": proposed[i]} for i in range(len(segs))],
                      f, ensure_ascii=False)

        # 同场人耳确认段(用台账文件判定 who)
        ledger_conf = defaultdict(list)     # name -> [seg_idx]
        for lp in os.environ.get("LEDGER_FILES",
                                  "/tmp/ledger_13.json,/tmp/ledger_30.json").split(","):
            lp = lp.strip()
            if not lp or not os.path.exists(lp):
                continue
            ld = json.load(open(lp, encoding="utf-8"))
            for b in ld.get("blocks", []):
                if b.get("_可用") is False:
                    continue
                if int(b["meeting"]) != mid:
                    continue
                who = {"环境声": None, "人群杂音": None, "视频": None}.get(b.get("who"), b.get("who"))
                if not who:
                    continue
                s0, e0 = float(b["s"]), float(b["e"])
                for i, s in enumerate(segs):
                    st, en = float(s.get("start") or 0), float(s.get("end") or 0)
                    if st >= s0 - 1e-6 and en <= e0 + 1e-6:
                        ledger_conf[who].append(i)

        for name in sorted(set(proposed)):
            if name == "发言人?":
                continue
            newly_idx = [i for i in range(len(segs))
                         if proposed[i] == name and old[i] != name]
            if not newly_idx:
                continue
            conf_idx = ledger_conf.get(name, [])
            line = "--- %s: 新增 %d 段 (占全场 %.1f%%), 同场人耳确认 %d 段 ---" % (
                name, len(newly_idx), len(newly_idx) / max(1, len(segs)) * 100, len(conf_idx))
            a = anchor.get(name)
            if a is not None:
                d_new = [float(np.linalg.norm(seg_embs[i] - a)) for i in newly_idx
                         if seg_embs[i] is not None]
                d_con = [float(np.linalg.norm(seg_embs[i] - a)) for i in conf_idx
                         if seg_embs[i] is not None]
                line += ("\n    到 anchor: 新增中位 %s (n=%d) / 人耳确认中位 %s (n=%d)" % (
                    _median(d_new), len(d_new), _median(d_con), len(d_con)))
                if d_new and d_con:
                    line += "  比值 %s" % round(_median(d_new) / max(1e-9, _median(d_con)), 3)
            tc = truth_centroid.get(name)
            if tc is not None:
                t_new = [float(np.linalg.norm(seg_embs[i] - tc)) for i in newly_idx
                         if seg_embs[i] is not None]
                t_con = [float(np.linalg.norm(seg_embs[i] - tc)) for i in conf_idx
                         if seg_embs[i] is not None]
                t_all = [float(np.linalg.norm(cache_emb[i] - tc))
                         for i in confirmed_rows.get(name, [])]
                # ⚠️ **对照组**: 同一场里**仍然被判「发言人?」**的段到同一质心的距离 ——
                #   若 newly 与「仍未识别」距离相近 ⇒ 这次命名几乎没有信息量(任意切分);
                #   若 newly 明显更近 ⇒ 命名有意义。
                unk_idx = [i for i in range(len(segs)) if proposed[i] == "发言人?"
                           and seg_embs[i] is not None]
                t_unk = [float(np.linalg.norm(seg_embs[i] - tc)) for i in unk_idx]
                line += ("\n    到跨场真值质心: 新增中位 %s (p90 %s) / 同场确认中位 %s / "
                         "全库确认中位 %s (基线, n=%d)" % (
                             _median(t_new), _pct(t_new, 90), _median(t_con),
                             _median(t_all), len(t_all)))
                line += ("\n      对照组『仍未识别 %d 段』到同质心中位 %s" % (
                    len(t_unk), _median(t_unk)))
                if t_new and t_unk and _median(t_unk):
                    line += "  ⇒ newly/未知 比值 %s" % round(_median(t_new) / _median(t_unk), 3)
            # 时长对照(长块 vs 短段 —— 类 20.245: 短段 embedding 系统性不同)
            dur_new = [float(segs[i].get("end") or 0) - float(segs[i].get("start") or 0)
                       for i in newly_idx]
            dur_con = [float(segs[i].get("end") or 0) - float(segs[i].get("start") or 0)
                       for i in conf_idx]
            line += ("\n    时长中位: 新增 %ss / 人耳确认 %ss" % (
                _median(dur_new), _median(dur_con)))
            report.append(line)

        await engine.dispose()

    txt = "\n".join(report)
    with open("/tmp/gate_c_%d.txt" % mid, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    asyncio.run(main())
