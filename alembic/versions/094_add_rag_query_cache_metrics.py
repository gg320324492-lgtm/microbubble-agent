"""add rag query cache metrics

Revision ID: 094_add_rag_query_cache_metrics
Revises: 093_add_search_log_answer_rating
Create Date: 2026-08-02

W99-RAG-1 W99 +20..+23 Query Cache 结果层 (commit 4/6)

新增 2 个 nullable 列到 search_logs:
  - cache_hit: Integer(0/1) — 是否命中 query cache (精确 / 语义相似)
  - cache_similarity: Float — 语义相似命中 cosine 值, 精确命中 1.0

W93 PR7 B-7 模式沿用:
  - 仅 ADD COLUMN nullable=True (老数据兼容)
  - 不动老字段
  - 不写 alembic 已有迁移

W92 alembic 串单链纪律:
  - down_revision 必须明确写 093_add_search_log_answer_rating
  - merge 后必 verify 1 head
"""
from alembic import op
import sqlalchemy as sa

revision = "094_add_rag_query_cache_metrics"
down_revision = "093_add_search_log_answer_rating"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """新增 query cache 监控字段 (2 列, nullable=True)"""
    op.add_column(
        "search_logs",
        sa.Column("cache_hit", sa.Integer(), nullable=True),
    )
    op.add_column(
        "search_logs",
        sa.Column("cache_similarity", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    """回滚 (W99-RAG-1 据实, 严格按 upgrade 逆序)"""
    op.drop_column("search_logs", "cache_similarity")
    op.drop_column("search_logs", "cache_hit")
