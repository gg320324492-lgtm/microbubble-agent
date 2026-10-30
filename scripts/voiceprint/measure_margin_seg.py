"""margin 的**段级**测量(补簇级之外的另一半)。

关键机制: margin 弃权是**段级不投票**, 但最终标签按**簇**给 ⇒
margin 过大 ⇒ 某些簇的 votes_ratio 跌破 0.30 / min_votes ⇒
**整簇几百段一起变成「发言人?」** ⇒ 这才是"30-63% 未识别"的来源。

所以要同时看两栏:
  簇级: 正确 / 错名 / 无名(几组)
  段级: 有名字段数 / 总段数, 以及"拿到名字但名字错"的段数
"""
import asyncio
import collections
import json
import sys

import numpy as np

sys.path.insert(0, "/app")
MARGINS = [0.00, 0.03, 0.05, 0.08, 0.10, 0.15]


async def main():
    d = np.load("/tmp/vp/all3.npz")
    E = d["emb"].astype(np.float32)
    M = json.load(open("/tmp/vp/all3_meta.json", encoding="utf-8"))

    idx = [i for i, m in enumerate(M) if m.get("in_ledger") == 1 and m.get("who")]
    groups = collections.OrderedDict()
    for i in idx:
        m = M[i]
        groups.setdefault((m["meeting"], m["who"]), []).append(i)

    seg_embs, labels, truth, gid = [], [], [], []
    for gi, (k, ids) in enumerate(groups.items()):
        for i in ids:
            seg_embs.append(E[i])
            labels.append(gi)
            truth.append(k[1])
            gid.append(gi)
    print("[vp] 理想聚类 %d 组 / %d 段\n" % (len(groups), len(seg_embs)), flush=True)

    from sqlalchemy import select
    from app.core.celery_db import create_celery_engine_and_session
    from app.models.member import Member
    from app.services.voiceprint_voting import vote_with_quality_gates

    engine, Session = create_celery_engine_and_session()
    enrolled = []
    async with Session() as db:
        for m in (await db.execute(
                select(Member).where(Member.voice_embedding.isnot(None)))).scalars().all():
            enrolled.append((m.id, m.name, np.asarray(m.voice_embedding, dtype=np.float32),
                             m.voice_sample_count or 1))

    print("%-8s | %-26s | %s" % ("margin", "簇级(41+组)", "段级(命名率 / 错名段)"))
    print("-" * 78)
    for margin in MARGINS:
        res = vote_with_quality_gates(
            seg_embs, labels, enrolled, context_names=None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
            avg_conf_threshold=0.30, match_threshold=0.7,
            sample_count_penalty_factor=0.5, min_margin=margin)
        c_ok = c_bad = c_none = 0
        for gi, (k, ids) in enumerate(groups.items()):
            r = res.get(gi)
            if r is None or not r[0]:
                c_none += 1
            elif r[0] == k[1]:
                c_ok += 1
            else:
                c_bad += 1
        named = wrong_seg = 0
        for j, gi in enumerate(gid):
            r = res.get(gi)
            if r and r[0]:
                named += 1
                if r[0] != truth[j]:
                    wrong_seg += 1
        n = len(seg_embs)
        print("margin=%.2f | 正确%3d 错名%3d 无名%3d(共%3d组) | 命名 %5.1f%% (%d/%d)  其中错名段 %d (%.1f%%)" % (
            margin, c_ok, c_bad, c_none, len(groups), named / n * 100, named, n,
            wrong_seg, wrong_seg / n * 100), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
