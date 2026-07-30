# alembic Migration 模板 (PR2/3/5/8 RAG 系列共用)

> **用途**: RAG 大改造 PR2 (chunking)、PR3 (GIN+tsvector)、PR5 (RAGAS eval)、PR8 (rag_search_logs) 共用 alembic migration 派工模板
> **适用 PR 范围**: PR2 / PR3 / PR5 / PR8 (全部新表 + 索引类, 无老路径改造)
> **依赖前序 PR**: PR1 (Embedding 一致性) 已合并 main HEAD
> **目标锚点范式区间**: W86 第 1 批 320 → W86 mini-3 322 (PR2/3 估 +1 守恒 +1 实施 = +2, PR5/8 估 +1 守恒 +1 实施 = +2)
> **CLAUDE.md 引用章节**:
> - "0 production code 改动铁律" (W67 第 41 步 + W68 第 6+7+8 批增补)
> - "2026-07-24 alembic 并行 agent 串单链纪律 (commit `1852468a6`)" — 5 条铁律
> - "alembic 串单链纪律 (062→063→064→065, 066→067 等)" — W68 第 6+7 批 §2.3
> - "派工前提铁律 12 + 类 20 实战 18 实例"
> - "2026-06-13 webhint PWA 5 警告全栈修复新增" 段 ② (跨 PR 部署 cp + clear cache)

---

## 派工 v10 段 0-9 内容 (主拍预填, agent 实施时按段实拍)

### 段 0: down_revision 接续关系 (必填首行, 段 0 第 1 行铁律)

```bash
# 派工 prompt 第 1 行必含 down_revision 链序 (派工前提铁律 12 第 11 条)
# 例: 本 PR 接 086_backfill_drive_file_versions (W85 第 1 批后 base HEAD)
down_revision = "086_backfill_drive_file_versions"   # 主拍决策: 接最新 head, 不并行双头
```

### 段 1: 0. alembic chain 风险 (必填第 0 节, 参考 drive-v2-pr9-deployment.md 第 0 节)

```
0. alembic chain 风险
   - 当前 head: <python -m alembic heads 输出 (派工前实测)>
     期望: 1 个 head, 即 ['086_backfill_drive_file_versions']
     verify 命令:
       python -c "from alembic.config import Config; from alembic.script import ScriptDirectory; c=Config(); c.set_main_option('script_location','alembic'); s=ScriptDirectory.from_config(c); print(s.get_heads())"
   - 本 PR 新增迁移: <编号> (例: 088_rag_chunks) 接 <down_revision>
   - 回滚步骤: alembic downgrade -1 (单链纪律, 不用 `heads` 复数)
   - 离线窗口: <预计耗时 (秒/分钟)> — 例: 1 GIN 索引 ~30s (CONCURRENTLY 不锁表), 1 张新表 + 索引 ~10s
```

### 段 2: idempotent guard 模板 (DO $$ ... IF NOT EXISTS, 参考 alembic 087 模式)

