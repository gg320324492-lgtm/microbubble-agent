#!/usr/bin/env python
"""最近 anchor 交叉验证: 某个簇/某个成员的段, **逐段最近的 anchor 到底是谁**。

为什么需要这个工具
------------------
`relabel_by_margin.py` 的安全闸 B「台账里没出现过的成员不得占 >10% 的段」在本项目
**会误报** —— 因为人工台账覆盖率只有 4%–23%(229 = 8.5%, 243 = 4.1%),
此时「台账里没出现」**≠**「没发言」(类 20.249 ②)。

实测: 会议 229 的杜同贺拿到 31 段(10.9%)触发闸 B, 但**逐段最近 anchor 有 24/31
指向杜同贺** ⇒ 他确实发言了 ⇒ 闸 B 是假阳性。

⇒ 本工具给出闸 B2 所需的证据: **逐段最近 anchor 分布**。

⚠️ **闸 B2 单独用会给出假阳性** —— 会议 243 里宋洋也是「最近 anchor 多数」,
但那是因为**真值人物王天志被 `context` 过滤踢出了候选池**(闸 B1 拦得住)。
⇒ **必须先过闸 B1(候选池覆盖台账真值人物)** 再看本工具的输出。

用法 (容器内):
    python scripts/voiceprint/nearest_anchor_check.py --meeting 229
"""
import argparse
import asyncio
import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, "/app")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from relabel_by_margin import SR, MIN_SEC, decode_audio, fetch_audio  # noqa: E402

NEGATIVE = {"环境声", "人群杂音", "视频"}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meeting", type=int, required=True)
    ap.add_argument("--ledger-files", default=os.environ.get(
        "LEDGER_FILES", "/tmp/ledger_13.json,/tmp/ledger_30.json"))
    args = ap.parse_args()
    mid = args.meeting

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.meeting import Meeting
    from app.models.member import Member
    from app.services.voiceprint_service import VoiceprintService
    from app.services.voiceprint_voting import (
        get_min_margin, smart_select_k, vote_with_quality_gates,
        extract_context_speakers, get_recent_meeting_speakers, resolve_context_to_names,
    )

    engine, Session = create_celery_engine_and_session()
    async with Session() as db:
        mrow = (await db.execute(select(Meeting).where(Meeting.id == mid))).scalar_one()
        raw = list(mrow.transcript or [])
        segs = sorted(raw, key=lambda s: float(s.get("start") or 0))

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
        embs = VoiceprintService().batch_extract_embeddings(clips)
        seg_embs = [None] * len(segs)
        for i, e in zip(idxs, embs):
            if e is not None and not np.all(e == 0):
                seg_embs[i] = np.asarray(e, dtype=np.float32)

        rows = (await db.execute(
            select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all()
        enrolled = [(r.id, r.name, np.array(r.voice_embedding, dtype=np.float32),
                      r.voice_sample_count or 1) for r in rows]
        all_names = {e[1] for e in enrolled}
        ctx_names = set()
        ctx_raw = extract_context_speakers(mrow)
        ctx_names = await resolve_context_to_names(ctx_raw, db) if ctx_raw else set()
        hist = await get_recent_meeting_speakers(mid, db, lookback_count=10, lookback_days=90)
        if hist:
            ctx_names = ctx_names | set(hist)
        if ctx_names:
            filt = [e for e in enrolled if e[1] in ctx_names]
            if filt:
                enrolled = filt

        labels, k, _score, _ = smart_select_k(seg_embs=seg_embs, n_expected=3, min_k=2, max_k=8)
        margin = get_min_margin()
        cluster_names = vote_with_quality_gates(
            seg_embs, list(labels), enrolled, context_names=None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
        )

        names = [n for (_i, n, _v, _c) in enrolled]
        vecs = np.stack([v for (_i, _n, v, _c) in enrolled])
        vecs = vecs / (np.linalg.norm(vecs, axis=1, keepdims=True) + 1e-9)

        rep = []
        rep.append("=== 会议 %d: %d 段 (有效嵌入 %d), margin=%.2f, K=%d, 候选池 %d 人 ===" % (
            mid, len(segs), sum(1 for e in seg_embs if e is not None), margin, k, len(enrolled)))
        rep.append("候选池: %s" % ", ".join(sorted(names)))
        dropped = sorted(all_names - set(names))
        if dropped:
            rep.append("⚠ 被 context 过滤踢出池的人(不可识别): %s" % ", ".join(dropped))
        rep.append("簇命名: %s" % {c: (v[0], round(v[1], 3), v[2], v[3])
                                  for c, v in cluster_names.items()})

        # ---- 台账真值(按会议过滤) ----
        lb = []
        for lp in args.ledger_files.split(","):
            lp = lp.strip()
            if not lp or not os.path.exists(lp):
                continue
            ld = json.load(open(lp, encoding="utf-8"))
            for b in ld.get("blocks", []):
                if b.get("_可用") is False or int(b["meeting"]) != mid:
                    continue
                lb.append((float(b["s"]), float(b["e"]), b["who"]))

        by_cluster = {}
        for i, c in enumerate(labels):
            if c is None or c < 0 or seg_embs[i] is None:
                continue
            by_cluster.setdefault(int(c), []).append(i)

        for c in sorted(by_cluster):
            idxs_c = by_cluster[c]
            entry = cluster_names.get(c)
            cname = entry[0] if entry else None
            nearest = Counter()
            d_named = []
            for i in idxs_c:
                e = seg_embs[i]
                d = np.linalg.norm(vecs - e, axis=1)
                j = int(np.argmin(d))
                nearest[names[j]] += 1
                if cname and cname in names:
                    d_named.append(float(d[names.index(cname)]))
            rep.append("--- 簇 %d: %d 段, 投票名=%s (簇心距 %s)" % (
                c, len(idxs_c), cname, round(entry[1], 3) if entry else None))
            rep.append("    逐段最近 anchor 分布: %s" % dict(nearest.most_common(6)))
            if d_named:
                rep.append("    到本簇名 anchor 距离: 中位 %.4f" % float(np.median(d_named)))
            tc = Counter()
            for i in idxs_c:
                st = float(segs[i].get("start") or 0)
                en = float(segs[i].get("end") or 0)
                midp = (st + en) / 2.0
                for s0, e0, who in lb:
                    if s0 <= midp <= e0:
                        tc["(负样本)" if who in NEGATIVE else who] += 1
                        break
            if tc:
                rep.append("    簇内台账真值分布: %s" % dict(tc.most_common(6)))

        await engine.dispose()

    txt = "\n".join(rep)
    with open("/tmp/nearest_anchor_%d.txt" % mid, "w", encoding="utf-8") as f:
        f.write(txt + "\n")
    print(txt)


if __name__ == "__main__":
    asyncio.run(main())
