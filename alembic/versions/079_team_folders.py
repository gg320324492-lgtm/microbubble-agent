"""Drive v2 PR18 — 团队共享盘 (Team Folder) + 4 维审计日志 (2026-07-24, W68 第 14 批 B-2)

背景:
- ppt-word-replicated-swing.md PR7 部分真未实施:
    * 团队共享盘 (Team Folder) — 让用户明确创建一个"team 级"文件夹, 邀请多成员协作
    * 审计日志 — record_audit 4 维度 (read/write/delete/share/restore)
- 后端 PR7 反转后没补 API, 本 PR18 弥补缺口

设计:
- team_folders 表 — 团队共享盘主表 (区别于普通 Folder)
  * id (PK)
  * name VARCHAR(200) NOT NULL
  * owner_id INT NOT NULL FK members(id) ON DELETE RESTRICT
  * member_ids INT[] NOT NULL DEFAULT '{}' — 受邀成员 ID 列表 (PostgreSQL ARRAY)
    (轻量级名单; 受邀与 members 关系不入 drive_share, 避免 PR7 圈子混乱)
  * visibility VARCHAR(16) NOT NULL DEFAULT 'team' — private/team/public
  * created_at / updated_at TIMESTAMPTZ

- team_folder_audit_log 表 — 4 维审计 (CLAUDE.md 2026-07-24 v78 audit_log 模式)
  * id BIGSERIAL PK
  * team_folder_id INT NOT NULL FK team_folders(id) ON DELETE CASCADE
  * actor_id INT NOT NULL FK members(id) ON DELETE RESTRICT
  * action VARCHAR(16) NOT NULL — 'read' | 'write' | 'delete' | 'share' | 'restore'
  * target_type VARCHAR(32) NOT NULL — 'folder' | 'file' | 'member' | 'permission'
  * target_id VARCHAR(64) NULL — 目标对象 ID (允许字符串, 兼容 path/复合 key)
  * extra JSONB NULL — 4 维以外的额外结构化字段 (页面 URL / request id / diff 等)
  * created_at TIMESTAMPTZ NOT NULL DEFAULT now()
- 索引:
  * ix_team_folder_audit_folder_time — (team_folder_id, created_at DESC) 用于按时间倒序列出
  * ix_team_folder_audit_actor_action — (actor_id, action) 用于"谁干了什么"统计
  * ix_team_folder_audit_action_time — (action, created_at) 用于全局按 action 过滤

依赖:
- 078_drive_dedupe_audit (上游, W68 第 14 批 B-1 PR17 hash 去重; 派工时 B-1 还没合并
  → B-2 agent 写 preview 态, 主指挥合并 B-1 后串单链 `076 → 078 → 079`)

W68 第 14 批 alembic 串单链纪律 (派工纪要 v4 铁律 1):
- 当前 HEAD 是 076_drive_comments_path_backfill (W68 第 13 批 grand closure 收尾后状态)
- B-1 引入 078_drive_dedupe_audit
- B-2 接 078 (preview 态) → 主指挥合并后串单链 `076 → 078 → 079`
- 主指挥合并 B-1 后必 verify ScriptDirectory.get_heads() == ['079_team_folders']
  (1 个 head, 0 双头, 见 CLAUDE.md "alembic 并行 agent 串单链纪律")

不破坏的边界:
- 不动 drive_* 任何老表 (PR6/PR7/PR9/PR10/PR11/PR12/PR13/PR14/PR15/PR16/PR17 完全不动)
- 不动 drive_share / drive_folder_members (PR7 老 API/表保持不变, 不合并)
- 新增的 2 表独立命名空间 (team_folders / team_folder_audit_log), 与 folders 不冲突
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "079_team_folders"
# 主指挥 W68 第 14 批合并收口修订 (2026-07-24): B-1 (alembic 078) stopped agent 未完工
# → 改接 076_drive_comments_path_backfill (W68 第 13 批 alembic renumber 终点).
# 串单链 076 → 079, 1 个 head 0 双头, 符合派工纪要 v4 铁律 1 + W68 第 13 批 C-1 实战教训.
down_revision: Union[str, None] = "076_drive_comments_path_backfill"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 4 维审计 action 枚举 (CLAUDE.md 2026-07-24 v78 audit_log 模式)
# 与 service 层 action 常量同步 (team_folder_service.AuditAction)
TEAM_FOLDER_AUDIT_ACTIONS: tuple = ("read", "write", "delete", "share", "restore")


def upgrade() -> None:
    """建 2 张表 + 3 索引

    步骤:
    1. team_folders (主表 + 1 索引)
    2. team_folder_audit_log (审计 + 3 索引)
    """

    # === 1. team_folders 主表 ===
    op.create_table(
        "team_folders",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "owner_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        # 受邀成员 ID 列表 (PG ARRAY, 默认空数组 '{}')
        # 注: 不走 drive_share 那套 share_token, 简单 ID 列表足够 team folder 场景
        sa.Column(
            "member_ids",
            postgresql.ARRAY(sa.Integer()),
            nullable=False,
            server_default=sa.text("'{}'::int[]"),
        ),
        # visibility: 'private' | 'team' | 'public'
        sa.Column(
            "visibility",
            sa.String(16),
            nullable=False,
            server_default="team",
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # 索引: owner_id + deleted_at (查"我创建的未删除 team folder" 高频)
    op.create_index(
        "ix_team_folders_owner_active",
        "team_folders",
        ["owner_id", "deleted_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # === 2. team_folder_audit_log 审计表 ===
    op.create_table(
        "team_folder_audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True, index=True),
        sa.Column(
            "team_folder_id",
            sa.Integer(),
            sa.ForeignKey("team_folders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "actor_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # action: 'read'|'write'|'delete'|'share'|'restore' — 4 维审计
        sa.Column("action", sa.String(16), nullable=False),
        # target_type: 'folder'|'file'|'member'|'permission' — 操作对象类型
        sa.Column("target_type", sa.String(32), nullable=False),
        # target_id: 字符串 (兼容 path/复合 key, 如 'file:42' 或 'permission:read')
        sa.Column("target_id", sa.String(64), nullable=True),
        # extra JSONB: 4 维以外的额外结构化字段
        sa.Column("extra", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # CHECK 约束: action 必须是合法枚举 (5 种)
    op.create_check_constraint(
        "ck_team_folder_audit_action",
        "team_folder_audit_log",
        sa.text("action IN ('read', 'write', 'delete', 'share', 'restore')"),
    )

    # 索引 1: 按 team_folder_id + 时间倒序 (查"某 team folder 最近操作")
    op.create_index(
        "ix_team_folder_audit_folder_time",
        "team_folder_audit_log",
        ["team_folder_id", sa.text("created_at DESC")],
    )

    # 索引 2: 按 actor + action (查"某用户做了什么")
    op.create_index(
        "ix_team_folder_audit_actor_action",
        "team_folder_audit_log",
        ["actor_id", "action"],
    )

    # 索引 3: 按 action + 时间 (查"全组所有 share 行为")
    op.create_index(
        "ix_team_folder_audit_action_time",
        "team_folder_audit_log",
        ["action", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    """回滚: 删索引 → 删 team_folder_audit_log → 删 team_folders"""
    # === team_folder_audit_log ===
    op.drop_index("ix_team_folder_audit_action_time", table_name="team_folder_audit_log")
    op.drop_index("ix_team_folder_audit_actor_action", table_name="team_folder_audit_log")
    op.drop_index("ix_team_folder_audit_folder_time", table_name="team_folder_audit_log")
    op.drop_table("team_folder_audit_log")

    # === team_folders ===
    op.drop_index("ix_team_folders_owner_active", table_name="team_folders")
    op.drop_table("team_folders")
