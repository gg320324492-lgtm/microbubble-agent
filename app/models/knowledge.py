from sqlalchemy import Column, Integer, String, Text, ARRAY, ForeignKey, Float, Boolean, DateTime
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
    category = Column(String(100))  # 预设分类（论文/方法/标准/综述/案例/FAQ/笔记/手册）
    topic = Column(String(200))  # 具体研究方向（如"臭氧气泡消毒动力学"）
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
    source_type = Column(String(50))  # paper/notes/sop/manual/conversation/auto_research/auto_expansion/chat
    meta = Column(JSONB, nullable=True)  # #043: 自动拓展条目的 RichBlock 数据 + qa-bench 元信息

    # 文件上传
    file_path = Column(String(500), nullable=True)  # MinIO object_name
    file_name = Column(String(200), nullable=True)  # 原始文件名
    file_type = Column(String(200), nullable=True)  # MIME 类型
    summary = Column(Text, nullable=True)  # LLM 生成的摘要
    formatted_content = Column(Text, nullable=True)  # AI 排版后的 Markdown 内容

    # 向量嵌入 (pgvector Vector(1024), v29 Qwen3-Embedding-0.6B, A/B baseline 验证完成)
    embedding = Column(Vector(1024), nullable=True)

    # 创建者
    created_by = Column(Integer, ForeignKey("members.id"))

    # ==================== 课题组网盘 (Lab Group Drive) 2026-07-01 ====================
    # storage_mode: kb (传统 KB 卡片) | drive (网盘原始文件，不入 embedding 索引)
    # visibility: private (仅 owner 可见) | team (全员可见) | public (含外部分享)
    # folder_id: NULL = 顶级目录，指向 folders.id (Folders 表自引用 parent_id)
    # deleted_at: 软删除时间戳，NULL = 活跃，Celery beat 3 天后物理删除
    storage_mode = Column(String(16), nullable=False, server_default="kb", index=True)
    folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    visibility = Column(String(16), nullable=False, server_default="team", index=True)
    deleted_at = Column(DateTime, nullable=True, index=True)
    # ==================== /课题组网盘 ====================

    # ==================== PR2.7 分享链接 + 下载计数 2026-07-01 ====================
    download_count = Column(Integer, nullable=False, server_default="0")   # 原子计数
    share_token = Column(String(32), nullable=True)                         # 公开分享 token
    share_expires_at = Column(DateTime, nullable=True)                       # 到期时间
    # ==================== /PR2.7 ====================

    # ==================== v2 PR1 分享链接提取码 2026-07-01 ====================
    # SHA256 hex hash (64 chars). NULL = 无提取码（公开分享），非 NULL = 必填密码访问。
    share_password = Column(String(64), nullable=True)
    # ==================== /v2 PR1 ====================

    def __repr__(self):
        return f"<Knowledge(id={self.id}, title='{self.title}', storage_mode='{self.storage_mode}')>"


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


class RAGEvaluation(Base, TimestampMixin):
    """RAG 评估记录 — 质量监控"""
    __tablename__ = "rag_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(Text, nullable=False)          # 用户问题
    answer = Column(Text, nullable=True)          # 生成的回答
    context = Column(Text, nullable=True)         # 检索到的上下文
    faithfulness = Column(Float, nullable=True)   # 回答是否基于检索结果
    answer_relevancy = Column(Float, nullable=True)  # 回答是否切题
    context_precision = Column(Float, nullable=True)  # 检索结果排序是否合理
    context_recall = Column(Float, nullable=True)     # 是否检索到了所有相关信息
