"""KnowledgeChunk 模型 — PR2 Knowledge 子表 (W88 +8)

设计 (RAG 工业级 v1.1 §3.2 PR2):
- 父表: knowledge (id, content, embedding Vector(1024), ...)
- 子表: knowledge_chunk (id, knowledge_id FK CASCADE, chunk_index, content, embedding Vector(1024), char_start, char_end, created_at, updated_at)
- parent-child 召回: parent 提供上下文 window, chunk 走精确向量检索
- chunk 行数 ∈ [parent×1.5, parent×6] (门禁 a)
- 召回 P95 ≤ 80ms (10w chunk, 门禁 b)
- parent_id FK 100% 完整 (门禁 c)
- qa-bench PASS ≥ 94% (门禁 d)

字段:
- knowledge_id: FK → knowledge.id ON DELETE CASCADE, NOT NULL, index
- chunk_index: 在 parent 内序号 (0,1,2...), 唯一 (knowledge_id, chunk_index)
- content: chunk 原文 (paragraph/heading/window 策略之一)
- embedding: Vector(1024), nullable（重算期间可能暂空）
- char_start/char_end: 在 parent.content 中的位置 (用于召回时拼上下文 window)
- char_count: 派生字段 (== len(content)), 方便巡检
- strategy: 'paragraph' | 'heading' | 'window' (PR2 强制可配置, 后续 PR4 复用)
- chunk_metadata: JSONB, {parent_length, overlap, section_title?, ...}
- created_at / updated_at: TimestampMixin

idempotent guard (alembic 088): CREATE TABLE IF NOT EXISTS + CREATE INDEX IF NOT EXISTS
"""
from sqlalchemy import (
    Column, Integer, String, Text, ForeignKey, DateTime, Index, CheckConstraint, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgeChunk(Base, TimestampMixin):
    """知识条目 chunk 子表 — parent-child retrieval (PR2)

    与 Knowledge 关系:
    - knowledge_id FK CASCADE: parent 删除时所有 chunk 自动清理
    - 1 个 parent → N 个 chunk (1.5x ≤ N ≤ 6x)
    - chunk.embedding 独立计算, parent.embedding 仍保留 (作为 fallback)
    - 召回时按 chunk 命中, 用 char_start/char_end 从 parent.content 拼上下文

    策略 (PR2 §11.2 chunking_service):
    - 'paragraph' 默认 (按 \\n\\n 切)
    - 'heading' (按 Markdown #/##/### 切)
    - 'window' (固定字符窗口 + overlap)
    """
    __tablename__ = "knowledge_chunks"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index = Column(Integer, nullable=False)  # 在 parent 内序号 0,1,2,...

    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)

    # 位置元数据 — 召回时拼上下文 window 用
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    char_count = Column(Integer, nullable=False)  # == char_end - char_start

    # chunking 策略 (可配置)
    strategy = Column(String(20), nullable=False, server_default="paragraph")

    # 额外元数据 (section_title, overlap_chars, ...)
    chunk_metadata = Column(JSONB, nullable=True)

    # unique (knowledge_id, chunk_index) — 防止同一 parent 重复 chunk_index
    __table_args__ = (
        UniqueConstraint(
            "knowledge_id", "chunk_index",
            name="uq_knowledge_chunks_kid_chunk_index",
        ),
        Index(
            "ix_knowledge_chunks_kid_strategy",
            "knowledge_id", "strategy",
        ),
        CheckConstraint(
            "char_start >= 0 AND char_end > char_start",
            name="ck_knowledge_chunks_char_range",
        ),
        CheckConstraint(
            "char_count > 0 AND char_count = char_end - char_start",
            name="ck_knowledge_chunks_char_count",
        ),
    )

    def __repr__(self):
        return (
            f"<KnowledgeChunk(id={self.id}, knowledge_id={self.knowledge_id}, "
            f"chunk_index={self.chunk_index}, strategy='{self.strategy}', "
            f"chars={self.char_count})>"
        )