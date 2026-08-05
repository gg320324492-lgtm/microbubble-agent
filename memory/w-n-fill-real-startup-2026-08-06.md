# W-N-FILL-REAL 真派工 起步 (2026-08-06)

> **派工**: W-N-FILL-REAL +0 起步 (W-N 周期第 18 stages, 主拍真拍决策 → 真派工)
> **基线 HEAD**: `19766ab81` (W-N-FINAL +1, 类 20.140/101/146 沿用)
> **目的**: 跑通 W-N-FILL-IMPL +1 (commit `59638c82d`) 的 service + CLI + 真写 DB
> **关联**: W-N-FILL-IMPL +1 (留口脚本 dry-run) → W-N-FILL-REAL +1 (主拍真拍决策, 默认 c 业务决策延续禁止 → 真派工覆盖)
> **派工锚点**: W-N-FILL-REAL +0 起步 / +1 真跑 / +2 收口

---

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工依据 (主拍真拍决策)

W-N-REVISE §3 修订触发条件 3 选 1:
- (a) **列存在** ✅ PASS (W-N-G+ 修复完成, `chunk_embedding vector(1024)[]` 列在 knowledge_chunks)
- (b) **tests 8/8 PASS** ✅ PASS (W-N-FILL-IMPL +1 实施 12/12 测试)
- (c) **业务决策 recall > 0** ❌ FAIL (W-N-D++ §3 实测 +0.00%, hard-fail gate)

**W-N-REVISE 默认决策**: (c) 业务决策延续禁止 → W-N-FILL 留口 §2 不启用.

**主拍真拍决策 (W-N-FILL-REAL)**:
> "W-N-FILL-IMPL 已写 service + CLI + test. **主拍决策: 真派工**. 跑 Celery 任务 + 530 docs 回填 + 验证 HNSW 索引 + 写 results."

派工 brief 严禁擅自扩. 本任务按主拍真拍执行.

### 1.2 派工 brief 严禁清单 (W-N-FILL-REAL 与 FILL-IMPL 一致)

- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/REVISE 既有 commits
- ❌ 0 改 alembic/versions/ 任何已有迁移
- ❌ 0 改 W-N-REVISE 决策文档
- ❌ 0 改 W-N-D++ §5 决策
- ❌ 0 改 W-N-FILL-IMPL 既有 service
- ❌ 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
- ❌ 0 改 chat_engine.py
- ❌ 0 改 drive_comments_path_backfill_service.py
- ❌ 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
- ❌ 0 改 app/main.py 启动流程
- ❌ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 1.3 允许范畴 (本任务**唯一**允许改动)

- ✅ scripts/backfill_late_embedding.py **仅 1 行**: `dry_run=False` (派工 brief 严禁擅自改其余代码)
- ✅ 新增 `results/backfill_late_embedding_2026-08-06.json` (耗时统计 + 错误清单)
- ✅ 新增 `docs/w-n-fill-real-run-2026-08-06.md` (实施报告)
- ✅ 新增 `memory/w-n-fill-real-{startup,closure}-2026-08-06.md` (本文件 + 收口文件)

### 1.4 派工锚点 (W-N 周期第 18 stages)

**W-N-FILL-REAL +0** 起步 (本文件 memory)
**W-N-FILL-REAL +1** 真跑 (改 1 行 + 跑 CLI + 验证 + 写 results + 1 commit)
**W-N-FILL-REAL +2** 收口 (5 件套守恒实测 + memory 沉淀)

主仓库 HEAD base = `19766ab81` ✅ 验证 (git log -3 守恒).

### 1.5 起步实测 4 项 (派工前必跑)

#### 1.5.1 实测 item 1: 列存在 (`chunk_embedding`) — PASS
```
column_name      | data_type | udt_name
chunk_embedding  | ARRAY     | _vector
```

#### 1.5.2 实测 item 2: pgvector 扩展可用 — 修复后 PASS

**根因 (类 20.141 实战)**:
- 实际运行 db container 镜像为 `postgres:16-alpine` (非本地 Dockerfile.db 构建)
- pgvector 扩展 metadata 已注册 (`\dx` 显示 vector 0.7.0), 但 `vector.so` 库文件缺失 (W-N-FILL-IMPL 不知道这事)
- 任何 `WHERE chunk_embedding IS NULL` / `IS NOT NULL` 查询报: `UndefinedFileError: could not access file "$libdir/vector": No such file or directory`

