from sqlalchemy import Column, Integer, BigInteger, SmallInteger, String, Text, ARRAY, ForeignKey, Float, Boolean, DateTime, Index
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


class FileMention(Base):
    """v2 PR6: @ 提醒 (mention notifications)

    - mentioned_user_id: 被 @ 的人 (受提醒者)
    - mentioned_by: 触发提醒的人 (NULL = 系统, 例如定时清理通知)
    - context: 触发场景 ('comment' | 'share' | 'mention' | 'version_restore')
    - is_read: 未读/已读 (前端 NotificationBell 红点)
    - read_at: 已读时间

    生命周期:
    - 写: drive_service 在评论/分享/上传时同步插入
    - 读: GET /notifications?unread_only=true
    - 删除: 已读后保留 30 天, Celery beat 清理
    """
    __tablename__ = "file_mentions"

    id = Column(BigInteger, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False)
    mentioned_user_id = Column(Integer, ForeignKey("members.id", ondelete="CASCADE"), nullable=False)
    mentioned_by = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    context = Column(String(500), nullable=True)
    is_read = Column(Boolean, nullable=False, server_default="false")
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default="now()")
    # v2 PR6-P7: 5s dedup 合并计数 (default 1, dedup 命中 +1)
    repeated_count = Column(Integer, nullable=False, server_default="1")

    def __repr__(self):
        return f"<FileMention(id={self.id}, file_id={self.file_id}, mentioned_user_id={self.mentioned_user_id}, is_read={self.is_read}, repeated_count={self.repeated_count})>"


class ActivityEvent(Base):
    """v2 PR6: 活动动态流 (audit trail for drive changes)

    - actor_id: 触发动作的人 (NULL = 系统清理)
    - action: upload | rename | move | delete | restore | share | version_restore | comment | mention | star
    - target_type: file | folder | comment
    - target_id: 对应目标 id
    - target_name: 冗余存名字 (目标删除后仍能展示)
    - metadata: JSONB, action 特定的额外信息 (例如 mention 列表 / old_value / new_value)

    用途:
    - /drive/activity 时间线 (按 created_at desc)
    - /admin/audit 安全审计
    - 个人主页 '最近活动'
    """
    __tablename__ = "activity_events"

    id = Column(BigInteger, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(50), nullable=False)
    target_type = Column(String(20), nullable=False)
    target_id = Column(Integer, nullable=True)
    target_name = Column(String(500), nullable=True)
    meta_data = Column("metadata", JSONB, nullable=True)  # 'metadata' PG 列名, Python attr 改名避开 SQLAlchemy reserved
    created_at = Column(DateTime, nullable=False, server_default="now()")

    def __repr__(self):
        return f"<ActivityEvent(id={self.id}, actor_id={self.actor_id}, action='{self.action}', target_type='{self.target_type}', target_id={self.target_id})>"


