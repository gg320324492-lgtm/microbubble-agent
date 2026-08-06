# W-N 周期部署状态最终报告 F2 (2026-08-06)

> **报告人**: W-N-DEPLOY-F2 部署验证 agent
> **报告时间**: 2026-08-06
> **base HEAD**: `6d8f0226f` (W-N-FILL-REAL-N 测试回归断言修正, 12/12 PASS)
> **派工锚点**: W-N-DEPLOY-F2 +0 / +1 (本文件) / +2
> **前序报告**: `docs/deploy-status-2026-08-05.md` (W-N-DEPLOY) → `docs/deploy-status-final-2026-08-06.md` (W-N-DEPLOY-FINAL, base `b170a8ff3`) → **本报告** (F2, base `6d8f0226f`, 19 stages 收口后复验)
> **本报告与前序关系**: **新增不覆盖**. 前序 224 行报告保留原样, 本报告独立 `-f2` 后缀. 前序 stage 表锚点列全为占位 "W-N +0", 本报告 stage 表**从 `git log` 实测重建** (CLAUDE.md §1 plans 审计纪律: 禁止批量复制粘贴)

---

## 0. 8 步验证结论速览

| Step | 验证项 | 判定 | 实测 |
|------|--------|------|------|
| 1 | local main vs origin/main 一致 | ✅ PASS | `git rev-list --left-right --count` = **0 / 0** |
| 2 | 容器状态 | ⚠️ 部分 | 核心 8 服务 Up, 3 服务 Exited (详见 §3) |
| 3 | alembic 1 head | ✅ PASS | host + 容器 + DB current 三方均 `105_fix_drift` |
| 4 | 3 套件 pytest | ✅ PASS | **42 passed** in 40.75s, 0 failed |
| 5 | `/health` 200 | ✅ PASS | `{"status":"healthy"}` |
| 6 | worktree clean | ✅ PASS | 0 tracked 改动 (1 untracked 属并发 agent, 见 §3.4) |
| 7 | 本报告 6 节 | ✅ | §1–§6 |
| 8 | commit 范畴 | ✅ | 1 docs + 2 memory |

**总判定: 部署状态健康, W-N 周期 19 stages 收口可交付.**

---

## 1. W-N 周期 19 stages 完整收口总结

### 1.1 周期定义与实测规模

- **周期起点**: `14bc9246e` (2026-08-05 19:04:59, W-N-A HNSW bench 工具 cherry-pick 推 main)
- **周期终点**: `6d8f0226f` (2026-08-06, W-N-FILL-REAL-N 测试断言修正)
- **实测 commit 数**: `git rev-list --count 14bc9246e..6d8f0226f` = **92 commits** (含周期起点则 93)

> **据实纠偏 (类 20.13)**: CLAUDE.md 顶部记 "锚点范式 ~537 → ~580 据实累计 +43 commits". 本次实测周期区间为 **92 commits**, 与 "+43" 差 +49. 原因: CLAUDE.md 的 "+43" 统计的是 **W-N-FINAL 之前的子集**, 而 `14bc9246e..HEAD` 覆盖 W-N-A 至 W-N-FILL-REAL-N **全区间** (含 W-N-MIN/ANS/XX/CLEAN/GLITCH/P3-A 等并行阶段与 Phase 5 DFT 平行 agent commits). **本报告以 git 实测 92 为准, 不改 CLAUDE.md 既有记载** (派工 brief: 0 改既有 commits), 差异留主拍决策是否 reconcile.

### 1.2 19 stages 一览 (git log 实测 commit 数, 非派工 brief 估值)

