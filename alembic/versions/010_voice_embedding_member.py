"""Add voice_embedding fields to members table

Wave 2a critical fix: Member.voice_embedding/voice_enrolled_at/voice_sample_count
defined in ORM (app/models/member.py:34-36) but missing from Alembic migration
chain. Without this migration, voiceprint_service.enroll_member() would fail with
"column does not exist" on a fresh DB initialized via alembic upgrade head.

注意：prod DB (microbubble) 已手工 ALTER TABLE 添加了这 3 个字段（不在迁移链中），
所以此迁移对 prod 是 no-op（IF NOT EXISTS 检查），但保证新部署的 DB 与 ORM 一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '010_voice_embedding_member'
# 2026-06-19 修复 pre-existing bug: 009 实际用 revision='009'（短 ID），但 010 原先期望 '009_formula_categories'
# 修正 down_revision 为 '009' 与 009 文件实际 revision 一致，恢复 alembic 链一致性
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用 IF NOT EXISTS 保证 prod DB（已手工 ALTER）也能幂等运行
    op.execute("""
        ALTER TABLE members
        ADD COLUMN IF NOT EXISTS voice_embedding vector(256),
        ADD COLUMN IF NOT EXISTS voice_enrolled_at timestamp with time zone,
        ADD COLUMN IF NOT EXISTS voice_sample_count integer DEFAULT 0
    """)


def downgrade() -> None:
    op.drop_column('members', 'voice_sample_count')
    op.drop_column('members', 'voice_enrolled_at')
    op.drop_column('members', 'voice_embedding')
