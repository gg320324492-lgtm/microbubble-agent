"""声纹 embedding 反推工具

v2026-06-27：用户决策永久禁用 auto-learn，但要求支持基于历史记录反推原始手工录入 embedding。

反推公式:
  emb_{N+1} = (N/(N+1)) * emb_N + (1/(N+1)) * emb_new
  → emb_N = ((N+1) * emb_{N+1} - emb_new) / N
  当 N=1 时: emb_0 = 2 * emb_1 - emb_new_1

使用前提: 至少有一次 manual_enroll 写入了 member_voice_history
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.member import Member
from app.models.member_voice_history import MemberVoiceHistory
import logging

logger = logging.getLogger("microbubble.voiceprint_recovery")


async def recover_original_embedding(
    db: AsyncSession, member_id: int
) -> Optional[List[float]]:
    """从 MemberVoiceHistory 反推回原始手工录入的 embedding

    Args:
        db: AsyncSession
        member_id: 成员 ID
    Returns:
        重建的原始 embedding (list of 192 floats) 或 None（无足够历史）
    """
    result = await db.execute(
        select(MemberVoiceHistory)
        .where(MemberVoiceHistory.member_id == member_id)
        .order_by(MemberVoiceHistory.created_at)
    )
    history = result.scalars().all()

    if not history:
        logger.warning(f"member {member_id} 没有 voice history, 无法反推")
        return None

    # 反向迭代：从最新到最旧，每步用反推公式
    # 当前 = history[-1].new_embedding（最新状态），N = sample_count_after
    current = np.array(history[-1].new_embedding, dtype=np.float32)
    current_n = history[-1].sample_count_after

    # 从 history[-2] 倒推到 history[0]
    # 公式: prev_emb = (current_n * current - new_emb_at_t) / n_before
    for t in range(len(history) - 2, -1, -1):
        prev_record = history[t]
        n_before = prev_record.sample_count_before
        new_emb_at_t = np.array(prev_record.new_embedding, dtype=np.float32)
        if n_before == 0:
            return current.tolist()
        prev_emb = (current_n * current - new_emb_at_t) / n_before
        current = prev_emb
        current_n = n_before

    return current.tolist()


async def apply_recovery(db: AsyncSession, member_id: int) -> bool:
    """反推 + 应用（更新 members.voice_embedding 为重建值 + 写 audit）"""
    recovered = await recover_original_embedding(db, member_id)
    if recovered is None:
        return False

    result = await db.execute(select(Member).where(Member.id == member_id))
    member = result.scalar_one_or_none()
    if not member:
        return False

    old_count = member.voice_sample_count or 0
    old_embedding_backup = list(member.voice_embedding) if member.voice_embedding else None

    member.voice_embedding = recovered
    member.voice_sample_count = 1
    member.voice_enrolled_at = datetime.utcnow()

    history = MemberVoiceHistory(
        member_id=member_id,
        source="recover",
        old_embedding=old_embedding_backup,
        new_embedding=recovered,
        sample_count_before=old_count,
        sample_count_after=1,
        weight=None,
        notes=f"Recovered from {old_count} auto-learned samples via reverse formula",
    )
    db.add(history)
    await db.commit()

    logger.info(
        f"member {member_id} 已恢复为原始手工录入 (sample_count: {old_count} → 1, audit 记录)"
    )
    return True