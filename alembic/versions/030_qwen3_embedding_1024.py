"""knowledge/memory/meeting/knowledge_entity 4 表 embedding 维度从 768 升到 1024

背景: v29 切换到 Qwen3-Embedding-0.6B (1024d) 替代 shibing624/text2vec-base-chinese (768d)。

策略: 双列并存 (embedding_v2) — 旧 embedding 列保留, 新列全量填好后再原子切换。
    1. 加 embedding_v2 vector(1024) 列 (4 张表)
    2. drop 旧 HNSW 索引 (meetings 表 idx_meeting_embedding 在 embedding 列, 维度变了会失效)
    3. 加新 HNSW 索引 (embedding_v2 列, 4 张表统一加, 含之前缺的 3 张)

后续 (手工执行, 不在 alembic 里):
    重算覆盖率 100% 后:
        ALTER TABLE knowledge DROP COLUMN embedding;
        ALTER TABLE knowledge RENAME COLUMN embedding_v2 TO embedding;
        ... (4 张表都做)

revision ID 短名 '030_qw3_1024' (10 字符), 兼容 alembic_version.version_num VARCHAR(32).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '030_qw3_1024'
down_revision: Union[str, None] = '029_kb_layout'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# 4 张需要改 embedding 维度的表 (含 knowledge_entities)
EMBEDDING_TABLES = ('knowledge', 'memories', 'meetings', 'knowledge_entities')


def upgrade() -> None:
    # 1. 加 embedding_v2 列 (4 张表, IF NOT EXISTS 幂等)
    for table in EMBEDDING_TABLES:
        op.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_v2 vector(1024)")

    # 2. drop 旧 HNSW 索引 (meetings 表原本有 idx_meeting_embedding, 维度变了会失效)
    #    IF EXISTS 避免重复执行报错
    op.execute("DROP INDEX IF EXISTS idx_meeting_embedding")

    # 3. 加新 HNSW 索引 (embedding_v2 列, 4 张表统一加)
    #    IF NOT EXISTS 幂等. 注意: 知识库/记忆/实体之前没建过 HNSW, 这次统一加上.
    for table in EMBEDDING_TABLES:
        op.execute(
            f"CREATE INDEX IF NOT EXISTS idx_{table}_embedding_v2 "
            f"ON {table} USING hnsw (embedding_v2 vector_cosine_ops)"
        )


def downgrade() -> None:
    # 按相反顺序回滚: 先 drop 索引, 再 drop 列
    for table in EMBEDDING_TABLES:
        op.execute(f"DROP INDEX IF EXISTS idx_{table}_embedding_v2")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS embedding_v2")
    # 恢复 meetings 的旧 HNSW 索引 (基于 768 维 embedding 列)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_meeting_embedding "
        "ON meetings USING hnsw (embedding vector_cosine_ops)"
    )
