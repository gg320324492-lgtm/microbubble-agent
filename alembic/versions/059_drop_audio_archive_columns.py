"""Drop audio_archive columns from meetings table

2026-07-12 死代码清理: app/services/audio_archive_service.py 已删 (孤儿, 无 caller)
- AudioArchiveWriter.feed_pcm() / .finalize() 从未被调用
- audio_archive_url / audio_archived / audio_archived_at 等列因此变成 write-only

但 alembic 011_meeting_audio_archive.py 创建的列实际在生产 DB 存在 (历史 ALTER TABLE)
- 保留 011 作为历史 (prod DB 已 ALTER, drop_column 会破坏数据迁移)
- 不动 011, 新加 059 安全 DROP

被删除的列 (write-only 永远 null/false):
- audio_archive_url (VARCHAR 500)
- audio_duration_seconds (FLOAT)
- audio_size_bytes (BIGINT)
- audio_archived_at (TIMESTAMPTZ)
- audio_archived (BOOLEAN)

相关代码清理:
- app/models/meeting.py: 删 5 个 Column
- app/api/v1/meeting.py: 删 DELETE /meetings/{id}/audio handler (lines 591-628)
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "059_drop_audio_archive_columns"
down_revision: Union[str, None] = "058_knowledge_is_team_shared"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF EXISTS 保证幂等 (prod DB 可能有/可能无这些列)
    op.execute("""
        ALTER TABLE meetings
        DROP COLUMN IF EXISTS audio_archived,
        DROP COLUMN IF EXISTS audio_archived_at,
        DROP COLUMN IF EXISTS audio_size_bytes,
        DROP COLUMN IF EXISTS audio_duration_seconds,
        DROP COLUMN IF EXISTS audio_archive_url
    """)


def downgrade() -> None:
    # 回滚: 重建列 (旧 prod 数据可能丢失 — 历史 IF NOT EXISTS 的反向无法恢复)
    op.execute("""
        ALTER TABLE meetings
        ADD COLUMN IF NOT EXISTS audio_archive_url VARCHAR(500),
        ADD COLUMN IF NOT EXISTS audio_duration_seconds FLOAT,
        ADD COLUMN IF NOT EXISTS audio_size_bytes BIGINT,
        ADD COLUMN IF NOT EXISTS audio_archived_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS audio_archived BOOLEAN DEFAULT FALSE
    """)