"""meetings.status VARCHAR(20) -> VARCHAR(32) (类 20.147 W2+N 修复)

2026-08-04 (W2 +N 紧急修复): meetings.status 字段长度限制 20 字符, 但后端 post_meeting_tasks.py:870
会写 'completed_with_warnings' (24 字符), 导致:
- 写入失败 (value too long for type character varying(20))
- 业务代码 catch 后回退到 'error'
- 前端显示 "处理失败", 但 transcript 数据实际完整

本次事故: 会议 252 重跑后前端显示 "处理失败", 实际 transcript 83351 字符 + polished 523 段
都正确入库, 只是 status 字段写入失败。

修复: ALTER COLUMN TYPE VARCHAR(32), 兼容未来更长的 status 字符串
(类 20.147 W2+N 沉淀, 永久纪律: schema 字段长度必须 ≥ 业务代码最长的 status 字面量 + 2 buffer)

不修改历史 migration, 严格接 097 单链。

Run ``alembic upgrade head`` after this file is added.
"""
from alembic import op


revision = "098_meetings_status_varchar_32"
down_revision = "097_meeting_processing_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE meetings ALTER COLUMN status TYPE VARCHAR(32)")
    # upload_status 也用 20 字符, 同样的"长度不够"风险
    op.execute("ALTER TABLE meetings ALTER COLUMN upload_status TYPE VARCHAR(32)")


def downgrade() -> None:
    # 反向时若数据长度 > 20 会被截断, 加 CASCADE 警告
    op.execute("ALTER TABLE meetings ALTER COLUMN upload_status TYPE VARCHAR(20)")
    op.execute("ALTER TABLE meetings ALTER COLUMN status TYPE VARCHAR(20)")
