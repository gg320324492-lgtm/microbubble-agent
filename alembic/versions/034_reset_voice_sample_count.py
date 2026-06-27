"""reset voice_sample_count to 1 for all enrolled members

2026-06-27 用户需求: 前端统一显示「1 次录入」。
原因: 自动学习链路已删除, 现有累计计数历史值无意义, 重置为干净基线。
保留 enroll_member L253 的 +1 自增逻辑 (成员主动录入时递增 1→2→3...)。

影响范围:
  - 15 个已录入成员 (voice_embedding IS NOT NULL) voice_sample_count 全部置 1
  - 13 个未录入成员保持 voice_sample_count = 0
  - 加权平均公式 (voiceprint_service.enroll_member L249) 仍依赖此字段, 不删字段
  - 投票加权 (post_meeting_tasks + reprocess_meeting) 仍读此字段, 不影响识别

rollback 风险: 原值不可恢复, downgrade 仅置 0 兜底, 无意义。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "034_reset_voice_sample_count"
down_revision: Union[str, None] = "033_mvh"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 只重置已录入成员 (voice_embedding IS NOT NULL), 未录入的保持 0
    op.execute(
        "UPDATE members SET voice_sample_count = 1 WHERE voice_embedding IS NOT NULL"
    )


def downgrade() -> None:
    # 不可逆操作 — 仅置 0 兜底, 原值无法恢复
    op.execute(
        "UPDATE members SET voice_sample_count = 0 WHERE voice_embedding IS NOT NULL"
    )