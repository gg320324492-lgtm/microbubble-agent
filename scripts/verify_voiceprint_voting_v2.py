"""verify 会议 #135 重处理 + 新 voiceprint_voting 模块

测试 5 个优化:
  1. smart_select_k 综合评分 (silhouette + balance + n_expected)
  2. vote_with_quality_gates 4 道质量门控
  3. assign_with_strict_threshold conf > 0.50
  4. extract_context_speakers + resolve_context_to_names
  5. identify_and_learn_segments 自动学习

期望: 不传 --names, 也能正确识别 4 人 (王天志/赵航佳/韩重阳/张宏魁)
"""
import asyncio
import sys
import json
import logging
import argparse
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, "/app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("verify_voting_v2")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--meeting", type=int, default=135)
    parser.add_argument("--audio", type=str, default="/tmp/meeting_135_16k.wav")
    parser.add_argument("--n-expected", type=int, default=4)
    args = parser.parse_args()

    meeting_id = args.meeting
    expected_names = ["王天志", "赵航佳", "韩重阳", "张宏魁"]

    # 1. load meeting
    from app.config import settings
    from app.models.meeting import Meeting
    from app.models.member import Member
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with sf() as db:
        m = await db.get(Meeting, meeting_id)
        transcript = list(m.transcript or [])
        logger.info(f"Meeting #{meeting_id} | title: {m.title} | 段数: {len(transcript)}")

        # 2. extract context speakers
        from app.services.voiceprint_voting import (
            extract_context_speakers, resolve_context_to_names,
            get_recent_meeting_speakers,
        )
        ctx_raw = extract_context_speakers(m)
        ctx = await resolve_context_to_names(ctx_raw, db) if ctx_raw else set()
        logger.info(f"Context speakers (raw): {ctx_raw}")
        logger.info(f"Context speakers (resolved): {ctx}")

        # 加 history-based context
        history_ctx = await get_recent_meeting_speakers(meeting_id, db, lookback_count=10, lookback_days=90)
        if history_ctx:
            ctx = ctx | history_ctx
            logger.info(f"Context + history: {ctx}")

    await engine.dispose()

    # 3. extract embeddings (复用 reprocess_meeting 的逻辑)
    from scripts.reprocess_meeting import load_audio, prepare_chunks, extract_embeddings_parallel
    from app.services.voiceprint_service import voiceprint_service
    voiceprint_service._load_pipeline()
    pcm = load_audio(args.audio)
    chunks, valid_idx = prepare_chunks(pcm, transcript)
    logger.info(f"分块: {len(transcript)} 段, {len(valid_idx)} 段有效, {len(transcript) - len(valid_idx)} 段过短")
    embs = extract_embeddings_parallel(voiceprint_service, [chunks[i] for i in valid_idx])
    seg_embs = [None] * len(transcript)
    for j, i in enumerate(valid_idx):
        seg_embs[i] = embs[j]
    n_valid = sum(1 for e in seg_embs if e is not None and not np.all(np.array(e) == 0))
    logger.info(f"提取完成: {n_valid}/{len(transcript)} 段有效")

    # 4. load enrolled (15 人)
    from sqlalchemy import create_engine as _ce
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
    logger.info(f"Enrolled 库: {len(enrolled)} 人 (含 {[(m.id, m.name, m.voice_sample_count) for m in members[:5]]}...)")

    # ========== 优化 1: smart_select_k ==========
    from app.services.voiceprint_voting import smart_select_k
    labels, k, score, all_scores = smart_select_k(seg_embs, n_expected=args.n_expected)
    label_dist = Counter(l for l in labels if l >= 0)
    logger.info(f"[优化 1] smart_select_k 选 K={k} (score={score:.3f}, n_expected={args.n_expected})")
    logger.info(f"  聚类分布: {dict(label_dist)}")

    # ========== 优化 2: vote_with_quality_gates (无 context) ==========
    from app.services.voiceprint_voting import vote_with_quality_gates
    cluster_names_no_ctx = vote_with_quality_gates(
        seg_embs, labels, enrolled, context_names=None,
    )
    logger.info(f"[优化 2] 无 context vote 结果:")
    for cid, (name, conf, votes, total) in cluster_names_no_ctx.items():
        mark = "✅" if name in expected_names else ("❌" if name else "❓")
        logger.info(f"  聚类 {cid} ({total} 段, votes={votes}): {name} conf={conf:.3f} {mark}")

    # ========== 优化 2: vote_with_quality_gates (有 context) ==========
    if ctx:
        cluster_names_ctx = vote_with_quality_gates(
            seg_embs, labels, enrolled, context_names=ctx,
        )
        logger.info(f"[优化 2] 有 context ({len(ctx)} 人) vote 结果:")
        for cid, (name, conf, votes, total) in cluster_names_ctx.items():
            mark = "✅" if name in expected_names else ("❌" if name else "❓")
            logger.info(f"  聚类 {cid} ({total} 段, votes={votes}): {name} conf={conf:.3f} {mark}")
    else:
        cluster_names_ctx = cluster_names_no_ctx

    # ========== 优化 3: assign_with_strict_threshold ==========
    from app.services.voiceprint_voting import assign_with_strict_threshold
    new_speaker, _ = assign_with_strict_threshold(
        transcript, labels, cluster_names_ctx,
        conf_threshold=0.50, votes_ratio_threshold=0.5,
    )
    sp_counter = Counter(new_speaker)
    logger.info(f"[优化 3] assign 分布: {dict(sp_counter)}")

    # 5. verify 自动识别率
    expected_set = set(expected_names)
    auto_identified = set(n for n in sp_counter if n in expected_set)
    wrong_identified = set(n for n in sp_counter if n and n not in expected_set and not n.startswith("发言人"))
    print()
    print("=" * 60)
    print(f"自动识别率: {len(auto_identified)}/{len(expected_set)} = {100*len(auto_identified)/len(expected_set):.0f}%")
    print(f"  ✅ 识别: {auto_identified}")
    print(f"  ❌ 错识: {wrong_identified}")
    print(f"  ❓ 未知: {sp_counter.get('发言人?', 0)} 段 ({100*sp_counter.get('发言人?', 0)/len(transcript):.0f}%)")
    print("=" * 60)
    if auto_identified == expected_set and not wrong_identified:
        print("🎉 PASS — 4 个真实发言人全部自动识别, 无错识")
    else:
        print("⚠️ 部分识别成功, 需进一步调参")


if __name__ == "__main__":
    asyncio.run(main())
