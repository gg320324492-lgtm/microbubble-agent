"""v2 PR6-P8: notification rich title/body (与推送服务 metadata 增强)

新增 3 列 (file_mentions):
- title: String(200) — 推送显示的标题 (如 '杜同贺 在 实验数据.xlsx 提到了你')
- body: Text — 推送显示的描述 (comment preview + 文件类型 + 时间)
- file_type: String(50) — 缓存 Knowledge.file_type (mention 创建时), 避免后续 join

设计要点:
- title/body 写时存, 同时通知推送时再实时拼一份 (推送服务的 metadata 增强)
- 历史数据 (052 之前) title/body 留 NULL, 走实时拼 fallback
- file_type 缓存避免 N+1 (PR6 已 _batch_user_names, 加 file_type 同模式)
- 不删老数据, NULL 字段不影响 5s dedup 逻辑 (PR6-P7 仍按 file_id+context 命中)

回滚策略: 直接 downgrade 删 3 列 + 1 索引
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "052_drive_notification_rich"
# 接 051 链 (PR6-P7 dedup)
down_revision: Union[str, None] = "051_drive_notification_dedup"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P8: rich title/body 字段 + file_type 缓存"""
    # title (e.g. "杜同贺 在 实验数据.xlsx 提到了你")
    op.add_column(
        "file_mentions",
        sa.Column("title", sa.String(length=200), nullable=True),
    )
    # body (e.g. "comment preview 60 字 · PDF · 5 分钟前")
    op.add_column(
        "file_mentions",
        sa.Column("body", sa.Text(), nullable=True),
    )
    # file_type 缓存 (mention 创建时从 Knowledge 取, 避免后续 join)
    op.add_column(
        "file_mentions",
        sa.Column("file_type", sa.String(length=50), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("file_mentions", "file_type")
    op.drop_column("file_mentions", "body")
    op.drop_column("file_mentions", "title")