"""v2026-06-29: meeting_templates 加 cloned_from_id 字段 (v77 P2.6-F.5 复制追溯)

Revision ID: 038_tpl_cloned_from
Revises: 037_knowledge_meta_jsonb
Create Date: 2026-06-29

背景:
- v77 P2.6-F.5 builtin "一键复制为自定义" 需要追溯 "哪个 builtin 派生"
- 现有 meeting_templates 表无复制来源字段
- 决策: 加 nullable self-FK, NULL = 原始 builtin, 非 NULL = 从 builtin 派生的 custom

新增字段:
- cloned_from_id: Integer, FK meeting_templates.id (ON DELETE SET NULL), nullable, indexed
  - nullable: 旧 builtin 模板 NULL = "原始 builtin" 语义
  - self-FK: SQLAlchemy 标准模式, 支持级联删除
  - indexed: 未来"按 builtin 统计派生链"查询性能

幂等: add_column 默认 nullable=True 不需要 IF NOT EXISTS (新列本来就不存在)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "038_tpl_cloned_from"
down_revision: Union[str, None] = "037_knowledge_meta_jsonb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meeting_templates",
        sa.Column("cloned_from_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_meeting_templates_cloned_from",
        "meeting_templates", "meeting_templates",
        ["cloned_from_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_meeting_templates_cloned_from",
        "meeting_templates",
        ["cloned_from_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_meeting_templates_cloned_from", table_name="meeting_templates")
    op.drop_constraint(
        "fk_meeting_templates_cloned_from",
        "meeting_templates",
        type_="foreignkey",
    )
    op.drop_column("meeting_templates", "cloned_from_id")
