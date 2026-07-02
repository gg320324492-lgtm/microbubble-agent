"""v2 PR6-P16: external_userid case-insensitive uniqueness (防未来 wechat/identity 撞车)

背景:
- PR6-P13 username + PR6-P14 wechat_id + PR6-P15 personal_wechat_id 已加 case-insensitive 唯一
  (alembic 053/054/055)
- 第四个 identifier 列: external_userid (微信互通外部用户ID, wm 开头, 通常大写)
- 当前 0 行非空 (35 行 members 全部 external_userid 为空字符串, psql 验证), 迁移 0 冲突
- 业务动机: app/wechat/identity.py:41 IdentityResolver.resolve_by_external_userid()
  当前用精确匹配 `Member.external_userid == external_userid` (case-sensitive)
- 与 PR6-P13/014/015 同模式: 防未来 wechat/identity.py 改 lower() 匹配时出现 map 撞车

设计:
1. 加 case-insensitive UNIQUE INDEX ix_members_external_userid_ci ON LOWER(external_userid)
2. NULL/空 external_userid 不进索引 (PG 默认 NULL 不参与 UNIQUE 约束, 多个 NULL 安全)
3. 旧版无 external_userid 索引, 无需 drop
4. 实际数据 0 冲突, 迁移无需数据修复

回滚策略: 直接 downgrade 删 case-insensitive index
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "056_external_userid_ci"
# 接 055 链 (PR6-P15 personal_wechat_id case-insensitive uniqueness)
# 注: 055 revision 是 "055_personal_wechat_ci" (24 chars, VARCHAR(32) 限制)
down_revision: Union[str, None] = "055_personal_wechat_ci"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P16: case-insensitive UNIQUE INDEX on LOWER(external_userid)

    步骤:
    1. 加 case-insensitive UNIQUE INDEX (PG 函数索引 LOWER(external_userid))
    """
    op.create_index(
        "ix_members_external_userid_ci",
        "members",
        [sa.text("LOWER(external_userid)")],
        unique=True,
        postgresql_using="btree",
    )


def downgrade() -> None:
    """回滚: 删 case-insensitive 索引"""
    op.drop_index("ix_members_external_userid_ci", table_name="members")