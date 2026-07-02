"""v2 PR6-P17: wechat_id NOT NULL 约束 (防 NULL 渗透)

背景:
- PR6-P13/14/15/16 收官: 4 个 identifier 列 (username/wechat_id/personal_wechat_id/external_userid)
  都加了 case-insensitive UNIQUE INDEX 兜底
- 但 wechat_id 列当前允许 NULL (Column(String(100)) 无 nullable=False)
- 14/35 行 members 的 wechat_id IS NULL (psql 验证 2026-07-03):
  - 8 个真实成员 (董昊宇/李锐远/周之超/雒培媛/alumni/孟祥琪/吴怡霏/蒋芦笛/刘子煜)
  - 6 个测试账号 (xiaoqi_testbot/Alice Drive Test/Bob/Charlie/pr1_temp_user/xiaoqi_testbot_2)

业务动机:
- 企业微信成员通常都有 wechat_id (否则无法接收 mention/wechat 消息)
- 当前 NULL wechat_id 容易"渗透" (例如: 新成员 API POST 时忘传 wechat_id → DB 接受 NULL → mention 永远无法 mention 这人)
- 加 NOT NULL 约束 = 防 NULL 渗透 (DB 层兜底, 未来任何 caller 忘传 → IntegrityError 立即报错)

设计 (3 步迁移):
1. 回填 14 行 NULL 为 placeholder `__NULL_BACKFILL_<id>__` (避免 PR6-P14 ix_members_wechat_id_ci UNIQUE 冲突)
   - placeholder 唯一性: `<id>` 数字保证不重复 (e.g. id=8 → '__NULL_BACKFILL_8__')
   - LOWER() 不冲突 (placeholder 格式特殊, 不可能撞真实 wechat_id)
2. ALTER COLUMN wechat_id SET NOT NULL (PG 11+ 不需 rewrite table)
3. UPDATE placeholder 加注释 (PR 描述标记, 留给后续 cleanup 真实值)

回滚策略: 直接 downgrade 删 NOT NULL + UPDATE placeholder 回 NULL (谨慎, 防回滚丢数据)

未来 follow-up:
- 应用层 MemberCreate schema wechat_id: Optional → required (本次范围外, 留给业务决定)
- 14 行 placeholder 需要 admin 真实填入 (本次范围外, 留给业务决定)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "057_wechat_id_not_null"
# 接 056 链 (PR6-P16 external_userid case-insensitive uniqueness)
down_revision: Union[str, None] = "056_external_userid_ci"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """PR6-P17: wechat_id NOT NULL 约束 (3 步迁移)

    步骤:
    1. 回填 14 行 NULL 为唯一 placeholder '__NULL_BACKFILL_<id>__'
       - 避免 PR6-P14 UNIQUE INDEX 冲突 (LOWER('') 多行重复 → UNIQUE 报错)
       - placeholder 唯一性: '<id>' 保证不重复
    2. ALTER COLUMN wechat_id SET NOT NULL
    3. 验证: 所有行 wechat_id NOT NULL (sanity check)
    """
    bind = op.get_bind()

    # 步骤 1: 回填 NULL 为唯一 placeholder
    # 使用原生 SQL (参数化绑定避免 SQL 注入)
    op.execute(
        sa.text(
            "UPDATE members SET wechat_id = '__NULL_BACKFILL_' || id::text || '__' "
            "WHERE wechat_id IS NULL"
        )
    )

    # 步骤 2: ALTER COLUMN SET NOT NULL
    # PG 11+ ALTER COLUMN ... SET NOT NULL 不需要 rewrite table (因为 wechat_id 已 NOT NULL via backfill)
    op.alter_column(
        "members",
        "wechat_id",
        existing_type=sa.String(length=100),
        nullable=False,
    )

    # 步骤 3: 验证 sanity check (应用层 sanity, alembic 不会自动跑)
    # 通过 raw SQL 检查所有行 wechat_id NOT NULL
    result = bind.execute(sa.text("SELECT COUNT(*) FROM members WHERE wechat_id IS NULL"))
    null_count = result.scalar()
    if null_count is not None and null_count > 0:
        raise RuntimeError(
            f"PR6-P17 迁移失败: 仍有 {null_count} 行 wechat_id IS NULL (回填步骤 1 未成功)"
        )


def downgrade() -> None:
    """回滚: 删 NOT NULL + placeholder 改回 NULL (谨慎, 防数据污染)"""
    # 步骤 1: ALTER COLUMN DROP NOT NULL
    op.alter_column(
        "members",
        "wechat_id",
        existing_type=sa.String(length=100),
        nullable=True,
    )
    # 步骤 2: placeholder 改回 NULL (admin 后续可填真实值)
    op.execute(
        sa.text(
            "UPDATE members SET wechat_id = NULL "
            "WHERE wechat_id LIKE '__NULL_BACKFILL_%__'"
        )
    )