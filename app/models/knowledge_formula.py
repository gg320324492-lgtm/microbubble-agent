from sqlalchemy import Column, Integer, String, Text, Float, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.base import TimestampMixin


class KnowledgeFormula(Base, TimestampMixin):
    __tablename__ = "knowledge_formulas"

    id = Column(Integer, primary_key=True, index=True)
    knowledge_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(200), nullable=False)
    formula_latex = Column(Text, nullable=True)
    formula_python = Column(Text, nullable=False)
    variables = Column(JSONB, default={})
    result_unit = Column(String(50), nullable=True)
    conditions = Column(Text, nullable=True)
    domain = Column(String(100), nullable=True)
    confidence = Column(Float, default=0.5)
    # Enhanced fields for formula library
    source_type = Column(String(20), default="extracted")  # builtin | extracted | manual
    category_id = Column(Integer, ForeignKey("formula_categories.id"), nullable=True)
    is_active = Column(Boolean, default=True)

    category = relationship("FormulaCategory", lazy="selectin")
