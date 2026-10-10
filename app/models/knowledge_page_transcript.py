"""PPT/文档**整页**视觉转写模型 (迁移 144, 2026-10-10 agent44)

## 为什么独立成表, 而不是复用 ``knowledge_images`` 或 ``knowledge_chunks``

- ``knowledge_images``: 语义是「文档里抽出的某张**图**」(figure_type /
  is_core_figure / section_hint / anchor_paragraph_index / visual_summary 全是
  图表级字段, 前端 RightImageRail 按 figure_no 渲染), 且 ``image_url`` NOT NULL
  —— 整页转写没有图片 URL, 塞进去只能造假, 还会污染既有 5446 行。
- ``knowledge_chunks``: CHECK 约束 (char_end > char_start 且
  char_count = char_end - char_start) 把每条 chunk 钉在 ``parent.content`` 的
  精确切片上。整页转写正文不在孪生行 content 里, 塞进去得改写 parent.content,
  连带作废该 parent 已有的 chunk 与 embedding。

详见迁移 144 的 docstring (含 dry-run 实测数据)。

## knowledge_id 指向 **kb 孪生行**, 不是 drive 行

``drive_to_kb_service`` 建的孪生行带 ``meta->>'drive_source_file_id'``,
且是 ``storage_mode='kb'``。295 个 drive 文件 100% 有且仅有 1 个孪生行,
全部 ``deleted_at IS NULL`` + ``visibility IN ('team','public')``。
指向孪生行的直接收益: ``multimodal_retriever`` 的 ``storage_mode == 'kb'``
硬过滤一行都不用改, 既有第 5 路的 5446 行候选池不受任何影响。

## blocked 行: 有 metadata, 无正文

``content IS NULL`` + ``block_reasons`` / ``chrome_ratio``, 供人工复核。
``ck_kpt_blocked_no_body`` 把这个不变量钉在数据库层。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgePageTranscript(Base, TimestampMixin):
    """一篇文档一页的整页视觉转写 (含 blocked 的 metadata-only 行)。"""

    __tablename__ = "knowledge_page_transcripts"

    id = Column(Integer, primary_key=True, index=True)

    #: 指向 kb 孪生行 (storage_mode='kb')。孪生行删除时级联清理。
    knowledge_id = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: 溯源: 产出该页转写的 drive 文件行 id (knowledge.storage_mode='drive')
    source_drive_file_id = Column(Integer, nullable=True)

    #: 页码 / 幻灯片序号, 从 1 起
    page_number = Column(Integer, nullable=False)

    #: 净化后正文 = page_transcript_filter.filter_page_transcript(...).text
    #: blocked 行恒为 None (metadata-only)
    content = Column(Text, nullable=True)
    char_count = Column(Integer, nullable=True)

    #: blocked 判定溯源 (人工复核用)
    blocked = Column(Boolean, nullable=False, default=False, server_default="false")
    block_reasons = Column(JSONB, nullable=True)
    chrome_ratio = Column(Float, nullable=True)

    #: A/B/C/D 字符分类 (agent43 pipeline 口径, 仅统计用)
    a_chars = Column(Integer, nullable=True)
    b_chars = Column(Integer, nullable=True)
    c_chars = Column(Integer, nullable=True)
    d_chars = Column(Integer, nullable=True)

    #: 冗余文件名, 便于人工复核时不 JOIN
    file_name = Column(String(300), nullable=True)

    #: 转写产出批次标识
    ingest_batch = Column(String(60), nullable=True)

    #: 净化后正文的向量 (Qwen3-Embedding-0.6B, 1024d)
    embedding = Column(Vector(1024), nullable=True)

    knowledge = relationship("Knowledge", lazy="selectin")

    __table_args__ = (
        UniqueConstraint(
            "knowledge_id", "page_number", name="uq_kpt_knowledge_page",
        ),
        Index("idx_kpt_kb_page", "knowledge_id", "page_number"),
        Index("idx_kpt_blocked", "blocked"),
        Index("idx_kpt_source_drive", "source_drive_file_id"),
        CheckConstraint(
            "(blocked = TRUE AND content IS NULL) OR "
            "(blocked = FALSE AND content IS NOT NULL AND char_count > 0)",
            name="ck_kpt_blocked_no_body",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<KnowledgePageTranscript(id={self.id}, knowledge_id={self.knowledge_id}, "
            f"page={self.page_number}, blocked={self.blocked}, "
            f"chars={self.char_count})>"
        )


__all__ = ["KnowledgePageTranscript"]