```python
# alembic/versions/088_rag_chunks.py
"""RAG 大改造 PR2: 知识库 chunking 表 (idempotent guard)

W86 第 1 批 PR2 派工:
- 新表: rag_chunks (id / knowledge_id / parent_chunk_id / chunk_index / content / token_count /
                    embedding vector(384) / created_at)
- 索引: GIN trgm on content (回退 LIKE 搜索) + btree on knowledge_id
- 约束: parent_chunk_id FK → rag_chunks.id (ON DELETE CASCADE, 孤儿巡检见段 4)

派工前提铁律 12 第 11 条 (W68 第 11 批 alembic rebase 纪律):
- down_revision 必须接最新 head (派工前实查 `alembic heads`)
- 部署前必跑 alembic chain verify, 必须 1 head
- idempotent guard: DO $$ ... IF NOT EXISTS 防止 hot-fix 重跑副作用

派工前提铁律 12 第 5 条: 实施前必先 information_schema 实查表名 + 列类型
派工前提铁律 12 第 9 条: 0 production code 例外必含派工批文 (主拍决策已批 PR2)
"""
from alembic import op
import sqlalchemy as sa


revision = "088_rag_chunks"
down_revision = "086_backfill_drive_file_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. 创建 rag_chunks 表 (idempotent guard)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = 'rag_chunks'
            ) THEN
                CREATE TABLE rag_chunks (
                    id BIGSERIAL PRIMARY KEY,
                    knowledge_id INTEGER NOT NULL REFERENCES knowledge(id) ON DELETE CASCADE,
                    parent_chunk_id BIGINT REFERENCES rag_chunks(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER NOT NULL,
                    embedding vector(384),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT uq_rag_chunks_knowledge_chunk UNIQUE (knowledge_id, chunk_index)
                );
            END IF;
        END$$;
    """
    )
    # 2. 创建 btree 索引 on knowledge_id (idempotent guard)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_indexes WHERE indexname = 'ix_rag_chunks_knowledge_id'
            ) THEN
                CREATE INDEX ix_rag_chunks_knowledge_id ON rag_chunks (knowledge_id);
            END IF;
        END$$;
    """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_rag_chunks_knowledge_id;")
    op.execute("DROP TABLE IF EXISTS rag_chunks;")
```

### 段 3: 跨 PR 部署 cp + clear cache 步骤 (CLAUDE.md 752 行铁律升级)

```bash
# ============ Step 1: 拷贝迁移文件进容器 ============
docker cp alembic/versions/088_rag_chunks.py microbubble-agent-app-1:/app/alembic/versions/

# ============ Step 2: 清 __pycache__ (派工 v10 段 7 实战 + CLAUDE.md 752 行铁律升级) ============
# __pycache__ 残留会让老 down_revision 继续生效, 双头假修复 (W68 第 11 批实战)
docker exec -e SKIP_DB_SETUP=1 microbubble-agent-app-1 rm -rf /app/alembic/versions/__pycache__

# ============ Step 3: 验证 alembic chain (必须 1 head) ============
docker exec microbubble-agent-app-1 alembic heads
# 期望输出: 088_rag_chunks (head) (单 head, 无 multi-head 错误)

# ============ Step 4: 跑迁移 ============
docker exec microbubble-agent-app-1 alembic upgrade head

# ============ Step 5: 验证表已建 (派工前提铁律 12 第 5 条 — 实查) ============
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d rag_chunks"
# 期望: 列出全部列 + 索引, 无 UndefinedTable 错误

# ============ Step 6: 重启 Python 进程 ============
docker compose restart app celery-worker
```

### 段 4: 实施后必跑 (派工前提铁律 12 第 5 条实查 + §2.2 plans 真实施)

```bash
# 1. 验证 chunk 与 knowledge 表 FK 关系
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
SELECT conname, conrelid::regclass, confrelid::regclass
FROM pg_constraint
WHERE conname LIKE '%rag_chunks%' AND contype = 'f';
"

# 2. 验证 embedding 列类型 (vector(384), pgvector 扩展必须已装)
docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "
SELECT column_name, data_type, udt_name
FROM information_schema.columns
WHERE table_name = 'rag_chunks' AND column_name = 'embedding';
"

# 3. 验证单 head 守恒
docker exec microbubble-agent-app-1 alembic heads
# 期望: 088_rag_chunks (head) 单行
```

### 段 5: 派工 brief 据实上报铁律 (W83 C-1 + W84 C-2 实战)

派工 brief 描述**必须**与实际工作内容一致:
- 派工 brief 写"创建 GIN trgm 索引" → 实际必须创建 GIN trgm (而非 GIN btree)
- 派工 brief 写"chunking 服务" → 实际必须含 chunking 服务 (而不仅是表)
- **不擅自扩** (例: 派工 brief 不含 embedding 列 → 实际不加)
- **不擅自缩** (例: 派工 brief 含 chunking 服务 → 实际不能仅创建表)

