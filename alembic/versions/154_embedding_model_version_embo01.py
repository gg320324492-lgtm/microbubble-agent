"""embedding_model_version 标记同步为 embo-01 (1536d 云端切换收口).

2026-11-17 切 MiniMax embo-01 后，`embedding_model_version` 的 server_default 仍是
`qwen3-0.6b` ⇒ 新写入的行会**谎报**模型版本（类 20.220：状态字段说谎）。
本迁移：

1. 把 knowledge / meetings 两表的 server_default 改为 `embo-01`
2. 把**已经重建过 1536 维向量**的行（embedding_mm IS NOT NULL）标记为 `embo-01`
   —— 只改这些行，旧 1024 列仍是 qwen3 的行保持原值，回滚语义清楚

revision: 154 (≤32 字符)
down_revision: 153_minimax_embed_1536
"""
from alembic import op

revision = "154_embedding_model_marker"
down_revision = "153_minimax_embed_1536"
branch_labels = None
depends_on = None

TABLES = ["knowledge", "meetings"]


def upgrade() -> None:
    for table in TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding_model_version "
            f"SET DEFAULT 'embo-01'"
        )
        op.execute(
            f"UPDATE {table} SET embedding_model_version = 'embo-01' "
            f"WHERE embedding_mm IS NOT NULL "
            f"AND COALESCE(embedding_model_version, '') <> 'embo-01'"
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN embedding_model_version "
            f"SET DEFAULT 'qwen3-0.6b'"
        )
        op.execute(
            f"UPDATE {table} SET embedding_model_version = 'qwen3-0.6b' "
            f"WHERE embedding_model_version = 'embo-01'"
        )
