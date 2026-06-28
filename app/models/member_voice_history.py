"""成员声纹 embedding 历史（每次主动录入的 audit trail）

未来反推公式: emb_N = ((N+1) * emb_{N+1} - emb_new) / N

设计动机:
- 2026-06-19 之前 auto-learn 因 batch bug 97% 静默失败
- 2026-06-19 修复后 auto-learn 开始生效，但污染会议 151 等
- 2026-06-27 用户决策永久禁用 auto-learn
- 为支持未来"反推原始手工录入 embedding"，需要 audit 表记录每次录入的 old/new
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey, Index
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

from app.core.database import Base


class MemberVoiceHistory(Base):
    """成员声纹 embedding 历史表

    source:
      - "manual_enroll": 用户主动录入（enroll_member 流程）
      - "recover": 通过反推公式恢复的原始 embedding
      - "recover_from_meeting": 通过会议音频重建（v2026-06-27 新增）
      - "reset": 管理员手动重置
    """
    __tablename__ = "member_voice_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    source = Column(String(20), nullable=False)

    # 录入前的 embedding（首次录入时为 NULL）
    old_embedding = Column(Vector(192), nullable=True)
    # 本次写入后的 embedding
    new_embedding = Column(Vector(192), nullable=False)

    # 加权平均公式的中间状态
    sample_count_before = Column(Integer, nullable=False, server_default="0")
    sample_count_after = Column(Integer, nullable=False)
    # 加权平均权重 old 的（new 的是 1-weight）
    weight = Column(Float, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        Index("idx_member_voice_history_member_created", "member_id", "created_at"),
    )