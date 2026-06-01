"""Add HNSW index on members.voice_embedding

Wave 3a: 加速声纹识别和跨成员匹配
为 members 表的 voice_embedding（vector(256)）字段创建 HNSW 索引，
使用 vector_cosine_ops 算子加速 pgvector cosine 距离搜索。

背景：
- 010 迁移已添加 voice_embedding 列（vector(256)）
- voiceprint_service.enroll/identify 用 cosine_distance < 0.55 匹配
- 大规模成员（>100）时全表扫描会变慢，HNSW 索引可显著加速
- IF NOT EXISTS 保护幂等性
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '013_member_voice_embedding_hnsw'
down_revision: Union[str, None] = '012_meeting_embedding_agenda'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HNSW 索引加速 cosine 距离搜索（pgvector >= 0.5）
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_member_voice_embedding "
        "ON members USING hnsw (voice_embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_member_voice_embedding")
