#!/usr/bin/env python3
"""验证 083 cluster_centers vs 3 个 enrolled 人的距离，确认 cluster→name 映射

2026-06-27 P1-3 改进: 加 Hungarian 配对 + top-3 候选 + 不确信度评分
  - 输出 Hungarian 配对 (最小总距离) 作推荐
  - 输出每 cluster top-3 候选 (按 cos sim 倒序)
  - 不确信度评分: top1-top2 距离差距 < 0.05 → ⚠️ 不确信, 需人工复核
  - 段数推断作 sanity check, 与 Hungarian 对比

不重跑 KMeans，直接读 /tmp/reprocess_083/reprocess_83_result.json 里的
new_speaker 索引模式 + 重新提取 embedding 来 group by cluster_id。

但是 result.json 没有保存 labels。只能重新做一次 extract+cluster 然后
立即聚合 cluster_centers。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import wave
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.meeting import Meeting
from app.services.voiceprint_service import voiceprint_service
from app.services.voiceprint_voting import smart_select_k
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

    # 1. 加载 wav (16kHz mono int16)
    wav_path = "/tmp/meeting_083_16k.wav"
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        pcm_i16 = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16)
    pcm = pcm_i16.astype(np.float32) / 32768.0
    print(f"loaded wav: {len(pcm)} samples @ {sr}Hz = {len(pcm)/sr:.1f}s")

    # 2. 加载 transcript 段（按 start/end 取音频）
    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == 83))
        m = r.scalar_one()
        transcript = list(m.transcript or [])
        print(f"transcript segments: {len(transcript)}")

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
        if len(chunk) < sr * 0.5:  # <0.5s 视为过短（与 reprocess_meeting 一致）
            continue
        seg_audios.append(chunk)
        valid_idx.append(i)
    print(f"valid chunks: {len(seg_audios)} / {len(transcript)}")

    # 3. 批量提取 embedding (与 reprocess_meeting 一样 ThreadPoolExecutor)
    seg_embs = voiceprint_service.batch_extract_embeddings(seg_audios)
    valid_emb_count = sum(1 for e in seg_embs if e is not None and not np.all(np.array(e) == 0))
    print(f"valid embeddings: {valid_emb_count}")

    # 4. KMeans K=3 (固定 K，跳过 smart_select_k)
    valid_emb_objs = [e for e in seg_embs if e is not None and not np.all(np.array(e) == 0)]
    valid_emb_array = np.array(valid_emb_objs, dtype=np.float32)
    km = KMeans(n_clusters=3, random_state=42, n_init=10).fit(valid_emb_array)
    labels_per_valid = km.labels_

    # 映射回 transcript idx
    labels_per_seg = [-1] * len(seg_audios)
    j = 0
    for i in range(len(seg_audios)):
        if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0):
            labels_per_seg[i] = int(labels_per_valid[j])
            j += 1

    # 5. 算每个 cluster 的 center
    cluster_centers = {}
    cluster_seg_counts = {}
    for cid in range(3):
        idxs = [i for i, lab in enumerate(labels_per_seg) if lab == cid]
        embs = [seg_embs[i] for i in idxs if seg_embs[i] is not None and not np.all(np.array(seg_embs[i]) == 0)]
        if not embs:
            continue
        arr = np.array(embs, dtype=np.float32)
        center = np.mean(arr, axis=0)
        norm = np.linalg.norm(center)
        if norm > 0:
            center = center / norm
        cluster_centers[cid] = center
        cluster_seg_counts[cid] = len(embs)

    print(f"\n=== cluster centers (K=3) ===")
    for cid in sorted(cluster_centers):
        print(f"  cluster_{cid}: {cluster_seg_counts[cid]} 段有效")

    # 6. 算 cluster_center vs enrolled 3 人的 cos
    async with sf() as db:
        r = await db.execute(
            select(Member).where(Member.name.in_(["杨慈", "王天志", "杜同贺"]))
        )
        members = {mm.name: mm for mm in r.scalars()}

    print(f"\n=== cluster_center vs enrolled 3 人 cos ===")
    print(f"  cluster | segs |   杨慈   |   王天志  |   杜同贺  | best_match")
    for cid in sorted(cluster_centers):
        center = cluster_centers[cid]
        sims = {
            name: cos(center, list(m.voice_embedding))
            for name, m in members.items()
        }
        best = max(sims, key=sims.get)
        print(
            f"  cluster_{cid} | {cluster_seg_counts[cid]:3d} | "
            f" {sims['杨慈']:.4f} | {sims['王天志']:.4f} | {sims['杜同贺']:.4f} | {best} ({sims[best]:.4f})"
        )

    # 7. 2026-06-27 P1-3: Hungarian 配对 top-3 + 不确信度评分
    sorted_clusters = sorted(cluster_centers.keys(), key=lambda c: cluster_seg_counts[c], reverse=True)
    print(f"\n=== Hungarian 配对 (推荐, 最小总距离) ===")
    enrolled_names = ["杨慈", "王天志", "杜同贺"]
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
            a_n = center / (np.linalg.norm(center) + 1e-8)
            b_n = emb_arr / (np.linalg.norm(emb_arr) + 1e-8)
            cost_matrix[i, j] = float(1.0 - np.dot(a_n, b_n))

    try:
        from scipy.optimize import linear_sum_assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        hungarian_mapping = {
            sorted_clusters[r]: enrolled_names[c]
            for r, c in zip(row_ind, col_ind)
        }
        total_cost = float(cost_matrix[row_ind, col_ind].sum())
        print(f"  Hungarian 配对结果:")
        for cid in sorted_clusters:
            name = hungarian_mapping[cid]
            dist = cost_matrix[sorted_clusters.index(cid), enrolled_names.index(name)]
            print(f"    cluster_{cid} → {name} (dist={dist:.4f}, n={cluster_seg_counts[cid]})")
        print(f"  总距离: {total_cost:.4f}")
    except ImportError:
        hungarian_mapping = None
        print(f"  ⚠️ scipy.optimize.linear_sum_assignment 不可用, 跳过 Hungarian 配对")

    # 8. top-3 候选 + 不确信度评分 (P1-3 关键: 识别"不确信配对")
    print(f"\n=== cluster → enrolled top-3 候选 + 不确信度 ===")
    print(f"  cluster | top1 (dist) | top2 (dist) | top3 (dist) | 不确信度 | 推荐")
    high_uncertainty = []  # 不确信度 > 阈值 的 cluster 需人工复核
    for cid in sorted_clusters:
        center = cluster_centers[cid]
        ranked = sorted(
            [(name, cos(center, list(members[name].voice_embedding)))
             for name in enrolled_names
             if members.get(name) and members[name].voice_embedding is not None
             and not np.all(np.array(members[name].voice_embedding) == 0)],
            key=lambda x: -x[1],  # 按 cos 倒序 (高相似度排前)
        )
        if not ranked:
            continue
        top3 = ranked[:3]
        # 不确信度: top1 - top2 (差距越小越不确信, 需人工复核)
        top1_dist = 1.0 - top3[0][1]  # 转 cos_dist
        top2_dist = 1.0 - top3[1][1] if len(top3) > 1 else 999.0
        diff = top2_dist - top1_dist
        # diff < 0.05 → top1 和 top2 距离接近, 配对不确信
        uncertain = diff < 0.05
        uncertainty_str = f"diff={diff:.3f}" + (" ⚠️ 不确信" if uncertain else " ✅ 确信")
        hungarian_pick = hungarian_mapping[cid] if hungarian_mapping else "?"
        recommended = hungarian_pick if not uncertain else f"⚠️ 人工复核 (top1={top3[0][0]} vs top2={top3[1][0]})"
        top3_str = " | ".join(f"{n} {1.0 - d:.3f}" for n, d in top3)
        print(f"  cluster_{cid} | {top3_str} | {uncertainty_str} | {recommended}")
        if uncertain:
            high_uncertainty.append((cid, top3[ 0], top3[1], diff))

    if high_uncertainty:
        print(f"\n⚠️ 发现 {len(high_uncertainty)} 个 cluster 配对不确信 (top1-top2 差距 < 0.05)")
        print(f"   建议人工复核 cluster_centers vs enrolled cos 表, 或对比段文本内容辅助判断")
    else:
        print(f"\n✅ 所有 cluster 配对确信 (top1-top2 差距 >= 0.05)")

    # 9. 推荐映射（段数推断作 sanity check, 与 Hungarian 对比）
    print(f"\n=== 推荐 cluster → name 映射 ===")
    print(f"  按段数排序: {[f'cluster_{c}({cluster_seg_counts[c]})' for c in sorted_clusters]}")
    print(f"  真实参会人: 杨慈, 王天志, 杜同贺")
    if hungarian_mapping:
        print(f"  ✅ Hungarian 配对 (推荐):")
        for cid in sorted_clusters:
            print(f"    cluster_{cid} → {hungarian_mapping[cid]}")
        # 段数 sanity check
        segment_count_suggested = {
            sorted_clusters[0]: "王天志",  # 主讲
            sorted_clusters[1]: "杜同贺",
            sorted_clusters[2]: "杨慈",
        }
        print(f"  (sanity check) 段数从大到小分配:")
        for cid in sorted_clusters:
            h_name = hungarian_mapping[cid]
            s_name = segment_count_suggested[cid]
            tag = "✅" if h_name == s_name else "⚠️"
            print(f"    {tag} cluster_{cid}: Hungarian={h_name} vs 段数={s_name}")
    else:
        print(f"  段数从大到小分配:")
        suggested = {
            sorted_clusters[0]: "王天志",
            sorted_clusters[1]: "杜同贺",
            sorted_clusters[2]: "杨慈",
        }
        for cid in sorted_clusters:
            print(f"    cluster_{cid} → {suggested[cid]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())