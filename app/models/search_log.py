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
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY

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

    # 点击行为 (前端后续 PATCH 更新)
    clicked_id = Column(Integer, nullable=True)
    click_position = Column(Integer, nullable=True)  # 1-based, 在 top_ids 中的位置

    # 上下文
    session_id = Column(String(100), nullable=True, index=True)  # 前端生成 UUID
    source = Column(
        String(50), nullable=True, index=True
    )  # 'knowledge_search' / 'agent_chat' / 'mobile'

    # 时间戳 (TimestampMixin 提供 created_at/updated_at)
    # 单独加 raw 字段方便查询时直接 SELECT
    # 注: TimestampMixin.created_at 已是 DateTime, 这里不重复定义

    __table_args__ = (
        Index("idx_search_logs_created_at", "created_at"),
        Index("idx_search_logs_query_model", "query", "embedding_model"),
        Index("idx_search_logs_source_created", "source", "created_at"),
        # gin trigram 索引: 模糊匹配重复 query
        # 注: pg_trgm 扩展可能未启用, alembic 迁移用 SQL 'CREATE EXTENSION IF NOT EXISTS pg_trgm'
    )

    def __repr__(self) -> str:
        return f"<SearchLog(id={self.id}, query='{self.query[:30]}', model='{self.embedding_model}')>"
