"""search_logs 埋点表 (v31 检索质量监控)

背景: v29 切换 Qwen3 + v30 A/B 评估只用 38 条 query (一次性快照).
本表为长期生产监控: 用户在 KnowledgeView 搜索 / Agent 调用 search_knowledge 工具时,
静默记录 query + top_ids + 是否点击 + 点击位置. 用于:
  - 长期 A/B 监控 (按 embedding_model 分组)
  - 发现真实用户 query 痛点 (评估集覆盖不到)
  - dashboard 显示 5 个核心指标 (CTR / 零点击率 / 平均点击位置 / 总搜索 / 总点击)
  - 未来切模型时直接对比历史数据

revision ID 短名 '031_search_log' (15 字符, 兼容 alembic_version VARCHAR(32)).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '031_search_log'
down_revision: Union[str, None] = '030_qw3_1024'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 search_logs 表 (字段顺序对齐 app/models/search_log.py)
    op.execute("""
        CREATE TABLE search_logs (
            id BIGSERIAL PRIMARY KEY,
            query TEXT NOT NULL,
            embedding_model VARCHAR(200),
            top_ids INTEGER[] NOT NULL,
            clicked_id INTEGER,
            click_position INTEGER,
            session_id VARCHAR(100),
            source VARCHAR(50),
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """)

    # 索引: created_at 用于时间范围查询 (stats endpoint 按 days 过滤)
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_created_at ON search_logs (created_at)")

    # 索引: query + embedding_model 用于分析 "某 query 在某模型下表现"
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_query_model ON search_logs (query, embedding_model)")

    # 索引: source + created_at 用于按数据源分组 (knowledge_search vs agent_chat)
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_source_created ON search_logs (source, created_at)")

    # 单列索引 (高频过滤场景)
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_embedding_model ON search_logs (embedding_model)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_session_id ON search_logs (session_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_search_logs_source ON search_logs (source)")


def downgrade() -> None:
    # 降级顺序: 先删索引再删表
    op.execute("DROP INDEX IF EXISTS idx_search_logs_source")
    op.execute("DROP INDEX IF EXISTS idx_search_logs_session_id")
    op.execute("DROP INDEX IF EXISTS idx_search_logs_embedding_model")
    op.execute("DROP INDEX IF EXISTS idx_search_logs_source_created")
    op.execute("DROP INDEX IF EXISTS idx_search_logs_query_model")
    op.execute("DROP INDEX IF EXISTS idx_search_logs_created_at")
    op.execute("DROP TABLE IF EXISTS search_logs")
