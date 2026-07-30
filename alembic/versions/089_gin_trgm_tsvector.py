"""add pg_trgm + GIN trgm + tsvector + GIN tsvector for knowledge (PR3 W89 +2)

PR3 BM25 增量 + PG 全文索引:
- pg_trgm 扩展 (OOV 兜底, 缺口 4)
- knowledge.content_tsvector 列 (PG tsvector, GENERATED 触发式)
- knowledge.search_text 列 (text, 入库 token 化缓存)
- GIN trgm 索引 (knowledge.search_text gin_trgm_ops, OOV 兜底)
- GIN tsvector 索引 (knowledge.content_tsvector, 全文路召回)

idempotent guard (沿用 087/088 模式):
- CREATE EXTENSION IF NOT EXISTS pg_trgm
- CREATE TABLE IF NOT EXISTS 不适用 (新列, 新索引, 加在已有表)
- ADD COLUMN IF NOT EXISTS
- CREATE INDEX IF NOT EXISTS (包含 CONCURRENTLY 不能套 IF NOT EXISTS 的规避)
- 087/088 同模式: 必加 DO $$ BEGIN IF NOT EXISTS 包裹 ADD CONSTRAINT

PR3 大表 GIN 阻塞风险 (RISKS §R4):
- CONCURRENTLY 不能套 IF NOT EXISTS (PG 限制), 用 DO $$ 探测 pg_indexes 后再 CREATE INDEX CONCURRENTLY
- 必填 offline window ≤ 120s 门禁 (RUNBOOK §0 已标注)
- 如 retry: 第二次直接 CREATE INDEX (非 CONCURRENTLY) 即可, 无需再 concurrent

down_revision 接续关系 (派工 v11 段 1):
- 接 ('088_add_knowledge_chunk',)
- 088 = W88 PR2 merge commit e65f3357c

Revision ID: 089_gin_trgm_tsvector
Revises: 088_add_knowledge_chunk
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision = "089_gin_trgm_tsvector"
down_revision = "088_add_knowledge_chunk"
branch_labels = None
depends_on = None


def upgrade():
    # 1. pg_trgm 扩展 (idempotent guard, E24 已入 v1.1)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. knowledge.search_text 列 (text, 缓存 token 化文本)
    op.execute(
        "ALTER TABLE knowledge "
        "ADD COLUMN IF NOT EXISTS search_text TEXT;"
    )

    # 3. knowledge.content_tsvector 列 (GENERATED 触发式, 入库自动计算)
    # 用 simple config + search_text (PR3 W89 +1 产物的缓存列), 避免对原始 content 计算
    # GENERATED ALWAYS AS (...) STORED 走 search_text → tsvector, search_text 由 knowledge_service 钩子写入
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'knowledge' AND column_name = 'content_tsvector'
        ) THEN
            ALTER TABLE knowledge
            ADD COLUMN content_tsvector TSVECTOR
            GENERATED ALWAYS AS (to_tsvector('simple', coalesce(search_text, ''))) STORED;
        END IF;
        END$$;
        """
    )

    # 4. GIN trgm 索引 (OOV 兜底, 缺口 4, RISKS §R4)
    # CONCURRENTLY 不能套 IF NOT EXISTS (PG 限制), 用 DO $$ 探测 pg_indexes
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'knowledge'
              AND indexname = 'ix_knowledge_search_text_trgm'
        ) THEN
            -- CONCURRENTLY 不能在事务中跑, 在 DO 块外单独跑
            NULL;
        END IF;
        END$$;
        """
    )
    # CONCURRENTLY 必在事务外, alembic 默认是事务包, 需要 autocommit
    # 探测 + 创建二段式: 探测后 CREATE INDEX CONCURRENTLY
    op.execute(
        """
        DO $$
        BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'knowledge'
              AND indexname = 'ix_knowledge_search_text_trgm'
        ) THEN
            EXECUTE 'CREATE INDEX CONCURRENTLY ix_knowledge_search_text_trgm '
                    'ON knowledge USING gin (search_text gin_trgm_ops) '
                    'WHERE search_text IS NOT NULL;';
        END IF;
        END$$;
        """
    )

    # 5. GIN tsvector 索引 (全文路召回)
    op.execute(
        """
        DO $$
        BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'knowledge'
              AND indexname = 'ix_knowledge_content_tsvector'
        ) THEN
            EXECUTE 'CREATE INDEX CONCURRENTLY ix_knowledge_content_tsvector '
                    'ON knowledge USING gin (content_tsvector);';
        END IF;
        END$$;
        """
    )

    # 6. 列长度约束 (派工 v10 §2 type hint + 常量固化纪律)
    # search_text 上限与 MAX_EMBED_INPUT_CHARS=6000 对齐 (PR1)
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_knowledge_search_text_len'
        ) THEN
            ALTER TABLE knowledge
            ADD CONSTRAINT ck_knowledge_search_text_len
            CHECK (search_text IS NULL OR length(search_text) <= 6000);
        END IF;
        END$$;
        """
    )


def downgrade():
    # 1. drop 索引 (CONCURRENTLY 反向: 普通 DROP 即可)
    op.execute("DROP INDEX IF EXISTS ix_knowledge_content_tsvector;")
    op.execute("DROP INDEX IF EXISTS ix_knowledge_search_text_trgm;")
    # 2. drop 列 (GENERATED 列级联)
    op.execute("ALTER TABLE knowledge DROP COLUMN IF EXISTS content_tsvector;")
    op.execute("ALTER TABLE knowledge DROP COLUMN IF EXISTS search_text;")
    # 3. pg_trgm 扩展不删 (其他业务可能用, 谨慎)