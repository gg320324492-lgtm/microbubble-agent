"""SearchLog model - 检索质量监控埋点 (v30)

背景:
  v29 切换到 Qwen3-Embedding-0.6B 后, 需要长期监控检索质量.
  38 条 A/B 评估 (build_eval_set.py) 是合成数据, 不能完全代表真实用户行为.
  本表记录: 用户在 KnowledgeView 搜索时的 query + 检索结果 + 点击行为,
  用于后期统计: 任何点击率 / top-1 点击率 / 平均点击位置 / 零点击率,
  支持按 embedding_model 分组的 A/B 长期监控.

数据流:
  用户在 UI 搜索框输入 query
    → 后端 GET /api/v1/knowledge?search=query (现有, 不用改)
    → 后端返回 top-K (id + title + snippet)
  用户点击某条结果
    → 前端 POST /api/v1/analytics/search (log search event)
    → 前端 PATCH /api/v1/analytics/search/{id}/click (log click event)

埋点字段:
  - query: 用户原始搜索词
  - top_ids: top-K 检索结果 ID 列表 (按相似度排序)
  - clicked_id: 用户点击的 ID (NULL=没点)
  - click_position: 1-based, top_ids 数组里的位置
  - embedding_model: 当前 EMBEDDING_MODEL_NAME env 值, 用于 A/B 分组
  - source: 'knowledge_search' / 'agent_chat' / 'mobile'
  - session_id: 前端生成 UUID, 关联同次会话的多次搜索
  - created_at: 时间戳 (默认 NOW())

参考:
  - app/services/embedding_service.py (用 model=get_embedding_dimension 模式)
  - app/api/v1/knowledge.py (现有 knowledge_search 端点)
"""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from app.core.database import Base
from app.models.base import TimestampMixin


