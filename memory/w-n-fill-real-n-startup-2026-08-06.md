# W-N-FILL-REAL-N 修 Bug 2 + 真派工 起步 (2026-08-06)

> **派工**: W-N-FILL-REAL-N +0 起步 (W-N 周期第 19 stages, 主拍决策: 修 service Bug 2 + 加 HNSW 索引 + 重做真派工)
> **基线 HEAD**: `e52e6fb9e` (W-N-MASTER + W-N-P3-A-REV 收口)
> **目的**: 修 W-N-FILL-REAL commit `06f700be5` Bug 2 阻断 (`SQLAlchemy text() ::vector[]` 语法错) + 加 HNSW 索引 + 重做真派工
> **关联**: W-N-FILL-REAL (Bug 2 阻断) → W-N-FILL-REAL-N (本任务, 修 Bug 2)
> **派工锚点**: W-N-FILL-REAL-N +0 起步 / +1 修 Bug 2 + 真派工 / +2 收口

---

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工依据 (主拍决策)

W-N-FILL-REAL commit `06f700be5` (Thu Aug 6 00:58) dry-run 跑通 + apply Bug 2 阻断:
- service `app/services/late_embedding_backfill.py:275` SQL `SET chunk_embedding = :chunk_emb::vector[]`
- SQLAlchemy `text()` 把 `:` 当参数占位符, 后续 `::vector[]` 报 `syntax error at or near ":"`
- 0 chunks written 实测
- 派工 brief 留口 "W-N-FILL-REAL-N 修 Bug 2 + 加 HNSW 索引 + 重做真派工"

**W-N-REVISE §3 修订触发条件**:
- (a) 列存在 ✅ PASS (W-N-G+ 验证, `chunk_embedding vector(1024)[]`)
- (b) tests 8/8 PASS ✅ PASS (W-N-FILL-IMPL +1 实施 12/12 测试)
- (c) 业务决策 recall > 0 ❌ FAIL (W-N-D++ §3 实测 +0.00%, 维持默认禁止)

**主拍决策 (W-N-FILL-REAL-N)**: "W-N-FILL-REAL 留口明确: 修 Bug 2 + 加 HNSW 索引 + 重做真派工 + 验证 37 chunks 回填. 真派工执行. 派工 brief 严禁 0 改其余范畴."

### 1.2 派工 brief 严禁清单 (W-N-FILL-REAL-N 与 FILL-REAL 一致 + 增修 Bug 2 例外)

- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/REVISE 既有 commits
- ❌ 0 改 alembic/versions/ 任何已有迁移 (派工 brief 严禁改 alembic)
- ❌ 0 改 W-N-REVISE 决策文档
- ❌ 0 改 W-N-D++ §5 决策
- ❌ 0 改 W-N-FILL-IMPL 既有 service 之外
- ❌ 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
- ❌ 0 改 chat_engine.py
- ❌ 0 改 drive_comments_path_backfill_service.py
- ❌ 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
- ❌ 0 改 app/main.py 启动流程
- ❌ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 1.3 允许范畴 (本任务**唯一**允许改动)

- ✅ **修 `app/services/late_embedding_backfill.py:275` Bug 2** (派工 brief 严禁例外允许, Bug 2 拦截是 W-N-FILL-REAL-N 派工核心)
  - 修法: `SET chunk_embedding = :chunk_emb::vector[]` → 用 named param + cast 在 SQL 端
  - 推荐方案 A: `SET chunk_embedding = CAST(:chunk_emb AS vector[])` (PG 端 CAST 表达式)
- ✅ **加 HNSW 索引 DDL** (派工 brief 严禁改 alembic, 仅 DDL 运行时):
  - `docker exec ... psql -c "CREATE INDEX IF NOT EXISTS ..."` (HNSW on chunk_embedding::halfvec(1024))
- ✅ **新增 `results/backfill_late_embedding_2026-08-06.json`** (耗时 + 错误清单)
- ✅ **新增 `docs/w-n-fill-real-n-run-2026-08-06.md`** (实施报告)
- ✅ **新增 `memory/w-n-fill-real-n-{startup,closure}-2026-08-06.md`** (本文件 + 收口文件)

### 1.4 派工锚点 (W-N 周期第 19 stages)

**W-N-FILL-REAL-N +0** 起步 (本文件 memory)
**W-N-FILL-REAL-N +1** 修 Bug 2 + 加 HNSW 索引 + 重做真派工 (1 service fix + 1 results + 1 docs + 2 memory 范畴, 1 commit)
**W-N-FILL-REAL-N +2** 收口 (5 件套守恒实测 + memory 沉淀)

主仓库 HEAD base = `e52e6fb9e` ✅ 验证 (`git log -3` 守恒):
- `e52e6fb9e docs(memory): 6 untracked 文件 commit 推 main (W-N-MASTER + W-N-P3-A-REV 收口)`
- `06f700be5 feat(memory): W-N-FILL-REAL 真派工 dry-run 跑通, apply Bug 2 阻断据实上报`
- `9c52f94f6 docs(memory): W-N-W72-START +2 收口沉淀`