| # | Stage | 实测 commits | 主题 | 收口状态 |
|---|-------|-------------|------|---------|
| 1 | **W-N-A** | 2 | HNSW 参数调优 + bench 工具 (232 行小数据 PG 默认已最优 recall@10=1.0 p95=1.06ms) | ✅ 收口, 099 迁移跳过 |
| 2 | **W-N-B** | — (并入 D 计数) | halfvec 半精度量化 3 表迁移 + HalfVector wrapper | ✅ 收口 |
| 3 | **W-N-C** | 5 | bge-m3 双后端灰度 + `embedding_model_version` 字段 | ✅ 收口, Qwen3 默认保留 |
| 4 | **W-N-D** | 18 | 多向量 + Late Chunking 服务 + 104 迁移 + hybrid_retriever 接入 | ✅ 收口 |
| 5 | **W-N-E** | 3 | 冷热分层路由 PoC (3 门禁 2/3 PASS → 整段归档) | ✅ 归档 |
| 6 | **W-N-F** | 3 | LoRA 微调起步 (5 维决策 + 4 触发条件, 当前不启动) | ✅ 决策 |
| 7 | **W-N-G+** | 8 | schema drift 修复 → `105_fix_drift` | ✅ 收口 |
| 8 | **W-N-OBS** | 2 | observability 显式失败 + 计数器 | ✅ 收口 |
| 9 | **W-N-RAG** | 4 | RAG eval set + 评测入口 | ✅ 收口 |
| 10 | **W-N-BGE** | 5 (+4 PRE +1 REAL +1 A) | bge-m3 真路径 + 1000 题真测 | ✅ 收口, 见 §5 |
| 11 | **W-N-GRAND** | 4 | 14 stages 总 grand closure runbook | ✅ 收口 |
| 12 | **W-N-FILL** | 6 (+6 IMPL +1 REAL +3 REAL-N) | late_embedding 回填探索 → 真派工 | ✅ 收口, 见 §4 |
| 13 | **W-N-P3-A** | 3 (+1 REV) | P3-A 1 表试点 (决策 (b) 暂不启动) | ✅ 决策 |
| 14 | **W-N-W72** | 3 (+2 START) | W72 派工范式链接 | ✅ 收口 |
| 15 | **W-N-GLITCH** | 4 (+2 IMPL) | glitchtip restart loop 修复 | ✅ 修复, 见 §3.3 |
| 16 | **W-N-CLEAN** | 5 (+2 FINAL +2 F) | worktree / 残留清理 | ✅ 收口 |
| 17 | **W-N-MIN / ANS / XX** | 7 / 7 / 7 | 极简版 / 锚点同步 / 联合 commit 配套 | ✅ 收口 |
| 18 | **W-N-GC / ANC / MEM / ARC** | 3 / 2 / 3 / 1 (+3 GC-FINAL +1 MEM-FINAL) | CLAUDE.md 同步 / 锚点补 / MEMORY 索引 / worktree 归档 | ✅ 收口 |
| 19 | **W-N-DEPLOY / MASTER / FINAL / REVISE** | 3 / 1 / 2 / 1 | 部署验证 / 主收口 / 终极收口 / backfill 决策修订 | ✅ 收口 (本报告为 DEPLOY-F2) |

> **计数口径**: 上表 commits 数 = `git log 14bc9246e~1..6d8f0226f` commit message 中 stage 前缀出现次数 (一条 commit 可含多个 stage 前缀, 如 4-agent 联合 commit `b170a8ff3`), **非互斥分区**, 故各行相加 > 92. 精确总数以 §1.1 的 92 为准.

### 1.3 关键交付物

- **服务层新增**: `late_chunking_service.py` / `cold_hot_router.py` / `late_embedding_backfill.py` / `embedding_service.py` 双后端扩展 (+145 行, 0 改老 API)
- **alembic 迁移**: 098 → 100 → 101 → 102 → 103 → 099 → 104 → 105 单链 (含 Phase 5 平行 agent `099_add_dft_jobs` 串单链纪律守恒)
- **决策文档 5 份**: bge-m3 / cold-hot-routing / lora-finetune / e2e-late-chunking / late-embedding-backfill-revise
- **bench / utility 脚本**: `bench_hnsw_params.py` / `bench_late_chunking.py` / `reembed_knowledge_bge_m3.py` / `check_pgvector_version.py` / `backfill_late_embedding.py`
- **类 20 沉淀**: ~60 条 (类 20.144 – 类 20.184)

---

## 2. 5 件套实测

| # | 件 | 判定 | 实测证据 |
|---|----|------|---------|
| 1 | **alembic 1 head** | ✅ PASS | host `python -m alembic heads` = `105_fix_drift (head)`; 容器 `docker exec ... alembic heads` = `105_fix_drift (head)`; 容器 `alembic current` = `105_fix_drift (head)` — **三方一致, 无 drift, 无双头** |
| 2 | **pytest 3 套件** | ✅ PASS | **42 passed, 7 warnings in 40.75s, 0 failed** (明细 §2.1) |
| 3 | **PWA build** | ⚠️ 沿用 | 沿用 W100 +75 基线. 本任务 **0 frontend 改动** (`web/src/` 未触碰), 未重跑 `npm run build` |
| 4 | **0 production code** | ✅ PASS | 本任务仅写 1 docs + 2 memory. `app/` `web/src/` `alembic/versions/` `docker-compose*` `.env` `tests/` **全 0 改动** |
| 5 | **锚点范式** | ✅ PASS | W-N-DEPLOY-F2 +0 (startup memory) / +1 (本报告 + commit) / +2 (closure memory) 据实累计 |

