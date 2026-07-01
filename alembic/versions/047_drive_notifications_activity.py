"""v2 PR6: 通知 + @ 提醒 + 活动动态流 + 文件评论

新增 3 张表:
- file_mentions: @ 提醒 (file_id + mentioned_user + context + read_at)
- activity_events: 活动动态流 (actor + action + target_type + target_id + metadata)
- file_comments: 文件评论 (file_id + user_id + content + mentions)

设计要点:
- file_mentions.mentioned_user_id: 受提醒的人
- file_mentions.mentioned_by: 触发提醒的人
- activity_events.action: upload | rename | move | delete | restore | share | version_restore | comment | mention
- file_comments.mentions ARRAY(Integer): 评论里 @ 的人 (冗余存,前端 O(1) 显示)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "047_drive_notifications_activity"
down_revision: Union[str, None] = "045_drive_quota_thumbnail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # file_mentions
    op.create_table(
        "file_mentions",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentioned_user_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mentioned_by", sa.Integer(), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("context", sa.String(500), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_file_mentions_mentioned_user_id", "file_mentions", ["mentioned_user_id"])
    op.create_index("ix_file_mentions_file_id", "file_mentions", ["file_id"])
    op.create_index("ix_file_mentions_unread", "file_mentions", ["mentioned_user_id", "is_read"],
                    postgresql_where=sa.text("is_read = false"))

    # activity_events
    op.create_table(
        "activity_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),  # upload|rename|move|delete|restore|share|version_restore|comment|mention
        sa.Column("target_type", sa.String(20), nullable=False),  # file|folder|comment
        sa.Column("target_id", sa.Integer(), nullable=True),
        sa.Column("target_name", sa.String(500), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()"), index=True),
    )
    op.create_index("ix_activity_events_actor_id", "activity_events", ["actor_id"])
    op.create_index("ix_activity_events_action", "activity_events", ["action"])
    op.create_index("ix_activity_events_target", "activity_events", ["target_type", "target_id"])

    # file_comments
    op.create_table(
        "file_comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mentions", postgresql.ARRAY(sa.Integer()), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_file_comments_file_id", "file_comments", ["file_id"])
    op.create_index("ix_file_comments_user_id", "file_comments", ["user_id"])
    op.create_index("ix_file_comments_created_at", "file_comments", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_file_comments_created_at", table_name="file_comments")
    op.drop_index("ix_file_comments_user_id", table_name="file_comments")
    op.drop_index("ix_file_comments_file_id", table_name="file_comments")
    op.drop_table("file_comments")

    op.drop_index("ix_activity_events_target", table_name="activity_events")
    op.drop_index("ix_activity_events_action", table_name="activity_events")
    op.drop_index("ix_activity_events_actor_id", table_name="activity_events")
    op.drop_index("ix_activity_events_created_at", table_name="activity_events")
    op.drop_table("activity_events")

    op.drop_index("ix_file_mentions_unread", table_name="file_mentions")
    op.drop_index("ix_file_mentions_file_id", table_name="file_mentions")
    op.drop_index("ix_file_mentions_mentioned_user_id", table_name="file_mentions")
    op.drop_table("file_mentions")