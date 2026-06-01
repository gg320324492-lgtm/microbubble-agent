"""声纹识别置信度历史表"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class VoiceprintHistory(Base, TimestampMixin):
    """每次声纹识别 → 一行历史（per meeting_id + member_id）"""
    __tablename__ = "voiceprint_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    recorded_at = Column(DateTime(timezone=True), nullable=False)

    meeting = relationship("Meeting", back_populates="voiceprint_history")
    member = relationship("Member")

    __table_args__ = (
        Index("idx_voiceprint_history_meeting_member", "meeting_id", "member_id"),
    )
