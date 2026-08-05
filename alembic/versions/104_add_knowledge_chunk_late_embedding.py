"""Add late-chunking multi-vector storage to knowledge_chunks.

Revision: 104_add_knowledge_chunk_late_embedding
Revises: 103_add_embedding_model_version
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

revision = "104_add_knowledge_chunk_late_embedding"
down_revision = "099_add_dft_jobs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_chunks",
        sa.Column("chunk_embedding", ARRAY(Vector(1024)), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_chunks", "chunk_embedding")
