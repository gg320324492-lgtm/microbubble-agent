"""v31 兼容: 041_dedup_empty_sessions 是与 PR1-6 链并行的 data-migration 分支
(down_revision=040_drive_storage_mode, 不接 041_drive_share_download_count)

049 仅作为 merge point (空升级), 把两条 head (048 / 041_dedup_empty_sessions) 收口
跑完 upgrade head 后 DB 实际进度 = 048 (无 schema 改动, 041 的数据修复已 prior 跑过)

警告: 此迁移**不重跑** 041_dedup_empty_sessions 的数据修复 (chat_sessions dedup)。
原因: 041 数据修复是 destructive, 在 PR1-6 上线后已大概率跑过 (DB 留有 audit)。
如果 PR1 部署时没跑 041, 此处需手动:
  docker exec microbubble-agent-app-1 alembic upgrade 041_dedup_empty_sessions
然后再 alembic upgrade head。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "049_dedup_empty_sessions_merge"
# 接 041_dedup_empty_sessions (平行分支) + 048 (新 PR7)
# 升 049 后整链统一到 049
down_revision: Union[str, tuple, None] = ("041_dedup_empty_sessions", "048_drive_requests_audit")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空 merge: 只 stamp"""
    pass


def downgrade() -> None:
    """空 merge: 不 reverse 任何分支"""
    pass
