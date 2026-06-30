#!/usr/bin/env python3
"""#167 张宏魁声纹最终确定: 4 段高质量 (段 4, 10, 11, 12, 不含段 1)

2026-06-30 用户最终决策 (interrupt 后续):
- 5 段 → 4 段 (去掉段 1 0.95s, conf 0.361 噪声)
- 总时长 ~16.24s (4 段)
- 之前的 history audit 保留 (audit trail)
- "确定不再改变" → 标记 voice_confirmed_at + 永久锁定

4 段列表:
- 段 4: [9.99-16.61] 6.62s  "在此方案中加入主要设备功率以及电汇核酸部分单独列表。"
- 段 10: [32.29-34.65] 2.36s "一边使用8小时。"
- 段 11: [35.20-40.48] 5.28s "六方抽氧功率4.5千瓦, 100克抽氧发生器功率850瓦。"
- 段 12: [41.12-43.10] 1.98s "设备是情况使用。"

排除段 1 (0.95s, "然后就允许。") - conf 0.361 噪声, 拉低 weighted_avg 质量.

用法:
  python scripts/finalize_zhang_4segments.py
"""
import asyncio
import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/app")

import numpy as np
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings
from app.models.member import Member
from app.models.member_voice_history import MemberVoiceHistory
from app.services.file_service import file_service
from app.services.audio_processor import audio_processor
from app.services.voiceprint_service import voiceprint_service


# 用户确定的 4 段高质量样本
ZHANG_FINAL_SEGMENTS = [
    (9.99, 16.61, "段4: 在此方案中加入主要设备功率..."),
    (32.29, 34.65, "段10: 一边使用8小时"),
    (35.20, 40.48, "段11: 六方抽氧功率4.5千瓦..."),
    (41.12, 43.10, "段12: 设备是情况使用"),
]


