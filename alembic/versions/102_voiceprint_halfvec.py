"""W-N-B 阶段 B.4: members.voice_embedding Vector(192) -> HalfVector(192)

3D-Speaker ERes2Net 192 维说话人嵌入.
实测索引名 idx_member_voice_embedding (不是派工 brief ix_members_voice_embedding_hnsw).
down_revision = ("101_meetings_halfvec",)
"""
from alembic import op

revision = "102_voiceprint_halfvec"
down_revision = ("101_meetings_halfvec",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_member_voice_embedding;")
    op.execute("""
        ALTER TABLE members
        ALTER COLUMN voice_embedding TYPE halfvec(192)
        USING voice_embedding::halfvec(192);
    """)
    op.execute("""
        CREATE INDEX idx_member_voice_embedding
        ON members
        USING hnsw (voice_embedding halfvec_cosine_ops);
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_member_voice_embedding;")
    op.execute("""
        ALTER TABLE members
        ALTER COLUMN voice_embedding TYPE vector(192)
        USING voice_embedding::vector(192);
    """)
    op.execute("""
        CREATE INDEX idx_member_voice_embedding
        ON members
        USING hnsw (voice_embedding vector_cosine_ops);
    """)
