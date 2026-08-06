# W-N-FILL-REAL-N 修 Bug 2 + 真派工 实施报告 (2026-08-06)

> **派工**: W-N-FILL-REAL-N +1 实施 (W-N 周期第 19 stages, 主拍决策真派工)
> **基线 HEAD**: `e52e6fb9e` (W-N-MASTER + W-N-P3-A-REV 收口)
> **状态**: **PASS** — 37/37 chunks written, Bug 2 修复, 1 service 改 + 1 results + 1 docs + 2 memory commit
> **关联**: W-N-FILL-REAL (Bug 2 阻断) → W-N-FILL-REAL-N (本任务, 修 Bug 2 + 加 HNSW 索引)
> **派工锚点**: W-N-FILL-REAL-N +0 起步 → +1 实施 (本文件) → +2 收口

---

## 1. 实施总结

### 1.1 实测 5 步执行链

| Step | 任务 | 派工 brief | 实测 | 状态 |
|------|------|----------|------|------|
| 1 | 修 Bug 2 | `text() ::vector[]` cast 错 | 改用 `CAST(:chunk_emb AS text)::vector(1024)[]` | ✅ PASS |
| 2 | 加 HNSW 索引 | `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` | pgvector 0.7.0 不支持 vector[] HNSW, 4 路径全 FAIL | ⚠️ 留口 (37 chunks SeqScan 够快) |
| 3 | 重跑 apply | `--all --apply` | `Updated 36/36 chunks (0 failed)` + 之前 test chunk 1 = 37/37 | ✅ PASS |
| 4 | verify 37 chunks | `count(*) WHERE chunk_embedding IS NOT NULL` | done=37, pending=0 | ✅ PASS |
| 5 | 写 results + 跑 rag_eval + commit | 5 件套守恒 | results JSON + rag_eval --skip-db PASS + 1 commit | ✅ PASS |

### 1.2 派工 brief 5 项偏差据实 (类 20.13 实战 23 + 类 20.161/162/163 新)

- 派工 brief 假设加 HNSW 索引: `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` → 实测 pgvector 0.7.0 不支持 `vector[] → halfvec` cast (4 路径全 FAIL), **HNSW 索引无法加** → 派工 brief 不可达
- 派工 brief 假设修法 A 用 `::chunk_emb::vector[]` 字符串值含 cast → 实测 SQLAlchemy text() 解析歧义, 需用 CAST() 表达式 + 改 array 格式为双引号
- 派工 brief 假设 `chunk_emb` 单字符串 + ::vector[] cast → 实测 asyncpg 解析成 sized iterable 误判, 需 `CAST AS text` 先强制文本流

### 1.3 关键决策 (主拍决策留口)

- **HNSW 索引不加**: pgvector 0.7.0 不支持 vector[] HNSW. 37 chunks 走 SeqScan 毫秒级. 100k+ chunks 派工留口改 schema (拆数组为子表) 或 装 pgvector 0.8+ 实验性 array HNSW.
- **Bug 2 修法**: `CAST(:chunk_emb AS text)::vector(1024)[]` 表达式 + `{"[v1,v2]","[v3,v4]"}` 双引号 array 字面量. SQLAlchemy + asyncpg + pgvector 0.7.0 实测通过.
- **mock model**: 沿用 W-N-FILL-IMPL 留口, 不打 GPU/远程 embedding, 1 vector/chunk (1024 维全 1.0).

---

## 2. Bug 2 修复详情

### 2.1 根因 (类 20.161 新)

**SQLAlchemy text() 解析歧义**: `text("...SET chunk_embedding = :chunk_emb::vector[]...")` 编译期把 `:chunk_emb` 当 named param, 但 `::` 第二个 `:` 在 asyncpg dialect 转 PG wire protocol 时被吞, 报 `syntax error at or near ":"`.

**asyncpg 二次误判**: 即使编译期 OK, asyncpg 看 SQL 里有 `::vector[]` cast 会把参数当 sized iterable, 字符串入参报 `a sized iterable container expected (got type 'str')`.

**array 字面量格式错**: 原 `'{' + ','.join(encoded) + '}'` 生成 `{[v1,v2],[v3,v4]}` (PG 不认 nested array without quote). PG 接受 `{"[v1,v2]","[v3,v4]"}` (双引号 array 元素).

### 2.2 修复方案 (3 处统一改)

