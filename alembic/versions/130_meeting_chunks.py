"""meeting_chunks 表 — 会议转录 chunk 级入 RAG (WP1, 2026-09-02)

审计缺口: 会议转录 (22 场, 平均 11.5 万字/场) 从未被索引 — hybrid_retriever
不查 meetings, meeting.embedding 只覆盖摘要且从未接线。本迁移建 chunk 级表,
配合 meeting_chunk_service 提供会议转录的向量召回 (hybrid 第 6 路)。

列设计:
- meeting_id FK CASCADE — 会议删除时 chunk 级联清理
- content: 拼接后的转录文本 (含【speaker】前缀, 已清洗 EMO 标签)
- embedding vector(1024): 与知识库同 embedding 模型, 召回与 RRF 合并同空间
- start_sec / end_sec: 该 chunk 覆盖的转录时间窗 (前端定位/引用用)
- speakers: 该 chunk 涉及的说话人 (逗号拼接)
- chunk_metadata JSONB: 段数等扩展信息

Revision ID: 130_meeting_chunks
Revises: 129_knowledge_image_embedding
Create Date: 2026-09-02
"""
from alembic import op

revision = "130_meeting_chunks"
down_revision = "129_knowledge_image_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS meeting_chunks (
            id SERIAL PRIMARY KEY,
            meeting_id INTEGER NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1024),
            start_sec DOUBLE PRECISION,
            end_sec DOUBLE PRECISION,
            speakers VARCHAR(500),
            chunk_metadata JSONB,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            CONSTRAINT uq_meeting_chunks_meeting_idx UNIQUE (meeting_id, chunk_index)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meeting_chunks_meeting "
        "ON meeting_chunks (meeting_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_meeting_chunks_embedding_hnsw "
        "ON meeting_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS meeting_chunks")
