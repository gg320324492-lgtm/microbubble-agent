"""切换 MiniMax embo-01 embedding (1536d): 新增 embedding_mm 列, 旧 1024 列保留为回滚.

2026-11-17 主指挥拍板: Embedding 切云端 MiniMax embo-01 (评测 5/5 top-1 与 Qwen3 一致,
省本地 1.2GB 模型与显存)。本地 Qwen3-Embedding-0.6B 保留为失败回退替补。

策略 (与 030 迁移同款"加列不覆盖"模式):
  - 9 张表各加 embedding_mm vector(1536) 列 (nullable)
  - 旧 embedding vector(1024) 列原样保留 ⇒ 回滚时改回代码 ENV 即可, 数据不丢
  - 存量向量重建由独立脚本 (scripts/backfill_minimax_embedding.py) 走云端 API 批量回填,
    迁移本身不动数据 (23671 行走云端 API 耗时/费用不宜塞进 DDL 事务)

revision: 153 (≤32 字符)
down_revision: 152
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "153_minimax_embed_1536"
down_revision = "152_knowledge_file_request_id"
branch_labels = None
depends_on = None

# (table, column) 需要新增 embedding_mm 的表; 旧列名统一为 embedding
TABLES = [
    "knowledge",
    "knowledge_chunks",
    "meetings",
    "memories",
    "kg_entities",
    "knowledge_entities",
    "knowledge_images",
    "knowledge_page_transcripts",
    "meeting_chunks",
]


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name=:t AND column_name=:c"),
        {"t": table, "c": column}).fetchone()
    return row is not None


def upgrade() -> None:
    for table in TABLES:
        if not _column_exists(table, "embedding"):
            # 表无旧 embedding 列 ⇒ 无切换语义, 跳过 (防御: 备份表/未来结构变化)
            continue
        if _column_exists(table, "embedding_mm"):
            continue
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS embedding_mm vector(1536)"
        )


def downgrade() -> None:
    for table in TABLES:
        if _column_exists(table, "embedding_mm"):
            op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS embedding_mm")
