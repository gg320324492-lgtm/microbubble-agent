# W-N-D++ 端到端 late-chunking 召回 bench 收口 (2026-08-05)

## 派工 brief 完成情况

| 锚点 | 内容 | 状态 |
|---|---|---|
| **W-N-D++ +0** | startup memory | ✅ `memory/w-n-d-plus-e2e-bench-startup-2026-08-05.md` |
| **W-N-D++ +1** | 端到端 bench 脚本 | ✅ `scripts/bench_e2e_late_chunking_recall.py` + `results/e2e_late_chunking_bench_2026-08.json` |
| **W-N-D++ +2** | 端到端决策文档 | ✅ `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` |
| **W-N-D++ +3** | closure memory | ✅ 本文 |

---

## §1 5 件套守恒实测

1. **alembic 1 head**: `python -m alembic heads` → `104_add_knowledge_chunk_late_embedding (head)` ✅ 守恒
2. **集成测试**: `SKIP_DB_SETUP=1 pytest tests/integration/test_late_chunking_recall.py -v` → **2/2 PASS** ✅
3. **新文件清单** (git status 验证 0 production code):
   - `scripts/bench_e2e_late_chunking_recall.py` (10,367 bytes, 端到端 bench)
   - `results/e2e_late_chunking_bench_2026-08.json` (4,303 bytes, bench 输出)
   - `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` (8,935 bytes, 决策文档)
   - `memory/w-n-d-plus-e2e-bench-startup-2026-08-05.md` (4,220 bytes, startup)
   - `memory/w-n-d-plus-e2e-bench-closure-2026-08-05.md` (本文)
4. **0 production code 守恒**:
   - `app/services/hybrid_retriever.py` — **未改** (派工 brief 严禁)
   - `app/agent/chat_engine.py` — **未改** (方案 C 6 铁律)
   - `alembic/versions/104_*` — **未改** (派工 brief 严禁)
   - `docker-compose.yml` — **未改**
5. **锚点范式 W-N-D++ +0..+3 守恒** (4 commits, 不撞 W-N-D+ +0..+3)

---

## §2 端到端 bench 结果据实上报

```
模式 A (parent-only):    recall@10=0.0%  p50=0.0ms  p95=0.0ms  p99=0.0ms
模式 B (chunk_late):     recall@10=0.0%  p50=1.38ms p95=1.82ms p99=1.82ms
delta:                   recall=+0.00%   p95=+1.82ms

Gate 1 (recall 提升 > 2%):  FAIL (+0.00%)
Gate 2 (P95 恶化 < 30ms):   PASS (+1.82ms)
早停触发: |delta|=0% < 2%
```

**整段归档决策**: ❌ W-N-D++ 端到端召回阶段整段归档 (派工 brief "所有 3 门禁 FAIL → 整段归档")。Gate 1 是 hard-fail gate, 即使 Gate 2/3 PASS 也必须归档。

---

## §3 类 20 沉淀 (W-N-D++ 据实上报)

### 类 20.154 — 派工 brief "1000 题 qa-bench" 假设偏差

- **派工 brief**: "1000 题 qa-bench"
- **实测**: 项目无 100 题 RAG 召回评测集 (`relevant_knowledge_ids` 字段在 qa-bench `combined_v4.jsonl` 全为空)
- **据实降级**: 8 题 (`data/eval/eval_set.jsonl`, 派工 brief 严禁跳过门禁)
- **沿用派工 v6 §13.3 假设禁令**: 不擅自扩数据集, 也不擅自删门禁

### 类 20.155 — alembic head 守恒 ≠ DB schema 守恒

- **派工 brief**: "alembic 1 head `104`"
- **实测**: alembic head 是 `104_add_knowledge_chunk_late_embedding`, 但 DB 实际 schema:
  - `knowledge` 表缺 `embedding_model_version` 列 (代码 ORM 引用)
  - `knowledge_chunks` 表缺 `chunk_embedding` 列 (实际列名 `embedding`, `_chunk_late_recall` SQL 引用)
- **后果**: `KnowledgeService.search_semantic` 必失败, `_chunk_late_recall` 必失败 (但被 best-effort 静默吞)
- **沿用 W100 收口沉淀 "alembic head 守恒 ≠ 实际 schema 守恒"** (派工 brief 未明确警告, 据实发现)