async def main():
    engine = create_async_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
        poolclass=NullPool,
    )
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # ========== 步骤 1: 备份当前 5 段状态 ==========
    async with sf() as db:
        r = await db.execute(select(Member).where(Member.name == "张宏魁"))
        zhang = r.scalar_one()
        zhang_id = zhang.id
        old_state = {
            "member_id": zhang_id,
            "name": zhang.name,
            "voice_embedding": zhang.voice_embedding.tolist() if zhang.voice_embedding is not None else None,
            "voice_sample_count": zhang.voice_sample_count,
            "voice_enrolled_at": str(zhang.voice_enrolled_at) if zhang.voice_enrolled_at else None,
            "voice_confirmed_at": str(zhang.voice_confirmed_at) if zhang.voice_confirmed_at else None,
            "voice_confirmed_by": zhang.voice_confirmed_by,
            "voice_confirmed_meeting_id": zhang.voice_confirmed_meeting_id,
            "backup_time": datetime.now(timezone.utc).isoformat(),
            "reason": "5 段 → 4 段, 去掉段 1 (0.95s 噪声), 用户确定不再改变",
        }
        with open("/tmp/zhang_v2_5seg_backup.json", "w", encoding="utf-8") as f:
            json.dump(old_state, f, ensure_ascii=False, indent=2)
        print(f"步骤1: 备份当前 5 段状态 → /tmp/zhang_v2_5seg_backup.json")
        print(f"  old samples={old_state['voice_sample_count']}, emb_dim={len(old_state['voice_embedding']) if old_state['voice_embedding'] else 0}")

    # ========== 步骤 2: 下载 #167 音频 + VAD 分段 ==========
    print("步骤2: 下载 #167 音频")
    audio = await file_service.download_file("recordings/23fa1b5ccd90459ea418c41e877382fc.webm")
    pcm, segments, sr = await audio_processor.convert_and_segment(audio)
    print(f"  VAD 段数: {len(segments)}, 总时长: {len(pcm)/sr:.2f}s")

    # ========== 步骤 3: 提取 4 段 embedding ==========
    print("步骤3: 提取 4 段高质量 embedding (不含段 1)")
    embeddings = []
    weights = []
    for s, e, desc in ZHANG_FINAL_SEGMENTS:
        seg_pcm = pcm[int(s*sr):int(e*sr)]
        dur = len(seg_pcm)/sr
        # 加权 (短段用 0.95 上限, 长段用 3.0 上限, 避免单段主导)
        weight = min(dur, 3.0)
        emb = voiceprint_service.extract_embedding(seg_pcm)
        if emb is None or len(emb) != 192:
            print(f"  X {desc}: 提取失败")
            continue
        norm = np.linalg.norm(emb)
        if norm < 1e-6:
            print(f"  X {desc}: 零向量")
            continue
        emb_norm = emb / norm
        embeddings.append(emb_norm)
        weights.append(weight)
        print(f"  OK {desc}: dur={dur:.2f}s, weight={weight:.2f}, norm={norm:.4f}")

    if not embeddings:
        print("FATAL: 无有效 embedding")
        return

    embeddings = np.array(embeddings)
    weights = np.array(weights)
    weighted_avg = np.average(embeddings, axis=0, weights=weights)
    weighted_avg = weighted_avg / np.linalg.norm(weighted_avg)
    new_emb_list = weighted_avg.tolist()
    print(f"  加权平均 {len(embeddings)} 段, L2 norm={np.linalg.norm(weighted_avg):.4f}")

    # ========== 步骤 4: 写新声纹 + history audit + confirmed_at ==========
    print("步骤4: 写新声纹 + audit + 用户确认")
    async with sf() as db:
        # 写新声纹 + sample_count=4 + voice_confirmed_at=now (用户最终确认)
        await db.execute(
            update(Member)
            .where(Member.id == zhang_id)
            .values(
                voice_embedding=new_emb_list,
                voice_sample_count=4,
                voice_enrolled_at=datetime.now(timezone.utc).replace(tzinfo=None),
                voice_confirmed_at=datetime.now(timezone.utc).replace(tzinfo=None),
                voice_confirmed_by="20",  # 张宏魁自己 (用户说"确定"作为成员自己确认, member.id=20)
                voice_confirmed_meeting_id=167,
            )
        )
        await db.commit()
        print(f"  张宏魁: 5→4 samples, voice_confirmed_at=now (永久锁定)")

        # 写 history audit
        hist = MemberVoiceHistory(
            member_id=zhang_id,
            source="user_final_decision",
            old_embedding=old_state["voice_embedding"],
            new_embedding=new_emb_list,
            sample_count_before=old_state["voice_sample_count"],
            sample_count_after=4,
            weight=None,
            notes=(
                "用户 2026-06-30 最终决策: 4 段高质量样本 (段 4/10/11/12, "
                "总 ~16.24s, max=6.62s, cos_dist 0.062-0.163) 作为张宏魁真实声纹. "
                "删除段 1 (0.95s, conf 0.361 噪声). 之前所有声纹历史 (history_id 3/28/46) "
                "保留作 audit trail. 用户明确说'确定不再改变' → voice_confirmed_at=now, "
                "voice_confirmed_by=张宏魁自身, voice_confirmed_meeting_id=167."
            ),
        )
        db.add(hist)
        await db.commit()
        await db.refresh(hist)
        print(f"  history_id={hist.id} audit 完成")

    # ========== 步骤 5: 验证 4/4 自洽 ==========
    print("步骤5: 验证 4/4 自洽性")
    async with sf() as db:
        r = await db.execute(select(Member).where(Member.name == "张宏魁"))
        zhang = r.scalar_one()
        final_emb = np.array(zhang.voice_embedding, dtype=np.float32)
        final_emb_norm = final_emb / np.linalg.norm(final_emb)
        print(f"  张宏魁新声纹: samples={zhang.voice_sample_count}, confirmed_at={zhang.voice_confirmed_at}")

    audio = await file_service.download_file("recordings/23fa1b5ccd90459ea418c41e877382fc.webm")
    pcm, segments, sr = await audio_processor.convert_and_segment(audio)

    print()
    print("  4 段最终样本验证 (应被识别为张宏魁):")
    correct = 0
    total = 0
    async with sf() as db:
        for s, e, desc in ZHANG_FINAL_SEGMENTS:
            seg_pcm = pcm[int(s*sr):int(e*sr)]
            dur = len(seg_pcm)/sr
            name, mid, conf = await voiceprint_service.identify_speaker(db, seg_pcm)
            ok = name == "张宏魁"
            mark = "OK" if ok else "X"
            print(f"    {mark} {desc}: ({dur:.2f}s) -> {name} conf={conf:.3f}")
            total += 1
            if ok:
                correct += 1

    print()
    print(f"=== 结果: {correct}/{total} PASS ===")
    if correct == total:
        print("=== 张宏魁声纹最终确定 (4 段高质量, 永久锁定) ===")
    else:
        print(f"=== FAIL: {total-correct} 段未识别为张宏魁 ===")


if __name__ == "__main__":
    asyncio.run(main())