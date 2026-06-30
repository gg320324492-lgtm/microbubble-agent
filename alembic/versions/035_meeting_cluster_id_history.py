"""v2026-06-27 P2-2: meetings 加 cluster_id_history 列

Revision ID: 035_cluster_id_history
Revises: 034_reset_voice_sample_count
Create Date: 2026-06-27

背景:
- 083 事件: cluster_id 注入到 transcript 后, 如果注入错误无法按时间戳回溯
  (只能 rollback voice_embedding, 不能 rollback transcript)
- 用户决策: 每次 inject cluster_id 时保留 history entry, 便于 rollback 工具定位

结构:
- JSONB 列, 默认 '[]'
- 每条 entry: {ts, source, injector, n_segments, kmeans_k, cluster_to_name, notes}
  - source: "inject_083" | "reprocess_meeting" | "purify" | "rollback"
  - injector: 操作人/脚本名
  - n_segments: 注入的段数
  - kmeans_k: KMeans K (如有)
  - cluster_to_name: cluster_N → name 映射
  - notes: 备注
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "035_cluster_id_history"
down_revision: Union[str, None] = "034_reset_voice_sample_count"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. 加 cluster_id_history 列 (JSONB, nullable, default='[]')
    op.add_column(
        "meetings",
        sa.Column("cluster_id_history", sa.JSON(), nullable=True),
    )
    # 2. 初始化已有 meetings 为空 list
    op.execute("UPDATE meetings SET cluster_id_history = '[]'::jsonb WHERE cluster_id_history IS NULL")
    # 3. 给未来新插入的会议加 server_default
    op.alter_column(
        "meetings",
        "cluster_id_history",
        server_default="[]",
    )


def downgrade() -> None:
    op.drop_column("meetings", "cluster_id_history")
