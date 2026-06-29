"""v2026-06-29: knowledge 加 meta JSONB 列 (#043 自动拓展)

Revision ID: 037_knowledge_meta_jsonb
Revises: 036_add_voice_confirmed
Create Date: 2026-06-29

背景:
- #043 自动拓展功能需要存 RichBlock 数据 + qa-bench 元信息
- 现有 Knowledge 表无 meta 字段
- entities JSONB 已被知识图谱服务占用, 不能复用

新增字段:
- meta: JSONB, nullable, 存自动拓展条目的 RichBlock 数据 + qa-bench 元信息
  (qa_id / intent / scope / score / tool_calls / rich_blocks)

幂等: IF NOT EXISTS
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "037_knowledge_meta_jsonb"
down_revision: Union[str, None] = "036_add_voice_confirmed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge",
        sa.Column("meta", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge", "meta")