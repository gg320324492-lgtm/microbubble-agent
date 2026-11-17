"""chunk 级多向量切 1536 维 + 主向量列建 HNSW 索引 (2026-11-17 链条收口).

背景：late-chunking 臂读 `knowledge_chunks.chunk_embedding vector(1024)[]`，由本地
Qwen3 的 token 级前向产生。切 MiniMax embo-01（云端，只给句/段向量、无 token 级输出）
后无法再做真正的 late chunking，改为**多窗口向量**：把 chunk 正文按句切窗，每窗用
embo-01 生成一个 1536 维向量，存入新列 `chunk_embedding_mm vector(1536)[]`。
检索语义保持"细粒度多向量取最小距离"，但向量空间与主检索一致。

同时给主向量列建 HNSW 索引（此前 knowledge/knowledge_chunks/meetings 的 embedding
列**都没有索引**，1.2 万行靠全表精扫；云端 embedding 后行数会继续增长，先补上）。

revision: 155 (≤32 字符)
down_revision: 154_embedding_model_marker
"""
from alembic import op
import sqlalchemy as sa

revision = "155_chunk_mm_and_indexes"
down_revision = "154_embedding_model_marker"
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    conn = op.get_bind()
    return conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=:t AND column_name=:c"),
        {"t": table, "c": column}).fetchone() is not None


def _has_index(name: str) -> bool:
    conn = op.get_bind()
    return conn.execute(sa.text(
        "SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname=:n"),
        {"n": name}).fetchone() is not None


def upgrade() -> None:
    if not _has_column("knowledge_chunks", "chunk_embedding_mm"):
        op.execute(
            "ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS "
            "chunk_embedding_mm vector(1536)[]"
        )
    # HNSW: 只对已有大量行的主向量列建；小表(meetings)建了也无害
    for table, col, idx in [
        ("knowledge_chunks", "embedding_mm", "ix_knowledge_chunks_embedding_mm_hnsw"),
        ("knowledge", "embedding_mm", "ix_knowledge_embedding_mm_hnsw"),
        ("meetings", "embedding_mm", "ix_meetings_embedding_mm_hnsw"),
    ]:
        if not _has_column(table, col) or _has_index(idx):
            continue
        op.execute(
            f"CREATE INDEX {idx} ON {table} USING hnsw ({col} vector_cosine_ops)"
        )


def downgrade() -> None:
    for idx in [
        "ix_knowledge_chunks_embedding_mm_hnsw",
        "ix_knowledge_embedding_mm_hnsw",
        "ix_meetings_embedding_mm_hnsw",
    ]:
        op.execute(f"DROP INDEX IF EXISTS {idx}")
    op.execute("ALTER TABLE knowledge_chunks DROP COLUMN IF EXISTS chunk_embedding_mm")