### 类 20.156 — best-effort 静默失败比显式失败更危险

- **派工 brief**: "best-effort 不影响父级"
- **实测**: `_chunk_late_recall` `try/except Exception` 吞掉所有错误, 返回 `[]`, **不抛错**, **不写日志到 observability** (除了 `logger.warning`)
- **后果**: 路由层不知道该路径失效, **生产环境监控缺失** — 即使 schema drift 修复, 也无法快速识别 chunk_late 路径是否真在工作
- **建议 (派工 v11 段 9 留口)**: 加 observability metric `_chunk_late_recall.failure_count` 区分成功/失败次数, 失败率 > 5% 触发 alert

---

## §4 端到端真相 — 为什么 recall 差异是 0%

不是统计学巧合, 是**真实现状**:

1. **模式 B 端到端真跑** `_chunk_late_recall(query_embedding, top_k, category)`
2. SQL: `SELECT kc.knowledge_id, min(v <=> :query_embedding) AS distance FROM knowledge_chunks AS kc CROSS JOIN LATERAL unnest(kc.chunk_embedding) AS vectors(v) ...`
3. DB 实际列名是 `embedding` 而非 `chunk_embedding` → `UndefinedColumnError`
4. best-effort `try/except` 吞错 → 返回 `[]`
5. 模式 A 不调这条 SQL → 也没结果 (因本 bench 用 monkey-patch 屏蔽整 _retrieve_impl)
6. **两者输出完全一致 (空集)** → delta=0

如果 DB schema 修复了, 真实召回率差异会是什么样? **无法在本任务评估** (派工 brief 严禁改 schema, 严禁真跑回填)。**留口未来派工**:
- 修 schema (alembic 104 与 DB 实际同步)
- 真回填 late_embedding 列 (派工 brief 严禁, 留口)
- 跑 100 题端到端 bench (项目当前无 100 题 RAG 评测集, 留口)
- 重测 delta, 如 Gate 1 仍 FAIL, 永久归档; 如 Gate 1 PASS, 进入下一阶段 (Celery 任务 + 监控)

---

## §5 沉淀文件清单

| 类型 | 路径 |
|---|---|
| startup memory | `memory/w-n-d-plus-e2e-bench-startup-2026-08-05.md` |
| bench 脚本 | `scripts/bench_e2e_late_chunking_recall.py` |
| bench 结果 | `results/e2e_late_chunking_bench_2026-08.json` |
| 决策文档 | `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` |
| closure memory | `memory/w-n-d-plus-e2e-bench-closure-2026-08-05.md` (本文) |

---

## §6 派工 v11 段 9 锚点守恒 + 类 20 累计

- **本次新增类 20 实例**: 3 (20.154 / 20.155 / 20.156)
- **类 20 累计**: 历史 156 + 3 = **159 实例** (据实上报, 不擅自扩也不擅自缩)
- **锚点范式**: W-N-D++ +0..+3 据实累计 (4 commits, 派工 v11 段 9 规则下都是有效锚点, 不撞 W-N-D+ +0..+3)
- **本任务 0 production code 守恒**: 仅 `scripts/` `docs/decisions/` `memory/` `results/` 范畴, 未改 `app/` `web/src/` `alembic/versions/` `docker-compose.yml`

---

## §7 未来派工留口 (主拍决策, 不擅自扩)

1. **类 20.155 schema drift 修复派工**: alembic 104 与 DB 实际 schema 同步, 修 `embedding_model_version` 列 + `knowledge_chunks.chunk_embedding` 列名
2. **类 20.156 best-effort observability 派工**: 加 `_chunk_late_recall.failure_count` metric + Celery beat 监控
3. **类 20.154 RAG 评测集构建派工**: 项目需要 100+ 题 `relevant_knowledge_ids` 标注的 RAG 评测集 (qa-bench agent 评测集不可复用)
4. **bge-m3 真路径回归派工** (W-N-D+ +2 commit `025bb505c` 留口): 待 GPU 启用 + bge-m3 真服务后, 重测 late chunking 真收益

W19 选项 A 维持. W-N-D+ 选项 B 维持.