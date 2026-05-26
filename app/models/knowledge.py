from sqlalchemy import Column, Integer, String, Text, ARRAY, ForeignKey, Float, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base
from app.models.base import TimestampMixin


class Knowledge(Base, TimestampMixin):
    """知识库模型"""
    __tablename__ = "knowledge"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)

    # 分类和标签
    category = Column(String(100))  # LLM动态生成的具体分类（如"臭氧气泡消毒动力学"）
    tags = Column(ARRAY(String))

    # 动态分析结果
    key_concepts = Column(ARRAY(String), nullable=True)     # LLM提取的核心概念
    related_topics = Column(ARRAY(String), nullable=True)   # LLM建议的关联主题
    knowledge_type = Column(String(50), nullable=True)      # 文献/方法/标准/综述/案例/报告/FAQ
    analysis_status = Column(String(20), default="pending") # pending/analyzing/done/failed
    auto_researched = Column(Boolean, default=False)        # 是否已触发自主研究
    quality_score = Column(Float, nullable=True)            # 内容质量评分 0-1
    needs_review = Column(Boolean, default=False)           # 是否需人工审阅（矛盾检测后标记）
    entities = Column(JSONB, nullable=True)                 # 实体三元组 [{subject, predicate, object, condition, confidence}]

    # 来源
    source = Column(String(500))  # 来源链接或文件路径
    source_type = Column(String(50))  # paper/notes/sop/manual/conversation/auto_research

    # 文件上传
    file_path = Column(String(500), nullable=True)  # MinIO object_name
    file_name = Column(String(200), nullable=True)  # 原始文件名
    file_type = Column(String(200), nullable=True)  # MIME 类型
    summary = Column(Text, nullable=True)  # LLM 生成的摘要

    # 向量嵌入 (pgvector Vector(768))
    embedding = Column(Vector(768), nullable=True)

    # 创建者
    created_by = Column(Integer, ForeignKey("members.id"))

    def __repr__(self):
        return f"<Knowledge(id={self.id}, title='{self.title}')>"


class KnowledgeRelation(Base, TimestampMixin):
    """知识条目之间的关联关系"""
    __tablename__ = "knowledge_relations"

    id = Column(Integer, primary_key=True, index=True)
    source_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False)
    target_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False)
    relation_type = Column(String(30))    # similar/supplements/contradicts/cites/extends/prerequisite
    score = Column(Float, default=0.5)    # 关联强度 0-1
    reason = Column(String(500))          # 关联原因
    created_by = Column(String(20), default="auto")  # auto/manual/llm


class KnowledgeGap(Base, TimestampMixin):
    """知识空白记录 — QA 引擎检测到的知识缺失"""
    __tablename__ = "knowledge_gaps"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)          # 触发空白的用户问题
    area = Column(String(200), nullable=True)     # 空白领域
    filled = Column(Boolean, default=False)       # 是否已填补
    filled_at = Column(String, nullable=True)     # 填补时间
    knowledge_ids = Column(ARRAY(Integer), default=[])  # 填补时入库的知识条目 ID
