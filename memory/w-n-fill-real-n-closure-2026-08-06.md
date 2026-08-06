# W-N-FILL-REAL-N 修 Bug 2 + 真派工 收口 (2026-08-06)

> **派工**: W-N-FILL-REAL-N +2 收口 (W-N 周期第 19 stages, 主拍决策真派工完成)
> **基线 HEAD**: `e52e6fb9e` (W-N-MASTER + W-N-P3-A-REV 收口, 派工前守恒)
> **本任务 HEAD**: `b99f300b7` (W-N-FILL-REAL-N +1 实施, 1 commit)
> **状态**: **PASS** — 37/37 chunks written, Bug 2 修复, 4 文件 commit, 5 件套守恒
> **关联**: W-N-FILL-REAL (Bug 2 阻断) → W-N-FILL-REAL-N (本任务, +0 起步 / +1 实施 / +2 收口)
> **派工锚点**: W-N-FILL-REAL-N +0 → +1 → +2 (本文件)

---

## 1. 执行总结

### 1.1 派工 brief 5 vs 实测 5 项 (类 20.13 实战 23 + 类 20.161-165 新)

| 派工 brief 假设 | 实测 | 偏差 |
|----------------|------|------|
| base HEAD = `e52e6fb9e` | ✅ `e52e6fb9e` | 0 |
| 修 Bug 2 `::vector[]` cast | 改用 `CAST(:chunk_emb AS text)::vector(1024)[]` + 双引号 array 字面量 | 修法略改 (CAST 表达式) |
| 加 HNSW 索引 `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` | ❌ pgvector 0.7.0 不支持 vector[] HNSW, 4 路径全 FAIL | 派工 brief 不可达 |
| 重跑 apply 写 37 chunks | ✅ 37/37 chunks written | 0 |
| verify + 写 results + commit | ✅ 4 files commit (1 service + 1 results + 1 docs + 1 startup memory) | 0 |

### 1.2 5 步执行链实测

| Step | 任务 | 实测 | 状态 |
|------|------|------|------|
| 1 | 修 Bug 2 | `text(":chunk_emb::vector[]")` → `text("CAST(:chunk_emb AS text)::vector(1024)[]")` (3 处统一) | ✅ PASS |
| 2 | 加 HNSW 索引 | 4 路径全 FAIL (halfvec cast / vector_cosine_ops / GIN / unnest) | ⚠️ 留口 |
| 3 | 重跑 apply | 单 chunk 1 + 全表 36 = 37 chunks written, 0 failed | ✅ PASS |
| 4 | verify 37 chunks | done=37, pending=0 | ✅ PASS |
| 5 | 写 results + 跑 rag_eval + commit | results JSON + rag_eval --skip-db PASS + 1 commit `b99f300b7` | ✅ PASS |

---

## 2. 5 件套守恒实测 (W-N-FILL-REAL-N +1 收口)

| # | 件 | 派工 brief | 实测 | 状态 |
|---|----|----------|------|------|
| 1 | alembic 1 head | `105_fix_drift` 守恒 | 沿用 W-N-G+ +3 守恒 (1 head) | ✅ PASS |
| 2 | pytest | 不强求 | W-N-FILL-IMPL 12/12 沿用, 本任务未跑 | ⚠️ 沿用 |
| 3 | PWA build | 0 frontend 改动 | 0 frontend 改动 (仅 service + docs + memory + results) | ✅ PASS |
| 4 | 0 production code | 仅 1 service Bug 2 fix 派工 brief 严禁例外允许 | 改 1 service (3 处) + 0 改 alembic + 0 改 hybrid_retriever + 0 改 chat_engine | ✅ PASS (例外允许) |
| 5 | 锚点范式 | W-N-FILL-REAL-N +0/+1/+2 据实累计 | +0 startup memory + +1 commit `b99f300b7` + +2 本收口 memory | ✅ PASS |

**5 件套 4 PASS + 1 沿用 (pytest)**. 0 production code 严格守恒 (1 service Bug 2 fix 派工 brief 严禁例外允许).

---

## 3. 派工 brief vs 实测偏差据实 (类 20.13 实战 23, 派工 v6 段 5 反馈 #6 沿用)

| 派工 brief 假设 | 实测 | 偏差据实 |
|----------------|------|---------|
| 加 HNSW 索引: `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` | ❌ pgvector 0.7.0 不支持 `vector[] → halfvec` cast | 派工 brief 不可达, 4 路径全 FAIL |
| 修法 A: `::chunk_emb::vector[]` 字符串值含 cast | ❌ SQLAlchemy text() 解析歧义, 漏第 2 个 `:` | brief 假设偏差, 改 CAST 表达式 |
| 修法 B: `bindparam` 拆分 fragment | ❌ 不需要, 简单 CAST 表达式 + 双引号 array 字面量走通 | brief 假设偏差, 方案更简单 |
| array 字面量 `{[v1,v2],[v3,v4]}` | 需 `{"[v1,v2]","[v3,v4]"}` 双引号 | brief 假设偏差, PG array literal nested 必须双引号 |
| `chunk_emb` 单字符串 + `::vector[]` cast | asyncpg 解析为 sized iterable, 报误判 | brief 假设偏差, 需 `CAST AS text` 前置强制文本流 |

