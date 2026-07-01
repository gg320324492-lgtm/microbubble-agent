"""v2 PR6-P5: 文件评论嵌套 (threading, max depth = 3)

新增 3 列:
- file_comments.parent_comment_id: 自引用 FK CASCADE (顶层 = NULL)
- file_comments.thread_depth: SmallInteger, 0/1/2 (顶层/回复/回复的回复)
- file_comments.reply_count: Integer 冗余存 (加速 tree list 渲染)

新增 2 索引:
- ix_file_comments_parent: parent_comment_id 单列 (递归查子树)
- ix_file_comments_file_parent: (file_id, parent_comment_id) 复合 (tree 列表)

设计要点:
- 不动现有评论数据 (现有 flat 评论自动成为 depth=0 顶层评论)
- thread_depth 在 service 层根据 parent 计算 (不在 DB 层 CHECK, 留给 service 强校验)
- MAX_DEPTH=3 实际是 depth 0/1/2 三层 (第 3 层 depth=2 是允许的最后回复, 不能再有 child)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "050_drive_comment_threading"
# 接 alembic 链: 050_audit_log_now_default 是 PR7 的真 PR
# v2 PR6-P5 threading 在 audit_log 之后 (避免 head 冲突)
down_revision: Union[str, None] = "050_audit_log_now_default"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) parent_comment_id: 自引用 FK CASCADE
    op.add_column(
        "file_comments",
        sa.Column(
            "parent_comment_id",
            sa.BigInteger(),
            sa.ForeignKey("file_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    # 2) thread_depth: SmallInteger (0/1/2), 顶层 = 0
    op.add_column(
        "file_comments",
        sa.Column(
            "thread_depth",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # 3) reply_count: Integer 冗余存
    op.add_column(
        "file_comments",
        sa.Column(
            "reply_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    # 索引: parent_comment_id 单列 (查某评论所有 child)
    op.create_index("ix_file_comments_parent", "file_comments", ["parent_comment_id"])
    # 索引: (file_id, parent_comment_id) 复合 (tree 渲染: 某文件下顶层 + 各层子评论)
    op.create_index(
        "ix_file_comments_file_parent",
        "file_comments",
        ["file_id", "parent_comment_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_file_comments_file_parent", table_name="file_comments")
    op.drop_index("ix_file_comments_parent", table_name="file_comments")
    op.drop_column("file_comments", "reply_count")
    op.drop_column("file_comments", "thread_depth")
    op.drop_column("file_comments", "parent_comment_id")