"""v2 PR6-P14: mention wechat_id case-insensitive uniqueness (防 mention 解析歧义)

背景:
- PR6-P13 已修 username case-insensitive 唯一 (alembic 053)
- comment_service.py mention 解析也用 `wechat_id_map[row.wechat_id.lower()]` 做 case-insensitive 匹配
- 旧 ix_members_wechat_id (没有, 0 索引) - wechat_id 列既不 UNIQUE 也不 INDEX
- 2 个 member 如果 wechat_id 只大小写不同 (e.g. "WangTianZhi" vs "wangtianzhi"),
  mention 解析会撞 map → 提到 @wangtianzhi 时只能匹配后插入的那个
- 实际触发现场: 2026-07-02 PR6-P13 收官时 user 提问 "wechat_id 也要修吧?" (PR6-P4 3 路匹配 wechat_id 优先)

设计:
1. 加 case-insensitive UNIQUE INDEX ix_members_wechat_id_ci ON LOWER(wechat_id)
2. NULL/空 wechat_id 不进索引 (PG 默认 NULL 不参与 UNIQUE 约束, 多个 NULL 安全)
3. 实际数据 0 冲突 (docker psql 验证 21 行非空 wechat_id 全部 case-insensitive 唯一)
4. 不改 Member 模型 (wechat_id 没有 unique=True 标记, 无需移除)

回滚策略: 直接 downgrade 删 case-insensitive index
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "054_member_wechat_id_ci_unique"
# 接 053 链 (PR6-P13 username case-insensitive uniqueness)
down_revision: Union[str, None] = "053_member_username_ci_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P14: case-insensitive UNIQUE INDEX on LOWER(wechat_id)

    步骤:
    1. 加 case-insensitive UNIQUE INDEX (PG 函数索引 LOWER(wechat_id))
    注意: wechat_id 旧版既不 UNIQUE 也不 INDEX, 不需要删任何旧索引
    """
    op.create_index(
        "ix_members_wechat_id_ci",
        "members",
        [sa.text("LOWER(wechat_id)")],
        unique=True,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """回滚: 删 case-insensitive 索引"""
    op.drop_index("ix_members_wechat_id_ci", table_name="members")