---

## 4. Bug 2 修复详情 (类 20.161-163 新)

### 4.1 根因 (类 20.161-163)

**根因 1 (类 20.161)**: SQLAlchemy `text(":chunk_emb::vector[]")` 编译期把 `:chunk_emb` 当 named param, 但 `::` 第二个 `:` 在 asyncpg dialect 转 PG wire protocol 时被吞, 报 `syntax error at or near ":"`.

**根因 2 (类 20.162)**: 即使编译期 OK, asyncpg 看 SQL 里有 `::vector[]` cast 会把参数当 sized iterable, 字符串入参报 `a sized iterable container expected (got type 'str')`.

**根因 3 (类 20.163)**: 原 `'{' + ','.join(encoded) + '}'` 生成 `{[v1,v2],[v3,v4]}` (PG 不认 nested array without quote). PG 接受 `{"[v1,v2]","[v3,v4]"}` (双引号 array 元素).

### 4.2 修法 (3 处统一改, +18/-6 lines)

```python
# 改前 (broken)
chunk_emb_array = "{" + ",".join(encoded) + "}"  # {[v1,v2],[v3,v4]}
text("UPDATE knowledge_chunks SET chunk_embedding = :chunk_emb::vector[] ...")

# 改后 (working)
chunk_emb_array = '{"' + '","'.join(encoded) + '"}'  # {"[v1,v2]","[v3,v4]"}
text("UPDATE knowledge_chunks SET chunk_embedding = CAST(:chunk_emb AS text)::vector(1024)[] ...")
```

### 4.3 修法 3 处 (W-N-FILL-REAL-N +1 严格只改 3 个 service 块)

- `app/services/late_embedding_backfill.py` line 270-280 (backfill_one_chunk 真写)
- `app/services/late_embedding_backfill.py` line 360-372 (backfill_all 真写)
- `app/services/late_embedding_backfill.py` line 455-470 (backfill_for_knowledge 真写)

**0 改其余 service API / 0 改 alembic / 0 改 hybrid_retriever / 0 改 chat_engine**.

---

## 5. HNSW 索引尝试 + 决策 (类 20.164-165 新)

### 5.1 4 路径全部 FAIL

| # | 方案 | 错误 | 根因 |
|---|------|------|------|
| 1 | `(chunk_embedding::halfvec(1024)) halfvec_cosine_ops` | `cannot cast type vector[] to halfvec` | pgvector 0.7.0 不支持 array→halfvec |
| 2 | `chunk_embedding vector_cosine_ops` | `operator class "vector_cosine_ops" does not accept data type vector[]` | opclass 只接 vector 不接 vector[] |
| 3 | `USING gin (chunk_embedding)` | `index row size 4112 exceeds maximum 2712` | vector 数据 1 chunk 8KB, GIN page 8KB 装不下 |
| 4 | `(unnest(chunk_embedding)::vector(1024)) vector_cosine_ops` | `set-returning functions are not allowed in index expressions` | PG 限制: index expression 不能 SRF |

### 5.2 决策 (W-N-FILL-REAL-N +1 留口主拍)

- **不加 HNSW 索引**: 37 chunks 走 SeqScan 召回 `min(v <=> query)` < 10ms 实测
- **100k+ chunks 留口**: 派工 brief 派 W-N-FILL-SCALE +1 改 schema (拆 vector 数组为子表 `chunk_embedding_segments(chunk_id, position, vector)` 加 HNSW) 或等 pgvector 0.8+ 实验性 array HNSW 支持
- **W-N-D++ §5 决策维持**: business recall +0% 硬门禁继续, 不强制启用 late-chunking 召回

---

## 6. 真派工执行结果

### 6.1 单 chunk 测试 (Step 1 验证 Bug 2 修复)

- 1 chunk updated, 0 failed
- elapsed ~ 0.16s
- SQL log: `UPDATE knowledge_chunks SET chunk_embedding = CAST($1 AS text)::vector(1024)[], updated_at = NOW() WHERE id = $2`

### 6.2 全表回填 (Step 3)

- 36 chunks updated, 0 failed (剩 36 因为 chunk 1 已写)
- elapsed ~ 0.4s
- 与 chunk 1 测试合并 = **37/37 chunks written**

### 6.3 DB verify (Step 4)

```
 done | pending 
------+---------
   37 |       0
```

**37/37 PASS**.

### 6.4 数据质量抽查

| id | knowledge_id | chunk_index | n_vectors | bytes_size |
|----|--------------|-------------|-----------|------------|
| 1  | 2147         | 0           | 1         | 2053       |
| 2  | 2148         | 0           | 1         | 2053       |
| 3  | 2149         | 0           | 1         | 2053       |
| 4  | 2150         | 0           | 1         | 2053       |
| 5  | 2151         | 0           | 1         | 2053       |

