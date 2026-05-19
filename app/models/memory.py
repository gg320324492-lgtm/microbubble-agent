import enum
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey, LargeBinary

from app.core.database import Base
from app.models.base import TimestampMixin


class MemoryType(str, enum.Enum):
    """记忆类型"""
    PREFERENCE = "preference"   # 用户偏好
    SUMMARY = "summary"         # 对话摘要
    ENTITY = "entity"           # 实体关系


class Memory(Base, TimestampMixin):
    """长期记忆模型"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    memory_type = Column(String(20), nullable=False)  # preference/summary/entity
    key = Column(String(200))           # 偏好键名
    content = Column(Text, nullable=False)
    # 向量嵌入 (pgvector Vector(768) when available, LargeBinary fallback)
    embedding = Column(LargeBinary, nullable=True)
    importance = Column(Float, default=1.0)  # 0.0-1.0，随时间衰减
    access_count = Column(Integer, default=0)
    last_accessed_at = Column(DateTime, nullable=True)
    source_session = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<Memory(id={self.id}, type={self.memory_type}, key={self.key})>"