**5 件套 4 PASS + 1 沿用 (PWA, 0 frontend 改动).**

### 2.1 pytest 明细 (Step 4 实测)

```
SKIP_DB_SETUP=1 python -m pytest \
  tests/test_w_n_fill_impl_backfill.py \
  tests/test_w_n_g_plus_chunk_late_recall.py \
  tests/rag/test_pr7_e2e.py -q
→ 42 passed, 7 warnings in 40.75s
```

| 套件 | 用例数 | 判定 | 覆盖 |
|------|-------|------|------|
| `tests/test_w_n_fill_impl_backfill.py` | **12** | ✅ PASS | W-N-FILL late_embedding 回填 (含 Bug 2 修复后 `CAST` / `vector(1024)[]` 断言) |
| `tests/test_w_n_g_plus_chunk_late_recall.py` | **8** | ✅ PASS | W-N-G+ 5 path 召回 (`test_retrieve_runs_all_5_paths` / category filter) |
| `tests/rag/test_pr7_e2e.py` | **22** | ✅ PASS | W97 PR7 全链路 observability e2e |
| **合计** | **42** | ✅ | |

> 7 warnings 全为 **pre-existing DeprecationWarning** (Pydantic V2 class-based config / `asyncio.get_event_loop` / SwigPy `__module__` / jieba `pkg_resources` / redis `setex`), **非本周期引入**, 不阻断.

---

## 3. 容器状态 (含 glitchtip 修复)

### 3.1 核心服务 Up (8)

| 容器 | 状态 | 端口 |
|------|------|------|
| `microbubble-agent-app-1` | **Up 38 min (healthy)** | `127.0.0.1:8000->8000` |
| `microbubble-agent-db-1` | **Up 44 min (healthy)** | `5432` (internal) |
| `microbubble-agent-redis-1` | **Up 44 min (healthy)** | `6379` (internal) |
| `microbubble-agent-nginx-1` | **Up 51 min** | `80->80`, `443->443` |
| `microbubble-agent-ollama-1` | **Up 51 min (healthy)** | `127.0.0.1:11434->11434` |
| `microbubble-agent-minio-1` | **Up 51 min (healthy)** | `9000-9001->9000-9001` |
| `microbubble-agent-celery-beat-1` | **Up 51 min** | `8000` (internal) |
| `microbubble-agent-glitchtip-dev-1` | **Up 51 min** | `0.0.0.0:8001->8000` |

### 3.2 Exited 服务 (3) — 据实上报, 不擅自重启

| 容器 | 状态 | 据实分析 |
|------|------|---------|
| `microbubble-agent-celery-worker-1` | Exited **(0)** 22 min ago | 退出码 **0 = 正常 warm shutdown**. 日志尾部: `worker: Warm shutdown (MainProcess)`, 停机前最后任务 `flush_ydoc_state_task` / `process_reminders_task` **均 succeeded**. 非崩溃 |
| `microbubble-agent-celery-meeting-worker-1` | Exited **(0)** 22 min ago | 同上, 正常退出 |
| `microbubble-agent-sensevoice-1` | Exited **(127)** 51 min ago | 退出码 **127 = command not found**. 停机前日志显示 `POST /transcribe 200 OK` rtf_avg 0.010–0.066 **服务本身功能正常**, 127 发生在重启入口. **留主拍决策**, 本任务不改 compose (派工 brief 严禁) |

> **影响评估**: celery worker 停机 → 异步任务 (提醒 / 会议后处理 / collab flush) 暂停; sensevoice 停机 → ASR 不可用. **不影响本次验证的 5 件套与 `/health`**. 恢复方式: `docker compose up -d celery-worker celery-meeting-worker sensevoice` (**归主拍 / W-N-CLEAN 范畴, 本任务不执行**).

### 3.3 glitchtip 修复回顾 (W-N-GLITCH-IMPL, commit `2e6b71dbf`)

