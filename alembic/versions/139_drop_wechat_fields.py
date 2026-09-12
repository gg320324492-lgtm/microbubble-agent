"""139: 企业微信下线 — members 删 6 个微信列 + 3 个 CI 唯一索引

2026-09 决策: 课题组不再使用企业微信, 相关代码整体清理 (app/wechat/ 包、
回调路由、提醒微信推送通道均删除, 提醒改走站内 notification_service)。

本迁移 (与 app/models/member.py 同步):
- 删列: wechat_id (NOT NULL, 057) / wechat_nickname / wechat_remark /
  personal_wechat_id / wechat_mobile / external_userid (002)
- 删索引: ix_members_wechat_id_ci (054) / ix_members_personal_wechat_id_ci (055) /
  ix_members_external_userid_ci (056) — 均为 LOWER() 函数唯一索引
- wechat_id 的 NOT NULL 约束随列删除消失, 新建成员不再需要微信标识
- member_seeder / sanitize_fixture / @提及 wechat_id 匹配等已同步清理

数据说明: 微信 ID 数据随 upgrade 丢弃 (课题组已停用企微, 数据无业务价值)。
downgrade 只恢复列结构 (wechat_id 用 057 同款 placeholder 回填), 不恢复数据。

Revision ID: 139_drop_wechat_fields
Revises: 138_recreate_commercial_tables
Create Date: 2026-09-12
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "139_drop_wechat_fields"
down_revision: Union[str, None] = "138_recreate_commercial_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (列名, 类型) — 升级删除 / 降级恢复
DROPPED_COLUMNS: list[tuple[str, sa.types.TypeEngine]] = [
    ("wechat_id", sa.String(100)),
    ("wechat_nickname", sa.String(100)),
    ("wechat_remark", sa.String(100)),
    ("personal_wechat_id", sa.String(100)),
    ("wechat_mobile", sa.String(20)),
    ("external_userid", sa.String(100)),
]

# 054/055/056 建的 LOWER() 函数唯一索引
CI_INDEXES: list[tuple[str, str]] = [
    ("ix_members_wechat_id_ci", "wechat_id"),
    ("ix_members_personal_wechat_id_ci", "personal_wechat_id"),
    ("ix_members_external_userid_ci", "external_userid"),
]


def upgrade() -> None:
    # 先删函数索引 (依赖列, 显式删更清晰; IF EXISTS 防环境差异)
    for index_name, _ in CI_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {index_name}")

    for column_name, _ in DROPPED_COLUMNS:
        op.drop_column("members", column_name)


def downgrade() -> None:
    # 恢复列结构; wechat_id 数据不可恢复, 用 057 同款 placeholder 回填满足 NOT NULL
    for column_name, column_type in DROPPED_COLUMNS:
        op.add_column("members", sa.Column(column_name, column_type, nullable=True))

    op.execute(
        "UPDATE members SET wechat_id = '__NULL_BACKFILL_' || id::text || '__' "
        "WHERE wechat_id IS NULL"
    )
    op.alter_column("members", "wechat_id", existing_type=sa.String(100), nullable=False)

    for index_name, column_name in CI_INDEXES:
        op.execute(
            f"CREATE UNIQUE INDEX {index_name} ON members (LOWER({column_name}))"
        )
