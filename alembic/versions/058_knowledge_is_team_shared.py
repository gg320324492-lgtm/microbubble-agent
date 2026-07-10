"""v2 PR6-P19: knowledge.is_team_shared 标志 (团队共享盘隔离)

背景:
- v2 PR6-P18 收官: drive 改 Pinia store (v2.15) + smart confirm (v2.14) + admin 越权 (v2.13)
- 当前问题: 用户上传到「团队共享盘」(specialView='team' 时) 的文件, 也显示在「个人网盘」root
  - 用户体验混乱: 「我明明是上传到团队盘, 怎么个人网盘也有?」
  - 业务动机: 个人网盘 = 私有/工作区文件, 团队盘 = 全员共享文件, 物理隔离
  - 现状 hardcode 关系: folder_id IS NULL = 个人网盘 root, 但 visibility=team 也包括个人 root
- 旧方案 (考虑过):
  - 纯前端过滤: 语义不清, 团队成员上传到 root visibility=team 算个人还是团队?
  - team 根 folder 隔离: 涉及 folder migration + auto-create, 改动面太大
- 选择方案: `is_team_shared` 布尔列, 默认 false (向后兼容), 用户在 team 视图上传 = true

设计 (1 步迁移 + 索引):
1. ALTER TABLE knowledge ADD COLUMN is_team_shared BOOLEAN NOT NULL DEFAULT FALSE
2. CREATE INDEX ix_knowledge_is_team_shared (where deleted_at IS NULL, partial)
   - 大部分文件 is_team_shared=false (个人), 加 partial index 让 list_drive_files 走索引
3. 不 backfill (历史文件默认 false, 全部归类为「个人网盘」)
   - 兼容: 历史用户在 team 视图上传的文件被归到「个人」, 这是用户的过去行为
   - 用户可手动从「个人」移到「团队」(批量改 is_team_shared, 留 v2.20 admin CLI)

回滚策略: 直接 DROP COLUMN (无依赖, 无 NOT NULL 风险)

未来 follow-up:
- v2.20 admin CLI: bulk update is_team_shared by uploaded_at range (修正历史误归类文件)
- v2.21 frontend: FolderTree 加 view 过滤 (按 specialView 隐藏 team/personal 各自不显示的 folder)
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


revision: str = "058_knowledge_is_team_shared"
down_revision: Union[str, None] = "057_wechat_id_not_null"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 1. 加 is_team_shared 列 (默认 false, NOT NULL 避免后端忘记传)
    op.add_column(
        "knowledge",
        sa.Column(
            "is_team_shared",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="v2 PR6-P19: True=用户上传时在 team shared 视图, 不在个人网盘显示",
        ),
    )

    # 2. 加 partial index (只索引活跃文件 + 团队共享, 大幅加速 list_drive_files view=personal 过滤)
    #    partial 索引: WHERE deleted_at IS NULL AND is_team_shared = true
    #    大部分行 is_team_shared=false, partial 让索引保持小, 写不频繁
    op.create_index(
        "ix_knowledge_team_shared",
        "knowledge",
        ["is_team_shared", "created_at"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL AND is_team_shared = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_team_shared", table_name="knowledge")
    op.drop_column("knowledge", "is_team_shared")
