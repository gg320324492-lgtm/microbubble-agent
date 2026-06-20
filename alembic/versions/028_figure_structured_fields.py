"""v28 step 2: 论文图片结构化字段（vision model 输出）

为 knowledge_images 表加 10 个字段，让后端视觉模型输出能被持久化：

- figure_no:              "Fig. 2" / "Fig. S2" / "Table 1" / "Scheme 1"
- figure_type:            "chart" | "scheme" | "table" | "cover" | "logo" | "publisher" | "experimental_setup" | "mechanism"
- is_core_figure:         bool  (正文核心图, 不是封面/logo)
- is_publisher_image:     bool  (Elsevier logo / 期刊封面 / 版权页)
- is_supporting_figure:   bool  (Fig. S\d+ 补充材料)
- section_hint:           str   (图所属章节标题或关键词)
- visual_summary:         text  (图的详细描述 100-300字)
- anchor_paragraph_index: int   (在所属章节中第几段首次引用, 0-indexed)
- anchor_text:            str   (首次引用的句子片段, 如 "shown in Fig. 2")
- vision_confidence:     float (0-1 综合置信度)

这些字段让前端 paperAdapter 不再靠正则推断，能直接读取结构化数据。

down_revision = 020_kb_multimodal
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "028_figure_structured"
down_revision: Union[str, None] = "020_kb_multimodal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. figure_no: 图号（"Fig. 2" / "Fig. S2" / "Table 1"）
    op.add_column(
        "knowledge_images",
        sa.Column("figure_no", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "idx_knowledge_image_figure_no",
        "knowledge_images",
        ["knowledge_id", "figure_no"],
    )

    # ── 2. figure_type: 图片类型
    op.add_column(
        "knowledge_images",
        sa.Column("figure_type", sa.String(length=50), nullable=True),
    )

    # ── 3. is_core_figure: 是否正文核心图
    op.add_column(
        "knowledge_images",
        sa.Column("is_core_figure", sa.Boolean(), nullable=True),
    )

    # ── 4. is_publisher_image: 是否出版商图 (logo / cover / publisher)
    op.add_column(
        "knowledge_images",
        sa.Column("is_publisher_image", sa.Boolean(), nullable=True),
    )

    # ── 5. is_supporting_figure: 是否补充材料图 (Fig. S\d+)
    op.add_column(
        "knowledge_images",
        sa.Column("is_supporting_figure", sa.Boolean(), nullable=True),
    )

    # ── 6. section_hint: 图所属章节标题或关键词
    op.add_column(
        "knowledge_images",
        sa.Column("section_hint", sa.String(length=200), nullable=True),
    )

    # ── 7. visual_summary: 图的详细描述
    op.add_column(
        "knowledge_images",
        sa.Column("visual_summary", sa.Text(), nullable=True),
    )

    # ── 8. anchor_paragraph_index: 首次引用段落索引（0-indexed）
    op.add_column(
        "knowledge_images",
        sa.Column("anchor_paragraph_index", sa.Integer(), nullable=True),
    )

    # ── 9. anchor_text: 首次引用的句子片段
    op.add_column(
        "knowledge_images",
        sa.Column("anchor_text", sa.String(length=500), nullable=True),
    )

    # ── 10. vision_confidence: 0-1 综合置信度
    op.add_column(
        "knowledge_images",
        sa.Column("vision_confidence", sa.Float(), nullable=True),
    )

    # ── 11. vision_model_used: 实际调用的视觉模型名（用于追溯）
    op.add_column(
        "knowledge_images",
        sa.Column("vision_model_used", sa.String(length=100), nullable=True),
    )

    # ── 12. vision_analyzed_at: 视觉分析时间戳
    op.add_column(
        "knowledge_images",
        sa.Column("vision_analyzed_at", sa.DateTime(), nullable=True),
    )

    # ── 13. 图号索引加速 RightImageRail sectionHint 匹配
    op.create_index(
        "idx_knowledge_image_is_core",
        "knowledge_images",
        ["knowledge_id", "is_core_figure"],
    )
    # 注意: idx_knowledge_image_kb_page (knowledge_id, page_number) 已在 020 迁移中创建,
    # 不再重复创建 page_number 索引,避免重名


def downgrade() -> None:
    # ── 删除索引
    op.drop_index("idx_knowledge_image_page", table_name="knowledge_images")
    op.drop_index("idx_knowledge_image_is_core", table_name="knowledge_images")
    op.drop_index("idx_knowledge_image_figure_no", table_name="knowledge_images")

    # ── 删除列（按反向顺序）
    op.drop_column("knowledge_images", "vision_analyzed_at")
    op.drop_column("knowledge_images", "vision_model_used")
    op.drop_column("knowledge_images", "vision_confidence")
    op.drop_column("knowledge_images", "anchor_text")
    op.drop_column("knowledge_images", "anchor_paragraph_index")
    op.drop_column("knowledge_images", "visual_summary")
    op.drop_column("knowledge_images", "section_hint")
    op.drop_column("knowledge_images", "is_supporting_figure")
    op.drop_column("knowledge_images", "is_publisher_image")
    op.drop_column("knowledge_images", "is_core_figure")
    op.drop_column("knowledge_images", "figure_type")
    op.drop_column("knowledge_images", "figure_no")