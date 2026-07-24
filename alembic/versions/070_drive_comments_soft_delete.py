"""Drive v2 PR9 续 — 评论软删 deleted_at + deleted_by (2026-07-24, W68 第 12 批 C-2)

背景:
- W68 第 8 批 PR9 (commit 0bfe36751) drive_comments 表只支持 hard delete (CASCADE 子回复)
- W68 第 12 批 C-2 加评论软删: author / file owner / 平台 admin 可软删, 保留 audit_log

设计:
- drive_comments 表加 2 列:
  * deleted_at TIMESTAMPTZ NULL — 软删时间戳 (NULL=未删)
  * deleted_by INT NULL FK members(id) ON DELETE SET NULL — 删除人
- 加索引 ix_drive_comments_deleted_at — 过滤未删评论常用
- ORM 模型 (app/models/drive_comment.py) 同步加 2 字段
- Service.delete_comment 改:
  * 仅 author OR file owner OR 平台 admin (Member.role='admin')
  * 软删: set deleted_at + deleted_by (不 DELETE FROM, 不 CASCADE 子回复)
  * 保留 audit_log (调用方显式写 AuditLog, service 层不写避免破坏幂等性)

依赖:
- 069_drive_comments_recursive_func (上游, W68 第 9 批 B-2 PR11 fallback)

W68 第 12 批 alembic 串单链纪律:
- 当前 HEAD 是 069 (B-2 075_drive_version_tags 还没合并), 先 down_revision 接 069
- B-2 合并后, 主指挥会按 alembic 链顺序 merge: 069 → 075 → 070
- 本文件命名为 070 而非 076, 因为 076 需要等 075 先存在 (CLAUDE.md W68 第 4 批 alembic 串单链铁律)
- 主指挥合并后 verify ScriptDirectory.get_heads() == ['075_drive_version_tags']
  本 migration (070) 串在 075 之后, 主指挥需要把 down_revision 改 '075_drive_version_tags'
  并改名 076_drive_comments_soft_delete.py
- 详见 memory/w68-route-12-c2-pr9-comment-delete-2026-07-24.md

不破坏的边界:
- 不删 drive_comments 任何列 (PR9 老 schema 完全保留)
- 不动 path 列 (PR11 物化保留)
- 不改 CK 约束 (target XOR)
- 不改 parent_id CASCADE (子回复仍自动维护)
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "070_drive_comments_soft_delete"
down_revision: Union[str, None] = "069_drive_comments_recursive_func"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """加 deleted_at + deleted_by 字段 + 索引

    步骤:
    1. 加 deleted_at TIMESTAMPTZ NULL
    2. 加 deleted_by INT NULL FK members(id) ON DELETE SET NULL
    3. 加 ix_drive_comments_deleted_at 索引
    """
    # === 1. deleted_at 列 ===
    op.add_column(
        "drive_comments",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # === 2. deleted_by 列 (FK members ON DELETE SET NULL) ===
    # 注: SET NULL 而非 CASCADE — 删除 member 时软删标记保留时间戳,
    #     避免追溯审计 (audit_log 已记录谁删的, 软删字段只是时间锚点)
    op.add_column(
        "drive_comments",
        sa.Column(
            "deleted_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # === 3. ix_drive_comments_deleted_at 索引 ===
    # 用途: list_comments 加 deleted_at IS NULL 默认过滤 (避免返回软删评论)
    op.create_index(
        "ix_drive_comments_deleted_at",
        "drive_comments",
        ["deleted_at"],
    )


def downgrade() -> None:
    """回滚: 删索引 → 删 deleted_by → 删 deleted_at"""
    op.drop_index("ix_drive_comments_deleted_at", table_name="drive_comments")
    op.drop_column("drive_comments", "deleted_by")
    op.drop_column("drive_comments", "deleted_at")