class FileComment(Base):
    """v2 PR6: 文件评论 (collaboration comments on drive files)

    - user_id: 评论者
    - content: 评论内容 (纯文本,前端 Markdown 渲染)
    - mentions: ARRAY 冗余存 user_id 列表 (前端 O(1) 显示 '王天志 提到 你')
    - parent_comment_id: 自引用 FK, NULL = 顶层评论 (v2 PR6-P5 threading)
    - thread_depth: 0/1/2 (顶层/回复/回复的回复), MAX_DEPTH=3 (v2 PR6-P5)
    - reply_count: 冗余存, 加快 tree list 渲染 (v2 PR6-P5)

    关联:
    - file_id → knowledge.id (CASCADE)
    - user_id → members.id (SET NULL = 用户注销保留评论)
    - parent_comment_id → file_comments.id (CASCADE, 子评论随父删)
    """
    __tablename__ = "file_comments"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("knowledge.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True)
    content = Column(Text, nullable=False)
    mentions = Column(ARRAY(Integer), nullable=True)
    parent_comment_id = Column(
        BigInteger, ForeignKey("file_comments.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    thread_depth = Column(SmallInteger, nullable=False, server_default="0")
    reply_count = Column(Integer, nullable=False, server_default="0")
    created_at = Column(DateTime, nullable=False, server_default="now()")

    def __repr__(self):
        return (
            f"<FileComment(id={self.id}, file_id={self.file_id}, user_id={self.user_id}, "
            f"parent_id={self.parent_comment_id}, depth={self.thread_depth})>"
        )


class FileRequest(Base):
    """v2 PR7: 文件请求 (Dropbox 招牌 '文件请求' 收作业场景)

    - token: 32 字符随机公开 token (URL 不暴露内部 id, 防枚举)
    - target_folder_id: 提交文件落到哪个文件夹 (NULL = 创建者根目录)
    - allowed_extensions ARRAY: 限制文件类型 ('pdf','docx',...), NULL = 不限
    - require_uploader_name: true=必填姓名 / false=可选 (匿名提交)
    - max_file_size_mb: 单文件大小上限 (NULL = 不限)
    - submission_count: 已成功提交数 (每次 submit +1)
    - is_active: false=手动关闭 / expires_at 过期后失效

    公开访问流程 (无 JWT):
      POST /api/v1/file-requests/{token}/submit  (multipart + uploader_name)

    关联:
      - created_by → members.id (RESTRICT, 不能删创建者后丢文件请求)
      - target_folder_id → folders.id (SET NULL, 文件夹删了文件请求保留)
    """
    __tablename__ = "file_requests"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(32), nullable=False, unique=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    target_folder_id = Column(Integer, ForeignKey("folders.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)
    allowed_extensions = Column(ARRAY(String), nullable=True)
    require_uploader_name = Column(Boolean, nullable=False, server_default="true")
    max_file_size_mb = Column(Integer, nullable=True)
    submission_count = Column(Integer, nullable=False, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, nullable=False, server_default="now()")
    updated_at = Column(DateTime, nullable=False, server_default="now()")

    def __repr__(self):
        return f"<FileRequest(id={self.id}, title='{self.title[:30]}', submissions={self.submission_count}, active={self.is_active})>"


class AuditLog(Base):
    """v2 PR7: 完整安全审计 (谁在什么时候做了什么)

    数据来源:
      - RequestLoggingMiddleware: 自动记录所有 /api/v1/* 调用
      - 服务层显式 log: 高敏感操作 (share-link 创建, visibility 改, 文件请求创建/submit)

    字段:
      - user_id: 登录用户 (NULL = 匿名, 如 /r/:token 公开提交)
      - ip_address: 客户端 IP (via X-Forwarded-For 或 request.client.host)
      - user_agent: 浏览器 UA (string, 用于审计浏览器版本)
      - method+path: HTTP 方法 + 路径 (token 查询参数已脱敏)
      - action: 标准化动作 ('read'| 'write'| 'delete'| 'login'| 'share'| ...)
      - resource_type+id: 受影响资源 ('file:42' | 'folder:7' | 'comment:99' | NULL)
      - status_code+duration_ms: HTTP 响应状态 + 耗时 (运维质量)
      - metadata JSONB: 动作特定扩展数据 (重命名 old/new name, 删除前 file 名, ...)

    生命周期:
      - 写: 同步写 (audit 必须可靠, 不能丢)
      - 读: GET /api/v1/admin/audit (admin only) + 30 天保留 (Celery beat)
    """
    __tablename__ = "audit_log"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True, index=True)  # IPv6 max 45
    user_agent = Column(Text, nullable=True)
    method = Column(String(10), nullable=False, index=True)
    path = Column(String(500), nullable=False, index=True)
    action = Column(String(50), nullable=False, index=True)
    resource_type = Column(String(20), nullable=True)
    resource_id = Column(String(50), nullable=True)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    meta_data = Column(JSONB, nullable=True)  # alembic 048 列名 = meta_data (与 ORM attr 统一, 不要 metadata 重名)
    created_at = Column(DateTime, nullable=False, server_default="now()", index=True)

    __table_args__ = (
        Index("ix_audit_log_user_action_time", "user_id", "action", "created_at"),
        Index("ix_audit_log_action_time", "action", "created_at"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action='{self.action}', user_id={self.user_id}, status={self.status_code})>"
