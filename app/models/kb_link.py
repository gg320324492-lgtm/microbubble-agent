"""KB Link — KB 之间相似度关联表 (W68 第 10 批 B-4, 2026-07-24)

## 背景

qa-bench 自动入库的 KB 卡片, 跟已有 KB 之间**完全无关联**, 检索时只能依赖关键词/向量匹配,
但缺持久化的"KB 与 KB 之间的关联边" (`kb_links` 表). 这导致:
- RAG 检索时不能跨 KB 联合召回
- 知识图谱视图 (`KnowledgeGraphView.vue`) 只有 entity 共现, 无 KB 整体相似度
- 用户问"微纳米气泡相关 KB"时只能 search 不能 browse

本表在 KB 入闭环的 **标注** stage 跑 top-3 vector search 后写入.

## 字段设计

- knowledge_id_a + knowledge_id_b: FK to knowledge.id (CASCADE), 两端 KB (强制 a < b)
- similarity_score: 0..1 (pgvector 余弦相似度)
- link_type: auto (vector 自动算) | manual (人工补) | derived (后续 entity 共现衍生)
- created_at: 创建时间
- UNIQUE (knowledge_id_a, knowledge_id_b): 同对 KB 只算 1 次 (避免重复)

## 依赖

- knowledge 表必须存在 (FK)
- pgvector 已 enable (main.py 启动时自动安装)
- knowledge.embedding 列 (Vector(1024), v29 Qwen3-Embedding-0.6B)

## 实施纪律

- 0 production code 改动铁律 (W68 第 10 批): 本表 + 配套 service 全部新增, 不动老路径
- 0-N 关系, 不冗余 link_type 维度 (枚举已收敛到 3 类)
"""
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)

from app.core.database import Base


# ============== link_type 枚举 ==============

LINK_TYPE_AUTO = "auto"  # vector search 自动算
LINK_TYPE_MANUAL = "manual"  # 人工补关联
LINK_TYPE_DERIVED = "derived"  # entity 共现衍生 (后续 PR)

VALID_LINK_TYPES = (
    LINK_TYPE_AUTO,
    LINK_TYPE_MANUAL,
    LINK_TYPE_DERIVED,
)


class KbLink(Base):
    """KB 之间的相似度关联 (top-3 vector search 自动写)"""

    __tablename__ = "kb_links"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id_a = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    knowledge_id_b = Column(
        Integer,
        ForeignKey("knowledge.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    similarity_score = Column(Float, nullable=False)  # 0..1
    link_type = Column(String(20), nullable=False, server_default=LINK_TYPE_AUTO)
    created_at = Column(DateTime, nullable=False, server_default="now()")

    __table_args__ = (
        # 同对 KB (无论 a/b 顺序) 只算 1 次 → 用 a < b 约束 (service 层强制)
        UniqueConstraint("knowledge_id_a", "knowledge_id_b", name="uq_kb_link_pair"),
        Index("idx_kb_link_a_score", "knowledge_id_a", "similarity_score"),
        Index("idx_kb_link_b_score", "knowledge_id_b", "similarity_score"),
    )

    def __repr__(self) -> str:
        return (
            f"<KbLink(id={self.id}, a={self.knowledge_id_a}, b={self.knowledge_id_b}, "
            f"score={self.similarity_score:.3f}, type='{self.link_type}')>"
        )