"""v2 PR7 收官: 修复 audit_log.created_at 默认值

048_drive_requests_audit.py 用 server_default="now()" 在某些 PG 版本下
被字面量化为执行那一刻的时间戳, 导致后续 INSERT 全部用同一固定时间。
结果: audit_log.created_at 永远是 2026-07-01 18:24:25.521563, 时间窗口查询
(如 "WHERE created_at > NOW() - INTERVAL '5 minutes'") 永远返回 0 行。

修复:
  ALTER TABLE audit_log ALTER COLUMN created_at SET DEFAULT now()

副作用:
  - 已有 250 行不动 (历史数据 created_at 已字面化)
  - 后续 INSERT 用真正的 now() 函数调用, 每次都返回 INSERT 时刻的 timestamp
  - 时间窗口查询生效 (Group 6 audit_log_auto_write 测试通过)

为何不能改 model 字段:
  - model 已经 sa.DateTime() 无 server_default (app 模型层默认 model_create),
    是 alembic 迁移执行时 PG 把字符串 'now()' 当字面量, 不是 SQL 函数
  - 修 model 重跑 alembic 不会改 default
  - 必须显式 ALTER COLUMN ... SET DEFAULT now()

为何不用 CURRENT_TIMESTAMP:
  - now() 和 CURRENT_TIMESTAMP 在 PG 9.x 都是 statement_timestamp() 同义词,
    同一 SQL 语句内多次调用返回同一值 (事务级一致性)
  - audit_log 写入是单条 INSERT, 用 now() 完全够用
"""
from typing import Sequence, Union

from alembic import op

revision: str = "050_audit_log_now_default"
down_revision: Union[str, None] = "049_dedup_empty_sessions_merge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 必须用 sa.text('now()') 让 alembic 生成 ALTER COLUMN ... SET DEFAULT now()
    # 注意: 不要写 sa.text('CURRENT_TIMESTAMP'), 两者效果一致但 now() 跟项目其他迁移一致
    op.execute("ALTER TABLE audit_log ALTER COLUMN created_at SET DEFAULT now()")


def downgrade() -> None:
    # 还原到错误的固定值 (灾难性, 仅供 alembic downgrade 一致性)
    # 实际生产别 downgrade 这个迁移 (会破坏所有新 audit_log 行的时间准确性)
    op.execute(
        "ALTER TABLE audit_log ALTER COLUMN created_at "
        "SET DEFAULT '2026-07-01 18:24:25.521563'::timestamp without time zone"
    )