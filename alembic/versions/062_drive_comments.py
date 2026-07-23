"""v2 PR9: drive_comments 评论 thread 表 (2026-07-24)

背景:
- Drive v2 PR6 已有 FileComment (file_comments), 仅单文件 + 2 层嵌套 + 无 resolved
- 课题组场景: 文件/文件夹讨论 + 多层嵌套回复 + 已解决标记 (GitHub PR review comments)
- 本 PR 引入 1 张新表: drive_comments
  * file_id / folder_id 二选一 (CK 约束)
  * parent_id 自引用, 嵌套深度不限
  * author_id NOT NULL CASCADE (作者删除 → 评论删)
  * mentions ARRAY 冗余 (前端 @ 高亮)
  * resolved_at / resolved_by (已解决状态)

权限模型:
- read 权限即可写评论 (类似 GitHub issue)
- 仅 author 可编辑/删除自己的评论
- author / file owner / folder admin / folder owner 可 resolve

依赖: knowledge (knowledge.id) + folders (folders.id) + members (members.id) 必须存在
下接: drive_comment endpoints (GET list / POST create / PATCH update / DELETE / POST resolve / POST unresolve)

回滚策略: DROP TABLE (无外部 FK 引用)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY


revision: str = "062_drive_comments"
down_revision: Union[str, None] = "061_drive_folder_share"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "drive_comments",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        # 主体 (二选一, CHECK 约束在下方)
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # 作者 (NOT NULL, CASCADE)
        sa.Column(
            "author_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        # 嵌套回复 (parent_id 自引用)
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("drive_comments.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("mentions", ARRAY(sa.Integer()), nullable=True),
        # resolved 状态 (NULL=未解决)
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column(
            "resolved_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # 时间戳 (复用 TimestampMixin)
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        # CHECK 约束: file_id / folder_id 二选一
        sa.CheckConstraint(
            "(file_id IS NOT NULL AND folder_id IS NULL) OR "
            "(file_id IS NULL AND folder_id IS NOT NULL)",
            name="ck_drive_comments_target_xor",
        ),
    )

    # === 索引 ===
    # 索引 1: file_id 单列 (list by file_id 常用)
    op.create_index(
        "ix_drive_comments_file_id",
        "drive_comments",
        ["file_id"],
        unique=False,
    )
    # 索引 2: folder_id 单列
    op.create_index(
        "ix_drive_comments_folder_id",
        "drive_comments",
        ["folder_id"],
        unique=False,
    )
    # 索引 3: author_id 单列 (list by author 常用)
    op.create_index(
        "ix_drive_comments_author_id",
        "drive_comments",
        ["author_id"],
        unique=False,
    )
    # 索引 4: parent_id 单列 (拉子回复)
    op.create_index(
        "ix_drive_comments_parent",
        "drive_comments",
        ["parent_id"],
        unique=False,
    )
    # 索引 5: resolved_at 单列 (filter 已解决)
    op.create_index(
        "ix_drive_comments_resolved_at",
        "drive_comments",
        ["resolved_at"],
        unique=False,
    )
    # 索引 6: file_id + resolved_at 组合 (list 文件的未解决评论)
    op.create_index(
        "ix_drive_comments_file_resolved",
        "drive_comments",
        ["file_id", "resolved_at"],
        unique=False,
    )
    # 索引 7: folder_id + resolved_at 组合
    op.create_index(
        "ix_drive_comments_folder_resolved",
        "drive_comments",
        ["folder_id", "resolved_at"],
        unique=False,
    )


def downgrade() -> None:
    # 顺序: 先删索引, 再删表
    op.drop_index("ix_drive_comments_folder_resolved", table_name="drive_comments")
    op.drop_index("ix_drive_comments_file_resolved", table_name="drive_comments")
    op.drop_index("ix_drive_comments_resolved_at", table_name="drive_comments")
    op.drop_index("ix_drive_comments_parent", table_name="drive_comments")
    op.drop_index("ix_drive_comments_author_id", table_name="drive_comments")
    op.drop_index("ix_drive_comments_folder_id", table_name="drive_comments")
    op.drop_index("ix_drive_comments_file_id", table_name="drive_comments")
    op.drop_table("drive_comments")