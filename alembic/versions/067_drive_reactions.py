"""v2 PR12: drive_reactions 表情反应表 (2026-07-24, W68 第 8 批 B-2)

背景:
- Drive v2 PR9 已实现评论 thread (drive_comments) + 文件版本历史 (drive_file_versions) + mention 提醒 (W68 PR10)
- Drive v2 PR10 实现 CRDT 协同编辑骨架
- Drive v2 PR11 实现 path materialized (PR9 后续, 未合并)
- **Drive v2 PR12 — 表情反应 (emoji reactions)**: GitHub / GitLab / Slack 风格的轻量反馈
  - 用户对 comment / file / note 任意一个加 emoji reaction (👍❤️🎉😂😮😢 等)
  - 同一 user 对同一 target 同一 emoji 只能 1 次 (UNIQUE 约束防重复)
  - 删除 reaction 即 toggle off (1 user 1 emoji)
  - WS 推送 reaction_added / reaction_removed 给其他在线协作用户

设计:
- 1 张新表: drive_reactions
  * target_type ENUM('comment', 'file', 'note') — polymorphic FK 来源
  * target_id Integer — polymorphic target ID (FK 字段不强制, 由 service 层验证)
  * member_id Integer — 谁反应了 (FK to members, NOT NULL CASCADE)
  * emoji VARCHAR(16) — emoji 字面值 (Unicode, e.g. "👍" 1 emoji = 4 byte UTF-8)
  * created_at / updated_at TimestampMixin
- UNIQUE 约束 (target_type, target_id, member_id, emoji) — 防重复反应
- 索引:
  * (target_type, target_id) — list_reactions 聚合高频
  * (member_id) — list_my_reactions 高频

为何 polymorphic FK:
- 表情反应需支持 comment / file / note 3 类目标
- 用 ENUM + INTEGER 比 3 个 FK 列 + 3 个 nullable 索引更紧凑
- 验证 FK 合法性由 service 层负责 (调对应 service 验证 target 存在)
- 删 comment / file → service 显式 CASCADE 清 reactions (避免 FK NULL 污染)

权限模型:
- 任何能访问 target (read 权限) 都能 add reaction (类似 GitHub)
- 仅 member 本人能 remove 自己添加的 reaction
- admin 不 override (类似 comment 的 author 主权)

实施纪律:
- 0 production code 改动铁律 (W68 第 5/8 批): 本表暂不部署, 仅作 schema 备案
- down_revision 接 066_drive_comments_path (PR11 后续, 未合并)
  - PR11 落地时会产生 065 + 066 两个 migration, PR12 落地前主指挥按顺序 merge
  - 串单链纪律: W68 第 3 批 062/063 双头事故教训 (memory/w68-alembic-chain-discipline)
- 表名: drive_reactions (与 reactions 表区分, drive_ 前缀命名空间)
- emoji 列宽 16 char (4 个全宽度 emoji 上限, 实际 1-2 emoji 为主)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "067_drive_reactions"
down_revision: Union[str, None] = "066_drive_comments_path"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ===== drive_reactions =====
    op.create_table(
        "drive_reactions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        # polymorphic target: 'comment' / 'file' / 'note'
        sa.Column(
            "target_type",
            sa.String(16),
            nullable=False,
            comment="目标类型: 'comment' (drive_comments.id) / 'file' (knowledge.id) / 'note' (drive_notes.id, 未来 PR)",
        ),
        sa.Column(
            "target_id",
            sa.Integer(),
            nullable=False,
            comment="polymorphic target ID (FK 由 service 层验证, 不在 DB 层强制)",
        ),
        sa.Column(
            "member_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="CASCADE"),
            nullable=False,
            comment="反应者 member.id (NOT NULL, CASCADE: 用户注销 → 反应全清)",
        ),
        sa.Column(
            "emoji",
            sa.String(16),
            nullable=False,
            comment="emoji 字面值 (Unicode, e.g. 👍 / ❤️ / 🎉 — 内置 12 个白名单)",
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
        # UNIQUE: 同一 user 对同一 target 同一 emoji 不能重复
        sa.UniqueConstraint(
            "target_type", "target_id", "member_id", "emoji",
            name="uq_drive_reactions_target_member_emoji",
        ),
        # CHECK: target_type 必须在白名单 (DB 层兜底)
        sa.CheckConstraint(
            "target_type IN ('comment', 'file', 'note')",
            name="ck_drive_reactions_target_type",
        ),
    )

    # === 索引 ===
    # 索引 1: (target_type, target_id) 复合 — list_reactions 聚合高频
    op.create_index(
        "ix_drive_reactions_target",
        "drive_reactions",
        ["target_type", "target_id"],
        unique=False,
    )
    # 索引 2: (member_id) 单列 — list_my_reactions 高频
    op.create_index(
        "ix_drive_reactions_member",
        "drive_reactions",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_drive_reactions_member", table_name="drive_reactions")
    op.drop_index("ix_drive_reactions_target", table_name="drive_reactions")
    op.drop_table("drive_reactions")