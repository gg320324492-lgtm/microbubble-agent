"""v2 PR6-P15: personal_wechat_id case-insensitive uniqueness (防未来 mention / wechat/identity 撞车)

背景:
- PR6-P13 username case-insensitive 唯一 (alembic 053)
- PR6-P14 wechat_id case-insensitive 唯一 (alembic 054)
- 个人微信号 personal_wechat_id 当前 0 行非空 (2026-07-02 psql 验证), 但:
  - app/wechat/identity.py:79 resolve_by_wechat_id() 用 `Member.personal_wechat_id == wechat_id` 精确匹配
  - 未来若改 lower() 匹配 (对齐 PR6-P4 mention 3 路模式), 同样有 map 撞车风险
- 先用 alembic 加 case-insensitive UNIQUE INDEX 兜底真唯一, 防止数据污染扩散

设计:
1. 加 case-insensitive UNIQUE INDEX ix_members_personal_wechat_id_ci ON LOWER(personal_wechat_id)
2. NULL/空 personal_wechat_id 不进索引 (PG 默认 NULL 不参与 UNIQUE 约束, 多个 NULL 安全)
3. 实际数据 0 冲突 (35 行 members 全部 personal_wechat_id 为空字符串)
4. 与 PR6-P13/P14 同模式, 扩展 _IDENTIFIER_COLUMNS 白名单加 1 行

回滚策略: 直接 downgrade 删 case-insensitive index
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "055_personal_wechat_ci"
# 接 054 链 (PR6-P14 wechat_id case-insensitive uniqueness)
down_revision: Union[str, None] = "054_member_wechat_id_ci_unique"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P15: case-insensitive UNIQUE INDEX on LOWER(personal_wechat_id)

    步骤:
    1. 加 case-insensitive UNIQUE INDEX (PG 函数索引 LOWER(personal_wechat_id))
    注意: personal_wechat_id 旧版既不 UNIQUE 也不 INDEX, 不需要删任何旧索引
    """
    op.create_index(
        "ix_members_personal_wechat_id_ci",
        "members",
        [sa.text("LOWER(personal_wechat_id)")],
        unique=True,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """回滚: 删 case-insensitive 索引"""
    op.drop_index("ix_members_personal_wechat_id_ci", table_name="members")