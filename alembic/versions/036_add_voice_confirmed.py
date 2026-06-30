"""v2026-06-28: members 加 voice_confirmed 字段 (增量 Cross-Anchor 策略)

Revision ID: 036_add_voice_confirmed
Revises: 035_cluster_id_history
Create Date: 2026-06-28

背景:
- 旧 strict pipeline 累积方式导致 #068 cluster_0 14 段被同时累积到陈金薪 + 杜同贺
  → 两人 embedding 互相污染 (cos_dist=0.067)
  → #158 听会时杜同贺本人说话被识别成陈金薪
- 用户决策 (2026-06-28): 改用增量 Cross-Anchor 策略
  - 已确认 (anchor) 的成员 embedding 永不再修改
  - 每次只确认 1 个未 confirmed 成员
  - 听一次会议 → 用 anchor 识别 → 用户确认 cluster 归属 → mark anchor

结构:
- voice_confirmed_at: 用户确认时间 (NULL=未确认, NOT NULL=anchor)
- voice_confirmed_by: 确认者 (用户 username 或 "user")
- voice_confirmed_meeting_id: 哪场会议触发的确认 (audit trail)

索引: 只对已确认成员建索引 (partial index with WHERE NOT NULL)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "036_add_voice_confirmed"
# 2026-06-28: merge 2 branches (031_search_log→032_search_log_uid 和 034→035)
# 两个 branch 都已 deployed 到 prod (alembic heads 显示 2 head revisions)
down_revision: Union[str, None] = ("032_search_log_uid", "035_cluster_id_history")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加 3 列到 members 表
    op.add_column(
        "members",
        sa.Column("voice_confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("voice_confirmed_by", sa.String(50), nullable=True),
    )
    op.add_column(
        "members",
        sa.Column("voice_confirmed_meeting_id", sa.Integer(), nullable=True),
    )

    # 2. partial index: 只索引已确认成员 (anchor 查询加速)
    op.create_index(
        "ix_members_voice_confirmed_at",
        "members",
        ["voice_confirmed_at"],
        postgresql_where=sa.text("voice_confirmed_at IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_members_voice_confirmed_at", table_name="members")
    op.drop_column("members", "voice_confirmed_meeting_id")
    op.drop_column("members", "voice_confirmed_by")
    op.drop_column("members", "voice_confirmed_at")
