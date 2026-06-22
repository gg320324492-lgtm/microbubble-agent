"""v28 step 105: 论文版面分析 Layout 表（vision model 扫描整篇论文输出）

新增 1 张表 knowledge_layouts:
- knowledge_id: 关联知识条目（unique）
- page_layout: JSONB，整篇论文每页的 blocks 数组
- total_pages / total_blocks: 统计
- vision_model_used: vision 模型名
- vision_analyzed_at: 扫描时间戳
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "029_kb_layout"
down_revision: Union[str, None] = "028_figure_structured"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_layouts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_id", sa.Integer(), sa.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("page_layout", JSONB(), nullable=False),
        sa.Column("total_pages", sa.Integer(), nullable=True),
        sa.Column("total_blocks", sa.Integer(), nullable=True),
        sa.Column("vision_model_used", sa.String(length=100), nullable=True),
        sa.Column("vision_analyzed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_knowledge_layout_kb", "knowledge_layouts", ["knowledge_id"])


def downgrade() -> None:
    op.drop_index("idx_knowledge_layout_kb", table_name="knowledge_layouts")
    op.drop_table("knowledge_layouts")