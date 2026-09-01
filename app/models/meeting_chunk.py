"""MeetingChunk model — 会议转录 chunk 级索引 (WP1, 2026-09-02)

会议转录入 RAG 的 chunk 存储 (迁移 130):
- 一场会议 → N 个转录文本窗口 (含【speaker】前缀, 已清洗 EMO 标签)
- embedding vector(1024) 供 hybrid_retriever meetings 路向量召回
- start_sec/end_sec/speakers 保留时间窗与说话人, 供引用与深读定位
"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class MeetingChunk(Base, TimestampMixin):
    """会议转录 chunk — hybrid_retriever meetings 路召回单元"""

    __tablename__ = "meeting_chunks"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(
        Integer,
        ForeignKey("meetings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)
    start_sec = Column(Float, nullable=True)
    end_sec = Column(Float, nullable=True)
    speakers = Column(String(500), nullable=True)  # 逗号拼接的说话人列表
    chunk_metadata = Column(JSONB, nullable=True)

    __table_args__ = (
        UniqueConstraint("meeting_id", "chunk_index", name="uq_meeting_chunks_meeting_idx"),
    )
