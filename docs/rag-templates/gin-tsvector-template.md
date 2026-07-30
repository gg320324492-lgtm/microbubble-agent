# GIN + tsvector 派工模板 (PR3 RAG 系列)

> **用途**: RAG 大改造 PR3 (GIN + tsvector + pg_trgm + 中文分词) 派工模板
> **适用 PR 范围**: PR3 (rag_chunks.content GIN trgm + tsvector + pg_trgm/pg_jieba 扩展)
> **依赖前序 PR**: PR2 (chunking + rag_chunks 表) 已合并 main HEAD
> **目标锚点范式区间**: W86 mini-3 322 → W86 mini-4 324 (+2, 守恒 +1 实施 +1)
> **CLAUDE.md 引用章节**:
> - "alembic 串单链纪律 (062→063→064→065, 066→067 等)" — W68 第 6+7 批 §2.3
> - "2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)" — 5 条铁律
> - `docs/rag-templates/alembic-migration-template.md` — down_revision 串单链
> - `docs/rag-templates/chunking-service-template.md` — rag_chunks 表 schema

---

## 派工 v10 段 0-9 内容 (主拍预填, agent 实施时按段实拍)

### 段 0: down_revision 接续关系 (必填首行)

```bash
# 派工 prompt 第 1 行必含 down_revision (派工前提铁律 12 第 11 条)
# PR3 必须等 PR2 合并后开工
down_revision = "088_rag_chunks"
# 派工前必跑 alembic heads 验证 base HEAD 已是 088
```

### 段 1: 派工范围 (PR3 GIN + tsvector 主体)

```
- alembic 089_rag_fts.py (B 路线 alembic agent):
  - 启用 pg_trgm 扩展 (CREATE EXTENSION IF NOT EXISTS pg_trgm)
  - rag_chunks.content 列加 GIN trgm 索引 (CREATE INDEX CONCURRENTLY)
  - rag_chunks.content 加 tsvector 列 (GENERATED ALWAYS AS ... STORED)
  - tsvector 列加 GIN 索引
  - 测试数据验证 LIKE / @@ 查询走索引
- app/services/rag_search_service.py (新增全文搜索服务)
- app/api/rag_search.py (5 端点: 全文搜索 + tsquery + 高亮)
- tests/test_rag_search_e2e.py (5 case PASS)
```

### 段 2: pg_trgm 扩展创建 (参考 alembic 066 模式)

```python
# alembic/versions/089_rag_fts.py
"""RAG 大改造 PR3: rag_chunks GIN trgm + tsvector 全文搜索

W86 第 1 批 PR3 派工:
- 启用 pg_trgm 扩展 (三元组相似度, LIKE '%keyword%' 加速)
- rag_chunks.content 加 tsvector 列 (GENERATED ALWAYS AS ... STORED)
- GIN trgm 索引 on content (回退 LIKE 搜索, W3 部署文档主推)
- GIN 索引 on tsvector 列 (PostgreSQL FTS, websearch_to_tsquery 支持)

派工前提铁律 12 第 11 条 (W68 第 11 批 alembic rebase 纪律):
- down_revision 必须接最新 head 088_rag_chunks (PR2 已合并)
- 部署前必跑 alembic chain verify, 必须 1 head
- CREATE INDEX CONCURRENTLY 防阻塞 (生产大表必加, 锁表 30s+)

派工前提铁律 12 第 5 条: 实施前必先 information_schema 实查表名 + 列类型
派工前提铁律 12 第 9 条: 0 production code 例外必含派工批文 (主拍决策已批 PR3)
"""
from alembic import op


revision = "089_rag_fts"
down_revision = "088_rag_chunks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 启用 pg_trgm 扩展 (idempotent guard)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. 加 tsvector 列 (GENERATED ALWAYS AS ... STORED, 自动维护)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'rag_chunks' AND column_name = 'content_tsvector'
            ) THEN
                ALTER TABLE rag_chunks
                ADD COLUMN content_tsvector tsvector
                GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED;
            END IF;
        END$$;
    """
    )

    # 3. GIN trgm 索引 on content (CONCURRENTLY, 不锁表, 参考 W68 第 6+7 批 §2.3)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_rag_chunks_content_trgm'
            ) THEN
                CREATE INDEX CONCURRENTLY ix_rag_chunks_content_trgm
                ON rag_chunks USING gin (content gin_trgm_ops);
            END IF;
        END$$;
    """
    )

    # 4. GIN 索引 on content_tsvector (CONCURRENTLY)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_rag_chunks_content_tsvector'
            ) THEN
                CREATE INDEX CONCURRENTLY ix_rag_chunks_content_tsvector
                ON rag_chunks USING gin (content_tsvector);
            END IF;
        END$$;
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_rag_chunks_content_tsvector;")
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_rag_chunks_content_trgm;")
    op.execute("ALTER TABLE rag_chunks DROP COLUMN IF EXISTS content_tsvector;")
    # pg_trgm 扩展不删除 (可能其他表用, 例如 meetings.cluster_id_history)
```

### 段 3: CREATE INDEX CONCURRENTLY 防阻塞 (W68 第 6+7 批 §2.3 + W74 B-1 084 实战)

