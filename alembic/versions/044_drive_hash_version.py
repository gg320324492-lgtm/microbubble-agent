"""v2026-07-01: 课题组网盘 v2 PR4 文件秒传 (hash) + 版本历史

Revision ID: 044_drive_hash_version
Revises: 043_drive_star_batch
Create Date: 2026-07-01

新增列 (Knowledge 表):
- file_size           (BigInteger, nullable)       文件字节大小（秒传校验 + dedup_saved_bytes 计算）
- file_hash           (String(64), nullable)        MD5/SHA256 hex hash（秒查 dedup）
- is_latest           (Boolean, default true)       是否当前活跃版本（多版本时旧行 = false）
- parent_version_id   (Integer, nullable)           父版本 ID（同 file 的前一个版本，Self FK）
- version_number      (Integer, default 1)          版本号 (v1 / v2 / v3...)

新增索引: ix_knowledge_file_hash (partial WHERE deleted_at IS NULL AND storage_mode='drive')

新增表 knowledge_versions:
- id, file_id (FK knowledge.id CASCADE), version_number, file_hash, file_size,
  uploaded_by (FK members.id), change_note (TEXT), created_at
- UQ(file_id, version_number)

约束: parent_version_id FK ON DELETE SET NULL（避免删一行连坐历史版本）
约束: knowledge_versions ON DELETE CASCADE（删 file 时版本记录自动清）

不变更: _to_item 之前 file_size=0 硬编码, 044 后用真实 file_size。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "044_drive_hash_version"
down_revision: Union[str, None] = "043_drive_star_batch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Knowledge 表: 5 个新列
    op.add_column(
        "knowledge",
        sa.Column("file_size", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column("file_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column(
            "is_latest",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "knowledge",
        sa.Column("parent_version_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "knowledge",
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # Self FK: parent_version_id → knowledge.id (SET NULL, 避免删父连坐子)
    op.create_foreign_key(
        "fk_knowledge_parent_version",
        "knowledge",
        "knowledge",
        ["parent_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    # 部分索引: 仅索引活跃 drive 文件的 hash (秒查 dedup 用)
    op.create_index(
        "ix_knowledge_file_hash",
        "knowledge",
        ["file_hash"],
        postgresql_where=sa.text("deleted_at IS NULL AND storage_mode='drive'"),
    )
    # 部分索引: 仅索引非最新版本 (历史版本查询)
    op.create_index(
        "ix_knowledge_is_latest",
        "knowledge",
        ["is_latest"],
        postgresql_where=sa.text("is_latest = true"),
    )

    # 新表 knowledge_versions (历史版本明细)
    op.create_table(
        "knowledge_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column(
            "uploaded_by",
            sa.Integer(),
            sa.ForeignKey("members.id"),
            nullable=False,
        ),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_knowledge_versions_file_ver",
        ),
    )
    op.create_index(
        "ix_knowledge_versions_file_id",
        "knowledge_versions",
        ["file_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_versions_file_id", table_name="knowledge_versions")
    op.drop_table("knowledge_versions")
    op.drop_index("ix_knowledge_is_latest", table_name="knowledge")
    op.drop_index("ix_knowledge_file_hash", table_name="knowledge")
    op.drop_constraint(
        "fk_knowledge_parent_version",
        "knowledge",
        type_="foreignkey",
    )
    op.drop_column("knowledge", "version_number")
    op.drop_column("knowledge", "parent_version_id")
    op.drop_column("knowledge", "is_latest")
    op.drop_column("knowledge", "file_hash")
    op.drop_column("knowledge", "file_size")