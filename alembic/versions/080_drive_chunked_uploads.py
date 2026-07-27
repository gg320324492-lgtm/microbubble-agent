"""W72 第 2 批 B-3 — Drive PR5 trash 收口 + 分片上传会话。

Revision ID: 080_drive_chunked_uploads
Revises: 078_drive_dedupe_audit
Create Date: 2026-07-27

当前真实 Alembic 链为 075 -> 076 -> 079 -> 078，因此 080 必须接当前唯一
head ``078_drive_dedupe_audit``。派工输入中的 ``079_drive_team_folder`` 不是仓库内
revision id；真实 revision 为 ``079_team_folders``，且它已是 078 的上游。

本迁移同时补齐 trash 原路径快照字段，确保父目录在回收期间变化时仍可按原位置恢复。
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "080_drive_chunked_uploads"
down_revision: Union[str, None] = "082_commercial_billing_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Trash 原位置快照。故意不加 FK：父目录若先被物理删除，原 id 仍需保留作审计，
    # restore service 会检测目录是否仍有效，不可用时安全回退到根目录。
    op.add_column(
        "knowledge",
        sa.Column("original_parent_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column("original_path", sa.String(length=1000), nullable=True),
    )

    op.create_table(
        "drive_chunked_uploads",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("upload_id", sa.String(length=64), nullable=False),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("chunk_size", sa.Integer(), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_chunks",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
        ),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("upload_id", name="uq_drive_chunked_uploads_upload_id"),
        sa.CheckConstraint("file_size > 0", name="ck_drive_chunked_uploads_file_size"),
        sa.CheckConstraint("chunk_size > 0", name="ck_drive_chunked_uploads_chunk_size"),
        sa.CheckConstraint("total_chunks > 0", name="ck_drive_chunked_uploads_total_chunks"),
        sa.CheckConstraint(
            "status IN ('pending', 'uploading', 'completed', 'aborted')",
            name="ck_drive_chunked_uploads_status",
        ),
    )
    op.create_index(
        "ix_drive_chunked_uploads_upload_id",
        "drive_chunked_uploads",
        ["upload_id"],
        unique=True,
    )
    op.create_index(
        "ix_drive_chunked_uploads_user_id",
        "drive_chunked_uploads",
        ["user_id"],
    )
    op.create_index(
        "ix_drive_chunked_uploads_status",
        "drive_chunked_uploads",
        ["status"],
    )
    op.create_index(
        "ix_drive_chunked_uploads_expires_at",
        "drive_chunked_uploads",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_drive_chunked_uploads_expires_at", table_name="drive_chunked_uploads")
    op.drop_index("ix_drive_chunked_uploads_status", table_name="drive_chunked_uploads")
    op.drop_index("ix_drive_chunked_uploads_user_id", table_name="drive_chunked_uploads")
    op.drop_index("ix_drive_chunked_uploads_upload_id", table_name="drive_chunked_uploads")
    op.drop_table("drive_chunked_uploads")

    op.drop_column("knowledge", "original_path")
    op.drop_column("knowledge", "original_parent_id")
