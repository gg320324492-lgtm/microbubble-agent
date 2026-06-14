from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


class Reminder(Base, TimestampMixin):
    """提醒模型"""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True)

    # 提醒时间
    remind_at = Column(DateTime, nullable=False)

    # 提醒类型
    remind_type = Column(String(20), default="wechat")  # wechat/email/sms

    # 状态
    status = Column(String(20), default="pending")  # pending/sent/cancelled/acknowledged

    # 发送时间
    sent_at = Column(DateTime)

    # Wave 3a
    target_type = Column(String(20), default='task')  # 'task' | 'meeting'
    meeting_id = Column(Integer, nullable=True)  # 关联 meeting

    # 2026-06-15 提醒策略 v2：ack/snooze 状态机
    acknowledged_at = Column(DateTime, nullable=True)  # 用户"收到"时间
    acknowledged_by = Column(
        Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )  # 哪个成员 ack
    ack_channel = Column(String(20), nullable=True)  # wechat / web / api
    snoozed_until = Column(DateTime, nullable=True)  # "今天别提醒"后推迟到的实际发送时间
    reminder_batch_date = Column(String(10), nullable=True)  # 11AM 批次日期 YYYY-MM-DD（北京）
    policy_version = Column(Integer, nullable=False, default=2)  # v1=旧/v2=新 11AM

    # 关系
    task = relationship("Task", back_populates="reminders")

    def __repr__(self):
        return f"<Reminder(id={self.id}, task_id={self.task_id})>"
