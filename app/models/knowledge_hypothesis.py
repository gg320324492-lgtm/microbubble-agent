from sqlalchemy import Column, Integer, String, Text, ARRAY, Float, DateTime
from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgeHypothesis(Base, TimestampMixin):
    __tablename__ = "knowledge_hypotheses"

    id = Column(Integer, primary_key=True, index=True)
    statement = Column(Text, nullable=False)
    rationale = Column(Text, nullable=True)
    suggested_experiment = Column(Text, nullable=True)
    supporting_entity_ids = Column(ARRAY(Integer), default=[])
    confidence = Column(Float, default=0.5)
    priority = Column(String(20), default="medium")
    status = Column(String(20), default="proposed")
    tags = Column(ARRAY(String), default=[])
    validated_at = Column(DateTime, nullable=True)
