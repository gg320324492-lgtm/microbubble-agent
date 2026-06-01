"""会议模板模型"""
from sqlalchemy import Column, Integer, String, Text, JSON, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class MeetingTemplate(Base, TimestampMixin):
    """会议模板（预置 + 用户自定义）"""
    __tablename__ = "meeting_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, index=True)
    title_template = Column(String(200), nullable=True)
    description = Column(Text, nullable=True)
    agenda = Column(JSON, nullable=True)
    default_duration_minutes = Column(Integer, default=60)
    default_participant_ids = Column(JSON, nullable=True)
    default_location = Column(String(200), nullable=True)
    is_builtin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)

    creator = relationship("Member")

    def __repr__(self):
        return f"<MeetingTemplate(id={self.id}, name='{self.name}')>"
