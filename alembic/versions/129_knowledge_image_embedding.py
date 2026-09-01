"""knowledge_images 加 embedding 列 — WP5 多模态第 5 路向量持久化 (2026-09-01)

此前 multimodal_retriever 每次 query 对全部 OCR 文本实时重算 candidate embedding
(无持久化列) → 图多了直接拖垮每次检索。本迁移加 vector(1024) 列 + HNSW 索引,
写入侧 (search_images + backfill 脚本) 只对 embedding IS NULL 的候选实时算并回填。

Revision ID: 129_knowledge_image_embedding
Revises: 128_research_workspace
Create Date: 2026-09-01
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "129_knowledge_image_embedding"
down_revision = "128_research_workspace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 加列 (幂等)
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='knowledge_images' AND column_name='embedding'
            ) THEN
                ALTER TABLE knowledge_images
                    ADD COLUMN embedding vector(1024);
            END IF;
        END $$;
        """
    )
    # 2. HNSW 索引 (幂等; vector_cosine_ops 与 vector 列类型匹配 — 类 20.162)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_images_embedding_hnsw
        ON knowledge_images USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_knowledge_images_embedding_hnsw"
    )
    op.execute(
        "ALTER TABLE knowledge_images DROP COLUMN IF EXISTS embedding"
    )
