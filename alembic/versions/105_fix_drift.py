"""W-N-G+ schema drift 修复迁移 (基于实测, 不假设)

实测 DB 实际状态 vs alembic code head 104:
- knowledge.embedding: halfvec(1024) ✅ (100 已应用)
- knowledge.embedding_model_version: 缺失 ❌ (103 未应用)
- meetings.embedding: halfvec(1024) ✅ (101 已应用)
- meetings.embedding_model_version: 缺失 ❌ (103 未应用)
- members.voice_embedding: halfvec(192) ✅ (102 已应用)
- knowledge_chunks.embedding: vector(1024) ✅ (088 已应用)
- knowledge_chunks.chunk_embedding: 缺失 ❌ (104 未应用)

修复策略:
- IF NOT EXISTS 兼容 idempotent (允许 103/104 已部分应用场景)
- down_revision 接续 head 104
- 本迁移是"兜底", 不取代 103/104, 仅补 103+104 应做但未做的列

W-N-G+ +1 (派工 v6 §13 仓库实情真查 + 类 20.131 派工起点必 fetch + 类 20.144
生产代码路径必须包含所有 seed step 沿用).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from pgvector.sqlalchemy import Vector

revision = "105_fix_drift"
down_revision = "104_add_knowledge_chunk_late_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 修复 1: knowledge.embedding_model_version (VARCHAR(32), default 'qwen3-0.6b')
    # IF NOT EXISTS 兼容 (W73 铁律: idempotent + 不假设)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='knowledge' AND column_name='embedding_model_version'
            ) THEN
                ALTER TABLE knowledge
                ADD COLUMN embedding_model_version VARCHAR(32) NOT NULL
                DEFAULT 'qwen3-0.6b';
                CREATE INDEX IF NOT EXISTS ix_knowledge_embedding_model_version
                ON knowledge (embedding_model_version);
            END IF;
        END$$;
    """)

    # 修复 2: meetings.embedding_model_version (VARCHAR(32), default 'qwen3-0.6b')
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='meetings' AND column_name='embedding_model_version'
            ) THEN
                ALTER TABLE meetings
                ADD COLUMN embedding_model_version VARCHAR(32) NOT NULL
                DEFAULT 'qwen3-0.6b';
            END IF;
        END$$;
    """)

    # 修复 3: knowledge_chunks.chunk_embedding (ARRAY(Vector(1024)) for late-chunking 多向量)
    # pgvector ARRAY(Vector) 支持 (pgvector 0.7+)
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='knowledge_chunks' AND column_name='chunk_embedding'
            ) THEN
                ALTER TABLE knowledge_chunks
                ADD COLUMN chunk_embedding vector(1024)[];
            END IF;
        END$$;
    """)


def downgrade() -> None:
    # 安全 down (IF EXISTS 兜底)
    op.execute("""
        ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS chunk_embedding;
        ALTER TABLE meetings DROP COLUMN IF EXISTS embedding_model_version;
        ALTER TABLE knowledge DROP COLUMN IF EXISTS embedding_model_version;
        DROP INDEX IF EXISTS ix_knowledge_embedding_model_version;
    """)