| 项 | 内容 |
|----|------|
| **故障** | `glitchtip-dev-1` restart loop, `restartCount=936`, Django `OperationalError` 连不上 db/redis |
| **根因** | 类 20.140 — 容器漏 attach 到 default network, `getent hosts db` 返回空 |
| **修法 (A 方案)** | `docker-compose.dev.yml` glitchtip service `networks` 段改 long-form 加 `aliases: [db, redis]` + 运行时 `CREATE DATABASE glitchtip` + `down` + `up` 重 attach |
| **修复后实测** | Networks=`[default]`, Aliases=`[glitchtip, db, redis]` 生效; Django migrate 成功无 OperationalError; `localhost:8001` HTTP 200 |
| **本次复验 (2026-08-06)** | `microbubble-agent-glitchtip-dev-1` **Up 51 minutes**, image `glitchtip/glitchtip:6.2.2`, 端口 `0.0.0.0:8001->8000` — **无 Restarting, 修复持续有效** ✅ |

### 3.4 环境实情据实 (类 20.13)

- **worktree cwd 空壳**: 派工 cwd `E:/microbubble-agent/.claude/worktrees/bold-mendeleev-fdc0e8` 实测为**空目录** (`ls -a` 仅 `.` `..`), git 解析回落主仓库 `E:/microbubble-agent` @ `main`. 本任务全程**绝对路径**操作主仓库.
- **并发批次共存**: `git status --short` 有 1 untracked `memory/w-n-clean-f2-startup-2026-08-06.md`, 属**并发 W-N-CLEAN-F2 agent** 产物. 本任务 **0 add / 0 改 / 0 删** (类 20.140 并发共存纪律).
- **worktree 在册 16 个**, 多个 HEAD `000000000` (prunable) + 8 个 `festive-mcclintock-*` Created 状态容器. **本任务不清理** (归 W-N-CLEAN 范畴, CLAUDE.md 类 20 E50 实战: 拒绝误判式 `rm -rf`).

---

## 4. W-N-FILL-REAL-N Bug 2 修复 + 测试 FAIL 修复详情

### 4.1 Bug 2 根因与修法 (commit `b99f300b7`)

| 项 | 内容 |
|----|------|
| **位置** | `app/services/late_embedding_backfill.py` 3 处 (line 281 / 374 / 467) |
| **症状** | W-N-FILL-REAL (`06f700be5`) 执行 **0 chunks written**, PG 报 syntax error |
| **根因** | SQL 写 `SET chunk_embedding = :chunk_emb::vector[]` — SQLAlchemy `text()` 解析 `:chunk_emb` 后, `::vector[]` 的**第 2 个 `:` 被吞**, 参数绑定与 cast 语法冲突; asyncpg 进而把单字符串误判为 sized iterable |
| **修法** | ① SQL 改 `SET chunk_embedding = CAST(:chunk_emb AS text)::vector(1024)[]` (CAST 表达式前置强制文本流, 规避冒号歧义)<br>② array 字面量格式 `{[v1,v2],[v3,v4]}` → `{"[v1,v2]","[v3,v4]"}` (PG nested array literal **必须双引号**) |
| **diff 规模** | +18 / −6 lines, 3 处统一 |
| **验证** | 容器内 asyncpg + pgvector 0.7.0 + 1024 dim 实测通过 |

### 4.2 真派工执行结果

| 阶段 | 命令 | 结果 |
|------|------|------|
| 单 chunk test | `backfill_late_embedding.py --apply` (1 chunk) | 1 updated / 0 failed, **0.16s** |
| 全表 apply | `backfill_late_embedding.py --all --apply` | **36 updated / 0 failed**, ~0.4s |
| dry-run 复验 | `backfill_late_embedding.py --all` | pending = **0** |
| **DB 直查 (本报告 2026-08-06 复验)** | `SELECT count(*), count(chunk_embedding) FROM knowledge_chunks` | **37 / 37** ✅ 0 残余 |
| 数据质量 | `array_length(chunk_embedding,1)`, `octet_length(...::text)` | 每 chunk 1 vector, 1024 维, 2053 bytes |

### 4.3 HNSW 索引 4 路径全 FAIL (派工 brief 不可达, 据实上报)

| 路径 | DDL | PG 报错 |
|------|-----|---------|
| halfvec cast | `USING hnsw ((chunk_embedding::halfvec(1024)) halfvec_cosine_ops)` | `cannot cast type vector[] to halfvec` |
| vector_cosine_ops 直接 | `USING hnsw (chunk_embedding vector_cosine_ops)` | `operator class 'vector_cosine_ops' does not accept data type vector[]` |
| GIN | `USING gin (chunk_embedding)` | `index row size 4112 exceeds maximum 2712` |
| unnest 表达式索引 | `USING hnsw ((unnest(chunk_embedding)::vector(1024)) vector_cosine_ops)` | `set-returning functions are not allowed in index expressions` |

