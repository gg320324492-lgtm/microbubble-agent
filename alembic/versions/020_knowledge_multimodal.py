"""Phase 7: 知识库多模态提取（图片/公式/表格 OCR 入库）

新增两张表：
- knowledge_images: PDF/PPTX 提取的图片 + OCR 结果
- knowledge_extractions: 统一存储公式/表格/图表/图片-OCR 块

两表均按 knowledge_id CASCADE 删除。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "020_kb_multimodal"
down_revision: Union[str, None] = "019_reminder_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. knowledge_images 表
    op.create_table(
        "knowledge_images",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_id", sa.Integer(), sa.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("position_data", JSONB(), nullable=True),
        sa.Column("image_url", sa.String(length=500), nullable=False),
        sa.Column("image_object_name", sa.String(length=500), nullable=True),
        sa.Column("mime_type", sa.String(length=50), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("ocr_error", sa.Text(), nullable=True),
        sa.Column("ocr_model", sa.String(length=100), nullable=True),
        sa.Column("ocr_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_knowledge_image_status", "knowledge_images", ["knowledge_id", "ocr_status"])
    op.create_index("idx_knowledge_image_kb_page", "knowledge_images", ["knowledge_id", "page_number"])

    # ── 2. knowledge_extractions 表
    op.create_table(
        "knowledge_extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("knowledge_id", sa.Integer(), sa.ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_image_id", sa.Integer(), sa.ForeignKey("knowledge_images.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("position_data", JSONB(), nullable=True),
        sa.Column("data", JSONB(), nullable=True),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column("model_used", sa.String(length=100), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="auto"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_kb_extraction_kb_kind", "knowledge_extractions", ["knowledge_id", "kind"])
    op.create_index("idx_kb_extraction_active", "knowledge_extractions", ["knowledge_id", "kind", "is_active"])


def downgrade() -> None:
    op.drop_index("idx_kb_extraction_active", table_name="knowledge_extractions")
    op.drop_index("idx_kb_extraction_kb_kind", table_name="knowledge_extractions")
    op.drop_table("knowledge_extractions")

    op.drop_index("idx_knowledge_image_kb_page", table_name="knowledge_images")
    op.drop_index("idx_knowledge_image_status", table_name="knowledge_images")
    op.drop_table("knowledge_images")
