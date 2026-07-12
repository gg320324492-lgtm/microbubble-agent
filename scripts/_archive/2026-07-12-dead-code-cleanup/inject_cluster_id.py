"""把 reprocess_meeting.py result.json 里的 cluster_id 注入到 meeting transcript

通用化 inject — 把 cluster_id 和 cluster_to_name 写入 transcript[i].cluster_id 和 .speaker

用法:
    python scripts/inject_cluster_id.py --meeting 70 --result-json /tmp/reprocess_70_result.json

会自动:
1. 读 result.json (含 cluster_names + speaker_label_to_name + new_speaker)
2. 跑一次 extract+cluster 重算 cluster_id per segment (用相同的 audio + 模型)
3. 写入 meeting.transcript[i].cluster_id 和 speaker

简化版: 直接用 speaker_label_to_name 把 cluster_id 写到每段 (假设 speaker_label 命名规则)
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import wave
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.meeting import Meeting
from app.services.voiceprint_service import voiceprint_service
from sklearn.cluster import KMeans


def cos(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, required=True)
    parser.add_argument("--audio", type=str, required=True, help="音频文件路径 (16kHz mono wav 推荐)")
    parser.add_argument("--result-json", type=str, required=True, help="reprocess_meeting 输出的 result.json")
    parser.add_argument("--cluster-to-member", type=str, required=True,
                        help="cluster → member 映射. 支持 cluster_0+cluster_1:name 合并多 cluster")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # 1. 读 result.json
    with open(args.result_json, "r", encoding="utf-8") as f:
        result = json.load(f)
    cluster_names = result["cluster_names"]
    n_segments = result["n_segments"]
    n_clusters = result["n_clusters"]

    # 解析 --cluster-to-member, 支持 cluster_0+cluster_1:member_name (合并多 cluster)
    # 每个 raw group 是 (kmeans_cid_list, name)
    raw_groups = []  # [( [kmeans_cid1, kmeans_cid2, ...], name )]
    for item in args.cluster_to_member.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            print(f"WARN: 跳过无效项 '{item}'")
            continue
        cids_str, name = item.split(":", 1)
        name = name.strip()
        cids = []
        for c in cids_str.split("+"):
            c = c.strip()
            if c.startswith("cluster_"):
                c = c[8:]
            try:
                cids.append(int(c))
            except ValueError:
                pass
        if cids:
            raw_groups.append((cids, name))

    # 投票编号 (从 0 开始连续)
    cluster_to_name = {}
    kmeans_to_vote = {}  # kmeans_cid → vote_cid
    for vote_cid, (cids, name) in enumerate(raw_groups):
        cluster_to_name[vote_cid] = name
        for kc in cids:
            kmeans_to_vote[kc] = vote_cid
    print(f"meeting #{args.meeting}: {n_segments} 段, {n_clusters} KMeans cluster → {len(raw_groups)} vote group")
    print(f"  cluster_to_name (vote): {cluster_to_name}")
    print(f"  KMeans→vote 映射: {kmeans_to_vote}")

    # 2. 加载 wav
    with wave.open(args.audio, "rb") as wf:
        sr = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    # 3. 读 transcript
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)

    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == args.meeting))
        m = r.scalar_one()
        transcript = list(m.transcript or [])
        print(f"  DB transcript 段数: {len(transcript)}")

    # 4. 按 transcript segment 取 chunk + 提 embedding + KMeans K=n_clusters 聚类
    seg_audios = []
    valid_idx = []
    for i, seg in enumerate(transcript):
        if not isinstance(seg, dict):
            continue
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        s = int(start * sr)
        e = int(end * sr)
        chunk = pcm[s:e]
        if len(chunk) < sr * 0.3:  # 短段 (<0.3s) 跳过
            continue
        seg_audios.append(chunk)
        valid_idx.append(i)

    print(f"  有效 chunks: {len(seg_audios)} / {len(transcript)}")

    seg_embs = voiceprint_service.batch_extract_embeddings(seg_audios)
    valid_embs = np.array([e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)], dtype=np.float32)

    if len(valid_embs) < n_clusters:
        print(f"  ❌ 有效 embeddings ({len(valid_embs)}) < K ({n_clusters}), 不能聚类")
        await engine.dispose()
        return

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10).fit(valid_embs)

    # 5. 映射回 segment idx — 用 kmeans_to_vote 映射 (支持 cluster 合并)
    cluster_id_per_seg = {seg_idx: -1 for seg_idx in range(len(transcript))}
    j = 0
    for i, emb in enumerate(seg_embs):
        if emb is not None and not np.all(np.array(emb) == 0):
            kmeans_cid = int(km.labels_[j])
            # 用 kmeans_to_vote 映射 (支持 cluster_0+cluster_1 合并)
            vote_cid = kmeans_to_vote.get(kmeans_cid, kmeans_cid)
            cluster_id_per_seg[valid_idx[i]] = vote_cid
            j += 1

    # 6. cluster_centers 用于 sanity check
    cluster_centers = {}
    for cid in range(n_clusters):
        idxs = [k for k, v in cluster_id_per_seg.items() if v == cid]
        embs = [seg_embs[valid_idx.index(k)] for k in idxs if k in valid_idx]
        embs = [e for e in embs if e is not None and not np.all(np.array(e) == 0)]
        if not embs:
            continue
        arr = np.array(embs, dtype=np.float32)
        center = np.mean(arr, axis=0)
        center /= np.linalg.norm(center)
        cluster_centers[cid] = center

    print(f"\n  cluster 段数:")
    for cid in range(n_clusters):
        n = sum(1 for v in cluster_id_per_seg.values() if v == cid)
        print(f"    cluster_{cid}: {n} 段 → {cluster_to_name.get(cid, '?')}")

    # 7. 写入 transcript
    new_transcript = []
    for i, seg in enumerate(transcript):
        new_seg = dict(seg)
        new_seg["cluster_id"] = cluster_id_per_seg.get(i, -1)
        cid = new_seg["cluster_id"]
        if cid >= 0 and cid in cluster_to_name:
            new_seg["speaker"] = cluster_to_name[cid]
        new_transcript.append(new_seg)

    # 8. speaker_mapping
    new_mapping = {f"cluster_{cid}": name for cid, name in cluster_to_name.items()}

    print(f"\n  写入 DB:")
    print(f"    transcript.{len(new_transcript)} 段 + cluster_id")
    print(f"    speaker_mapping: {new_mapping}")

    if args.dry_run:
        print(f"\n[DRY-RUN] 不写 DB")
        await engine.dispose()
        return

    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == args.meeting))
        m = r.scalar_one()
        m.transcript = new_transcript
        m.speaker_mapping = new_mapping
        # 写 cluster_id_history entry (P2-2)
        from datetime import datetime
        history_entry = {
            "ts": datetime.utcnow().isoformat(),
            "source": "inject_cluster_id",
            "injector": "scripts/inject_cluster_id.py",
            "n_segments": len(new_transcript),
            "n_with_cluster_id": sum(1 for v in cluster_id_per_seg.values() if v >= 0),
            "kmeans_k": n_clusters,
            "cluster_to_name": {str(k): v for k, v in cluster_to_name.items()},
            "notes": "通用化 inject cluster_id (P1-2 扩展, 不只支持 083)",
        }
        if m.cluster_id_history is None:
            m.cluster_id_history = []
        m.cluster_id_history.append(history_entry)
        flag_modified(m, "cluster_id_history")
        from datetime import datetime as _dt
        m.updated_at = _dt.utcnow()
        await db.commit()
        print(f"\n  ✅ DB updated")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())