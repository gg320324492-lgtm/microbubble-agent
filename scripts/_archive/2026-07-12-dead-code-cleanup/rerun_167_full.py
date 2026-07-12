#!/usr/bin/env python3
"""基于剔除+重学后的张宏魁新声纹，重新跑 #167 全 18 段识别"""
import asyncio
import sys
import logging

import numpy as np

sys.path.insert(0, "/app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("rerun_167")


async def main():
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy.pool import NullPool
    from app.config import settings
    from app.models.member import Member
    from app.services.file_service import file_service
    from app.services.audio_processor import audio_processor
    from app.services.voiceprint_service import voiceprint_service, MATCH_THRESHOLD

    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # 加载所有有 embedding 的成员
    async with sf() as db:
        r = await db.execute(select(Member).where(Member.voice_embedding.isnot(None)))
        members = list(r.scalars().all())
        print(f"\n=== 有声纹的成员 ({len(members)} 人) ===")
        for m in sorted(members, key=lambda x: -x.voice_sample_count):
            print(f"  id={m.id:2d} {m.name:8s} samples={m.voice_sample_count:4d}")

    # 下载 #167 音频
    audio = await file_service.download_file("recordings/23fa1b5ccd90459ea418c41e877382fc.webm")
    pcm, segments, sr = await audio_processor.convert_and_segment(audio)
    print(f"\n=== #167 音频 ===")
    print(f"  VAD 段数: {len(segments)}, 总时长: {len(pcm)/sr:.2f}s")

    # 18 段 (从 DB transcript 拿时间戳 + 文本)
    async with sf() as db:
        from app.models.meeting import Meeting
        r = await db.execute(select(Meeting).where(Meeting.id == 167))
        m167 = r.scalar_one()
        transcript = m167.transcript

    print(f"\n=== 18 段完整重跑 (新声纹识别) ===\n")
    print(f"{'#':>3s} {'时间':^14s} {'时长':>5s} {'cos_dist':>8s} {'识别':>8s} {'conf':>5s} {'文本':<35s}")
    print("-" * 100)

    # 收集结果
    results = []
    async with sf() as db:
        for i, seg in enumerate(transcript):
            seg_idx = i + 1
            start = float(seg.get("start", 0))
            end = float(seg.get("end", 0))
            text = seg.get("text", "")
            db_speaker = seg.get("speaker", "?")

            seg_pcm = pcm[int(start*sr):int(end*sr)]
            dur = len(seg_pcm)/sr

            # 同时算 vs 所有成员的 cos 距离
            emb = voiceprint_service.extract_embedding(seg_pcm)
            emb_norm = emb / (np.linalg.norm(emb) + 1e-8)

            cos_dists = []
            for m in members:
                db_emb = np.array(m.voice_embedding, dtype=np.float32)
                db_emb_norm = db_emb / (np.linalg.norm(db_emb) + 1e-8)
                cos_dist = float(1.0 - np.dot(emb_norm, db_emb_norm))
                cos_dists.append((m.name, m.voice_sample_count, cos_dist))
            cos_dists.sort(key=lambda x: x[2])

            # 系统 identify_speaker 返回值 (用 MATCH_THRESHOLD=0.7 决定是否识别)
            name, mid, conf = await voiceprint_service.identify_speaker(db, seg_pcm)

            # 显示 top3 距离
            top3_str = " | ".join([f"{n}({s}s,d={d:.3f})" for n, s, d in cos_dists[:3]])

            display_name = name if name else "未识别"
            mark = "  " if name else "❓"
            print(f"{seg_idx:>3d} [{start:>5.2f}-{end:>5.2f}] {dur:>4.2f}s {cos_dists[0][2]:>8.3f} {display_name:>6s} {conf:>5.3f} {mark} {text[:35]}")
            print(f"      top3: {top3_str}")
            print(f"      DB原标: {db_speaker}")
            print()

            results.append({
                "seg_idx": seg_idx,
                "start": start,
                "end": end,
                "duration": dur,
                "text": text,
                "db_speaker": db_speaker,
                "new_speaker": name,
                "confidence": conf,
                "best_match_name": cos_dists[0][0],
                "best_match_dist": cos_dists[0][2],
                "top3": cos_dists[:3],
            })

    # 总结
    print("\n=== 总结 ===")
    new_zhang_count = sum(1 for r in results if r["new_speaker"] == "张宏魁")
    new_dth_count = sum(1 for r in results if r["new_speaker"] == "杜同贺")
    new_unknown = sum(1 for r in results if r["new_speaker"] is None)
    print(f"张宏魁: {new_zhang_count}/18 段被新声纹识别")
    print(f"杜同贺: {new_dth_count}/18 段被新声纹识别")
    print(f"未识别: {new_unknown}/18 段 (cos_dist >= 0.7)")


if __name__ == "__main__":
    asyncio.run(main())