"""v2 PR7: drive folder share + member 两表 (2026-07-23)

背景:
- 课题组场景: 老师看学生实验数据 / 学生之间共享论文 / 全组共用模板
- 文件分享 (Knowledge.share_token, PR2.7) 仅支持单文件 + 公开链接 + 提取码,
  不足以支撑 folder 级别 + 成员权限模型
- v2 PR6 通知 + @提醒 让文件层面交互完善, 但 folder 仍只 owner 一人可见

设计:
- 2 张新表:
  * drive_folder_shares: folder 公开链接 (folder_id + share_token UNIQUE + permission + expires_at + created_by + revoked_at)
  * drive_folder_members: folder 邀请成员 (folder_id + member_id + permission + invited_by, UNIQUE(folder_id, member_id))

权限枚举 (3 级): read | write | admin
过期策略: expires_at NOT NULL (不允许永久, 7 天默认, 上限 365 天)

依赖: drive_folders (folders.id) + members (members.id) 必须存在
下接: drive_share endpoints (POST/GET/POST/DELETE)

回滚策略: 直接 DROP TABLE (无其他依赖, 无外部 FK 引用)

后续 PR (PR8/未来):
- PR8 移动端 /api/v1/mobile/dashboard 加 "我被分享的 folders" section
- 后续 PR 加 list_folder_members endpoint (本 PR 仅暴露 service 层)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "061_drive_folder_share"
down_revision: Union[str, None] = "060_meeting_user_agent"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. drive_folder_shares 表
    op.create_table(
        "drive_folder_shares",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "share_token",
            sa.String(length=64),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "permission",
            sa.String(length=16),
            nullable=False,
            server_default="read",
            comment="read | write | admin",
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=False,
            comment="必有过期时间, 不允许永久分享",
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(),
            nullable=True,
            comment="主动撤销时间 (NULL=未撤销)",
        ),
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
    )
    # 索引: folder_id + revoked_at 组合 (常用查询: 找 folder 的活跃 share)
    op.create_index(
        "ix_drive_folder_shares_folder_active",
        "drive_folder_shares",
        ["folder_id", "revoked_at"],
        unique=False,
    )
    # 索引: created_by (常用查询: 找某用户创建的所有 share)
    op.create_index(
        "ix_drive_folder_shares_created_by",
        "drive_folder_shares",
        ["created_by"],
        unique=False,
    )

    # 2. drive_folder_members 表
    op.create_table(
        "drive_folder_members",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "permission",
            sa.String(length=16),
            nullable=False,
            server_default="read",
            comment="read | write | admin",
        ),
        sa.Column(
            "invited_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        # 同一 folder 同一 member 只能有一条 (重复邀请幂等)
        sa.UniqueConstraint(
            "folder_id", "member_id",
            name="uq_drive_folder_members_folder_member",
        ),
    )
    # 索引: folder_id (常用查询: 列 folder 的所有成员)
    op.create_index(
        "ix_drive_folder_members_folder",
        "drive_folder_members",
        ["folder_id"],
        unique=False,
    )
    # 索引: member_id (常用查询: 列我被邀请的所有 folder)
    op.create_index(
        "ix_drive_folder_members_member",
        "drive_folder_members",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    # 顺序: 先删 members (依赖 shares 的 folder FK)
    op.drop_index("ix_drive_folder_members_member", table_name="drive_folder_members")
    op.drop_index("ix_drive_folder_members_folder", table_name="drive_folder_members")
    op.drop_table("drive_folder_members")

    op.drop_index("ix_drive_folder_shares_created_by", table_name="drive_folder_shares")
    op.drop_index("ix_drive_folder_shares_folder_active", table_name="drive_folder_shares")
    op.drop_table("drive_folder_shares")