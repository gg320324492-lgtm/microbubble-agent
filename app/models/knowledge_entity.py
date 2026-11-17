from sqlalchemy import Column, Integer, String, Text, ARRAY, Float, UniqueConstraint
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgeEntity(Base, TimestampMixin):
    __tablename__ = "knowledge_entities"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(500), nullable=False)
    predicate = Column(String(200), nullable=False)
    object = Column(Text, nullable=False)
    condition = Column(String(500), nullable=True)
    confidence = Column(Float, default=0.5)
    source_knowledge_ids = Column(ARRAY(Integer), default=[])
    occurrence_count = Column(Integer, default=1)
    # 向量嵌入 (pgvector Vector(1024), v29 Qwen3-Embedding-0.6B, A/B baseline 验证完成)
    embedding = Column(Vector(1024), nullable=True)
    # 2026-11-17: 切 embedding_mm (1536d, MiniMax embo-01) — DB 为 vector(1536) (迁移 153);
    # 旧 vector(1024) 列冻结保留为回滚, 不再写入。
    embedding_mm = Column(Vector(1536), nullable=True)


class EntityCoOccurrence(Base, TimestampMixin):
    __tablename__ = "entity_co_occurrence"

    id = Column(Integer, primary_key=True, index=True)
    entity_a_id = Column(Integer, nullable=False)
    entity_b_id = Column(Integer, nullable=False)
    knowledge_id = Column(Integer, nullable=False)
    weight = Column(Float, default=1.0)

    __table_args__ = (
        UniqueConstraint("entity_a_id", "entity_b_id", "knowledge_id"),
    )
