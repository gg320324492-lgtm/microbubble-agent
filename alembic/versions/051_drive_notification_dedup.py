"""v2 PR6-P7: notification 5s dedup (合并 + repeated_count)

新增 1 列:
- file_mentions.repeated_count: Integer, default 1 (后续 dedup 命中 +1)

新增 1 索引:
- ix_file_mentions_receiver_file_recent: (mentioned_user_id, file_id, created_at DESC)
  (加速 dedup 查询 WHERE mentioned_user_id=? AND file_id=? AND created_at >= now-5s)

设计要点:
- 不删除现有数据, 现有 mention 自动 default repeated_count=1
- 5s 窗口由 service 层 WHERE created_at >= now-5s 决定 (不写 DB)
- alembic 加列不锁表 (smallint default 1 一次性完成)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "051_drive_notification_dedup"
# 接 alembic 链: 050_drive_comment_threading 是 PR6-P5 的真 PR
# v2 PR6-P7 dedup 在 threading 之后
down_revision: Union[str, None] = "050_drive_comment_threading"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P7: 加 repeated_count 列 + dedup 查询索引"""
    op.add_column(
        "file_mentions",
        sa.Column("repeated_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_file_mentions_receiver_file_recent",
        "file_mentions",
        ["mentioned_user_id", "file_id", sa.text("created_at DESC")],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index("ix_file_mentions_receiver_file_recent", table_name="file_mentions", if_exists=True)
    op.drop_column("file_mentions", "repeated_count")