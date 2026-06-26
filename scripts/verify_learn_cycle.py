"""完整 verify learn→re-recognize 闭环:

  1. 提取会议 #135 段 embeddings
  2. 用用户已 override 的 speaker 分配作为 "ground truth" 构造 verified mapping
  3. 调 learn_from_verified_segments 把每 cluster 的段 embedding 累积到对应 member
  4. 重新跑 auto-recognize, 看 韩/张 距离是否缩短, 识别率是否提升

期望:
  - learn 前: 韩/张 距离 0.7-1.0, auto-recognize 失败
  - learn 后: 韩/张 距离下降到 0.5-0.6, auto-recognize 成功率提升
"""
import asyncio
import sys
import json
import logging
from pathlib import Path
import numpy as np
from collections import Counter

sys.path.insert(0, "/app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("learn_cycle")


async def run_recognition(seg_embs, labels, n_expected, expected_names, with_context=True):
    """跑一次 auto-recognize, 返回 cluster → name 映射 + 距离"""
    from app.config import settings
    from app.models.member import Member
    from sqlalchemy import select, create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm

    _sync_engine = _ce(settings.DATABASE_URL)
    SyncS = _sm(bind=_sync_engine)
    with SyncS() as sdb:
        members = sdb.execute(
            select(Member).where(Member.voice_embedding.isnot(None))
        ).scalars().all()
    _sync_engine.dispose()
    enrolled = [
        (m.id, m.name, np.array(m.voice_embedding, dtype=np.float32), m.voice_sample_count or 1)
        for m in members if m.voice_embedding is not None
    ]
    logger.info(f"  enrolled 库: {len(enrolled)} 人")

    from app.services.voiceprint_voting import smart_select_k, vote_with_quality_gates, assign_with_strict_threshold
    labels2, k, score, _ = smart_select_k(seg_embs, n_expected=n_expected)
    label_dist = Counter(l for l in labels2 if l >= 0)
    logger.info(f"  smart_select_k: K={k}, 分布: {dict(label_dist)}")

    ctx = set(expected_names) if with_context else None
    cluster_names = vote_with_quality_gates(
        seg_embs, labels2, enrolled, context_names=ctx,
        center_dist_threshold=0.75, min_votes=3, votes_ratio_threshold=0.30,
    )
    new_speaker, _ = assign_with_strict_threshold(
        [{} for _ in seg_embs], labels2, cluster_names,  # 假 transcript, 只用 cluster_names
        conf_threshold=0.50, votes_ratio_threshold=0.5,
    )
    sp_counter = Counter(new_speaker)
    logger.info(f"  最终: {dict(sp_counter)}")
    return cluster_names, new_speaker, sp_counter


async def main():
    from app.config import settings
    from app.models.meeting import Meeting
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    meeting_id = 135
    expected_names = ["王天志", "赵航佳", "韩重阳", "张宏魁"]

    # 1. load meeting + embeddings
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        transcript = list(m.transcript or [])

    # 2. extract embeddings
    from scripts.reprocess_meeting import load_audio, prepare_chunks, extract_embeddings_parallel
    from app.services.voiceprint_service import voiceprint_service
    voiceprint_service._load_pipeline()
    pcm = load_audio("/tmp/meeting_135_16k.wav")
    chunks, valid_idx = prepare_chunks(pcm, transcript)
    embs = extract_embeddings_parallel(voiceprint_service, [chunks[i] for i in valid_idx])
    seg_embs = [None] * len(transcript)
    for j, i in enumerate(valid_idx):
        seg_embs[i] = embs[j]

    # 3. KMeans K=4 (基于 ground truth, 实际 #135 真实就是 4 人)
    from sklearn.cluster import KMeans
    valid = np.array([e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)])
    km = KMeans(n_clusters=4, random_state=42, n_init=10).fit(valid)
    labels = [-1] * len(seg_embs)
    j = 0
    for i, e in enumerate(seg_embs):
        if e is not None and not np.all(np.array(e) == 0):
            labels[i] = int(km.labels_[j])
            j += 1

    # 4. 构造 verified mapping (从 transcript.speaker 拿, 已经被 override)
    from collections import defaultdict
    cluster_to_member = {}  # cid → member_id
    cluster_to_name = {}  # cid → name
    for cid in sorted(set(labels)):
        if cid < 0:
            continue
        # 找该 cluster 中 sample_speaker (verify_eight_fields 已知正确)
        # 用 mode (出现最多的 name) 作为 cluster 名字
        names_in_cluster = []
        for i, lab in enumerate(labels):
            if lab == cid and i < len(transcript):
                sp = transcript[i].get("speaker", "")
                if sp and not sp.startswith("发言人"):
                    names_in_cluster.append(sp)
        if names_in_cluster:
            top_name = Counter(names_in_cluster).most_common(1)[0][0]
            cluster_to_name[cid] = top_name

    # 查 member_id
    from app.models.member import Member
    async with sf() as db:
        for name in set(cluster_to_name.values()):
            r = await db.execute(select(Member).where(Member.name == name))
            m_obj = r.scalar_one_or_none()
            if m_obj:
                for cid, n in cluster_to_name.items():
                    if n == name:
                        cluster_to_member[cid] = m_obj.id

    logger.info(f"=== cluster → name (来自 override) ===")
    for cid, n in sorted(cluster_to_name.items()):
        mid = cluster_to_member.get(cid)
        n_segs = sum(1 for lab in labels if lab == cid)
        logger.info(f"  C{cid}: {n} (id={mid}, {n_segs} 段)")

    # 5. baseline: auto-recognize without any learning
    print("\n========== 步骤 A: LEARN 前 (baseline) ==========")
    cluster_names_a, new_speaker_a, sp_a = await run_recognition(
        seg_embs, labels, n_expected=4, expected_names=expected_names, with_context=True
    )
    correct_a = sum(1 for n in new_speaker_a if n in expected_names)
    print(f"  段数: {sum(sp_a.values())}, 其中 correct={correct_a}/{len(new_speaker_a)} = {100*correct_a/max(len(new_speaker_a),1):.0f}%")

    # 6. learn: 把每 cluster 的段 embedding 累积到对应 member
    print("\n========== 步骤 B: 调 learn_from_verified_segments ==========")
    from app.services.voiceprint_voting import learn_from_verified_segments

    # 构造 member_id → [seg_emb, ...]
    member_to_segs = defaultdict(list)
    for cid in sorted(set(labels)):
        if cid < 0 or cid not in cluster_to_member:
            continue
        for i, lab in enumerate(labels):
            if lab == cid and seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0):
                member_to_segs[cluster_to_member[cid]].append(seg_embs[i])

    async with sf() as db:
        learned = await learn_from_verified_segments(dict(member_to_segs), db, max_segments_per_member=15)
    logger.info(f"  learn 结果: {learned}")

    # 7. re-recognize: 期望 sample_count 提升 → distance 缩小 → 识别率提升
    print("\n========== 步骤 C: LEARN 后 (re-recognize) ==========")
    cluster_names_c, new_speaker_c, sp_c = await run_recognition(
        seg_embs, labels, n_expected=4, expected_names=expected_names, with_context=True
    )
    correct_c = sum(1 for n in new_speaker_c if n in expected_names)
    print(f"  段数: {sum(sp_c.values())}, 其中 correct={correct_c}/{len(new_speaker_c)} = {100*correct_c/max(len(new_speaker_c),1):.0f}%")

    # 8. 对比 cluster 距离
    print("\n========== 步骤 D: 距离对比 (LEARN 前 → LEARN 后) ==========")
    from app.config import settings
    from app.models.member import Member
    from sqlalchemy import select, create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm

    # 算聚类中心
    cluster_centers = {}
    for cid in sorted(set(labels)):
        if cid < 0:
            continue
        idxs = [i for i, lab in enumerate(labels) if lab == cid and seg_embs[i] is not None]
        c = np.mean([seg_embs[i] for i in idxs], axis=0)
        c = c / (np.linalg.norm(c) + 1e-8)
        cluster_centers[cid] = c

    # 重新加载 enrolled (用 learn 后的)
    _sync_engine = _ce(settings.DATABASE_URL)
    SyncS = _sm(bind=_sync_engine)
    with SyncS() as sdb:
        members_after = sdb.execute(
            select(Member).where(Member.voice_embedding.isnot(None))
        ).scalars().all()
    _sync_engine.dispose()
    for real_name in expected_names:
        m = next((x for x in members_after if x.name == real_name), None)
        if not m:
            continue
        print(f"  {real_name} (samples={m.voice_sample_count}):")
        for cid in sorted(cluster_centers):
            d = 1.0 - float(np.dot(cluster_centers[cid], np.array(m.voice_embedding, dtype=np.float32) / (np.linalg.norm(m.voice_embedding)+1e-8)))
            mark = "✅" if d < 0.65 else "❌"
            print(f"    C{cid}: dist={d:.3f} {mark}")

    await engine.dispose()


asyncio.run(main())
