"""W-N-B 阶段 B.4: meetings.embedding Vector(1024) -> HalfVector(1024)

同 knowledge 模式, 实测索引名 idx_meetings_embedding (不是派工 brief ix_meetings_embedding_hnsw).
down_revision = ("100_embedding_halfvec",)
"""
from alembic import op

revision = "101_meetings_halfvec"
down_revision = ("100_embedding_halfvec",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meetings_embedding;")
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN embedding TYPE halfvec(1024)
        USING embedding::halfvec(1024);
    """)
    op.execute("""
        CREATE INDEX idx_meetings_embedding
        ON meetings
        USING hnsw (embedding halfvec_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_meetings_embedding;")
    op.execute("""
        ALTER TABLE meetings
        ALTER COLUMN embedding TYPE vector(1024)
        USING embedding::vector(1024);
    """)
    op.execute("""
        CREATE INDEX idx_meetings_embedding
        ON meetings
        USING hnsw (embedding vector_cosine_ops);
    """)