**为什么必加 CONCURRENTLY**:
- 大表 (>10K 行) 加 GIN 索引不锁表, 允许并发 INSERT/UPDATE/DELETE
- 不加 CONCURRENTLY → `ALTER TABLE` 锁 30s+, 生产阻塞
- alembic 默认不加 CONCURRENTLY (历史教训 W74 B-1 084, 派工 v6 段 5 反馈 #7)

**CONCURRENTLY 限制**:
1. 不能在事务中运行 (alembic 默认每 migration 一个事务, 需 `op.execute()` 单独执行, 已在本模板体现)
2. 创建时间 ~ 2x 普通 (因为后台并发维护)
3. 失败时留 INVALID 索引, 必须 `DROP INDEX CONCURRENTLY invalid_idx;` 清理

**实施后验证** (派工前提铁律 12 第 5 条实查):
```sql
-- 验证索引有效 (非 INVALID)
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'rag_chunks'
  AND indexname LIKE 'ix_rag_chunks_%';
-- 期望: 至少 2 行, 无 INVALID 状态

-- 验证 EXPLAIN 走索引 (LIKE '%微纳米%')
EXPLAIN ANALYZE
SELECT id, content FROM rag_chunks
WHERE content LIKE '%微纳米%'
LIMIT 10;
-- 期望: Bitmap Index Scan on ix_rag_chunks_content_trgm
```

### 段 4: 中文分词器选型 (3 选 1, 主拍拍板)

#### 选型 A: jieba (Python 端, 不依赖 PostgreSQL 扩展)

```python
# app/services/rag_search_service.py
import jieba

def tokenize_chinese_jieba(text: str) -> list[str]:
    """jieba 中文分词, Python 端, 不依赖 PostgreSQL 扩展"""
    return list(jieba.cut(text))
```

**优点**: 无需 PostgreSQL 扩展, 部署简单
**缺点**: 分词在 Python 端, 数据库无法用 `to_tsvector('jieba', text)` (需自定义配置)

#### 选型 B: pg_jieba (PostgreSQL 扩展, smlar + zhparser)

```sql
-- 启用 pg_jieba
CREATE EXTENSION pg_jieba;

-- 加自定义文本搜索配置
CREATE TEXT SEARCH CONFIGURATION chinese_jieba (PARSER = pg_jieba);
ALTER TEXT SEARCH CONFIGURATION chinese_jieba
ADD MAPPING FOR n, v, a, i, e, l, d, m WITH simple;
```

```python
# app/services/rag_search_service.py
async def search_chinese(db: AsyncSession, query: str) -> list[dict]:
    """pg_jieba 全文搜索"""
    result = await db.execute(
        text("""
        SELECT id, content, ts_rank(content_tsvector, query) AS rank
        FROM rag_chunks, websearch_to_tsquery('chinese_jieba', :query) AS query
        WHERE content_tsvector @@ query
        ORDER BY rank DESC
        LIMIT 20;
        """),
        {"query": query}
    )
    return [dict(row) for row in result]
```

**优点**: 数据库原生中文分词, 性能好
**缺点**: 需编译 pg_jieba 扩展, Docker 镜像需 apt-get install (派工时需确认 docker-compose.yml)

#### 选型 C: zhparser (中文解析器, ZParser)

```sql
CREATE EXTENSION zhparser;
CREATE TEXT SEARCH CONFIGURATION chinese_zhparser (PARSER = zhparser);
ALTER TEXT SEARCH CONFIGURATION chinese_zhparser
ADD MAPPING FOR n, v, a, i, e, l WITH simple;
```

**优点**: 工业级中文分词, scws 后端
**缺点**: 需 ZParser 商业许可 / 自编译, 维护成本高

**主拍决策 (派工时拍板)**: 默认**选型 A (jieba Python 端)** — 不依赖 PostgreSQL 扩展, 部署简单, 适合 W86 范围。后续 PR 可升级到选型 B (派工 v10 段 7 后续优化)。

### 段 5: 全文搜索服务实现 (tsvector + pg_trgm 双策略)

```python
# app/services/rag_search_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List
import logging

logger = logging.getLogger(__name__)


class RagSearchService:
    """RAG 全文搜索服务: tsvector (PostgreSQL FTS) + pg_trgm (LIKE 加速) 双策略"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def search_fts(self, query: str, limit: int = 20) -> List[dict]:
        """tsvector 全文搜索 (websearch_to_tsquery, 支持 AND/OR/'phrase')"""
        result = await self.db.execute(
            text("""
            SELECT id, knowledge_id, content, chunk_index,
                   ts_rank(content_tsvector, query) AS rank,
                   ts_headline('simple', content, query, 'MaxFragments=2') AS highlight
            FROM rag_chunks, websearch_to_tsquery('simple', :query) AS query
            WHERE content_tsvector @@ query
            ORDER BY rank DESC
            LIMIT :limit;
            """),
            {"query": query, "limit": limit}
        )
        return [dict(row) for row in result]

    async def search_trgm(self, query: str, limit: int = 20) -> List[dict]:
        """pg_trgm 三元组相似度搜索 (回退 LIKE, 支持模糊匹配)"""
        result = await self.db.execute(
            text("""
            SELECT id, knowledge_id, content, chunk_index,
                   similarity(content, :query) AS sim
            FROM rag_chunks
            WHERE content % :query
            ORDER BY sim DESC
            LIMIT :limit;
            """),
            {"query": query, "limit": limit}
        )
        return [dict(row) for row in result]
```

### 段 6: tsvector 列 + GENERATED ALWAYS AS ... STORED

**为什么用 STORED 而非 VIRTUAL**:
- STORED: tsvector 实际写入磁盘, 查询时无需重算, 索引扫描快
- VIRTUAL: 视图层计算, 每次查询重算, 索引不能直接用
- **本项目派工前主拍拍板 STORED** (W68 第 6+7 批 §2.3 实战)

**自动维护**: `GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED` — content 写入/更新时 tsvector 自动重算, 无需 trigger。

### 段 7: 派工 brief 据实上报铁律

派工 brief 描述**必须**与实际工作内容一致:
- 派工 brief 写"GIN trgm + tsvector" → 实际必须建**两个** GIN 索引 (而非只建 trgm)
- 派工 brief 写"CONCURRENTLY" → 实际必须用 `CREATE INDEX CONCURRENTLY` (而非普通 CREATE INDEX)
- 派工 brief 写"jieba / pg_jieba / zhparser 选型" → 实际必须明确选 1 个 (而非"待定")

类 20.13 实战 19 (W85 D-2 据实上报): 锚点范式 +6 不凑 +7 — PR3 实测 +1/+2 守恒, 不虚报 +3。

### 段 8: 与 PR1/2/5/8 接续关系

| PR | 共享 schema | 依赖 |
|----|------------|------|
| PR1 (Embedding 一致性) | embedding model 384 dim | 无 |
| PR2 (chunking) | rag_chunks 表 | PR1 |
| **PR3 (本 PR, GIN + tsvector)** | rag_chunks.content 索引 | **PR2** |
| PR5 (RAGEvaluator) | rag_eval_report 表 | 无 (独立) |
| PR8 (rag_search_logs) | rag_search_logs 表 | 无 (独立) |

**串单链纪律**: PR3 等 PR2 合并后开工 (down_revision = "088_rag_chunks"), PR5/PR8 可并行 (见 alembic-migration-template.md 段 6)。

---

## 5 件套验证

| 验证项 | 命令 | 期望 |
|--------|------|------|
| 1. alembic 1 head | `docker exec microbubble-agent-app-1 alembic heads` | 1 行, 单 head |
| 2. pg_trgm 扩展已装 | `docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "SELECT extname FROM pg_extension WHERE extname = 'pg_trgm';"` | 1 行, pg_trgm |
| 3. tsvector 列存在 | 段 3 实查 SQL | content_tsvector 列, udt_name = `tsvector` |
| 4. GIN 索引有效 | 段 3 实查 SQL | 2 行 (trgm + tsvector), 无 INVALID |
| 5. EXPLAIN 走索引 | 段 3 EXPLAIN ANALYZE | Bitmap Index Scan on ix_rag_chunks_* |
| 6. e2e PASS | `pytest tests/test_rag_search_e2e.py -v` | 全部 PASS |

---

## 据实上报铁律

1. **派工 brief 与实测不符时, 必须据实上报** — 不擅自扩, 不擅自缩 (派工 v10 段 7 19 类实战)
2. **0 hit / 0 改动时不实施** — 例: 派工 brief 写"3 选型"实际只实现 jieba, 据实上报"jieba 实施 + pg_jieba/zhparser 占位"
3. **CONCURRENTLY 必加** — 不写 CONCURRENTLY = 大表锁 30s+ = 派工 v4 铁律 3 违规
4. **STORED 而非 VIRTUAL** — STORED 性能好, 索引可用, VIRTUAL 不能建索引 (派工 v4 铁律 3 实战)
5. **历史锚点永久保留** — 任何 GIN/索引实施教训 (e.g. W74 B-1 084 json→jsonb P1 / W82 B-2 Survey 错配) 必入 memory

---

## 引用章节 (CLAUDE.md 永久锚点)

- `## W68 第 6+7 批纪律沉淀 (永久锚点)` §2.3 alembic 串单链纪律 — CONCURRENTLY 实战
- `## 2026-07-24 alembic 并行 agent 串单链纪律 (commit 1852468a6)` — 5 条铁律
- `## 派工前提铁律 12 + 类 20 实战 18 实例` — 段 5/9 据实上报铁律
- `## 派工 v4 铁律 3 实战` — 实施前 plans 真验证
- `docs/rag-templates/alembic-migration-template.md` — down_revision 串单链
- `docs/rag-templates/chunking-service-template.md` — rag_chunks 表 schema

---

**模板版本**: v1.0 (W86 第 1 批 PR3 派工预填, 2026-07-30)
**作者**: support-docs-runbook agent
**沉淀**: memory 主题 9 (W 批 grand closure + 派工纪要 + 锚点范式)