"""Add embedding + agenda + related_meeting_ids fields to meetings table

Wave 3a: 跨会议相似度匹配需要 meeting embedding + HNSW 索引

为 meetings 表增加 3 个字段：
- agenda (JSON) — 议题列表（Wave 3b 准备）
- embedding (vector(768)) — 会议文本 embedding，pgvector cosine 距离
- related_meeting_ids (JSON) — 人类选择的关联会议 ID 列表

并创建 idx_meeting_embedding HNSW 索引（vector_cosine_ops）加速 cosine 搜索。

注意：prod DB (microbubble) 需手工 ALTER TABLE 添加（不在迁移链中），
所以此迁移对 prod 是 no-op（IF NOT EXISTS 检查），但保证新部署的 DB 与 ORM 一致。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '012_meeting_embedding_agenda'
down_revision: Union[str, None] = '011_meeting_audio_archive'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 用 IF NOT EXISTS 保证 prod DB（已手工 ALTER）也能幂等运行
    op.execute("""
        ALTER TABLE meetings
        ADD COLUMN IF NOT EXISTS agenda JSON,
        ADD COLUMN IF NOT EXISTS embedding vector(768),
        ADD COLUMN IF NOT EXISTS related_meeting_ids JSON
    """)
    # HNSW 索引加速 cosine 距离搜索（pgvector >= 0.5）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_meeting_embedding "
        "ON meetings USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meeting_embedding")
    op.drop_column('meetings', 'related_meeting_ids')
    op.drop_column('meetings', 'embedding')
    op.drop_column('meetings', 'agenda')