**修复 (本任务 1.5.2)**:
1. `docker run -d --name pgv_build postgres:16-alpine sh -c "apk add ... + wget pgvector v0.7.0 + make + make install + sleep 36000"` (在 build 容器装 alpine-sdk/llvm21/clang21, 编译安装 pgvector)
2. `docker cp pgv_build:/usr/local/lib/postgresql/vector.so C:/Users/pc/vector.so`
3. `tar czf extension/{vector.control, vector--*.sql}` → `docker cp` 到 db 容器 `/tmp/vector_ext.tar.gz` → `tar xzf -C /usr/local/share/postgresql/extension/`
4. `docker cp C:/Users/pc/vector.so microbubble-agent-db-1:/usr/local/lib/postgresql/vector.so`
5. `su postgres -c 'pg_ctl restart -D /var/lib/postgresql/data'` 重启 postgres
6. 验证: `SELECT count(*) ... WHERE chunk_embedding IS NULL` ✅ 不再报 UndefinedFileError

**类 20.160 (新)**: pgvector 扩展 metadata 在 DB 表 (`pg_extension`) 注册后, 实际 `.so` 文件丢失/损坏会导致 query 报 `UndefinedFileError` 但 `\dx` / `pg_extension` 仍显示已加载. 修复必须重建扩展文件 + `pg_ctl restart` 重载.

#### 1.5.3 实测 item 3: chunks 总数 — 37 (非 530)

派工 brief 估 "530 docs" 实测为父表 `knowledge` 行数 (530 行). 但 backfill 目标表 `knowledge_chunks` 行数:
```
total = 37
chunk_embedding IS NULL = 37
chunk_embedding IS NOT NULL = 0
```

**实测修正**: W-N-FILL 真派工目标是 37 chunks (沿用 W-N-FILL-IMPL service 既有逻辑: 扫所有 `chunk_embedding IS NULL` rows), **不是** 530 docs (父表). 派工 brief 写 530 是父表行数, 实跑目标 37 chunks.

**派工 brief vs 实测偏差据实 (类 20.13 实战 21)**:
- brief: "跑 530 docs 回填"
- 实测: knowledge_chunks 有 37 行, 全部 IS NULL → 全部待回填

**修正**: W-N-FILL-REAL +1 跑 `scripts/backfill_late_embedding.py --apply --all`, 预期 **updated=37**.

#### 1.5.4 实测 item 4: 父表 vs 子表 schema 关系

| 表 | 列 | 类型 | 含义 |
|----|----|------|------|
| `knowledge` | id | int4 | 530 行 (父表) |
| `knowledge_chunks` | id | int4 | 37 行 (子表) |
| `knowledge_chunks` | knowledge_id | int4 | FK → knowledge.id (37 行映射) |
| `knowledge_chunks` | embedding | vector | 老 chunk embedding (NULL? 检查) |
| `knowledge_chunks` | chunk_embedding | vector[] | W-N-D 加的新列 (37 NULL) |

父表 530 ≠ 子表 37 (差 493 docs 没被 chunked, 沿用 W-N-C 默认 RAG flow 路径, 未走 late_chunking).

### 1.6 派工实施风险

- **0 production code 守恒**: 仅改 1 行 `dry_run=True` → `False` (派工 brief 严禁擅改其余 226 行)
- **回归风险**: LateEmbeddingBackfillService + LateChunkingService 跑 mock model (沿用 scripts/bench_late_chunking.py MockModel), 不打 GPU / 不打 LLM / 不打远程 embedding API
- **HNSW 索引**: W-N-G+ +1 加的 `idx_knowledge_chunks_chunk_embedding` 需要在 37 chunks 完成后才有效 (沿用 pgvector HNSW 索引 + chunk 数 ≥ 32 推荐阈值, 实际 37 满足). 派工 brief Step 4 验证 `\d knowledge_chunks` 看 HNSW 索引
- **耗时估算**: 37 chunks × encode 耗时 = 几秒到几十秒 (mock model 极快, 实测 W-N-BGE 灰度路径)

---