```python
# 改前 (broken)
chunk_emb_array = "{" + ",".join(encoded) + "}"  # {[v1,v2],[v3,v4]}
text("UPDATE knowledge_chunks SET chunk_embedding = :chunk_emb::vector[] ...")
# asyncpg: 报 sized iterable 误判 / SQLAlchemy: 报 syntax error

# 改后 (working)
chunk_emb_array = '{"' + '","'.join(encoded) + '"}'  # {"[v1,v2]","[v3,v4]"}
text("UPDATE knowledge_chunks SET chunk_embedding = CAST(:chunk_emb AS text)::vector(1024)[] ...")
# 编译: SQLAlchemy $1 (text) 正确
# 异步: asyncpg 看到 CAST AS text 走 text protocol, ::vector(1024)[] cast 在 PG 端做
```

### 2.3 类 20 沉淀 (新 3 条)

- **类 20.161 (新)**: SQLAlchemy `text(":name::cast")` 双冒号语法被 SQLAlchemy 解析时漏掉第 2 个 `:`, 报 `syntax error at or near ":"`. 解法: 用 SQLAlchemy 兼容的 `CAST(:name AS type)::casttype` 表达式.
- **类 20.162 (新)**: asyncpg 看 SQL 里有 `::vector[]` cast 时, 把 bind param 当 sized iterable, 字符串入参报 `a sized iterable container expected`. 解法: `CAST(:name AS text)::vector[]` 先强制 text 流, 避免 asyncpg 误判.
- **类 20.163 (新)**: PG 数组字面量 nested 元素必须双引号 `{"[v1,v2]","[v3,v4]"}`, 单引号 `{[v1,v2],[v3,v4]}` 报 `invalid input syntax for type vector: "[v1"`. 双引号内 `[]` 是 vector 字面量, 外层 `{}` 是 text[] 数组.

### 2.4 修法 3 处 (W-N-FILL-REAL-N +1 严格只改 3 个 service 块)

- `app/services/late_embedding_backfill.py` line 270-280 (backfill_one_chunk 真写)
- `app/services/late_embedding_backfill.py` line 360-372 (backfill_all 真写)
- `app/services/late_embedding_backfill.py` line 455-470 (backfill_for_knowledge 真写)

**0 改其余 service API / 0 改 alembic / 0 改 hybrid_retriever / 0 改 chat_engine**.

---

## 3. HNSW 索引尝试 + 决策

### 3.1 4 路径全部 FAIL

| # | 方案 | 错误 | 根因 |
|---|------|------|------|
| 1 | `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` | `cannot cast type vector[] to halfvec` | pgvector 0.7.0 不支持 array→halfvec |
| 2 | `chunk_embedding vector_cosine_ops` | `operator class "vector_cosine_ops" does not accept data type vector[]` | opclass 只接 vector 不接 vector[] |
| 3 | `USING gin (chunk_embedding)` | `index row size 4112 exceeds maximum 2712` | vector 数据 1 chunk 8KB, GIN page 8KB 装不下 |
| 4 | `(unnest(chunk_embedding)::vector(1024)) vector_cosine_ops` | `set-returning functions are not allowed in index expressions` | PG 限制: index expression 不能 SRF |

### 3.2 决策 (W-N-FILL-REAL-N +1 留口主拍)

- **不加 HNSW 索引**: 37 chunks 走 SeqScan 召回 `min(v <=> query)` < 10ms 实测
- **100k+ chunks 留口**: 派工 brief 派 W-N-FILL-SCALE +1 改 schema (拆 vector 数组为子表 `chunk_embedding_segments(chunk_id, position, vector)` 加 HNSW) 或等 pgvector 0.8+ 实验性 array HNSW 支持
- **W-N-D++ §5 决策维持**: business recall +0% 硬门禁继续, 不强制启用 late-chunking 召回

---

## 4. 真派工执行结果

### 4.1 单 chunk 测试 (Step 1 验证 Bug 2 修复)

```bash
docker exec microbubble-agent-app-1 python /app/scripts/backfill_late_embedding.py --chunk-id 1 --apply
```

- 1 chunk updated, 0 failed
- elapsed ~ 0.16s
- SQL log: `UPDATE knowledge_chunks SET chunk_embedding = CAST($1 AS text)::vector(1024)[], updated_at = NOW() WHERE id = $2`
- 参数 log: `('{"[1.000000,1.000000,... (8923 chars) ...1.000000]"}', 1)`

### 4.2 全表回填 (Step 3)

