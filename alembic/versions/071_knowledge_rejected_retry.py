"""knowledge_rejected 加 retry 跟踪字段 (2026-07-24, W68 第 10 批 B-3)

背景:
- B-2 (alembic 070) 已建 knowledge_rejected + knowledge_pending_review 表
- 本 PR 加 3 列跟踪 B-3 auto_intake_rollback_task 重试生命周期:
  * retry_count: 已重试次数 (0-3, ≥3 触发永久挂起)
  * next_retry_at: 下次重试时间 (24h 间隔, NULL = 不重试)
  * permanent_suspended: True = 已转 knowledge_pending_review (不再自动重试)

说明:
- 070 migration 已把这 3 列加在表上 (避免双迁移), 实际本迁移是个 no-op
- 保留本迁移文件以满足串单链 + 让 alembic head 071
- 实际场景: B-3 与 B-2 在同 agent 实施 → 071 是占位"已完成", 仅更新 revision 字符串

设计: 部分 partial index on next_retry_at WHERE permanent_suspended=false
- Celery beat 调度只扫描 active retry 候选, 不扫永久挂起 (减少索引体积)

依赖: knowledge_rejected 表 (B-2 已建)
下接: 未来 PR 可加 last_error_at / suspended_at 等审计字段

实施纪律:
- 0 production code 改动铁律 (W68 第 7 批): 仅 metadata, 不改老路径
- W68 第 11 批 C-1 alembic 串单链 rebase: down_revision 接 070_knowledge_rejected (B-2 新位置)
- 文件名 067 → 071: 避开 main 已存在的 067_drive_reactions
- 071 = B-3 retry/suspend/health-check 收尾 (占位 no-op, 字段已在 070 加好)
"""
from typing import Union

import sqlalchemy as sa
from alembic import op


revision: str = "071_knowledge_rejected_retry"
down_revision: Union[str, None] = "070_knowledge_rejected"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # 070 migration 已把 retry_count / next_retry_at / permanent_suspended 加在 knowledge_rejected 表上
    # (避免 071 重复 ALTER TABLE 报 column already exists)
    # 本 migration 仅作为 alembic 串单链占位, 真正的字段定义在 070
    #
    # 防御性 ALTER: 用 IF NOT EXISTS 兼容老库 (071 已存在但 070 还没跑过)
    op.execute(
        "ALTER TABLE knowledge_rejected ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0"
    )
    op.execute(
        "ALTER TABLE knowledge_rejected ADD COLUMN IF NOT EXISTS next_retry_at TIMESTAMP"
    )
    op.execute(
        "ALTER TABLE knowledge_rejected ADD COLUMN IF NOT EXISTS permanent_suspended BOOLEAN NOT NULL DEFAULT FALSE"
    )

    # partial index (Celery 调度只扫 active retry)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_knowledge_rejected_next_retry_at_partial
        ON knowledge_rejected (next_retry_at)
        WHERE permanent_suspended = FALSE
        """
    )


def downgrade() -> None:
    # 防御性 DROP: 不强删 (避免 066 跑过再跑 067 downgrade 时把 066 的列也删掉)
    op.execute("DROP INDEX IF EXISTS ix_knowledge_rejected_next_retry_at_partial")
    # 列定义是 066 拥有, 这里不下 ALTER TABLE (066 downgrade 会兜底)