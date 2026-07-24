"""v2 PR17: 文件秒传 (hash dedupe) 审计字段 (2026-07-24, W68 第 14 批 B-1)

背景:
- ppt-word-replicated-swing.md PR4 部分真未实施: 文件秒传 (hash dedupe)
  * W68 第 6 批调研发现 knowledge.file_hash 字段已有 (PR4 加的, alembic 044)
  * 但**上传时未走查重**: 每次上传都实打实写 MinIO, 相同内容浪费带宽/存储
- PR17 补齐"秒传"能力: 上传前算 sha256, hash 命中已存在 file → 秒返 file_id, 跳过 MinIO 上传

设计:
- 加 2 列到 knowledge (审计用, 不影响老逻辑):
  * drive_dedupe_count Integer default 0: 该 file 被秒传命中的累计次数
  * drive_dedupe_first_hit_at DateTime nullable: 首次被秒传命中的时间戳
- 秒传本身走 file_hash (已有列 + ix_knowledge_file_hash 部分索引已有 alembic 044)
- 这 2 列纯审计: 统计"秒传节省了多少次真实上传", 首次命中时间用于分析热点文件

依赖:
- 044 (PR4): knowledge.file_hash + ix_knowledge_file_hash 部分索引 (WHERE deleted_at IS NULL AND storage_mode='drive')
- 076_drive_comments_path_backfill: alembic 链末尾 (W68 第 13 批 renumber 后)

实施纪律:
- alembic 串单链 (接 076_drive_comments_path_backfill, 留 079+ 后续 PR)
  不可双 head (CLAUDE.md 2026-07-24 alembic chain discipline 铁律)
- 纯加列, 不动老列 / 不改 file_hash 索引 (0 production code 改动铁律 — 新功能扩展例外已批)
- server_default '0' 让存量行 (百万条) 立即有值, 不 NULL (避免 count+1 时 NULL+1 报错)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "078_drive_dedupe_audit"
# W68 第 14 批 hot-fix: B-2 alembic 079 (team_folders) 已合并到 main, 必接 079
# 串单链 076 → 079 → 078 (主指挥 d5ff4d8f2 + 2ea3c26aa 修订)
down_revision: Union[str, None] = "079_team_folders"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    """PR17: knowledge 加秒传审计 2 列"""
    op.add_column(
        "knowledge",
        sa.Column(
            "drive_dedupe_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "knowledge",
        sa.Column(
            "drive_dedupe_first_hit_at",
            sa.DateTime(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """PR17 downgrade: 删 2 审计列"""
    op.drop_column("knowledge", "drive_dedupe_first_hit_at")
    op.drop_column("knowledge", "drive_dedupe_count")
