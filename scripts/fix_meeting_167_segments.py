#!/usr/bin/env python3
"""#167 段 15/16/17/18 修正: speaker → 杜同贺 + cluster_id → 5

用户 2026-06-30 决定:
- 段 15 "10" (0.51s) cluster_2 → 杜同贺 cluster_5
- 段 16 "每日电费约为121.6元, 收费约3648元" (6.33s) cluster_2 → 杜同贺 cluster_5
- 段 17 "90天按照10000元算" (2.14s) cluster_0 → 杜同贺 cluster_5
- 段 18 "很简单" (0.70s) cluster_3 → 杜同贺 cluster_5

理由:
- 段 15/16/17/18 按语义连贯性都属"杜同贺算账+评论"主题
- 段 16/17 是声纹反向误识 (cos_dist 张宏魁 0.665 vs 杜同贺 0.682, 差 0.017)
- 段 18 用户确认是杜同贺
- 必须同时改 cluster_id, 否则 Part 2 过滤规则未来重跑 #167 会把段 16/17 当短段 cluster 过滤掉

用法:
  python scripts/fix_meeting_167_segments.py
"""
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/app")

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.orm.attributes import flag_modified

from app.config import settings
from app.models.meeting import Meeting


async def main():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ========== 备份 ==========
    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == 167))
        m167 = r.scalar_one()
        backup = {
            "id": m167.id,
            "speaker_mapping": m167.speaker_mapping,
            "transcript": m167.transcript,
            "transcript_polished": m167.transcript_polished,
            "summary": m167.summary,
            "key_points": m167.key_points,
            "backup_time": datetime.now(timezone.utc).isoformat(),
            "reason": "Part 1: 段 15,16,17,18 speaker → 杜同贺 + cluster_id → 5",
        }
        with open("/tmp/meeting_167_backup_v2.json", "w", encoding="utf-8") as f:
            json.dump(backup, f, ensure_ascii=False, indent=2)
        print(f"备份 #167 → /tmp/meeting_167_backup_v2.json")

    # ========== 修正 transcript ==========
    # 段索引 14, 15, 16, 17 (对应段号 15, 16, 17, 18)
    # 0-indexed: 14=段15, 15=段16, 16=段17, 17=段18
    segments_to_fix = [14, 15, 16, 17]  # 0-indexed → 段 15, 16, 17, 18
    # 段 1 cluster_id=4 是张宏魁, 但其他张宏魁段都是 cluster_1, 统一改 cluster_1 避免 Part 2 过滤
    zhang_cluster_normalize = [0]  # 0-indexed 段 1

    async with sf() as db:
        r = await db.execute(select(Meeting).where(Meeting.id == 167))
        m167 = r.scalar_one()

        if not m167.transcript:
            print("FATAL: transcript 为空")
            return

        transcript = list(m167.transcript)
        print(f"\n=== 修正前 ({len(transcript)} 段) ===")
        for i, seg in enumerate(transcript):
            if not isinstance(seg, dict):
                continue
            seg_idx = i + 1
            print(f"  段{seg_idx:2d} cluster_id={seg.get('cluster_id')} speaker={seg.get('speaker', '?')!r:15s} text={seg.get('text','')[:30]!r}")

        # 改 speaker + cluster_id
        for i in segments_to_fix:
            if i >= len(transcript):
                print(f"WARN: 段 {i+1} 超出范围")
                continue
            seg = transcript[i]
            if not isinstance(seg, dict):
                continue
            old_speaker = seg.get("speaker", "?")
            old_cluster = seg.get("cluster_id")
            seg["speaker"] = "杜同贺"
            seg["cluster_id"] = 5
            print(f"  段{i+1:2d}: speaker {old_speaker!r}→'杜同贺' cluster_id {old_cluster}→5")

        # 段 1 cluster_id 4 → 1 (统一张宏魁 cluster, 避免 Part 2 按 cluster_4 短段过滤)
        for i in zhang_cluster_normalize:
            if i < len(transcript) and isinstance(transcript[i], dict):
                seg = transcript[i]
                if seg.get("cluster_id") == 4:
                    seg["cluster_id"] = 1
                    print(f"  段{i+1:2d}: cluster_id 4→1 (统一张宏魁 cluster)")

        m167.transcript = transcript
        flag_modified(m167, "transcript")

        # ========== 修正 transcript_polished (按索引对齐, 段 15,16,17,18 = index 14,15,16,17) ==========
        if m167.transcript_polished:
            polished = list(m167.transcript_polished)
            for i in segments_to_fix:
                if i < len(polished):
                    pseg = polished[i]
                    if isinstance(pseg, dict):
                        old_sp = pseg.get("speaker", "?")
                        pseg["speaker"] = "杜同贺"
                        print(f"  polished 段{i+1:2d}: speaker {old_sp!r}→'杜同贺'")
            m167.transcript_polished = polished
            flag_modified(m167, "transcript_polished")

        # ========== 修正 speaker_mapping ==========
        # 段 16 cluster_2 / 段 17 cluster_0 / 段 15 cluster_2 / 段 18 cluster_3 都改 cluster_5 后, 这些 cluster 没段了, 移除
        # cluster_1 张宏魁 + cluster_5 杜同贺 保留
        new_mapping = {
            "cluster_1": "张宏魁",  # 段 1, 4, 10, 11, 12 (5 段 ~17.2s)
            "cluster_5": "杜同贺",  # 段 3, 6, 7, 8, 9, 14, 15, 16, 17, 18 (10 段 ~28.8s)
        }
        m167.speaker_mapping = new_mapping
        flag_modified(m167, "speaker_mapping")
        print(f"\n  speaker_mapping 更新: {new_mapping}")

        # ========== 修正 summary / key_points ==========
        if isinstance(m167.summary, str):
            # 段 16 "王天志" 已被纠正为杜同贺, 段 17 cluster_0 之前是发言人A, 不影响 summary
            # 段 16 已经从 cluster_2 移到 cluster_5 杜同贺, 不需要改 summary
            # 但段 17 cluster_0 之前是 "发言人A", 现在是杜同贺, summary 不会有 "发言人A" 引用
            pass
        if m167.key_points and isinstance(m167.key_points, list):
            new_kp = []
            for kp in m167.key_points:
                if isinstance(kp, str):
                    kp = kp.replace("【王天志】计算每日电费", "【杜同贺】计算每日电费")
                new_kp.append(kp)
            m167.key_points = new_kp
            flag_modified(m167, "key_points")

        await db.commit()
        print(f"\n=== 修正后 ===")
        for i, seg in enumerate(transcript):
            if not isinstance(seg, dict):
                continue
            seg_idx = i + 1
            print(f"  段{seg_idx:2d} cluster_id={seg.get('cluster_id')} speaker={seg.get('speaker', '?')!r:15s} text={seg.get('text','')[:30]!r}")
        print(f"\nspeaker_mapping: {new_mapping}")
        print(f"\n=== #167 修正完成 ===")


if __name__ == "__main__":
    asyncio.run(main())