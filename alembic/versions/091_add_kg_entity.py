"""add kg_entities 知识图谱扁平实体表 (PR8 W94 +1)

PR8 知识图谱深度联动 — 实体链召回主表:
- kg_entities 表 (entity_name / entity_type / knowledge_id FK / embedding Vector(1024)
  / first_seen_at / last_seen_at / mention_count)
- uq_kg_entities_name_type_kid 幂等唯一约束 (重跑抽取不产生重复行)
- ix_kg_entities_name / ix_kg_entities_type / ix_kg_entities_knowledge_id (B-tree)
- ix_kg_entities_embedding_hnsw (pgvector HNSW, 实体链召回 P95 ≤ 100ms 门禁 b)

idempotent guard (沿用 087/088/089/090 模式):
- CREATE TABLE IF NOT EXISTS kg_entities (...)
- DO $$ BEGIN IF NOT EXISTS (pg_constraint) THEN ADD CONSTRAINT ... END IF; END$$;
- CREATE INDEX IF NOT EXISTS (B-tree)
- CONCURRENTLY 不能套 IF NOT EXISTS (PG 限制) → DO $$ 探测 pg_indexes 二段式 (089 同模式)

E11 GIN/HNSW 大表阻塞风险 (RISKS §R4, 089 同款处置):
- CREATE INDEX CONCURRENTLY 避免写锁阻塞入库
- kg_entities 是**新建空表**, 首次建索引 0 阻塞 (与 089 在已有 knowledge 表建索引不同)
- 但仍用 CONCURRENTLY: 幂等重放时表已有数据, 避免二次 upgrade 阻塞
- 离线窗口门禁 ≤ 120s (RUNBOOK §0.7 已标注)

down_revision 接续关系 (派工 v11 段 1):
- 接 ('090_add_rag_eval_report',)
- 090 = PR5 merge commit 5fdcb6819 → MERGE-03 收口 034343f8a (锚点 459)

**PR8 是 10 PR 中最后 1 个 alembic PR**:
- 串单链全景: 087 → 088 (PR2 chunk) → 089 (PR3 GIN/tsvector) → 090 (PR5 rag_eval) → **091 (PR8 kg_entity)**
- 091 之后 10 PR alembic 收口, PR9 (auto-research) / PR10 (docs) 均无迁移

Why new table (派工 v11 §13 仓库实情真查, 类 20 #33 brief 错配 #1):
- 已有 knowledge_entities (KnowledgeEntity SPO 三元组) + entity_co_occurrence (共现网络)
  两表走 lifespan Base.metadata.create_all, **0 alembic 迁移** (仅 030 改过 embedding 维度)
- 091 **不动**上述两表, 仅建 kg_entities (扁平命名实体, 与三元组互补非替代)
- 与 PR5 处置 RAGEvaluationReport vs 已有 RAGEvaluation 完全同款模式

Revision ID: 091_add_kg_entity
Revises: 090_add_rag_eval_report
Create Date: 2026-07-30
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "091_add_kg_entity"
down_revision = "090_add_rag_eval_report"
branch_labels = None
depends_on = None


def upgrade():
    # 1. CREATE TABLE IF NOT EXISTS kg_entities (idempotent guard 087/088/089/090 模式)
    # embedding vector(1024) — 与 app/models/kg_entity.py KG_ENTITY_VECTOR_DIM 对齐
    # pgvector 扩展已在 main.py lifespan 启动时安装 (CLAUDE.md 架构决策), 此处不重复 CREATE EXTENSION
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS kg_entities (
            id SERIAL PRIMARY KEY,
            entity_name VARCHAR(500) NOT NULL,
            entity_type VARCHAR(32) NOT NULL DEFAULT 'OTHER',
            knowledge_id INTEGER NOT NULL
                REFERENCES knowledge(id) ON DELETE CASCADE,
            embedding vector(1024),
            first_seen_at TIMESTAMP NOT NULL DEFAULT now(),
            last_seen_at TIMESTAMP NOT NULL DEFAULT now(),
            mention_count INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP NOT NULL DEFAULT now(),
            updated_at TIMESTAMP NOT NULL DEFAULT now()
        );
        """
    )

    # 2. 幂等唯一约束 uq_kg_entities_name_type_kid (重跑实体抽取不产生重复行)
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'uq_kg_entities_name_type_kid'
        ) THEN
            ALTER TABLE kg_entities
            ADD CONSTRAINT uq_kg_entities_name_type_kid
            UNIQUE (entity_name, entity_type, knowledge_id);
        END IF;
        END$$;
        """
    )

    # 3. CheckConstraint ck_kg_entities_mention_count (mention_count >= 1)
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_kg_entities_mention_count'
        ) THEN
            ALTER TABLE kg_entities
            ADD CONSTRAINT ck_kg_entities_mention_count
            CHECK (mention_count >= 1);
        END IF;
        END$$;
        """
    )

    # 4. CheckConstraint ck_kg_entities_name_nonempty (entity_name 非空串)
    op.execute(
        """
        DO $$ BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint
            WHERE conname = 'ck_kg_entities_name_nonempty'
        ) THEN
            ALTER TABLE kg_entities
            ADD CONSTRAINT ck_kg_entities_name_nonempty
            CHECK (length(entity_name) >= 1);
        END IF;
        END$$;
        """
    )

    # 5. B-tree 索引 (实体链召回精确匹配路 + 类型聚合 + FK join)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_entities_name "
        "ON kg_entities (entity_name);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_entities_type "
        "ON kg_entities (entity_type);"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_kg_entities_knowledge_id "
        "ON kg_entities (knowledge_id);"
    )

    # 6. pgvector HNSW 索引 (实体链召回 P95 ≤ 100ms 门禁 b, E38)
    # CONCURRENTLY 不能套 IF NOT EXISTS (PG 限制) → DO $$ 探测 pg_indexes 二段式 (089 同模式)
    # E11 大表阻塞: kg_entities 首次为空表 0 阻塞; 幂等重放时 CONCURRENTLY 避免写锁
    # vector_cosine_ops — 与 entity_service._generate_entity_embedding cosine 距离一致
    op.execute(
        """
        DO $$
        BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_indexes
            WHERE schemaname = 'public'
              AND tablename = 'kg_entities'
              AND indexname = 'ix_kg_entities_embedding_hnsw'
        ) THEN
            EXECUTE 'CREATE INDEX CONCURRENTLY ix_kg_entities_embedding_hnsw '
                    'ON kg_entities USING hnsw (embedding vector_cosine_ops);';
        END IF;
        END$$;
        """
    )


def downgrade():
    # DROP TABLE 自动级联所有 index + constraint (090 同模式)
    # CASCADE 处理 FK 引用 (knowledge_id → knowledge.id)
    op.execute("DROP TABLE IF EXISTS kg_entities CASCADE;")
