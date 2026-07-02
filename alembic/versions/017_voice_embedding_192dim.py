"""voice_embedding 列类型从 vector(256) 改为 vector(192)

3D-Speaker ERes2Net 实际输出 192 维，原项目误写为 256。
修正模型 ID 之后必须同步修正列类型。prod DB 验证全为 NULL。

注意：revision ID 用短名 `017_v192`（8 字符），
因 alembic_version.version_num 列是 VARCHAR(32)，长名会触发
`value too long for type character varying(32)` 错误。
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '017_v192'
down_revision: Union[str, None] = '015_reminder_task_id_nullable'  # 2026-07-03 跳过 016_meeting_template (模板管理已删除)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # prod DB 验证 voice_embedding 全为 NULL，ALTER TYPE 安全
    op.execute("ALTER TABLE members ALTER COLUMN voice_embedding TYPE vector(192)")
    # HNSW 索引（migrations/013）自动跟随列类型变化，无需重建


def downgrade() -> None:
    op.execute("ALTER TABLE members ALTER COLUMN voice_embedding TYPE vector(256)")
