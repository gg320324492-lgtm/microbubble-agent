from sqlalchemy import Column, Integer, String, Text, ForeignKey
from app.core.database import Base
from app.models.base import TimestampMixin


class FormulaCategory(Base, TimestampMixin):
    __tablename__ = "formula_categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    display_name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String(50), nullable=True)
    parent_id = Column(Integer, ForeignKey("formula_categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)