类 20.13 实战 19 (W85 D-2 据实上报): 锚点范式 +6 不凑 +7 — 实际 +2/+1 守恒预测, 不虚报 +3 凑"7 守恒"。

### 段 6: 与 PR1/3/5/8 接续关系

| PR | 依赖本 PR | 共享 alembic head |
|----|----------|------------------|
| PR1 (embedding 一致性) | 否 (无新表) | 087 (W85 hot-fix base) |
| PR2 (chunking + 表) | 否 (PR1 已合并, 新表 rag_chunks) | **088** |
| PR3 (GIN tsvector + pg_trgm) | **是 (依赖 PR2 的 rag_chunks 表)** | **089** (接 088) |
| PR5 (RAGEvaluator + rag_eval_report) | 否 (新表独立) | **090** (可与 089 并行, 接 088) |
| PR8 (rag_search_logs) | 否 (新表独立) | **091** (可与 089/090 并行, 接 090) |

**串单链纪律 (派工前提铁律 12 第 11 条)**:
1. PR3 必须等 PR2 合并后开工 (down_revision = "088_rag_chunks")
2. PR5 / PR8 可与 PR3 并行开工 (down_revision = "088_rag_chunks", PR3 合并后主指挥改 PR5/PR8 down_revision = "089_rag_fts")
3. **严禁** PR2/3/5/8 四个 agent 并行声明 down_revision = "087_*" → 必双头

---

## 5 件套验证 (派工 v4 铁律 3 实战)

| 验证项 | 命令 | 期望 |
|--------|------|------|
| 1. alembic 1 head | `docker exec microbubble-agent-app-1 alembic heads` | 1 行, 单 head |
| 2. 表已建 | `docker exec microbubble-agent-postgres-1 psql -U postgres -d microbubble -c "\d rag_chunks"` | 列出全部列 + 索引 |
| 3. FK 约束存在 | 段 4 第 1 步 | 至少 1 行 (FK → knowledge.id) |
| 4. embedding 列类型 | 段 4 第 2 步 | udt_name = `vector` |
| 5. 老路径 e2e PASS | `pytest tests/test_knowledge_e2e.py -v` | 全部 PASS, 无 regression |

---

## 据实上报铁律 (派工 v10 段 7 19 类实战 + W83/W84/W85 类 20 实战)

1. **派工 brief 与实测不符时, 必须据实上报** — 不擅自扩, 不擅自缩
2. **0 hit / 0 改动时不实施** — 例: W85 B-2 useTask 0 hit (派工 brief 假设有 useTask 钩子, 实测 0), 据实上报"0 hit 不实施"
3. **锚点范式不凑 +7** — 实测 +1/+2/+6 据实写, 不虚报凑 "W86 mini-N 7 守恒"
4. **production code 例外清单必含派工批文** — 派工前提铁律 12 第 9 条
5. **历史锚点永久保留** — 任何 alembic chain 错配教训 (W74 B-1 084 P1 / W82 B-2 Survey 错配 / W83 C-1 派工偏差) 必入 memory

---

## 引用章节 (CLAUDE.md 永久锚点)

- `## 0 production code 改动铁律` — W67 第 41 步 + W68 第 6+7+8 批增补
- `## 2026-07-24 alembic 并行 agent 串单链纪律 (commit 1852468a6)` — 5 条铁律
- `## W68 第 6+7 批纪律沉淀 (永久锚点)` §2.3 alembic 串单链纪律
- `## W68 第 11 批 grand closure` — alembic rebase 066/067/068/069 实战
- `## 派工前提铁律 12 + 类 20 实战 18 实例` — 段 5 据实上报铁律
- `## 派工 v10 段 7 19 类实战` — 段 0-9 派工 prompt 模板升级

---

**模板版本**: v1.0 (W86 第 1 批 PR2/3/5/8 派工预填, 2026-07-30)
**作者**: support-docs-runbook agent
**沉淀**: memory 主题 9 (W 批 grand closure + 派工纪要 + 锚点范式)