"""v2026-07-01: 课题组网盘 (Lab Group Drive) PR1 基础设施

Revision ID: 040_drive_storage_mode
Revises: 039_chat_history
Create Date: 2026-07-01

背景:
- 用户痛点: 组员桌面散落 PPT/Word/音频, 缺乏团队共享归档
- 当前 KB 上传强制解析入库, 不适合原始文件归档
- KB 卡片无文件夹/可见性维度

设计决策 (用户 2026-07-01 确认):
1. 单系统双模式: Knowledge 表加 storage_mode (kb/drive), 不新建独立表
2. drive 模式默认不入 embedding 索引
3. drive → kb 升级必须含 visibility 升级 (用户主动暴露给团队)
4. 文件夹 visibility 是文件可见性的硬上限
5. private 文件完全隔离 (其他人看不到文件名)
6. 软删除 3 天保留期 (与 task/chat 一致)

新增:
- Knowledge 表: 4 列 (storage_mode / folder_id / visibility / deleted_at) + 2 部分索引
- Folder 表: 9 列 + 自引用 parent_id + path 物化 + depth 上限 5
- folders.* 索引: 3 个 (parent_active / owner_active / parent_id 单独)

零迁移负担:
- 新列 server_default 全有, 旧 SELECT 不受影响
- 必须 lint 提醒: 所有 SELECT Knowledge 处加 .where(Knowledge.deleted_at.is_(None))
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "040_drive_storage_mode"
down_revision: Union[str, None] = "039_chat_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ==================== 1. Folder 表 (新建) ====================
    op.create_table(
        "folders",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "parent_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "visibility",
            sa.String(16),
            nullable=False,
            server_default="team",
        ),  # private | team | public
        sa.Column(
            "path",
            sa.String(1000),
            nullable=False,
            server_default="/",
        ),  # 物化路径 '/1/4/7/'
        sa.Column(
            "depth",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),  # max=5 (用户决策: 限 5 层)
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    # 索引
    op.create_index("ix_folders_owner_id", "folders", ["owner_id"])
    op.create_index("ix_folders_parent_id", "folders", ["parent_id"])
    op.create_index("ix_folders_visibility", "folders", ["visibility"])
    op.create_index("ix_folders_deleted_at", "folders", ["deleted_at"])
    op.create_index("ix_folders_parent_active", "folders", ["parent_id", "deleted_at"])
    op.create_index("ix_folders_owner_active", "folders", ["owner_id", "deleted_at"])

    # ==================== 2. Knowledge 表加 4 列 ====================
    # storage_mode: kb | drive
    op.add_column(
        "knowledge",
        sa.Column(
            "storage_mode",
            sa.String(16),
            nullable=False,
            server_default="kb",
        ),
    )
    op.create_index(
        "ix_knowledge_storage_mode", "knowledge", ["storage_mode"]
    )

    # visibility: private | team | public (硬上限语义见 plan 4.0)
    op.add_column(
        "knowledge",
        sa.Column(
            "visibility",
            sa.String(16),
            nullable=False,
            server_default="team",
        ),
    )
    op.create_index(
        "ix_knowledge_visibility", "knowledge", ["visibility"]
    )

    # folder_id: NULL = 顶级
    op.add_column(
        "knowledge",
        sa.Column(
            "folder_id",
            sa.Integer(),
            sa.ForeignKey("folders.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_knowledge_folder_id", "knowledge", ["folder_id"]
    )

    # deleted_at: 软删除时间戳
    op.add_column(
        "knowledge",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "ix_knowledge_deleted_at", "knowledge", ["deleted_at"]
    )

    # 部分索引 (避免拖慢热路径, 仅针对常用过滤组合)
    # drive 模式活跃文件 (软删除排除)
    op.create_index(
        "ix_kb_drive_active",
        "knowledge",
        ["folder_id"],
        postgresql_where=sa.text("storage_mode='drive' AND deleted_at IS NULL"),
    )
    # kb 模式活跃文件
    op.create_index(
        "ix_kb_kb_active",
        "knowledge",
        ["created_by"],
        postgresql_where=sa.text("storage_mode='kb' AND deleted_at IS NULL"),
    )
    # team/public 可见 (Agent 检索路径)
    op.create_index(
        "ix_kb_kb_team_public",
        "knowledge",
        ["created_by"],
        postgresql_where=sa.text("storage_mode='kb' AND deleted_at IS NULL AND visibility IN ('team', 'public')"),
    )

    # ==================== 3. 显式 UPDATE 让 audit log 清晰 ====================
    # 即使 server_default 已生效, 显式 UPDATE 一次便于审计追溯
    op.execute(
        "UPDATE knowledge SET storage_mode='kb', visibility='team' "
        "WHERE storage_mode IS NULL OR visibility IS NULL"
    )


def downgrade() -> None:
    # ==================== 1. 删除 Knowledge 表新列 ====================
    op.drop_index("ix_kb_kb_team_public", table_name="knowledge")
    op.drop_index("ix_kb_kb_active", table_name="knowledge")
    op.drop_index("ix_kb_drive_active", table_name="knowledge")
    op.drop_index("ix_knowledge_deleted_at", table_name="knowledge")
    op.drop_index("ix_knowledge_folder_id", table_name="knowledge")
    op.drop_index("ix_knowledge_visibility", table_name="knowledge")
    op.drop_index("ix_knowledge_storage_mode", table_name="knowledge")

    op.drop_column("knowledge", "deleted_at")
    op.drop_column("knowledge", "folder_id")
    op.drop_column("knowledge", "visibility")
    op.drop_column("knowledge", "storage_mode")

    # ==================== 2. 删除 Folder 表 ====================
    op.drop_index("ix_folders_owner_active", table_name="folders")
    op.drop_index("ix_folders_parent_active", table_name="folders")
    op.drop_index("ix_folders_deleted_at", table_name="folders")
    op.drop_index("ix_folders_visibility", table_name="folders")
    op.drop_index("ix_folders_parent_id", table_name="folders")
    op.drop_index("ix_folders_owner_id", table_name="folders")
    op.drop_table("folders")