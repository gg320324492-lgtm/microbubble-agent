"""v2 PR15: drive_version_tags 表 (2026-07-24, W68 第 12 批 B-2)

背景:
- W68 第 8 批 B-2 PR9 文件版本历史 (commit 21a1906a8) 已实现 version_number 自动递增
  * drive_file_versions.version_number: 1, 2, 3... 单调递增整数
  * is_current 标识当前版本
  * Knowledge 主表保留当前版本 (1 行)
- 但**无标签系统** (semantic tag 如 v1.0 / release-2024.10 / stable / deprecated)
- 用户期望给特定版本打标签 (release / stable / deprecated / security / auto-save / manual)
- 缺语义标签时, 用户无法快速定位"哪个版本是 2024 年 10 月的发布版"
- 本 PR 引入 drive_version_tags 表 (1:N to drive_file_versions) + 12 个内置白名单

设计:
- 1 张新表:
  * drive_version_tags: 文件版本标签表 (id + version_id (FK) + tag_name + tag_description + color + created_by + created_at)
  * 注意: tag 关联到 DriveFileVersion.id (不是 file_id) — 同一 file_id 不同 version 可有不同 tag
  * 理由: 标签是版本的属性, 不是文件的属性 (v1=stable, v2=deprecated, v3=experimental)
- 主键 file_id 关联到 knowledge.id (FK ON DELETE CASCADE, 删主表行自动清历史)
- UNIQUE 约束 (version_id, tag_name) — 同一 version 同一 tag 唯一
- tag_name 长度 VARCHAR(64) — 容纳 12 个内置白名单 (最长 "release-2024.10" 约 16 字符)
- color VARCHAR(16) — 16 进制色 (#FF7A5C / red / blue 等 16 字符内, 简单 hex)
- 索引: (version_id) 单列 — list_tags_by_version 高频
- 索引: (tag_name) 单列 — get_file_by_tag 跨文件反查高频

依赖: drive_file_versions 表必须存在 (FK)
下接: PR16+ 继续 (label 自动规则 + 跨文件标签搜索)

回滚策略: 直接 DROP TABLE (无其他依赖, 无外部 FK 引用)

实施纪律:
- 0 production code 改动铁律 (W68 第 12 批): 纯新功能, 不动 PR9/PR11 老逻辑
- W68 第 4 批 串单链纪律: down_revision 接 069_drive_comments_recursive_func (current main HEAD)
  merge 后 verify ScriptDirectory.get_heads() == ['070_drive_version_tags']
  期望只 1 个 head (CLAUDE.md W68 第 4 批纪律 + memory/w68-alembic-chain-discipline-2026-07-24.md)
- 不用 PostgreSQL function (纯 schema 扩展, 不需要 STABLE 标记)
- 不创建新 GIN 索引 (tag_name 是分类查询, btree 已够用)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "070_drive_version_tags"
down_revision: Union[str, None] = "069_drive_comments_recursive_func"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # drive_version_tags 表
    op.create_table(
        "drive_version_tags",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "version_id",
            sa.Integer(),
            sa.ForeignKey("drive_file_versions.id", ondelete="CASCADE"),
            nullable=False,
            comment="DriveFileVersion.id — 标签关联的具体版本 (FK ON DELETE CASCADE)",
        ),
        sa.Column(
            "tag_name",
            sa.String(length=64),
            nullable=False,
            comment="标签名称 (12 个内置白名单: release/stable/deprecated/security/auto-save/manual/breaking/experimental/legacy/featured/archived/final)",
        ),
        sa.Column(
            "tag_description",
            sa.Text(),
            nullable=True,
            comment="标签描述 (用户输入, 可选, 比如 '2024 年 10 月发布版 - 论文终稿')",
        ),
        sa.Column(
            "color",
            sa.String(length=16),
            nullable=True,
            comment="标签颜色 (16 进制 hex e.g. '#FF7A5C', NULL 用默认色)",
        ),
        sa.Column(
            "created_by",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
            comment="标签创建者 member.id",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # UNIQUE 约束: (version_id, tag_name) — 同一 version 同一 tag 唯一
    op.create_unique_constraint(
        "uq_drive_version_tags_version_tag",
        "drive_version_tags",
        ["version_id", "tag_name"],
    )

    # 索引: version_id 单列 — list_tags_by_version 高频
    op.create_index(
        "ix_drive_version_tags_version",
        "drive_version_tags",
        ["version_id"],
        unique=False,
    )

    # 索引: tag_name 单列 — get_file_by_tag 跨文件反查高频 (e.g. 找所有 'release' 标签)
    op.create_index(
        "ix_drive_version_tags_tag_name",
        "drive_version_tags",
        ["tag_name"],
        unique=False,
    )

    # 索引: created_by 单列 — 按标签创建者查询 (审计)
    op.create_index(
        "ix_drive_version_tags_created_by",
        "drive_version_tags",
        ["created_by"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_drive_version_tags_created_by", table_name="drive_version_tags")
    op.drop_index("ix_drive_version_tags_tag_name", table_name="drive_version_tags")
    op.drop_index("ix_drive_version_tags_version", table_name="drive_version_tags")
    op.drop_constraint("uq_drive_version_tags_version_tag", "drive_version_tags", type_="unique")
    op.drop_table("drive_version_tags")