**结论**: pgvector 0.7.0 **不支持对 `vector[]` 列建 HNSW** (仅支持 `vector`). 当前 37 chunks 走 SeqScan 召回**毫秒级** (实测 < 10ms), 不加索引. **留口**: 100k+ chunks 时改 schema (拆数组为子表) 或升 pgvector 0.8+ → **W-N-FILL-SCALE, 主拍决策**.

### 4.4 测试 FAIL 修复 (commit `6d8f0226f`)

| 项 | 内容 |
|----|------|
| **触发** | Bug 2 修复改了 SQL 字面量, 原测试断言 `assert 'vector[]' in str(executed_sql)` 与新 SQL 不匹配 → **1 FAIL** |
| **修法** | 断言更新: `'vector[]'` → `'vector(1024)[]'`, 并**新增** `assert 'CAST' in str(executed_sql)` (类 20.161 反向验证 Bug 2 修复真生效) |
| **结果** | **12/12 PASS in 0.83s** |
| **本报告复验** | `tests/test_w_n_fill_impl_backfill.py` **12 passed** ✅ 与收口记载一致 |

> **纪律标注**: 该测试断言修改由 **W-N-FILL-REAL-N 派工授权**完成 (commit `6d8f0226f`). **本次 W-N-DEPLOY-F2 派工明确严禁改 `tests/`**, 本任务仅**只读运行**验证, 0 改动.

---

## 5. W-N-BGE-A 1000 题 encoder-only 真测数据

**数据源**: `results/round11-bge-m3-encoder-1000.json` (77 行, commit `8c50c777a`)

### 5.1 模型加载实测 (真模型, 非 mock)

| 指标 | 实测值 | 派工 brief 门禁 | 判定 |
|------|--------|----------------|------|
| `is_mock` | **false** | 必须真模型 | ✅ |
| `encoder_name` | `bge_m3_real` | — | ✅ |
| device | **cuda** (RTX 5090) | GPU | ✅ |
| `vram_total_gb` | 31.84 | — | — |
| `vram_after_load_gb` | **2.115** | < 4 GB | ✅ **远低于门禁** |
| `vram_after_encode_gb` | 2.146 | — | ✅ 编码增量仅 +0.031 GB |
| `load_time_s` | 202.67 | — | 首次加载 ~3.4 min |
| `model_dim` | **1024** | 对齐 Qwen3 1024d | ✅ |
| `max_seq_length` | **8192** | — | 长文优势 |

### 5.2 1000 题编码实测

| 指标 | 实测值 |
|------|--------|
| `total_requested` / `total_loaded` | **1000 / 1000** ✅ 全量加载 |
| `batch_size` | 32 |
| 类别覆盖 | **23 类** (A/B/C/D/E/F/G/H/K/M/P/U/X/Z + member/task/meeting/project/knowledge/cross/casual/memory/extreme) |
| 延迟 (100 texts) | 30576.56 ms → **305.77 ms/doc** |
| 吞吐 | **3.27 docs/s** (batch=32) |

### 5.3 决策 5 维度

| 维度 | 数据 | 状态 |
|------|------|------|
| true_pass_rate | **null** — 未跑端到端 qa-bench runner | ⚠️ 待测 |
| chinese_academic_capability | **null** — 待 R{N+1} qa-bench 真测 | ⚠️ 待测 |
| latency (GPU) | 305.77 ms/doc 真测 | ✅ 有数 |
| VRAM | 2.115 GB 真测 | ✅ 有数 |
| maintenance_cost | 0 切换风险 (双后端已就绪), 切换开销 = 改 `EMBEDDING_BACKEND` env + restart ≈ 5 min | ✅ 有数 |

### 5.4 决策与边界 (据实, 严禁越界)

- **决策 (a): 暂不切生产, 维持 Qwen3 1024d 默认** ✅
- **明确不声称端到端 recall** — 本轮为 **encoder-only**, 派工 brief 严禁声称端到端召回提升
- **⚠️ JSON 数据自洽性问题 (本报告新发现, 据实上报)**: `results/round11-bge-m3-encoder-1000.json` 顶层 `is_mock: false` + `encoder_name: "bge_m3_real"` + 真 VRAM/latency 数据, 但**文件末尾 `note` 字段仍写 "模型下载失败, fallback mock encoder (零向量)"** — 该 note 为**修订前的陈旧残留**, 与同文件真测字段矛盾. **本任务严禁改 `results/`, 仅据实标注**, 建议主拍在后续派工中清理该 note 以免误导.

