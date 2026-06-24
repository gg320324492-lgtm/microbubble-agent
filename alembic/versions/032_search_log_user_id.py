"""v31.2 检索质量增强: search_logs 加 user_id 列 (可选 auth 归属)

Revision ID: 032_search_log_uid
Revises: 031_search_log
Create Date: 2026-06-25

背景: v31 analytics 后续要做 per-user 聚合 (人均搜索 / 零点击用户数 等),
search_logs 当前无归属列. 匿名用户允许 NULL (前端未登录时仍可上报).

策略: 沿用 019 reminder 模式 (nullable + ondelete=SET NULL), 保留历史数据.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "032_search_log_uid"
down_revision: Union[str, None] = "030_qw3_1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加 user_id 列 (nullable=True 允许匿名, ondelete=SET NULL 保留历史)
    op.add_column(
        "search_logs",
        sa.Column("user_id", sa.Integer(), nullable=True),
    )
    # 2. FK 到 members.id
    op.create_foreign_key(
        "fk_search_logs_user_id",
        "search_logs",
        "members",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 3. 单列索引 (按用户过滤)
    op.create_index(
        "idx_search_logs_user_id",
        "search_logs",
        ["user_id"],
    )
    # 4. 复合索引 (按用户按时段聚合, v31.2 stats 主查询路径)
    op.create_index(
        "idx_search_logs_user_created",
        "search_logs",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_search_logs_user_created", table_name="search_logs")
    op.drop_index("idx_search_logs_user_id", table_name="search_logs")
    op.drop_constraint("fk_search_logs_user_id", "search_logs", type_="foreignkey")
    op.drop_column("search_logs", "user_id")