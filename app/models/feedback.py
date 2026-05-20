"""用户反馈模型"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.core.database import Base
from app.models.base import TimestampMixin


class Feedback(Base, TimestampMixin):
    """用户对 AI 回复的反馈"""
    __tablename__ = "feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    session_id = Column(String(100))
    rating = Column(Integer, nullable=False)  # 1-5
    comment = Column(Text)  # 用户反馈内容
    agent_reply = Column(Text)  # 被评价的 AI 回复内容（截取前500字）

    def __repr__(self):
        return f"<Feedback(id={self.id}, user_id={self.user_id}, rating={self.rating})>"