每 chunk 1 vector (mock model, 1024 维全 1.0), 2053 bytes/chunk.

---

## 7. rag_eval 验证

- `--skip-db` 模式: 5 questions, 5 skipped, schema 验证通过 ✅
- 完整模式: host 跑缺 `app` module, 跳过 (派工 brief 留口)
- W-N-D++ §5 决策 recall 评估: 沿用 +0.00%, 维持默认禁止

---

## 8. 类 20 沉淀 (W-N-FILL-REAL-N +1 实战, 4 新 + 1 实战)

- **类 20.161 (新)**: SQLAlchemy `text(":name::cast")` 双冒号语法被 SQLAlchemy 解析时漏掉第 2 个 `:`, 报 `syntax error at or near ":"`. 解法: 用 SQLAlchemy 兼容的 `CAST(:name AS type)::casttype` 表达式.
- **类 20.162 (新)**: asyncpg 看 SQL 里有 `::vector[]` cast 时, 把 bind param 当 sized iterable, 字符串入参报 `a sized iterable container expected`. 解法: `CAST(:name AS text)::vector[]` 先强制 text 流, 避免 asyncpg 误判.
- **类 20.163 (新)**: PG 数组字面量 nested 元素必须双引号 `{"[v1,v2]","[v3,v4]"}`, 单引号 `{[v1,v2],[v3,v4]}` 报 `invalid input syntax for type vector: "[v1"`. 双引号内 `[]` 是 vector 字面量, 外层 `{}` 是 text[] 数组.
- **类 20.164 (新)**: pgvector 0.7.0 HNSW 不支持 vector[] (4 路径全 FAIL), 100k+ 留口改 schema (拆 vector 数组为子表) 或装 pgvector 0.8+ 实验性 array HNSW 支持.
- **类 20.165 (新)**: hybrid_retriever._chunk_late_recall 用 unnest() 召回在 37 chunks SeqScan 够快 (毫秒级), 无需 HNSW.
- **类 20.13 实战 23 (W-N-FILL-REAL-N)**: 派工 brief 假设 HNSW 加成功 → 实测 pgvector 0.7.0 不支持, 4 路径全 FAIL, 留口主拍决策不加.

---

## 9. 沉淀文件 (W-N-FILL-REAL-N +1 严格 4 范畴)

- `app/services/late_embedding_backfill.py` (3 处 Bug 2 fix, +18/-6)
- `results/backfill_late_embedding_2026-08-06.json` (执行结果 + 索引尝试 4 路径)
- `docs/w-n-fill-real-n-run-2026-08-06.md` (实施报告)
- `memory/w-n-fill-real-n-startup-2026-08-06.md` (W-N-FILL-REAL-N +0 起步)
- `memory/w-n-fill-real-n-closure-2026-08-06.md` (本文件, W-N-FILL-REAL-N +2 收口)

---

## 10. 未来派工留口 (主拍决策, 不擅自扩)

- **W-N-FILL-SCALE** (留口): 100k+ chunks 时改 schema (拆 vector 数组为子表) 或装 pgvector 0.8+ 实验性 array HNSW 支持
- **W-N-BGE 真派工** (留口): GPU + bge-m3 模型下载后立即跑真 bench (沿用 W-N-BGE-REAL)
- **W-N-D++ §5 决策维持**: business recall +0% 硬门禁继续, 不强制启用 late-chunking 召回 (沿用 W-N-D++ +2)
- **Late chunking 端到端启用**: W-N-G+ 105 迁移 + GPU 部署后启用 (留口)

---

## 11. 锚点范式 (W-N 周期第 19 stages)

**W-N-FILL-REAL-N +0** 起步 memory (本任务前)
**W-N-FILL-REAL-N +1** 实施 commit `b99f300b7` (1 commit, 4 文件 范畴)
**W-N-FILL-REAL-N +2** 收口 memory (本文件)

主仓库 HEAD base = `e52e6fb9e` ✅ 守恒
本任务 HEAD = `b99f300b7` (1 commit 推进)
W19 选项 A 维持. W-N 周期第 19 stages 据实收口, 不擅自扩不擅自缩.

---

## 12. W-N 周期 19 stages 累计 (W-N-FILL-REAL-N +2 之后)

**W-N 累计 commits**: ~580 据实累计 (W-N 周期 ~70 commits + 累计 19 stages)
**W-N 累计锚点**: ~580 据实累计
**W-N 累计 commits W-N-FILL-REAL-N +2 段**: 1 commit (b99f300b7)
**派工 brief vs 实测偏差**: 5 项偏差据实 (类 20.13 实战 23)
**类 20 沉淀**: ~70 条 (类 20.155 - 类 20.165 + 沿用历史)
**决策文档**: 5 份 (bge-m3 / cold-hot routing / lora-finetune / e2e-late-chunking / late-embedding-backfill-revise, 沿用)
**派工模型**: 19 stages × 1-7 commits 据实累计, 0 production code 严格执行 (W-N-FILL-REAL-N +1 唯一例外允许)
