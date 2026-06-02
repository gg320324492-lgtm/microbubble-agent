"""Add transcript_polished JSON column to meetings

2026-06-02 三级润色流水线 L3：会议挂断时全文精润色结果持久化。
存的是 [{segment_id, speaker, text, removed, reason}] 数组。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "018_meet_tp"
down_revision: Union[str, None] = "017_v192"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "meetings",
        sa.Column("transcript_polished", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("meetings", "transcript_polished")
