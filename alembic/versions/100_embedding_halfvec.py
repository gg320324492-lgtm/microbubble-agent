"""阶段 B.3: knowledge.embedding Vector(1024) -> HalfVector(1024)

ALTER TABLE ... TYPE halfvec(1024) USING embedding::halfvec(1024)

注意:
- halfvec 不需要重建 HNSW 索引 (pgvector 0.7+ 同列类型即可)
- HNSW 索引会自动用新列类型重建 (CONCURRENTLY 不支持 TYPE 变更, 需要短锁)
- 派工 brief 索引名错配: 实测 idx_knowledge_embedding (不是 ix_knowledge_embedding_hnsw)

W-N-B down_revision = ("098_meetings_status_varchar_32",)
(不依赖 099_hnsw_param_tune, 阶段 A 不在本批次)
"""
from alembic import op

revision = "100_embedding_halfvec"
down_revision = ("098_meetings_status_varchar_32",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 删除旧 HNSW 索引 (新列类型不兼容旧索引)
    op.execute("DROP INDEX IF EXISTS idx_knowledge_embedding;")
    # 2. 改列类型 float32 -> float16
    op.execute("""
        ALTER TABLE knowledge
        ALTER COLUMN embedding TYPE halfvec(1024)
        USING embedding::halfvec(1024);
    """)
    # 3. 重建 HNSW 索引 (halfvec_cosine_ops pgvector 0.7+ 支持)
    op.execute("""
        CREATE INDEX idx_knowledge_embedding
        ON knowledge
        USING hnsw (embedding halfvec_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_knowledge_embedding;")
    op.execute("""
        ALTER TABLE knowledge
        ALTER COLUMN embedding TYPE vector(1024)
        USING embedding::vector(1024);
    """)
    op.execute("""
        CREATE INDEX idx_knowledge_embedding
        ON knowledge
        USING hnsw (embedding vector_cosine_ops);
    """)
