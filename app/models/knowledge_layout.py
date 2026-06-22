"""论文版面分析 Layout 模型 — Phase 8: vision model 扫描整篇论文

存 vision model 输出的 page layout：
- knowledge_id: 关联知识条目
- page_layout: JSONB，整篇论文每页的 blocks 数组
- vision_model_used: 实际调用的 vision 模型
- vision_analyzed_at: 扫描时间戳

page_layout 数据结构（每页）：
[
  {
    "page_number": 8,
    "blocks": [
      {"type": "heading", "level": 2, "order": 1, "text": "2.1 Test system"},
      {"type": "paragraph", "order": 2, "text": "..."},
      {"type": "image", "order": 3, "image_index": 0, "caption": "Fig. 1. ...", "figure_no": "Fig. 1", "position": "below_paragraph"},
      {"type": "table", "order": 5, "caption": "Table 1.", "headers": [...], "rows": [[...]]},
      {"type": "formula", "order": 6, "latex": "..."}
    ]
  }
]
"""

from sqlalchemy import Column, Integer, String, Text, Index, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgeLayout(Base, TimestampMixin):
    """论文版面分析结果 — vision model 扫描整篇论文输出"""
    __tablename__ = "knowledge_layouts"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(
        Integer, ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )

    # 整篇论文的 page layout（JSONB）
    page_layout = Column(JSONB, nullable=False)

    # 统计
    total_pages = Column(Integer, nullable=True)
    total_blocks = Column(Integer, nullable=True)

    # vision 模型元数据
    vision_model_used = Column(String(100), nullable=True)
    vision_analyzed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_knowledge_layout_kb", "knowledge_id"),
    )