### 1.5 起步实测 4 项 (派工前必跑)

#### 1.5.1 实测 item 1: base HEAD 守恒 ✅
```
e52e6fb9e127ac842d63f34d462ccb1a79978ec1 (W-N-MASTER + W-N-P3-A-REV 收口)
```

#### 1.5.2 实测 item 2: 列存在 (`chunk_embedding vector(1024)[]`) ✅
```
                                           Table "public.knowledge_chunks"
     Column      |            Type             | Collation | Nullable |                   Default
-----------------+-----------------------------+-----------+----------+----------------------------------------------
 chunk_embedding | vector(1024)[]              |           |          |
```

#### 1.5.3 实测 item 3: pgvector 扩展可用 (沿用 W-N-FILL-REAL 修复) ✅
- 沿用 W-N-FILL-REAL +1 (类 20.160) 修复的 `vector.so` 库文件
- 实测 `SELECT count(*) FROM knowledge_chunks WHERE chunk_embedding IS NULL` ✅ 不再报 UndefinedFileError, 返回 37

#### 1.5.4 实测 item 4: HNSW 索引当前状态 ⚠️
```
Indexes:
    "knowledge_chunks_pkey" PRIMARY KEY, btree (id)
    "ix_knowledge_chunks_embedding_hnsw" hnsw (embedding vector_cosine_ops)  ← 老列 embedding HNSW
    "ix_knowledge_chunks_id" btree (id)
    ...
```

**结论**: **无** `chunk_embedding` HNSW 索引. W-N-FILL-REAL-N +1 必须 DDL 加索引 (派工 brief 严禁改 alembic).

### 1.6 派工实施风险

- **0 production code 守恒 (1 service Bug 2 例外)**: 修 1 service file (Bug 2 fix) + 加 1 HNSW 索引 DDL + 1 results JSON + 2 memory 范畴
- **回归风险**: LateEmbeddingBackfillService + LateChunkingService 跑 mock model (沿用 scripts/bench_late_chunking.py MockModel), 不打 GPU / 不打 LLM / 不打远程 embedding API
- **HNSW 索引**: 加完后 37 chunks 可走向量召回 (HNSW 索引需 chunk 数 ≥ 32 推荐, 实际 37 满足)
- **耗时估算**: 37 chunks × encode 耗时 = 几秒到几十秒 (mock model 极快, 实测 W-N-BGE 灰度路径)
- **Bug 2 修复风险**: 改 SQL `text()` 用 `CAST(:chunk_emb AS vector[])` 必须验证 PG 端接受这种 named param cast 语法 (W73 铁律: 改前实测)

---

## 2. 派工实施计划 (W-N-FILL-REAL-N +1)

### Step 1: 修 `app/services/late_embedding_backfill.py:275` Bug 2
- 改 `SET chunk_embedding = :chunk_emb::vector[]` → `SET chunk_embedding = CAST(:chunk_emb AS vector[])`
- 3 处统一修 (line 275, 364, 455 都是同一模式)
- 实测: 容器内跑单 chunk 验证 SQL 通过

### Step 2: 加 HNSW 索引 DDL (派工 brief 严禁改 alembic)
```bash
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "
CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_chunk_embedding_hnsw
  ON knowledge_chunks
  USING hnsw ((chunk_embedding::halfvec(1024)) halfvec_cosine_ops)
"
```

### Step 3: 重跑 apply
```bash
docker exec microbubble-agent-app-1 python scripts/backfill_late_embedding.py --apply --all
```

### Step 4: verify 37 chunks
```bash
docker exec microbubble-agent-db-1 psql -U postgres -d microbubble -c "
SELECT count(*) FROM knowledge_chunks WHERE chunk_embedding IS NOT NULL
"
```
预期: 37

### Step 5: 写 results JSON
- `results/backfill_late_embedding_2026-08-06.json` (耗时 + 错误清单 + 索引前后)

### Step 6: 跑 `python tests/rag_eval/run_eval.py --skip-db` 验证
- (派工 brief 不强求真跑 eval, 沿用 W-N-RAG +2 --skip-db 模式)

### Step 7: commit 1 service fix + 1 results + 1 docs + 2 memory 范畴
- 1 commit 合并上述所有改动

---

## 3. 类 20 沉淀 (W-N-FILL-REAL-N 起步阶段, 留口给 +1 实战)

(暂无新增, 留口 W-N-FILL-REAL-N +1 实战时沉淀)

---

## 4. 派工 brief vs 实测偏差据实 (类 20.13 实战留口)

| 派工 brief 假设 | 实测 | 偏差 |
|----------------|------|------|
| base HEAD = `e52e6fb9e` | ✅ `e52e6fb9e` | 0 |
| Bug 2 修法: `named param + cast` | 待 +1 验证 | 0 |
| HNSW 加 halfvec(1024) cast | 待 +1 验证 | 0 |
| 重跑 apply 写 37 chunks | 待 +1 验证 | 0 |
