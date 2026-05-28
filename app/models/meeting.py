from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, ARRAY
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Meeting(Base, TimestampMixin):
    """会议模型"""
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text)

    # 时间信息
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)

    # 会议信息
    location = Column(String(200))  # 会议地点
    meeting_url = Column(String(500))  # 腾讯会议链接
    meeting_id = Column(String(100))  # 腾讯会议ID

    # 转写和纪要
    transcript = Column(JSON)  # 实时转写内容
    summary = Column(Text)  # 会议摘要
    key_points = Column(ARRAY(String))  # 讨论要点
    decisions = Column(ARRAY(String))  # 决议事项

    # 发言者分析
    speaker_mapping = Column(JSON)  # 发言者映射 {"原始标签": "真实姓名"}
    speaker_stats = Column(JSON)  # 发言者统计 [{"name":"...", "turn_count":N, ...}]

    # 状态
    status = Column(String(20), default="scheduled")  # scheduled/recording/completed

    # 创建者
    created_by = Column(Integer, ForeignKey("members.id"))

    # 关系
    creator = relationship("Member", back_populates="created_meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting")
    tasks = relationship("Task", backref="meeting")

    def __repr__(self):
        return f"<Meeting(id={self.id}, title='{self.title}')>"


class MeetingParticipant(Base):
    """会议参与者"""
    __tablename__ = "meeting_participants"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), default="participant")  # host/presenter/participant

    meeting = relationship("Meeting", back_populates="participants")
    member = relationship("Member")
