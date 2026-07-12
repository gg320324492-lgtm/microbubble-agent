"""dump 4 个聚类中心 vs 15 个 enrolled 的距离矩阵, 看真实情况"""
import asyncio
import sys
import logging
import numpy as np
from collections import Counter

sys.path.insert(0, "/app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dump_distance")


async def main():
    from app.config import settings
    from app.models.meeting import Meeting
    from app.models.member import Member
    from sqlalchemy import select, create_engine as _ce
    from sqlalchemy.orm import sessionmaker as _sm

    meeting_id = 135

    # 1. load meeting
    from app.core.database import async_session
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        transcript = list(m.transcript or [])
    await engine.dispose()

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

    # 3. KMeans K=4
    from sklearn.cluster import KMeans
    valid = np.array([e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)])
    km = KMeans(n_clusters=4, random_state=42, n_init=10).fit(valid)
    labels = [-1] * len(seg_embs)
    j = 0
    for i, e in enumerate(seg_embs):
        if e is not None and not np.all(np.array(e) == 0):
            labels[i] = int(km.labels_[j])
            j += 1

    # 4. 算 4 个聚类中心
    cluster_centers = {}
    for cid in sorted(set(labels)):
        if cid < 0:
            continue
        idxs = [i for i, l in enumerate(labels) if l == cid]
        emb_list = [seg_embs[i] for i in idxs if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0)]
        center = np.mean(emb_list, axis=0)
        norm = np.linalg.norm(center)
        if norm > 0:
            center = center / norm
        cluster_centers[cid] = center
        logger.info(f"聚类 {cid}: {len(idxs)} 段")

    # 5. 加载 15 人 enrolled
    _sync_engine = _ce(settings.DATABASE_URL)
    SyncS = _sm(bind=_sync_engine)
    with SyncS() as sdb:
        members = sdb.execute(
            select(Member).where(Member.voice_embedding.isnot(None))
        ).scalars().all()
    _sync_engine.dispose()
    logger.info(f"已 enrolled: {len(members)} 人")

    # 6. 算距离矩阵
    def cos_dist(a, b):
        a_n = a / (np.linalg.norm(a) + 1e-8)
        b_n = b / (np.linalg.norm(b) + 1e-8)
        return float(1.0 - np.dot(a_n, b_n))

    # Header
    print()
    print(f"{'聚类':<6}", end="")
    for m in members:
        print(f"{m.name[:6]:<7}", end="")
    print()
    print("-" * 110)

    for cid in sorted(cluster_centers.keys()):
        c = cluster_centers[cid]
        print(f"C{cid}({sum(1 for l in labels if l==cid):<3})", end="")
        for m in members:
            d = cos_dist(c, np.array(m.voice_embedding, dtype=np.float32))
            marker = " *" if d < 0.7 else ""
            print(f"{d:.3f}{marker:<2}", end=" ")
        print()

    # 7. Highlight real 4 speakers
    real_names = {"王天志", "赵航佳", "韩重阳", "张宏魁"}
    print()
    print("真实 4 人 (期望被识别):")
    for m in members:
        if m.name in real_names:
            print(f"  {m.name} (samples={m.voice_sample_count})")
            for cid in sorted(cluster_centers.keys()):
                d = cos_dist(cluster_centers[cid], np.array(m.voice_embedding, dtype=np.float32))
                print(f"    → C{cid}: {d:.3f}")


asyncio.run(main())
