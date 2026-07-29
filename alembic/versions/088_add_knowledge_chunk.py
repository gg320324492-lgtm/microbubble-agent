"""add knowledge_chunk 子表 (PR2 W88 +9)

PR2 Knowledge 子表:
- 1 parent → N chunks (1.5x ≤ N ≤ 6x)
- chunk 行数门禁: 召回 P95 ≤ 80ms (10w chunk), FK 100% 完整, qa-bench ≥ 94%

idempotent guard (沿用 087 模式):
- CREATE TABLE IF NOT EXISTS knowledge_chunks (...)
- CREATE INDEX IF NOT EXISTS 包裹每个 index
- DO $$ ... IF NOT EXISTS 包裹列添加（无, 表为新表）
- 重跑迁移必须幂等 (alembic upgrade head 重放验证)

down_revision 接续关系 (派工 v11 段 1):
- 接 ('087_add_knowledge_original_parent_id',)
- 087 = W85 hotfix (alembic head W85-87)

Revision ID: 088_add_knowledge_chunk
Revises: 087_add_knowledge_original_parent_id
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy.vector import Vector


# revision identifiers, used by Alembic.
revision = "088_add_knowledge_chunk"
down_revision = "087_add_knowledge_original_parent_id"
branch_labels = None
depends_on = None


def upgrade():
    # 1. CREATE TABLE IF NOT EXISTS knowledge_chunks (idempotent guard)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_chunks (
            id SERIAL PRIMARY KEY,
            knowledge_id INTEGER NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1024),
            char_start INTEGER NOT NULL,
            char_end INTEGER NOT NULL,
            char_count INTEGER NOT NULL,
            strategy VARCHAR(20) NOT NULL DEFAULT 'paragraph',
            chunk_metadata JSONB,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        );
    """
    )

    # 2. Index ix_knowledge_chunks_kid (FK 自动 + 加速按 parent 过滤)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_kid "
        "ON knowledge_chunks (knowledge_id);"
    )

    # 3. UniqueConstraint uq_knowledge_chunks_kid_chunk_index (idempotent 重新加)
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'uq_knowledge_chunks_kid_chunk_index') THEN "
        "ALTER TABLE knowledge_chunks "
        "ADD CONSTRAINT uq_knowledge_chunks_kid_chunk_index "
        "UNIQUE (knowledge_id, chunk_index); "
        "END IF; END$$;"
    )

    # 4. Index ix_knowledge_chunks_kid_strategy (按策略过滤)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_kid_strategy "
        "ON knowledge_chunks (knowledge_id, strategy);"
    )

    # 5. CheckConstraint ck_knowledge_chunks_char_range
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_knowledge_chunks_char_range') THEN "
        "ALTER TABLE knowledge_chunks "
        "ADD CONSTRAINT ck_knowledge_chunks_char_range "
        "CHECK (char_start >= 0 AND char_end > char_start); "
        "END IF; END$$;"
    )

    # 6. CheckConstraint ck_knowledge_chunks_char_count
    op.execute(
        "DO $$ BEGIN "
        "IF NOT EXISTS (SELECT 1 FROM pg_constraint "
        "WHERE conname = 'ck_knowledge_chunks_char_count') THEN "
        "ALTER TABLE knowledge_chunks "
        "ADD CONSTRAINT ck_knowledge_chunks_char_count "
        "CHECK (char_count > 0 AND char_count = char_end - char_start); "
        "END IF; END$$;"
    )

    # 7. HNSW index for embedding (pgvector, 与 knowledge 表一致)
    # 走 vector_cosine_ops (与知识表 embedding 列一致)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops);"
    )


def downgrade():
    # DROP TABLE 自动级联所有 index + constraint + FK (CASCADE)
    op.execute("DROP TABLE IF EXISTS knowledge_chunks CASCADE;")