---

## 6. 未来派工留口 (5 项)

| # | 留口 | 触发条件 / 现状 | 决策归属 |
|---|------|----------------|---------|
| 1 | **W-N-FILL-SCALE** — chunk_embedding HNSW 索引 | pgvector 0.7.0 对 `vector[]` 4 路径全 FAIL (§4.3). 当前 37 chunks SeqScan < 10ms 够用. 触发: chunks 达 **100k+** → 改 schema 拆子表 **或** 升 pgvector 0.8+ | 主拍 |
| 2 | **W-N-BGE 端到端 recall 真测 + 切生产** | encoder-only 已完成 (§5). 切生产需 ① 端到端 recall > Qwen3 baseline ② 3 门禁全 PASS. 需主拍选 B 方案 (批准调整 bench 入口). 用户另一窗口 `task_7c542d3d` 决策中 | 主拍 |
| 3 | **W-N-P3-A 真启动** | 当前决策 **(b) 暂不启动**维持. 1 表试点验证 ROI **0.75 天** vs 派工 brief 估 1–2 周 | 主拍 |
| 4 | **LoRA 微调启动** | **4 触发条件全未达**: qa-bench < 96% **OR** 530+ rows **OR** 冷热 PoC 失败 **OR** 真 bench < 90%. 当前不启动 | 自动触发 |
| 5 | **冷热分层路由启用** | 数据量 **530 rows** < **100k** 阈值, 不启动. W-N-E PoC 3 门禁 2/3 PASS 已整段归档 | 自动触发 |

### 6.1 本报告新增建议留口 (非派工 brief 5 项, 据实提出供主拍决策)

| 项 | 内容 | 建议归属 |
|----|------|---------|
| a | **3 Exited 容器恢复** — celery-worker / celery-meeting-worker (退出码 0 正常停机) + sensevoice (退出码 127, 入口命令问题). 恢复 = `docker compose up -d`, sensevoice 需查 entrypoint | W-N-CLEAN / 主拍 |
| b | **`results/round11-bge-m3-encoder-1000.json` 陈旧 note 清理** (§5.4) | 后续 BGE 派工 |
| c | **锚点计数口径 reconcile** — CLAUDE.md 记 "+43 commits" vs git 实测周期区间 92 commits (§1.1) | 主拍 |

### 6.2 W19 选项 A 维持

Phase 8.5 / P3 dedup / P3 跨 tab / 7 E2E 留未来 PR, **不发起新排期**.

---

## 7. 派工 brief 严禁清单 100% 守恒实测

| 严禁项 | 实测 | 判定 |
|--------|------|------|
| 0 改 W-N-* 既有 commits (A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++/FILL-IMPL/FILL-REAL/FILL-REAL-N) | 无 rebase / amend / revert, HEAD 线性追加 | ✅ |
| 0 改 `alembic/versions/` | `git status` 0 改动 | ✅ |
| 0 改 `app/` `web/src/` | `git status` 0 改动 | ✅ |
| 0 改 `docker-compose*` | `git status` 0 改动 | ✅ |
| 0 改 `.env` | 0 改动 | ✅ |
| 0 改 `tests/` **任何**文件 | 仅**只读运行** pytest, 0 改动 | ✅ |
| 0 改 plan 文件 | 0 改动 | ✅ |
| 不覆盖前序 `docs/deploy-status-final-2026-08-06.md` | 新建 `-f2` 后缀独立文件 | ✅ |
| 不动并发 agent untracked 文件 | `memory/w-n-clean-f2-startup-2026-08-06.md` 未 add / 未改 | ✅ |
| 范畴 = 1 docs + 2 memory | 本文件 + startup + closure | ✅ |

---

## 8. 关联文件

- `memory/w-n-deploy-f2-startup-2026-08-06.md` (W-N-DEPLOY-F2 +0)
- `memory/w-n-deploy-f2-closure-2026-08-06.md` (W-N-DEPLOY-F2 +2)
- 前序: `docs/deploy-status-final-2026-08-06.md` / `docs/deploy-status-2026-08-05.md`
- 周期 runbook: `docs/w-n-grand-closure-runbook.md`
- 决策 5 份: `docs/decisions/2026-08-05-{bge-m3-decision, cold-hot-routing-poc, lora-finetune-decision, e2e-late-chunking-decision}.md` + `late-embedding-backfill-revise`
- 数据: `results/round11-bge-m3-encoder-1000.json` / `results/backfill_late_embedding_2026-08-06.json`