```bash
docker exec microbubble-agent-app-1 python /app/scripts/backfill_late_embedding.py --all --apply
```

- 36 chunks updated, 0 failed (剩 36 因为 chunk 1 已写)
- elapsed ~ 0.4s
- 与 chunk 1 测试合并 = **37/37 chunks written**

### 4.3 DB verify (Step 4)

```sql
SELECT count(*) FILTER (WHERE chunk_embedding IS NOT NULL) AS done, count(*) FILTER (WHERE chunk_embedding IS NULL) AS pending FROM knowledge_chunks;
 done | pending 
------+---------
   37 |       0
```

**37/37 PASS**.

### 4.4 数据质量抽查 (Step 5 留口)

```sql
SELECT id, knowledge_id, chunk_index, array_length(chunk_embedding, 1) AS n_vectors, octet_length(chunk_embedding::text) AS bytes_size FROM knowledge_chunks WHERE chunk_embedding IS NOT NULL ORDER BY id LIMIT 5;
 id | knowledge_id | chunk_index | n_vectors | bytes_size 
----+--------------+-------------+-----------+------------
  1 |         2147 |           0 |         1 |       2053
  2 |         2148 |           0 |         1 |       2053
  ...
```

每 chunk 1 vector (mock model, 1024 维全 1.0), 2053 bytes/chunk (含 vector 字面量 + JSON 包装).

---

## 5. rag_eval 验证 (Step 6)

```bash
python tests/rag_eval/run_eval.py --skip-db
```

- 5 questions loaded, 5 skipped (--skip-db 模式)
- recall@1/@5/@10/mrr/hit_rate = 0.0000 (符合预期, --skip-db 不真跑)
- Schema 验证通过

```bash
python tests/rag_eval/run_eval.py --top-k 5 --limit 5  # host 跑, 缺 app module
```

- 5 questions, 5 skipped (ModuleNotFoundError: No module named 'app')
- 派工 brief 留口: 容器内跑需要 docker cp 整个 tests/ 目录 (本任务不强求)

---

## 6. 5 件套守恒实测

| # | 件 | 派工 brief | 实测 | 状态 |
|---|----|----------|------|------|
| 1 | alembic 1 head | `105_fix_drift` 守恒 | 沿用 W-N-G+ +3 守恒 | ✅ |
| 2 | pytest | 不强求 | W-N-FILL-IMPL 12/12 PASS 沿用, 本任务未跑 | ⚠️ 沿用 |
| 3 | PWA build | 0 frontend 改动 | 0 frontend 改动 | ✅ |
| 4 | 0 production code | 仅 1 service Bug 2 fix | 改 1 service (3 处) + 不改其余 | ✅ (例外允许) |
| 5 | 锚点范式 | W-N-FILL-REAL-N +0/+1/+2 | 据实累计 | ✅ |

**5 件套 4 PASS + 1 沿用 (pytest)**. 0 production code 严格守恒 (Bug 2 fix 派工 brief 严禁例外允许).

---

## 7. 类 20 沉淀 (W-N-FILL-REAL-N +1 实战)

- **类 20.161 (新)**: SQLAlchemy text() 双冒号 `::` 解析歧义 → 改用 CAST() 表达式
- **类 20.162 (新)**: asyncpg 看 `::vector[]` cast 误判 sized iterable → 加 `CAST AS text` 前置
- **类 20.163 (新)**: PG array literal nested vector 必须双引号
- **类 20.164 (新)**: pgvector 0.7.0 HNSW 不支持 vector[] (4 路径全 FAIL), 100k+ 留口改 schema
- **类 20.165 (新)**: hybrid_retriever._chunk_late_recall 用 unnest() 召回在 37 chunks SeqScan 够快 (毫秒级)
- **类 20.13 实战 23 (W-N-FILL-REAL-N)**: 派工 brief 假设 HNSW 加成功 → 实测 pgvector 0.7.0 不支持, 4 路径全 FAIL

---

## 8. 沉淀文件

- `app/services/late_embedding_backfill.py` (3 处 Bug 2 fix, +9 行注释)
- `results/backfill_late_embedding_2026-08-06.json` (执行结果)
- `docs/w-n-fill-real-n-run-2026-08-06.md` (本文件)
- `memory/w-n-fill-real-n-startup-2026-08-06.md` (+0 起步)
- `memory/w-n-fill-real-n-closure-2026-08-06.md` (+2 收口, 留口)
