"""W-N-C 阶段 C.2: knowledge + meetings 加 embedding_model_version 字段

灰度切换 embedding 后端时, 用此字段区分新旧向量:
  - qwen3-0.6b (默认, 当前生产全部行)
  - bge-m3 (灰度候选, 阶段 C.3 bench 决策后逐步切换)

设计:
  - nullable=False + server_default="qwen3-0.6b" 兼容历史数据
  - String(32) 够存 "Qwen/Qwen3-Embedding-0.6B" 缩写
  - 仅 knowledge 加 index (meetings 体量小, 灰度扫描不需要 index)
  - 字符串值用 snake_case 模型名短码 (不是完整 HF path), 防止过长

down_revision = ("102_voiceprint_halfvec",)
"""
from alembic import op
import sqlalchemy as sa

revision = "103_add_embedding_model_version"
down_revision = ("102_voiceprint_halfvec",)
branch_labels = None
depends_on = None


def upgrade() -> None:
    # knowledge: 加列 + index (灰度扫描会 WHERE embedding_model_version='qwen3-0.6b')
    op.add_column(
        "knowledge",
        sa.Column(
            "embedding_model_version",
            sa.String(length=32),
            nullable=False,
            server_default="qwen3-0.6b",
        ),
    )
    op.create_index(
        "ix_knowledge_embedding_model_version",
        "knowledge",
        ["embedding_model_version"],
    )

    # meetings: 加列 (无 index, 体量小且灰度不优先)
    op.add_column(
        "meetings",
        sa.Column(
            "embedding_model_version",
            sa.String(length=32),
            nullable=False,
            server_default="qwen3-0.6b",
        ),
    )


def downgrade() -> None:
    op.drop_column("meetings", "embedding_model_version")
    op.drop_index("ix_knowledge_embedding_model_version", table_name="knowledge")
    op.drop_column("knowledge", "embedding_model_version")