class SearchLog(Base, TimestampMixin):
    """检索质量埋点记录表"""

    __tablename__ = "search_logs"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 搜索内容
    query = Column(Text, nullable=False, index=True)  # gin index in alembic

    # 检索元数据
    embedding_model = Column(
        String(200), nullable=True, index=True
    )  # e.g. 'Qwen/Qwen3-Embedding-0.6B'
    top_ids = Column(ARRAY(Integer), nullable=False)  # top-K 检索结果 ID (按相似度排序)

    # v31.2: 归属列 (可选 auth 用户, 匿名 NULL)
    # nullable=True: 匿名用户发埋点时 user_id=NULL
    # ondelete=SET NULL: 成员删除时保留历史埋点记录 (不丢历史)
    user_id = Column(
        Integer,
        ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # 点击行为 (前端后续 PATCH 更新)
    clicked_id = Column(Integer, nullable=True)
    click_position = Column(Integer, nullable=True)  # 1-based, 在 top_ids 中的位置

    # W98 CHAT-P1-D3: 答案评价 (-1=👎 / 1=👍 / NULL=未反馈)
    # 与 feedback.message_id 同步写入: 前端 POST /chat/feedback 双写
    # CHECK 约束 ck_search_logs_answer_rating 在 alembic 093 实施 (server 端 NULL + 强校验)
    answer_rating = Column(Integer, nullable=True, index=True)

    # 上下文
    session_id = Column(String(100), nullable=True, index=True)  # 前端生成 UUID
    source = Column(
        String(50), nullable=True, index=True
    )  # 'knowledge_search' / 'agent_chat' / 'mobile'

    # ==================== W93 PR7 B-7 observability 扩展字段 ====================
    # 12+ 结构化字段, 全部 nullable=True (老数据兼容, 不破坏已有 schema)
    # 注: 不动已有字段 (id / query / embedding_model / top_ids / user_id / clicked_id
    #                     / click_position / session_id / source / created_at / updated_at)
    # PR7 不写 alembic (遵循 §11.2), 这些列先定义在 model, 等 PR10 阶段落库
    latency_ms = Column(Float, nullable=True)  # 单次召回总耗时 (毫秒)
    retrieval_method = Column(String(50), nullable=True)  # 'hybrid' / 'vector_only' / ...
    candidate_k = Column(Integer, nullable=True)  # 重排序前候选数
    top_k_actual = Column(Integer, nullable=True)  # 实际返回条数
    caller_path = Column(String(100), nullable=True)  # 调用方路径 (hybrid_retriever / kb_qa / ...)
    for_query = Column(Integer, nullable=True)  # 0/1, 是否 query 侧 (for_query=True)
    has_query_prompt = Column(Integer, nullable=True)  # 0/1, 是否启用 query prefix prompt
    original_len = Column(Integer, nullable=True)  # 原始 query 长度
    truncated_len = Column(Integer, nullable=True)  # 截断后 query 长度
    vector_score = Column(Float, nullable=True)  # 向量路 top-1 score
    bm25_score = Column(Float, nullable=True)  # BM25 路 top-1 score
    graph_score = Column(Float, nullable=True)  # 图谱路 top-1 score
    rerank_score = Column(Float, nullable=True)  # rerank 路 top-1 score
    per_path_latency_ms = Column(JSONB, nullable=True)  # {"vector": 12.3, "bm25": 8.1, "graph": 25.0, "rerank": 5.2}
    per_path_count = Column(JSONB, nullable=True)  # {"vector": 25, "bm25": 20, "graph": 5}
    per_path_error = Column(JSONB, nullable=True)  # {"vector": 0, "bm25": 1}
    slow_query = Column(Integer, nullable=True)  # 0/1, 是否触发慢查询告警 (P99 > 200ms)
    error_count = Column(Integer, nullable=True)  # 本次召回累计错误数
    error_msg = Column(Text, nullable=True)  # 首个错误信息 (截断 500 字)
    # ==================== W93 PR7 B-7 扩展字段结束 ====================

    # ==================== W99-RAG-1 Query Cache 扩展字段 ====================
    # 仅追加, 不改老字段, 全部 nullable=True (老数据兼容, 不破坏已有 schema)
    cache_hit = Column(Integer, nullable=True)  # 0/1, 是否命中 query cache (精确 / 语义相似)
    cache_similarity = Column(Float, nullable=True)  # 语义相似命中 cosine 值, 精确命中 1.0
    # ==================== W99-RAG-1 扩展字段结束 ====================

    # ==================== W99-RAG-2 Citation 段落级溯源 扩展字段 ====================
    # 仅追加, 不改老字段, 全部 nullable=True (老数据兼容, 不破坏已有 schema)
    citation_count = Column(Integer, nullable=True)  # 本次召回生成的 citation 数
    # ==================== W99-RAG-2 扩展字段结束 ====================

    # W100-RAG-5: 第 5 路 OCR 图片召回 top-1 similarity
    image_score = Column(Float, nullable=True)

    # 时间戳 (TimestampMixin 提供 created_at/updated_at)
    # 单独加 raw 字段方便查询时直接 SELECT
    # 注: TimestampMixin.created_at 已是 DateTime, 这里不重复定义

    __table_args__ = (
        Index("idx_search_logs_created_at", "created_at"),
        Index("idx_search_logs_query_model", "query", "embedding_model"),
        Index("idx_search_logs_source_created", "source", "created_at"),
        # v31.2: 复合索引 (按用户按时段聚合, per-user analytics 主查询路径)
        Index("idx_search_logs_user_created", "user_id", "created_at"),
        # gin trigram 索引: 模糊匹配重复 query
        # 注: pg_trgm 扩展可能未启用, alembic 迁移用 SQL 'CREATE EXTENSION IF NOT EXISTS pg_trgm'
        # W93 PR7 B-7: 慢查询索引 (grafana 慢查询面板主查询路径)
        Index("idx_search_logs_slow_query", "slow_query", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<SearchLog(id={self.id}, query='{self.query[:30]}', model='{self.embedding_model}')>"
