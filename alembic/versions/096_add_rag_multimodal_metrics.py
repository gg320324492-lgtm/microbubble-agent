"""add rag multimodal metrics

Revision ID: 096_add_rag_multimodal_metrics
Revises: 095_add_rag_citation_metrics
Create Date: 2026-08-02

W100-RAG-5 Multimodal Retriever 第 5 路 metrics.
"""
from alembic import op
import sqlalchemy as sa

revision = "096_add_rag_multimodal_metrics"
down_revision = "095_add_rag_citation_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "search_logs",
        sa.Column("image_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("search_logs", "image_score")
