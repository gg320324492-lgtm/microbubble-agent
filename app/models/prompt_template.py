"""提示词模板模型"""

from sqlalchemy import Column, Integer, String, Text, Boolean, ForeignKey
from app.core.database import Base
from app.models.base import TimestampMixin


class PromptTemplate(Base, TimestampMixin):
    """可配置的系统提示词模板"""
    __tablename__ = "prompt_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False, index=True)  # 模板名称
    template = Column(Text, nullable=False)  # 模板内容
    is_active = Column(Boolean, default=True)  # 是否启用
    created_by = Column(Integer, ForeignKey("members.id"))  # 创建者
    version = Column(Integer, default=1)  # 版本号

    def __repr__(self):
        return f"<PromptTemplate(id={self.id}, name='{self.name}', v{self.version})>"
