from sqlalchemy import Column, Integer, BigInteger, String, Text, ARRAY, ForeignKey, Float, Boolean, DateTime
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

    # ==================== v2 PR2 收藏星标 2026-07-01 ====================
    # is_starred: 用户收藏标记 (True=收藏, False=普通)
    # starred_at: 收藏时间 (用于 sort by starred_at desc; 取消收藏时重置为 NULL)
    # 索引: ix_knowledge_starred (partial WHERE is_starred = true, alembic 043)
    is_starred = Column(Boolean, nullable=False, server_default="false")
    starred_at = Column(DateTime, nullable=True)
    # ==================== /v2 PR2 ====================

    # ==================== v2 PR4 秒传 + 版本历史 2026-07-01 ====================
    # file_size: 文件字节大小（之前硬编码 0, 044 后真值; dedup_saved_bytes 计算 + UI 显示用）
    # file_hash: MD5/SHA256 hex hash (64 chars); 部分索引 WHERE deleted_at IS NULL AND storage_mode='drive'
    # is_latest: 当前活跃版本标记 (True=显示给用户的最新版本); 多版本时旧行 = False
    # parent_version_id: 父版本 ID (Self FK ON DELETE SET NULL); 同一文件多版本时记录历史链
    # version_number: 版本号 (v1 / v2 / v3...); 新上传默认 1, 创建版本时 +1
    file_size = Column(BigInteger, nullable=True)
    file_hash = Column(String(64), nullable=True)
    is_latest = Column(Boolean, nullable=False, server_default="true")
    parent_version_id = Column(Integer, ForeignKey("knowledge.id", ondelete="SET NULL"), nullable=True)
    version_number = Column(Integer, nullable=False, server_default="1")
    # ==================== /v2 PR4 ====================

    # ==================== v2 PR5 缩略图字段 2026-07-01 ====================
    # thumbnail_path: MinIO object_name (thumbnails/{file_id}.jpg), NULL = 未生成
    # thumbnail_status: pending | ready | failed
    # thumbnail_generated_at: 生成完成时间戳
    # 部分索引: ix_knowledge_thumb_pending (WHERE status='pending' AND storage_mode='drive')
    thumbnail_path = Column(String(500), nullable=True)
    thumbnail_status = Column(String(16), nullable=False, server_default="pending")
    thumbnail_generated_at = Column(DateTime, nullable=True)
    # ==================== /v2 PR5 ====================

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


class KnowledgeVersion(Base):
    """文件版本历史明细 (v2 PR4 引入)

    与 Knowledge (file_size/file_hash/is_latest/version_number) 配套:
    - knowledge 行的 is_latest=True 是当前用户看到的"活版本"
    - 每次 create_version() 会:
      1. 把旧 is_latest 翻 False (Knowledge 行保留, 历史可追溯)
      2. 新建一行 Knowledge (is_latest=True, version_number+=1, parent_version_id=旧.id)
      3. 在 knowledge_versions 写一条明细 (file_hash + file_size + uploaded_by + change_note)

    恢复版本 = create_version 同流程, 但从历史 object_name 重新 copy_object 取得数据
    ON DELETE CASCADE: 删 file 行 (is_latest=True) 时, 所有历史版本明细自动清
    """
    __tablename__ = "knowledge_versions"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("members.id"), nullable=False)
    change_note = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default="now()")


class ChunkedUploadSession(Base):
    """分片上传 + 断点续传 session (v2 PR5 引入)

    设计原则 (简化版, 不走 S3 真分片 API):
    - 前端把大文件切成 N 个 chunk (默认 5MB/chunk), 顺序 POST /files/upload/chunk/{idx}
    - 每个 chunk 完整写入 MinIO 的临时 staging object (upload_id/chunk_{idx})
    - /complete 把所有 chunks 顺序拼接 → 最终 object_name → 创建 Knowledge 行
    - /abort 删除 staging object 和 session

    断点续传:
    - 前端 reload 页面 / 切换网络 → 从 localStorage 读 upload_id → GET /files/upload/{id}
    - 端点返 { uploaded_chunks: [0,1,3], total_chunks: 5 } → 前端跳 4 和 2 重传
    - 服务端按需从已上传 chunks 拼接到当前位置

    字段:
    - id: uuid hex (32 chars), upload_id
    - uploaded_chunks: 已成功上传的 chunk 索引列表 (ARRAY)
    - status: active | completed | aborted | expired
    - expires_at: 24h 后, Celery beat 清理
    """
    __tablename__ = "chunked_upload_sessions"

    id = Column(String(32), primary_key=True)
    user_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False, index=True)
    file_name = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    file_hash = Column(String(64), nullable=True)
    folder_id = Column(Integer, nullable=True)
    visibility = Column(String(16), nullable=False, server_default="team")
    total_chunks = Column(Integer, nullable=False)
    uploaded_chunks = Column(ARRAY(Integer), nullable=False, server_default="{}")
    status = Column(String(16), nullable=False, server_default="active")
    object_name = Column(String(500), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default="now()")
    expires_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<ChunkedUploadSession(id='{self.id[:8]}...', user_id={self.user_id}, status='{self.status}', chunks={len(self.uploaded_chunks or [])}/{self.total_chunks})>"
