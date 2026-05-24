from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Reminder(Base, TimestampMixin):
    """提醒模型"""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)

    # 提醒时间
    remind_at = Column(DateTime, nullable=False)

    # 提醒类型
    remind_type = Column(String(20), default="wechat")  # wechat/email/sms

    # 状态
    status = Column(String(20), default="pending")  # pending/sent/cancelled

    # 发送时间
    sent_at = Column(DateTime)

    # 关系
    task = relationship("Task", back_populates="reminders")

    def __repr__(self):
        return f"<Reminder(id={self.id}, task_id={self.task_id})>"
