"""v2 PR7: 文件请求 + 审计日志 + 团队共享盘标识

新增 2 张表:
- file_requests: Dropbox 招牌 "文件请求" (收作业 / 收集反馈)
  - token (公开匿名访问,32 字符随机)
  - target_folder_id (提交的文件落到哪个文件夹)
  - allowed_extensions ARRAY(限制文件类型)
  - require_uploader_name (是否要求填姓名)
  - submission_count (已提交数 +1 on each submit)

- audit_log: 完整安全审计 (谁在什么 IP 用什么 UA 在什么时候做了什么)
  - ip_address INET (PostgreSQL 原生 INET 类型)
  - user_agent TEXT
  - status (success | error | 4xx | 5xx)
  - JSONB metadata (request params 但已脱敏)

新增 2 列:
- knowledge.is_team_default BOOL: 团队共享盘成员可见入口
- folders.is_team_default BOOL: 同上
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "048_drive_requests_audit"
# 接 PR6 链 (047_drive_notifications_activity)
# 041_dedup_empty_sessions 是并行 data-migration 分支, 详见 049_dedup_empty_sessions_merge
down_revision: Union[str, None] = "047_drive_notifications_activity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # === file_requests: 文件请求主表 ===
    op.create_table(
        "file_requests",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        # 32 字符随机 token (公开访问, 不暴露内部 id)
        sa.Column("token", sa.String(32), nullable=False, unique=True, index=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # 提交的文件落到哪个文件夹 (NULL = 用户根目录)
        sa.Column("target_folder_id", sa.Integer(), sa.ForeignKey("folders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("members.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("allowed_extensions", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("require_uploader_name", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("max_file_size_mb", sa.Integer(), nullable=True),
        sa.Column("submission_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default="now()"),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default="now()"),
    )
    op.create_index("ix_file_requests_created_by", "file_requests", ["created_by"])

    # === audit_log: 完整审计 ===
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, index=True),
        # 用户登录后才有 user_id (匿名访问 NULL, 如 /r/:token submit)
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("ip_address", sa.String(45), nullable=True, index=True),  # IPv6 max 45
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("method", sa.String(10), nullable=False, index=True),
        sa.Column("path", sa.String(500), nullable=False, index=True),
        sa.Column("action", sa.String(50), nullable=False, index=True),
        sa.Column("resource_type", sa.String(20), nullable=True),
        sa.Column("resource_id", sa.String(50), nullable=True),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("meta_data", postgresql.JSONB(), nullable=True),  # PG 列名 = 'metadata' (与 SQLAlchemy attr 区分)
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default="now()", index=True),
    )
    op.create_index("ix_audit_log_user_action_time", "audit_log", ["user_id", "action", "created_at"])
    op.create_index("ix_audit_log_action_time", "audit_log", ["action", "created_at"])

    # === Knowledge + folders: 团队共享盘标识 ===
    op.add_column(
        "knowledge",
        sa.Column("is_team_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "folders",
        sa.Column("is_team_default", sa.Boolean(), nullable=False, server_default="false"),
    )
    # 部分索引: 只索引 true 行 (PG 占空间小)
    op.create_index(
        "ix_knowledge_team_default",
        "knowledge",
        ["is_team_default"],
        postgresql_where=sa.text("is_team_default = true"),
    )
    op.create_index(
        "ix_folders_team_default",
        "folders",
        ["is_team_default"],
        postgresql_where=sa.text("is_team_default = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_folders_team_default", table_name="folders")
    op.drop_index("ix_knowledge_team_default", table_name="knowledge")
    op.drop_column("folders", "is_team_default")
    op.drop_column("knowledge", "is_team_default")
    op.drop_index("ix_audit_log_action_time", table_name="audit_log")
    op.drop_index("ix_audit_log_user_action_time", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_file_requests_created_by", table_name="file_requests")
    op.drop_table("file_requests")
