from sqlalchemy import Column, Integer, String, Text, ARRAY, ForeignKey, LargeBinary

from app.core.database import Base
from app.models.base import TimestampMixin


class Knowledge(Base, TimestampMixin):
    """知识库模型"""
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    # 分类和标签
    category = Column(String(50))  # 文献/实验/方法/FAQ
    tags = Column(ARRAY(String))

    # 来源
    source = Column(String(500))  # 来源链接或文件路径
    source_type = Column(String(50))  # paper/notes/sop/manual

    # 向量嵌入 (用于RAG检索，需要 pgvector 扩展)
    # 使用 LargeBinary 作为 fallback，pgvector 可用时会自动使用 Vector
    embedding = Column(LargeBinary, nullable=True)

    # 创建者
    created_by = Column(Integer, ForeignKey("members.id"))

    def __repr__(self):
        return f"<Knowledge(id={self.id}, title='{self.title}')>"
