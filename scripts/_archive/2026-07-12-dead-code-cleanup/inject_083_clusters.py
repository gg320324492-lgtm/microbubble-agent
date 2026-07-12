#!/usr/bin/env python3
"""手动注入 cluster_id 到 meeting 083 transcript

2026-06-27 P1-2 改进: 用 Hungarian algorithm 替代段数启发式
  - 旧: 按段数从大到小分配 cluster → name (083 主讲是王天志但段数次多, 启发式错)
  - 新: 算 cluster_centers vs enrolled cos 距离矩阵, Hungarian 找最小总距离配对
  - 段数推断保留作 sanity check, 不一致时打印警告

流程:
1. 加载 wav + transcript + 用 KMeans K=3 提取 cluster labels
2. 计算 cluster_centers vs enrolled 距离矩阵
3. Hungarian algorithm 找最优 cluster → name 配对 (最小总距离)
4. 段数推断作 sanity check (打印比较)
5. 注入 cluster_id 到 transcript 段
6. 更新 speaker_mapping: cluster_N → name
7. 备份后 commit
"""
import asyncio
import sys
import json
import wave
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.voiceprint_service import voiceprint_service
from sklearn.cluster import KMeans


def cos(a, b):
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


async def main():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, expire_on_commit=False)

    wav_path = "/tmp/meeting_083_16k.wav"
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0

    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == 83))
        m = r.scalar_one()
        transcript = list(m.transcript or [])
        print(f"meeting {m.id} '{m.title}' segments={len(transcript)}")

    # 1. 提取 chunk + embedding (按 transcript segment start/end)
    seg_audios = []
    valid_seg_idx = []
    for i, seg in enumerate(transcript):
        if not isinstance(seg, dict):
            continue
        start = seg.get("start", 0)
        end = seg.get("end", 0)
        s = int(start * sr)
        e = int(end * sr)
        chunk = pcm[s:e]
        if len(chunk) < sr * 0.5:
            continue
        seg_audios.append(chunk)
        valid_seg_idx.append(i)
    print(f"valid chunks: {len(seg_audios)} / {len(transcript)}")

    seg_embs = voiceprint_service.batch_extract_embeddings(seg_audios)
    valid_emb_objs = [
        (i, seg_embs[k]) for k, i in enumerate(valid_seg_idx)
        if seg_embs[k] is not None and not np.all(np.array(seg_embs[k]) == 0)
    ]
    print(f"valid embeddings: {len(valid_emb_objs)}")

    # 2. KMeans K=3
    valid_idx = [v[0] for v in valid_emb_objs]
    valid_embs = np.array([v[1] for v in valid_emb_objs], dtype=np.float32)
    km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(valid_embs)

    # 3. cluster sizes
    cnt = Counter(km.labels_)
    print(f"cluster sizes (KMeans K=3): {dict(cnt)}")

    # 4. 算 cluster_centers vs enrolled 距离矩阵 (Hungarian 配对)
    # 2026-06-27 P1-2: 用 Hungarian algorithm 找最小总距离配对, 替代段数启发式
    sorted_clusters = sorted(cnt.keys(), key=lambda c: cnt[c], reverse=True)

    # 读 enrolled (杨慈/王天志/杜同贺)
    async with sf() as db:
        r = await db.execute(
            select(Member).where(Member.name.in_(["杨慈", "王天志", "杜同贺"]))
        )
        members_list = list(r.scalars())
        members = {mm.name: mm for mm in members_list}
        enrolled_names = ["杨慈", "王天志", "杜同贺"]

        # 算每 cluster 中心 (复用步骤 7 的逻辑提前到这里)
        cluster_segs = {cid: [] for cid in sorted_clusters}
        for k, seg_idx in enumerate(valid_idx):
            cid = int(km.labels_[k])
            if cid in cluster_segs:
                cluster_segs[cid].append(valid_embs[k])

        cluster_centers = {}
        for cid, embs in cluster_segs.items():
            if not embs:
                continue
            arr = np.array(embs, dtype=np.float32)
            center = np.mean(arr, axis=0)
            n = np.linalg.norm(center)
            if n > 0:
                center = center / n
            cluster_centers[cid] = center

        # 距离矩阵 (cluster × enrolled) - P1-2
        n_cids = len(sorted_clusters)
        n_enrolled = len(enrolled_names)
        cost_matrix = np.full((n_cids, n_enrolled), 999.0, dtype=np.float32)
        for i, cid in enumerate(sorted_clusters):
            center = cluster_centers[cid]
            for j, name in enumerate(enrolled_names):
                emb = list(members[name].voice_embedding) if members.get(name) and members[name].voice_embedding is not None else None
                if emb is None:
                    continue
                emb_arr = np.array(emb, dtype=np.float32)
                if np.all(emb_arr == 0):
                    continue
                # 用 cosine distance 作 cost
                a_n = center / (np.linalg.norm(center) + 1e-8)
                b_n = emb_arr / (np.linalg.norm(emb_arr) + 1e-8)
                cost_matrix[i, j] = float(1.0 - np.dot(a_n, b_n))

        # Hungarian 配对 (最小总距离)
        try:
            from scipy.optimize import linear_sum_assignment
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            hungarian_mapping = {
                sorted_clusters[r]: enrolled_names[c]
                for r, c in zip(row_ind, col_ind)
            }
            print(f"\n=== Hungarian 配对 (推荐, 最小总距离) ===")
            total_cost = float(cost_matrix[row_ind, col_ind].sum())
            for cid in sorted_clusters:
                name = hungarian_mapping[cid]
                dist = cost_matrix[sorted_clusters.index(cid), enrolled_names.index(name)]
                print(f"  cluster_{cid} → {name} (dist={dist:.4f}, n={cnt[cid]})")
            print(f"  总距离: {total_cost:.4f}")
        except ImportError:
            hungarian_mapping = None
            print(f"\n⚠️ scipy.optimize.linear_sum_assignment 不可用, 回退段数启发式")

        # 段数推断 (sanity check)
        segment_count_mapping = {
            sorted_clusters[0]: "王天志",  # 段数最多 = 主讲
            sorted_clusters[1]: "杜同贺",  # 次多
            sorted_clusters[2]: "杨慈",   # 最少
        }
        print(f"\n=== 段数推断 (sanity check) ===")
        for cid in sorted_clusters:
            print(f"  cluster_{cid} → {segment_count_mapping[cid]} (n={cnt[cid]})")

        # 检查 Hungarian vs 段数一致性
        if hungarian_mapping:
            mismatches = [
                (cid, hungarian_mapping[cid], segment_count_mapping[cid])
                for cid in sorted_clusters
                if hungarian_mapping[cid] != segment_count_mapping[cid]
            ]
            if mismatches:
                print(f"\n⚠️ Hungarian 与段数推断不一致: {len(mismatches)} 处")
                for cid, h_name, s_name in mismatches:
                    print(f"    cluster_{cid}: Hungarian={h_name} vs 段数={s_name}")
                print(f"    采用 Hungarian 配对 (段数启发式仅作 sanity check)")

        # 最终使用 Hungarian (P1-2 默认)
        cluster_to_name = hungarian_mapping if hungarian_mapping else segment_count_mapping
        print(f"\ncluster → name 映射 (最终采用):")
        for cid, name in cluster_to_name.items():
            print(f"  cluster_{cid} → {name} (n={cnt[cid]})")

    # 5. 注入 cluster_id 到 transcript
    new_transcript = [dict(seg) for seg in transcript]
    cluster_id_per_seg = {seg_idx: -1 for seg_idx in range(len(transcript))}
    for k, seg_idx in enumerate(valid_idx):
        cluster_id_per_seg[seg_idx] = int(km.labels_[k])

    for i, seg in enumerate(new_transcript):
        if isinstance(seg, dict):
            seg["cluster_id"] = cluster_id_per_seg.get(i, -1)
            # 也按 cluster_to_name 重写 speaker
            cid = seg.get("cluster_id", -1)
            if cid >= 0 and cid in cluster_to_name:
                seg["speaker"] = cluster_to_name[cid]
            else:
                seg["speaker"] = "发言人?"

    # 6. speaker_mapping: cluster_N → name
    new_mapping = {f"cluster_{cid}": name for cid, name in cluster_to_name.items()}
    print(f"\nnew speaker_mapping: {new_mapping}")

    # 7. cluster_centers 已在上一步算好, 跳过重复计算

    # 8. 计算 cluster_centers vs enrolled 距离作为验证
    print(f"\n=== 验证 cluster_centers vs enrolled 距离 (cos similarity) ===")
    print(f"  cluster |   杨慈   |   王天志  |   杜同贺  |  assigned")
    for cid, center in cluster_centers.items():
        sims = {
            n: cos(center, list(m.voice_embedding))
            for n, m in members.items()
        }
        print(
            f"  cluster_{cid} | {sims['杨慈']:.4f} | {sims['王天志']:.4f} | {sims['杜同贺']:.4f} | "
            f"{cluster_to_name[cid]} (best match={max(sims, key=sims.get)})"
        )

    # 9. 写 DB (transcript + speaker_mapping + cluster_id_history entry)
    # 2026-06-27 P2-2: 写 cluster_id_history 便于 rollback 工具按时间戳回溯
    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == 83))
        m = r.scalar_one()
        m.transcript = new_transcript
        m.speaker_mapping = new_mapping
        # 追加 history entry (append 到现有 list)
        history_entry = {
            "ts": datetime.utcnow().isoformat(),
            "source": "inject_083",
            "injector": "scripts/inject_083_clusters.py",
            "n_segments": len(valid_idx),
            "n_with_cluster_id": sum(1 for v in cluster_id_per_seg.values() if v >= 0),
            "kmeans_k": len(cnt),
            "cluster_to_name": cluster_to_name,
            "notes": "083 strict pipeline 处理, P0/P1 优化后 (Hungarian 配对 + cluster_centers 合并)",
        }
        if m.cluster_id_history is None:
            m.cluster_id_history = []
        m.cluster_id_history.append(history_entry)
        m.updated_at = datetime.utcnow()
        await db.commit()
        print(f"\n✅ DB updated: meeting {m.id} transcript ({len(new_transcript)} 段, cluster_id 注入) + speaker_mapping ({len(new_mapping)} keys) + cluster_id_history (now {len(m.cluster_id_history)} entries)")

    # 10. 下一步: 用 Hungarian 配对的 cluster_to_name 跑 purify
    sorted_by_cid = sorted(cluster_to_name.keys())
    next_cmd = (
        f"--cluster-to-member '"
        + ",".join(f"cluster_{cid}:{cluster_to_name[cid]}" for cid in sorted_by_cid)
        + "'"
    )
    print(f"\n下一步: 跑 purify_voiceprints_from_meeting.py --meeting 83 {next_cmd} --strategy strict")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())