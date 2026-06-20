"""知识库多模态模型 — Phase 7: 图片/公式/表格 OCR 入库

设计要点：
- KnowledgeImage: 从 PDF/PPTX 提取的图片（含 OCR 结果）
- KnowledgeExtraction: 统一存储公式 / 表格 / 图表 / 图片-OCR 块提取物
- source_image_id 关联图片-OCR 块与具体图片
- data JSONB 存结构化结果（LaTeX/headers/rows/...）
- content_text 存纯文本用于全文搜索
- position_data 存 PDF/PPTX 内的位置（page, bbox）便于前端定位
- 独立于 knowledge.formatted_content，OCR 失败不影响主流程
"""

from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, ForeignKey, Index, DateTime,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.base import TimestampMixin


# 提取物类型（kind）枚举
EXTRACTION_KIND_FORMULA = "formula"
EXTRACTION_KIND_TABLE = "table"
EXTRACTION_KIND_CHART = "chart"
EXTRACTION_KIND_IMAGE_BLOCK = "image_block"  # 图中文字 OCR 块

VALID_EXTRACTION_KINDS = (
    EXTRACTION_KIND_FORMULA,
    EXTRACTION_KIND_TABLE,
    EXTRACTION_KIND_CHART,
    EXTRACTION_KIND_IMAGE_BLOCK,
)


class KnowledgeImage(Base, TimestampMixin):
    """从文档提取的图片（含 OCR 结果）"""
    __tablename__ = "knowledge_images"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(
        Integer, ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    # 图片位置与元数据
    page_number = Column(Integer, nullable=True)  # PDF/PPXT 页码（NULL=未记录）
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    position_data = Column(JSONB, nullable=True)  # {x, y, w, h, anchor}

    # 存储
    image_url = Column(String(500), nullable=False)  # MinIO 公开 URL
    image_object_name = Column(String(500), nullable=True)  # MinIO object_name（管理用）
    mime_type = Column(String(50), nullable=True)
    file_size = Column(Integer, nullable=True)

    # OCR 结果
    ocr_text = Column(Text, nullable=True)  # OCR 提取的纯文本
    ocr_status = Column(String(20), default="pending", nullable=False)  # pending/done/failed/skipped
    ocr_error = Column(Text, nullable=True)
    ocr_model = Column(String(100), nullable=True)  # 使用的模型名（llm-vision / tesseract / paddleocr）
    ocr_at = Column(DateTime, nullable=True)

    # ── v28 step 2: vision 模型输出的结构化字段（替代前端 paperAdapter 正则推断）
    # 图号与类型
    figure_no = Column(String(50), nullable=True)  # "Fig. 2" / "Fig. S2" / "Table 1" / "Scheme 1"
    figure_type = Column(String(50), nullable=True)  # chart / scheme / table / cover / logo / publisher / experimental_setup / mechanism
    is_core_figure = Column(Boolean, nullable=True)  # 是否正文核心图（不是封面/logo/补充材料）
    is_publisher_image = Column(Boolean, nullable=True)  # 是否出版商图（Elsevier logo / 期刊封面 / 版权页）
    is_supporting_figure = Column(Boolean, nullable=True)  # 是否补充材料图（Fig. S\d+）

    # 章节定位
    section_hint = Column(String(200), nullable=True)  # 图所属章节标题或关键词（用于 RightImageRail 匹配）
    anchor_paragraph_index = Column(Integer, nullable=True)  # 首次引用段落索引（0-indexed，所属章节内）
    anchor_text = Column(String(500), nullable=True)  # 首次引用句子片段（如 "shown in Fig. 2"）

    # 视觉描述
    visual_summary = Column(Text, nullable=True)  # 图的详细描述 100-300字

    # Vision 模型元数据
    vision_confidence = Column(Float, nullable=True)  # 0-1 综合置信度
    vision_model_used = Column(String(100), nullable=True)  # 实际调用的视觉模型名（追溯用）
    vision_analyzed_at = Column(DateTime, nullable=True)  # 视觉分析时间戳

    # 关系
    knowledge = relationship("Knowledge", backref="images", lazy="selectin")
    extractions = relationship(
        "KnowledgeExtraction",
        backref="source_image",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_knowledge_image_status", "knowledge_id", "ocr_status"),
        Index("idx_knowledge_image_kb_page", "knowledge_id", "page_number"),
        Index("idx_knowledge_image_figure_no", "knowledge_id", "figure_no"),  # v28 图号索引
        Index("idx_knowledge_image_is_core", "knowledge_id", "is_core_figure"),  # v28 核心图筛选
    )


class KnowledgeExtraction(Base, TimestampMixin):
    """统一提取物：公式 / 表格 / 图表 / 图片-OCR 块

    设计：单一表 + kind 字段区分类型，比多表 JOIN 简单。
    - formula  : data = {latex, variables, name, result_unit, conditions, domain}
    - table    : data = {headers: [...], rows: [[...]], caption}
    - chart    : data = {chart_type, description, data_summary}
    - image_block: data = {text, bbox_in_image, confidence}
    """
    __tablename__ = "knowledge_extractions"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(
        Integer, ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    source_image_id = Column(
        Integer, ForeignKey("knowledge_images.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # 提取物类型
    kind = Column(String(20), nullable=False, index=True)  # formula/table/chart/image_block

    # 位置
    page_number = Column(Integer, nullable=True)
    position_data = Column(JSONB, nullable=True)  # {x, y, w, h}

    # 提取数据
    data = Column(JSONB, nullable=True)  # 结构化结果（latex/headers/rows/...）
    content_text = Column(Text, nullable=True)  # 纯文本（搜索 + 简单展示）

    # 元数据
    confidence = Column(Float, default=0.5, nullable=False)  # 0-1
    model_used = Column(String(100), nullable=True)  # 实际模型名
    source = Column(String(20), default="auto", nullable=False)  # auto/manual/llm
    is_active = Column(Boolean, default=True, nullable=False)

    # 关系
    knowledge = relationship("Knowledge", backref="extractions", lazy="selectin")

    __table_args__ = (
        Index("idx_kb_extraction_kb_kind", "knowledge_id", "kind"),
        Index("idx_kb_extraction_active", "knowledge_id", "kind", "is_active"),
    )
