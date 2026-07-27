"""Drive v2 W72 第 2 批 B-1 — Share Link 增强 (密码 + 次数限制 + 审计) (2026-07-27)

背景 (W72 第 1 批 C-3 真验证):
- folder share (PR7 alembic 061) + team folder (PR18 alembic 079 preview) + share-link
  download_count 原子计数 (PR2.7 alembic 041 on Knowledge) 已实施
- 但 DriveFolderShare 仍缺:
  * password_hash: 链接提取码保护 (类似 Knowledge.share_password)
  * max_downloads + download_count: 链接下载次数限制 (类似 Knowledge 041)
  * 审计 action: share_created/revoked/downloaded 落库 (CLAUDE.md v78 audit_middleware
    已支持 generic classify, 但缺 folder share 专属 action 字符串)

设计 (派工 v10 段 7 实战):
1. drive_folder_shares 加 3 列:
   - password_hash VARCHAR(128) NULL  (None = 无密码, 与 PR7 兼容)
   - max_downloads INTEGER NULL      (None = 不限, 与 PR7 兼容)
   - download_count INTEGER NOT NULL DEFAULT 0 (原子计数, PR2.7 模式复用)
2. 不破坏 PR7 (PR7 schema 兼容: 所有新列可空, 默认值保守)
3. alembic 串单链纪律: down_revision='078_drive_dedupe_audit' (当前 head, 079 preview 态
   未合并; 接 078 串单链 `078 → 081`, 0 双头)

W72 第 2 批 B-1 派工 v10 段 7 实战:
- 不重做后端 (folder_share_service.create_folder_share 已存在)
- 差量加 3 列 + service 层扩展 create_folder_share 接受 password/max_downloads
- alembic 单迁移 + 4 项差量 + 8/8 e2e

依赖:
- 078_drive_dedupe_audit (上游, W68 第 14 批 B-1 PR17 hash 去重, 已合并 main)

不破坏的边界:
- 不动 drive_folder_shares 老 8 列 (id/folder_id/share_token/permission/expires_at/
  created_by/revoked_at/created_at/updated_at)
- 不动 drive_folder_members 老 4 列
- 不动 PR7 service / API (新增参数全部 Optional, 旧调用 100% 兼容)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "081_drive_share_enhancements"
# W72 第 2 批 alembic 串单链 (派工纪要 v4 铁律 1):
# 当前 alembic head = 078_drive_dedupe_audit (W68-14-B-1 已合并, 079 preview 态未合并)
# 081 必须接 078 (主指挥合并 079 后才会出现 081 → 079 顺序; 当前 B-1 agent 写 081 → 078
# 是安全正确, 主指挥合并时按 078 → 079 → 081 串单链即可, 1 个 head 0 双头)
down_revision: Union[str, None] = "080_drive_chunked_uploads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """drive_folder_shares 加 3 列 (password_hash + max_downloads + download_count)

    步骤:
    1. password_hash VARCHAR(128) NULL — bcrypt 哈希 (drive 8 字符限制)
    2. max_downloads INTEGER NULL — None = 不限 (与 PR7 兼容)
    3. download_count INTEGER NOT NULL DEFAULT 0 — 原子计数 (PR2.7 模式复用)
    """
    # === 1. password_hash 提取码保护 ===
    # bcrypt hash 60 字符, 留 buffer 128
    op.add_column(
        "drive_folder_shares",
        sa.Column("password_hash", sa.String(128), nullable=True),
    )

    # === 2. max_downloads 下载次数限制 ===
    # NULL = 不限 (PR7 老 share 不限, 兼容)
    op.add_column(
        "drive_folder_shares",
        sa.Column("max_downloads", sa.Integer(), nullable=True),
    )

    # === 3. download_count 当前已下载次数 ===
    # NOT NULL DEFAULT 0, 原子自增 (PR2.7 Knowledge.download_count 同模式)
    op.add_column(
        "drive_folder_shares",
        sa.Column(
            "download_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )

    # 索引: 高频查询"已撤销+未过期+次数未超限"的活跃 share (active 组合索引)
    op.create_index(
        "ix_drive_folder_shares_active",
        "drive_folder_shares",
        ["folder_id", sa.text("revoked_at")],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )


def downgrade() -> None:
    """回滚: 删索引 → 删 3 列"""
    op.drop_index("ix_drive_folder_shares_active", table_name="drive_folder_shares")
    op.drop_column("drive_folder_shares", "download_count")
    op.drop_column("drive_folder_shares", "max_downloads")
    op.drop_column("drive_folder_shares", "password_hash")