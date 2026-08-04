"""SQLAlchemy ORM — 会议处理运行/阶段持久化记录

2026-08-04 Batch B: 持久化阶段状态以替代 1h TTL Redis 丢失,
为后续重跑/质量门/管理面板提供溯源.
"""
from sqlalchemy import (
    Column, BigInteger, Integer, String, DateTime, Text,
    ForeignKey, Boolean, Index,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class MeetingProcessingRun(Base):
    """一次会议处理运行（初次处理或管理员重跑）"""
    __tablename__ = "meeting_processing_runs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(String(64), nullable=True)
    trigger = Column(String(32), nullable=False, default="initial")
    overall_status = Column(String(16), nullable=False, default="running")  # running/success/warning/error
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    requested_stages = Column(JSONB, nullable=True)
    warning_count = Column(Integer, nullable=False, default=0)
    error_summary = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=True)
    pipeline_version = Column(String(32), nullable=True)

    stages = relationship(
        "MeetingProcessingStage",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="MeetingProcessingStage.started_at",
    )

    __table_args__ = (
        Index("idx_meeting_proc_runs_meeting_started", "meeting_id", "started_at"),
        Index("idx_meeting_proc_runs_status", "overall_status", "started_at"),
    )


class MeetingProcessingStage(Base):
    """一次运行中的一个阶段/一次尝试"""
    __tablename__ = "meeting_processing_stages"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    run_id = Column(BigInteger, ForeignKey("meeting_processing_runs.id", ondelete="CASCADE"), nullable=False)
    stage = Column(String(32), nullable=False)
    attempt = Column(Integer, nullable=False, default=1)
    status = Column(String(16), nullable=False, default="started")  # started/success/retry/error/skipped
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    retryable = Column(Boolean, nullable=True)
    error_class = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)
    error_message = Column(Text, nullable=True)
    metrics = Column(JSONB, nullable=True)

    run = relationship("MeetingProcessingRun", back_populates="stages")

    __table_args__ = (
        Index("idx_meeting_proc_stages_run", "run_id", "stage", "attempt"),
    )