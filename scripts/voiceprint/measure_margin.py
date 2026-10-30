"""端到端复测 margin: 直接调**生产函数** `vote_with_quality_gates`,
用「理想聚类 = 按台账真值分组」评估 margin 0.00 / 0.05 / 0.10 的效果。

口径(与 CLAUDE.md 类 20.243 的落地测量一致):
  样本 = 全库台账覆盖段(in_ledger=1)
  理想聚类 = 按 (会议, 台账真值说话人) 分组 ⇒ 41 组 / ~2200 段
  产出三栏:
    聚类级命名正确  = 该组被冠以正确的名字
    命名错误        = 被冠以**别的**名字
    无名            = 弃权(发言人?)
"""
import asyncio
import collections
import json
import sys

import numpy as np

sys.path.insert(0, "/app")

MARGINS = [0.00, 0.05, 0.10, 0.15]


async def main():
    d = np.load("/tmp/vp/all3.npz")
    E = d["emb"].astype(np.float32)
    M = json.load(open("/tmp/vp/all3_meta.json", encoding="utf-8"))

    idx = [i for i, m in enumerate(M) if m.get("in_ledger") == 1 and m.get("who")]
    # 理想聚类: 按 (meeting, who) 分组
    groups = collections.OrderedDict()
    for i in idx:
        m = M[i]
        groups.setdefault((m["meeting"], m["who"]), []).append(i)
    print("[vp] 理想聚类: %d 组 / %d 段" % (len(groups), len(idx)), flush=True)

    # 段顺序: 按组拼起来(每个组的段连续), labels 相应给出组号
    seg_embs, labels, truth = [], [], []
    for gi, (k, ids) in enumerate(groups.items()):
        for i in ids:
            seg_embs.append(E[i])
            labels.append(gi)
            truth.append(k[1])
    print("[vp] 参与者:", sorted({k[1] for k in groups}), flush=True)

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
    print("[vp] enrolled 池 %d 人" % len(enrolled), flush=True)

    for margin in MARGINS:
        res = vote_with_quality_gates(
            seg_embs, labels, enrolled, context_names=None,
            center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
            avg_conf_threshold=0.30, match_threshold=0.7,
            sample_count_penalty_factor=0.5, min_margin=margin)
        # res: {cluster_idx: (name, center_dist, votes, total)}
        correct = wrong = unnamed = 0
        wrong_detail = collections.Counter()
        for gi, (k, ids) in enumerate(groups.items()):
            r = res.get(gi)
            if r is None or not r[0]:
                unnamed += 1
                continue
            got = r[0]
            if got == k[1]:
                correct += 1
            else:
                wrong += 1
                wrong_detail["%s->%s" % (k[1], got)] += 1
        tot = len(groups)
        print("[vp] margin=%.2f  正确 %2d  错名 %2d  无名 %2d   (共 %d 组)  %s" % (
            margin, correct, wrong, unnamed, tot,
            dict(wrong_detail.most_common(4))), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
