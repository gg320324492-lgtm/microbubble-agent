from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, ARRAY, Boolean, Float, BigInteger
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

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
    transcript_polished = Column(JSON)  # 2026-06-02 L3 全文精润色结果（hangup 后 Claude Sonnet 全文润色）
    summary = Column(Text)  # 会议摘要

    # 2026-06-27 P2-2: cluster_id 注入历史（便于 rollback 工具按时间戳回溯）
    # 结构: [{ts, source, injector, n_segments, kmeans_k, cluster_to_name, notes}, ...]
    # source: "inject_083" | "reprocess_meeting" | "purify" | "rollback"
    cluster_id_history = Column(JSON, nullable=True, default=list)
    key_points = Column(ARRAY(String))  # 讨论要点
    decisions = Column(ARRAY(String))  # 决议事项

    # 发言者分析
    speaker_mapping = Column(JSON)  # 发言者映射 {"原始标签": "真实姓名"}
    speaker_stats = Column(JSON)  # 发言者统计 [{"name":"...", "turn_count":N, ...}]

    # 状态
    status = Column(String(20), default="scheduled")  # scheduled/recording/processing/completed/error

    # 阶段 3：分片上传状态机（2026-06-12 防御机制）
    upload_status = Column(String(20), default="pending")  # pending/uploading/completed/failed/never_uploaded/partial
    last_chunk_index = Column(Integer, nullable=True)  # -1 表示无 chunk，>=0 表示收到的最大 idx
    total_chunks = Column(Integer, nullable=True)  # 累计收到的 chunk 数（含未上传的）
    error_reason = Column(Text, nullable=True)  # 录音失败 / 孤儿清理原因

    # 录音机模式（2026-06-04 重构）
    audio_url = Column(String(500), nullable=True)           # MinIO 录音路径
    audio_duration = Column(Integer, nullable=True)           # 录音时长（秒）
    recording_started_at = Column(DateTime, nullable=True)    # 开始听会时间
    recording_ended_at = Column(DateTime, nullable=True)      # 结束听会时间

    # 2026-07-12 死代码清理: 删 5 个 audio_archive_* 列 (audio_archive_service.py 孤儿, 列 write-only)
    # alembic 059_drop_audio_archive_columns.py DROP COLUMN IF EXISTS

    # Wave 3a: 跨会议关联
    agenda = Column(JSON, nullable=True)
    # 向量嵌入 (pgvector Vector(1024), v29 Qwen3-Embedding-0.6B, A/B baseline 验证完成)
    embedding = Column(Vector(1024), nullable=True)
    related_meeting_ids = Column(JSON, nullable=True)

    # 汇报人员（可多选，存为 JSON 数组）
    presenter_ids = Column(JSON)

    # 创建者
    created_by = Column(Integer, ForeignKey("members.id"))

    # 关系
    creator = relationship("Member", back_populates="created_meetings")
    participants = relationship("MeetingParticipant", back_populates="meeting")
    tasks = relationship("Task", backref="meeting")
    voiceprint_history = relationship(
        "VoiceprintHistory",
        back_populates="meeting",
        cascade="all, delete-orphan",
    )

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

    @property
    def name(self):
        return self.member.name if self.member else ""

    @property
    def avatar(self):
        return self.member.avatar if self.member else None
