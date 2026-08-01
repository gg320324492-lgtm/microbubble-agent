"""add rag citation metrics

Revision ID: 095_add_rag_citation_metrics
Revises: 094_add_rag_query_cache_metrics
Create Date: 2026-08-02

W99-RAG-2 W99 +10 Citation 段落级溯源 (commit 5/6)

新增 1 个 nullable 列到 search_logs:
  - citation_count: Integer — 本次召回生成的 citation 数

W93 PR7 B-7 / W99-RAG-1 模式沿用:
  - 仅 ADD COLUMN nullable=True (老数据兼容)
  - 不动老字段
  - 不写 alembic 已有迁移

W92 alembic 串单链纪律:
  - down_revision 必须明确写 094_add_rag_query_cache_metrics
  - merge 后必 verify 1 head (单链 093 → 094 → 095)
"""
from alembic import op
import sqlalchemy as sa

revision = "095_add_rag_citation_metrics"
down_revision = "094_add_rag_query_cache_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 citation 监控字段 (1 列, nullable=True)"""
    op.add_column(
        "search_logs",
        sa.Column("citation_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """回滚 (W99-RAG-2 据实, 严格按 upgrade 逆序)"""
    op.drop_column("search_logs", "citation_count")
