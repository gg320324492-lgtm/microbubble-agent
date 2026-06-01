"""Add audio archive fields to meetings table

Wave 2b: MinIO 音频存档 + Admin 删除支持

为 meetings 表增加 5 个字段：
- audio_archive_url (VARCHAR 500) — MinIO 中的存档 URL
- audio_duration_seconds (FLOAT) — 音频时长
- audio_size_bytes (BIGINT) — 音频文件大小
- audio_archived_at (TIMESTAMPTZ) — 存档时间
- audio_archived (BOOLEAN) — 是否已存档（默认 false）

注意：prod DB (microbubble) 需手工 ALTER TABLE 添加（不在迁移链中），
所以此迁移对 prod 是 no-op（IF NOT EXISTS 检查），但保证新部署的 DB 与 ORM 一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '011_meeting_audio_archive'
down_revision: Union[str, None] = '010_voice_embedding_member'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用 IF NOT EXISTS 保证 prod DB（已手工 ALTER）也能幂等运行
    op.execute("""
        ALTER TABLE meetings
        ADD COLUMN IF NOT EXISTS audio_archive_url VARCHAR(500),
        ADD COLUMN IF NOT EXISTS audio_duration_seconds FLOAT,
        ADD COLUMN IF NOT EXISTS audio_size_bytes BIGINT,
        ADD COLUMN IF NOT EXISTS audio_archived_at TIMESTAMP WITH TIME ZONE,
        ADD COLUMN IF NOT EXISTS audio_archived BOOLEAN DEFAULT FALSE
    """)


def downgrade() -> None:
    op.drop_column('meetings', 'audio_archived')
    op.drop_column('meetings', 'audio_archived_at')
    op.drop_column('meetings', 'audio_size_bytes')
    op.drop_column('meetings', 'audio_duration_seconds')
    op.drop_column('meetings', 'audio_archive_url')
