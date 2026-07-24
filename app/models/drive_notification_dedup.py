"""Rows used to suppress duplicate combined Drive notifications."""
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, text
from app.core.database import Base

class DriveNotificationDedup(Base):
    __tablename__ = "drive_notification_dedup"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    comment_id = Column(Integer, nullable=False, index=True)
    actions_hash = Column(String(64), nullable=False)
    sent_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    __table_args__ = (UniqueConstraint("user_id", "comment_id", "actions_hash", name="uq_drive_notification_dedup"),)
