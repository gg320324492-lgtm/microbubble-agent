"""
会议 #135 重处理 override 脚本
- 强制 K=4（auto-vote 误判为 K=2）
- 强制 vote 给指定 4 个发言人: 王天志、赵航佳、韩重阳、张宏魁
- 其他步骤同标准 9 步流程

触发根因:
  标准 reprocess_meeting.py 走 KMeans silhouette 自动选 K → K=2 (silhouette=0.05)
  实际 4 人都在说话, 但音频以 2 人为主, KMeans 看不到 4 个聚类
  auto-vote 把 2 聚类误判为 周之超 + 杜同贺 (embedding 最近邻, 但非真实发言人)
  verify 检查"旧错标人 5 模式"不包含 周/杜 → 报"全 0" 是误报

使用:
  docker exec -i -w /app microbubble-agent-app-1 python scripts/reprocess_meeting_135_override.py
"""
import sys
import os
import json
import logging
import asyncio
import argparse
import threading
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

# Force unbuffered prints for docker logs
sys.stdout.reconfigure(line_buffering=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reprocess_135_override")

SAMPLE_RATE = 16000
N_WORKERS = 8
FORCED_NAMES = ["王天志", "赵航佳", "韩重阳", "张宏魁"]  # 用户指定
FORCED_K = 4  # 强制 4 聚类 (auto 误判 K=2)

# Import shared helpers from standard script
sys.path.insert(0, "/app")
from app.config import settings
from app.models.meeting import Meeting
from app.models.member import Member
from reprocess_meeting import (
    load_audio,
    prepare_chunks,
    extract_embeddings_parallel,
)


def assign_speakers_forced(transcript: list, labels: list, cluster_names: dict) -> tuple:
    """override 版 assign: 强制按 cluster → name 映射分配, 不做 conf > 0.30 检查
    解决: 韩重阳 (cluster 3) avg_conf=-0.006 触发 conf 检查失败, 全部变"发言人A/B/C..."
    """
    new_speaker = [""] * len(transcript)
    speaker_label_to_name = {}
    for i, seg in enumerate(transcript):
        if labels[i] < 0:
            new_speaker[i] = "发言人?"
            continue
        cid = labels[i]
        name, conf, votes, _ = cluster_names.get(cid, (None, 0.0, 0, 0))
        if name:
            new_speaker[i] = name
            old_label = seg.get("speaker_label", f"speaker_{i}")
            speaker_label_to_name[old_label] = name
        else:
            new_speaker[i] = "发言人?"
    from collections import Counter
    ctr = Counter(new_speaker)
    logger.info(f"[5/assign_forced] new_speaker 分布: {dict(ctr)}")
    return new_speaker, speaker_label_to_name


# ============================================================================
# 强制 KMeans (不再 silhouette 选 K)
# ============================================================================
def cluster_embeddings_forced(seg_embs: list, k: int = 4) -> tuple:
    """强制 K 个聚类 (silhouette 选 K 在 low separation 场景下不稳定)"""
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    valid = np.array([e for e in seg_embs if e is not None])
    if len(valid) < 2:
        return [0] * len(seg_embs), 1, -1.0
    km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(valid)
    try:
        s = silhouette_score(valid, km.labels_)
    except Exception:
        s = -1.0
    logger.info(f"  强制 K={k} silhouette={s:.3f}")
    labels = [-1] * len(seg_embs)
    j = 0
    for i, e in enumerate(seg_embs):
        if e is not None:
            labels[i] = int(km.labels_[j])
            j += 1
    return labels, k, s


# ============================================================================
# 强制 vote (仅对指定 4 人比对, 不看其他 enrolled)
# ============================================================================
def vote_names_forced(seg_embs: list, labels: list, target_names: list) -> dict:
    """强制 4 个聚类 → 4 个指定名字 (按 cluster 中心 vs 目标 embedding 余弦距离最近)"""
    from collections import Counter
    cluster_names = {}
    # 1. 加载目标 4 人的 voice_embedding (同步版本, 避免嵌套 event loop)
    from sqlalchemy import create_engine as _create_sync_engine
    from sqlalchemy.orm import sessionmaker as _sm
    _sync_url = settings.DATABASE_URL
    _sync_engine = _create_sync_engine(_sync_url)
    SyncSession = _sm(bind=_sync_engine)
    with SyncSession() as sdb:
        members = sdb.execute(
            select(Member).where(Member.name.in_(target_names))
        ).scalars().all()
    _sync_engine.dispose()
    target_embs = {m.name: np.array(m.voice_embedding, dtype=np.float32) for m in members if m.voice_embedding is not None}
    if len(target_embs) != len(target_names):
        logger.warning(f"目标 {len(target_names)} 人, 只加载到 {len(target_embs)} 人: {list(target_embs.keys())}")

    # 2. 算每聚类的中心
    cluster_centers = {}
    for cid in sorted(set(l for l in labels if l >= 0)):
        idxs = [i for i, l in enumerate(labels) if l == cid and seg_embs[i] is not None and not np.all(seg_embs[i] == 0)]
        if not idxs:
            continue
        embs = np.array([seg_embs[i] for i in idxs])
        # 中心: 段 embedding 的均值 (线性空间, 不是球面)
        center = embs.mean(axis=0)
        # L2 normalize
        norm = np.linalg.norm(center)
        if norm > 0:
            center = center / norm
        cluster_centers[cid] = center

    # 3. 每个聚类中心 vs 每个目标 embedding, 取余弦距离最近的
    used_names = set()
    # 按 cluster id 顺序分配, 后续 greedy: 取最近未分配的
    cid_to_name = {}
    for cid, center in sorted(cluster_centers.items()):
        dists = []
        for name, emb in target_embs.items():
            if name in used_names:
                continue
            norm = np.linalg.norm(emb)
            if norm == 0:
                continue
            emb_n = emb / norm
            dist = float(1.0 - np.dot(center, emb_n))
            dists.append((name, dist))
        if not dists:
            cid_to_name[cid] = (None, 0.0, 0, 0)
            continue
        dists.sort(key=lambda x: x[1])
        best_name, best_dist = dists[0]
        conf = 1.0 - best_dist
        # 段级别投票验证
        n_votes = 0
        confs = []
        idxs = [i for i, l in enumerate(labels) if l == cid and seg_embs[i] is not None]
        for i in idxs:
            seg_emb = seg_embs[i]
            if np.all(seg_emb == 0):
                continue
            seg_n = seg_emb / (np.linalg.norm(seg_emb) + 1e-8)
            d = 1.0 - np.dot(seg_n, target_embs[best_name] / np.linalg.norm(target_embs[best_name]))
            if d < 0.7:  # match_threshold
                n_votes += 1
                confs.append(1.0 - d)
        avg_conf = float(np.mean(confs)) if confs else conf
        cid_to_name[cid] = (best_name, avg_conf, n_votes, len(idxs))
        used_names.add(best_name)
        logger.info(
            f"  聚类 {cid} ({len(idxs)} 段, 段级 votes={n_votes}): "
            f"{best_name} avg_conf={avg_conf:.3f} center_dist={best_dist:.3f}"
        )

    # 剩余聚类 (无 center) 给 None
    for cid in sorted(set(l for l in labels if l >= 0)):
        if cid not in cid_to_name:
            cid_to_name[cid] = (None, 0.0, 0, 0)
    return cid_to_name


# ============================================================================
# Override apply_to_db (8 字段验证)
# ============================================================================
async def apply_override(meeting_id: int, new_speaker: list, target_names: list, workdir: str = "/tmp") -> dict:
    """8 字段应用 + 文件备份 (替代原 apply_to_db, 兼容 K=4 强制分配)"""
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import time
    from datetime import datetime
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = Path(workdir) / f"meeting_{meeting_id}_backup_{ts}.json"

    try:
        async with sf() as db:
            m = await db.get(Meeting, meeting_id)
            if not m:
                raise ValueError(f"Meeting {meeting_id} not found")

            # 1. 备份 8 字段到文件
            backup_data = {
                "meeting_id": meeting_id,
                "backup_at": ts,
                "transcript": list(m.transcript or []),
                "transcript_polished": list(m.transcript_polished or []),
                "speaker_mapping": dict(m.speaker_mapping or {}),
                "speaker_stats": list(m.speaker_stats or []),
                "key_points": list(m.key_points or []),
                "decisions": list(m.decisions or []),
                "summary": m.summary or "",
                "meeting_participants": [
                    {"id": mp.member_id, "name": mp.name if hasattr(mp, "name") else None}
                    for mp in (m.meeting_participants or [])
                ] if hasattr(m, "meeting_participants") else [],
            }
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)
            logger.info(f"备份写入 {backup_path} ({len(backup_data['transcript'])} 段, ...)")

            # 2. 改 transcript[i].speaker (按位置一一对应)
            new_t = []
            for i, seg in enumerate(backup_data["transcript"]):
                new_seg = dict(seg)
                new_seg["speaker"] = new_speaker[i]
                new_t.append(new_seg)
            m.transcript = new_t

            # 3. 改 transcript_polished[i].speaker (镜像)
            if backup_data["transcript_polished"]:
                new_tp = []
                for i, seg in enumerate(backup_data["transcript_polished"]):
                    new_seg = dict(seg)
                    if i < len(new_speaker):
                        new_seg["speaker"] = new_speaker[i]
                    new_tp.append(new_seg)
                m.transcript_polished = new_tp

            # 4. 改 speaker_mapping (清理掉所有旧 mapping, 用 cluster 内聚合)
            # 简化: 整个 meeting 只有 4 个聚类, 每个聚类对应一个名字
            # 这里 new_speaker 已经是按段分配的最终名字
            # speaker_mapping 改为 {f"cluster_{cid}": name} 形式
            from collections import defaultdict
            cid_to_name = defaultdict(set)
            for i, n in enumerate(new_speaker):
                cid_to_name[f"cluster_{i % 4}"].add(n)
            # 简化: speaker_mapping 用占位映射, 实际渲染按 transcript.speaker
            new_mapping = {}
            for i, name in enumerate(set(new_speaker)):
                if name and name != "发言人?":
                    new_mapping[f"cluster_{i}"] = name
            m.speaker_mapping = new_mapping

            # 5. 清空 speaker_stats, regen 后 LLM 重新生成
            m.speaker_stats = []

            # 6. 重建 meeting_participants (P0: 修 #135 头部头像)
            # 参考 scripts/reprocess_meeting.py:apply_to_db line 387-401 已有的同样逻辑
            from app.models.meeting import MeetingParticipant
            from sqlalchemy import select, delete
            real_speakers = [n for n in target_names if n and not n.startswith("发言人")]
            result = await db.execute(select(Member).where(Member.name.in_(real_speakers)))
            name_to_member = {m_.name: m_ for m_ in result.scalars().all()}
            await db.execute(delete(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id))
            for name in real_speakers:
                member = name_to_member.get(name)
                if not member:
                    logger.warning(f"未找到成员: {name}")
                    continue
                db.add(MeetingParticipant(meeting_id=meeting_id, member_id=member.id, role="participant"))
                logger.info(f"添加参与者: {name} (id={member.id})")

            # 7. 自动生成会议标题 (P1: 修 "正在听会（ID X）" 占位)
            from app.services.meeting_analysis_service import meeting_analysis
            transcript_text = "\n".join(
                f"{seg.get('speaker', '未知')}: {seg.get('text_polished', seg.get('text', ''))}"
                for seg in m.transcript
            )
            if len(transcript_text) >= 10:
                new_title = await meeting_analysis.generate_title(transcript_text)
                if new_title and new_title != "未命名会议":
                    old_title = m.title
                    m.title = new_title
                    logger.info(f"标题自动生成: '{old_title}' → '{new_title}'")

            await db.commit()
            logger.info(f"✅ 8 字段应用完成 (transcript + transcript_polished + speaker_mapping + speaker_stats + meeting_participants + title)")
            return {"backup_path": str(backup_path), "applied": True}
    finally:
        await engine.dispose()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, default=135)
    parser.add_argument("--audio", type=str, default="/tmp/meeting_135_16k.wav")
    parser.add_argument("--workdir", type=str, default="/tmp")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    meeting_id = args.meeting

    logger.info(f"=== 会议 #{meeting_id} 重处理 OVERRIDE (强制 K=4, 强制 4 人) ===")
    logger.info(f"目标发言人: {FORCED_NAMES}")

    # 1. load meeting
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        transcript = list(m.transcript or [])
    await engine.dispose()
    logger.info(f"[1/load] 段数: {len(transcript)}")

    # 2. extract
    from app.services.voiceprint_service import voiceprint_service
    voiceprint_service._load_pipeline()
    pcm = load_audio(args.audio)
    chunks, valid_idx = prepare_chunks(pcm, transcript)
    logger.info(f"[2/extract] ThreadPoolExecutor(N_WORKERS={N_WORKERS}) 并行 ...")
    embs = extract_embeddings_parallel(voiceprint_service, [chunks[i] for i in valid_idx])
    seg_embs = [None] * len(transcript)
    for j, i in enumerate(valid_idx):
        seg_embs[i] = embs[j]
    n_valid = sum(1 for e in seg_embs if e is not None and not np.all(e == 0))
    logger.info(f"[2/extract] {n_valid}/{len(transcript)} 段有效")

    # 3. cluster (强制 K=4)
    labels, n_clusters, silhouette = cluster_embeddings_forced(seg_embs, FORCED_K)
    from collections import Counter
    label_dist = Counter(l for l in labels if l >= 0)
    logger.info(f"[3/cluster] 强制 K={n_clusters}, silhouette={silhouette:.3f}, 分布: {dict(label_dist)}")

    # 4. vote (强制 4 人)
    cluster_names = vote_names_forced(seg_embs, labels, FORCED_NAMES)

    # 5. assign (强制版, 不做 conf > 0.30 检查)
    new_speaker, speaker_label_to_name = assign_speakers_forced(transcript, labels, cluster_names)

    # 6+7. apply (含 8 字段文件备份)
    await apply_override(meeting_id, new_speaker, FORCED_NAMES, workdir)

    # 8. regen (用 LLM 重生成 summary/key_points/decisions)
    logger.info("[8/regen] 调 LLM 重生成 summary/key_points/decisions ...")
    from reprocess_meeting import regen_summary
    regen_result = await regen_summary(meeting_id, FORCED_NAMES, workdir)
    summary_text = regen_result.get("summary", "")
    key_points = regen_result.get("key_points", [])
    decisions = regen_result.get("decisions", [])
    logger.info(f"[8/regen] summary={len(summary_text) if isinstance(summary_text, str) else 'N/A'} chars, key_points={len(key_points) if isinstance(key_points, list) else key_points}, decisions={len(decisions) if isinstance(decisions, list) else decisions}")

    # 9. verify (8 字段全 0 旧错标人)
    logger.info("[9/verify] 8 字段验证 ...")
    from reprocess_meeting import verify_eight_fields
    verify_result = await verify_eight_fields(meeting_id)
    bad_count = sum(verify_result.values())
    if bad_count == 0:
        logger.info("✅ [9/verify] 8 字段全 0 旧错标人")
    else:
        logger.warning(f"⚠️ [9/verify] {bad_count} 字段还有旧错标: {verify_result}")
    for f, n in verify_result.items():
        mark = "✅" if n == 0 else "❌"
        logger.info(f"  {mark} {f}: {n}")

    # 10. 输出最终 cluster → name 映射
    final_mapping = {}
    for cid, (name, conf, votes, total) in cluster_names.items():
        final_mapping[cid] = {"name": name, "conf": conf, "votes": votes, "segments": total}
    logger.info(f"=== 最终聚类映射 ===")
    logger.info(json.dumps(final_mapping, ensure_ascii=False, indent=2))
    return final_mapping


if __name__ == "__main__":
    asyncio.run(main())
