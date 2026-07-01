"""v2 网盘 PR5: 配额 + 缩略图 + 分片断点续传

Revision ID: 045_drive_quota_thumbnail
Revises: 044_drive_hash_version
Create Date: 2026-07-01

3 块改动:
1. Knowledge +3 列 (thumbnail_path / thumbnail_status / thumbnail_generated_at)
2. Member +3 列 (drive_quota_bytes / drive_used_bytes / drive_quota_updated_at)
3. 新表 chunked_upload_sessions (断点续传 session)

降级策略:
- 缩略图生成失败时 status='failed', 后续可重试
- 配额超额返回 413 Payload Too Large, 不阻塞其他用户
- 断点续传 session 24h TTL, Celery beat 清理
"""
from typing import Union

import sqlalchemy as sa
from alembic import op

revision: str = "045_drive_quota_thumbnail"
down_revision: Union[str, None] = "044_drive_hash_version"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === Block 1: Knowledge 缩略图字段 ===
    op.add_column(
        "knowledge",
        sa.Column("thumbnail_path", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column(
            "thumbnail_status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
    )
    op.add_column(
        "knowledge",
        sa.Column("thumbnail_generated_at", sa.DateTime(), nullable=True),
    )
    # 部分索引: 仅 drive 模式 + 软删 NULL (节省索引空间, 避开 80% KB 条目)
    op.create_index(
        "ix_knowledge_thumb_pending",
        "knowledge",
        ["thumbnail_status"],
        postgresql_where=sa.text(
            "deleted_at IS NULL AND storage_mode='drive' AND thumbnail_status='pending'"
        ),
    )

    # === Block 2: Member 配额字段 ===
    op.add_column(
        "members",
        sa.Column(
            "drive_quota_bytes",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("10737418240"),  # 10 GB
        ),
    )
    op.add_column(
        "members",
        sa.Column(
            "drive_used_bytes",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "members",
        sa.Column("drive_quota_updated_at", sa.DateTime(), nullable=True),
    )

    # === Block 3: chunked_upload_sessions 表 (断点续传) ===
    op.create_table(
        "chunked_upload_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),  # uuid hex
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("file_name", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=True),
        sa.Column("folder_id", sa.Integer(), nullable=True),
        sa.Column(
            "visibility",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'team'"),
        ),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_chunks",
            sa.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'active'"),
        ),  # active | completed | aborted | expired
        sa.Column("object_name", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_chunked_session_status",
        "chunked_upload_sessions",
        ["status", "expires_at"],
        postgresql_where=sa.text("status='active'"),
    )
    op.create_index(
        "ix_chunked_session_user",
        "chunked_upload_sessions",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chunked_session_user", table_name="chunked_upload_sessions")
    op.drop_index("ix_chunked_session_status", table_name="chunked_upload_sessions")
    op.drop_table("chunked_upload_sessions")

    op.drop_column("members", "drive_quota_updated_at")
    op.drop_column("members", "drive_used_bytes")
    op.drop_column("members", "drive_quota_bytes")

    op.drop_index("ix_knowledge_thumb_pending", table_name="knowledge")
    op.drop_column("knowledge", "thumbnail_generated_at")
    op.drop_column("knowledge", "thumbnail_status")
    op.drop_column("knowledge", "thumbnail_path")