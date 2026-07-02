"""v2 PR6-P13: mention username case-insensitive uniqueness (防 mention 解析歧义)

背景:
- comment_service.py mention 解析用 `username_map[username.lower()]` 做 case-insensitive 匹配
- 旧 ix_members_username UNIQUE INDEX 是 case-sensitive (普通 btree)
- 2 个 member 如果 username 只大小写不同 (e.g. "Alice" vs "alice"), 旧约束允许 → username_map 冲突 → 提到 @alice 时只能匹配后写的那一个
- 实际触发现场: 2026-07-02 用户报告 "测试账号 xiaoqi_testbot 与 Alice 区分", 担心未来协作时其他成员被误通知

设计:
1. 删旧 case-sensitive UNIQUE INDEX ix_members_username
2. 加 case-insensitive UNIQUE INDEX ix_members_username_lower ON LOWER(username)
3. NULL/空 username 不进索引 (PG 默认 NULL 不参与唯一约束, 多个 NULL 安全)
4. 实际数据全部 lowercase (docker psql 验证 0 重复) → 迁移无需数据修复

回滚策略: 直接 downgrade 删 case-insensitive index + 重建 case-sensitive unique
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "053_member_username_ci_unique"
# 接 052 链 (PR6-P8 rich title/body)
down_revision: Union[str, None] = "052_drive_notification_rich"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P13: case-insensitive UNIQUE INDEX on LOWER(username)

    步骤:
    1. 删除旧 case-sensitive UNIQUE INDEX
    2. 创建 case-insensitive UNIQUE INDEX (PG 函数索引 LOWER(username))
    """
    # 1. 删旧 case-sensitive unique 索引
    op.drop_index("ix_members_username", table_name="members")

    # 2. 加 case-insensitive unique 索引 (函数索引: LOWER(username))
    op.create_index(
        "ix_members_username_ci",
        "members",
        [sa.text("LOWER(username)")],
        unique=True,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """回滚: 删 case-insensitive 索引, 重建 case-sensitive 索引"""
    op.drop_index("ix_members_username_ci", table_name="members")
    op.create_index(
        "ix_members_username",
        "members",
        ["username"],
        unique=True,
    )