"""v2 PR9: drive_file_versions 表 (2026-07-24)

背景:
- v2 PR4 (KnowledgeVersion + Knowledge.is_latest/version_number) 已实现"版本"概念,
  但每版都膨胀主表行, 7 列索引 + embedding 列每次都复用, 主表查询需要过滤 is_latest
- 本 PR 引入独立 drive_file_versions 表, 主表只保留当前版本 (1 行), 历史版本明细
  在独立表, query 简单 + 主表瘦身 + 变更审计与版本仓库职责分离

设计:
- 1 张新表:
  * drive_file_versions: 文件版本仓库 (file_id + version_number + minio_object_key + size + uploader_id + comment + is_current)
- 主键 file_id 关联到 knowledge.id (FK ON DELETE CASCADE, 删主表行自动清历史)
- (file_id, version_number) 复合索引: list_versions 高频
- (file_id, is_current) 复合索引: 查"当前版本" (每个 file_id 只 1 行 is_current=1)
- is_current 用 Integer 0/1 而非 Boolean: 跨 DB 兼容 (PG boolean/SQLite int), 业务层用 bool()

依赖: knowledge 表必须存在 (FK)
下接: drive_versions endpoints (POST/GET/DELETE)

回滚策略: 直接 DROP TABLE (无其他依赖, 无外部 FK 引用)

后续 PR (PR10):
- 共享盘版本 (folder 维度版本, 不同 file_id 间共享版本池)
- 版本对比 (diff 算法, 文本/二进制 hash diff)
- 版本标签 (v1.0 release tag, 自定义命名)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "063_drive_file_versions"
down_revision: Union[str, None] = "062_drive_comments"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # drive_file_versions 表
    op.create_table(
        "drive_file_versions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "file_id",
            sa.Integer(),
            sa.ForeignKey("knowledge.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_number",
            sa.Integer(),
            nullable=False,
            comment="同一 file_id 下的版本号 (1, 2, 3... 单调递增)",
        ),
        sa.Column(
            "minio_object_key",
            sa.String(length=500),
            nullable=False,
            comment="MinIO object_name (uploads/drive/{owner_id}/v{n}_{hash12}_{ts}{ext})",
        ),
        sa.Column(
            "size",
            sa.BigInteger(),
            nullable=False,
            comment="文件字节大小",
        ),
        sa.Column(
            "uploader_id",
            sa.Integer(),
            sa.ForeignKey("members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "comment",
            sa.Text(),
            nullable=True,
            comment="版本备注 (用户输入, 可选)",
        ),
        sa.Column(
            "is_current",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="是否当前版本 (1=是, 0=否, 同一 file_id 只有 1 行 =1)",
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

    # 索引: (file_id, version_number) 复合 — list_versions 按版本号降序排高频
    op.create_index(
        "ix_drive_file_versions_file_version",
        "drive_file_versions",
        ["file_id", "version_number"],
        unique=False,
    )
    # 索引: (file_id, is_current) 复合 — 查"当前版本" (每 file_id 只 1 行 is_current=1)
    op.create_index(
        "ix_drive_file_versions_file_current",
        "drive_file_versions",
        ["file_id", "is_current"],
        unique=False,
    )
    # 索引: uploader_id 单列 — 按上传者查询
    op.create_index(
        "ix_drive_file_versions_uploader",
        "drive_file_versions",
        ["uploader_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_drive_file_versions_uploader", table_name="drive_file_versions")
    op.drop_index("ix_drive_file_versions_file_current", table_name="drive_file_versions")
    op.drop_index("ix_drive_file_versions_file_version", table_name="drive_file_versions")
    op.drop_table("drive_file_versions")