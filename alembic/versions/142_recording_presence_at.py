"""142: 录音存活 presence 信号字段 (2026-10-08 P0-1 后端配套)

背景 (会议 255 事故根因 G 衍生):
- 09-15 修的心跳守卫是 Redis key (TTL 300s), 前端 60s 上报一次
- 实际事故中: 心跳根本未发 (根因 A), Redis key 在最后一次心跳后 300s 消失,
  cleanup 任务每 600s 扫一次 → 误杀窗口 = 心跳停止后 300~900 秒
- 2026-10-08 P0-3: 前端 pagehide/sendBeacon 通知后端 "页面离开" 事件,
  后端落库 recording_presence_at = NOW(). cleanup 看到 presence < N 分钟内的
  会议 → 跳过 (或降级为待确认, 不直接判死)

字段:
- recordings.recording_presence_at TIMESTAMP NULL
- 仅前端 pagehide/sendBeacon 写入, 正常心跳不写
- cleanup 用此字段做"软警告"判据: presence > 30min → 视为前端真消失 → 可判死
- presence <= 30min → 跳过 (即使是 error 状态, 也保留分片供前端重传)

不动 recording_started_at / recording_ended_at / heartbeat_redis (Redis key)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "142_recording_presence_at"
down_revision: Union[str, None] = "141_zb2_backup_kb_purge"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL 列, 不破坏老数据
    op.add_column(
        "meetings",
        sa.Column("recording_presence_at", sa.DateTime(), nullable=True),
    )
    # 索引用于 cleanup 扫描 (WHERE recording_presence_at < NOW() - INTERVAL '30 minutes')
    # 部分索引: 只索引 status='recording' 行, 大幅减小索引体积
    op.create_index(
        "ix_meetings_recording_presence_at_recording",
        "meetings",
        ["recording_presence_at"],
        postgresql_where=sa.text("status = 'recording'"),
    )


def downgrade() -> None:
    op.drop_index("ix_meetings_recording_presence_at_recording", table_name="meetings")
    op.drop_column("meetings", "recording_presence_at")