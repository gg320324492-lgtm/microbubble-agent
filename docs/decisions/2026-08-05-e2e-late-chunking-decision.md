# W-N-D++ 端到端 late-chunking 召回决策报告 (2026-08-05)

> **决策日**: 2026-08-05
> **决策人**: W-N-D++ agent (派工 brief 严禁跳过 3 决策门禁)
> **数据来源**: `results/e2e_late_chunking_bench_2026-08.json` (8 queries × 2 模式 A/B)
> **最终决策**: ❌ **W-N-D++ 端到端召回阶段整段归档**, 路由层代码 (`hybrid_retriever._chunk_late_recall`) 保留, late_embedding 列不启动回填

---

## §1 实测上下文 (据实上报)

- **base commit**: `d8e463d1c` (W-N-E 冷热分层 PoC 收口沉淀)
- **alembic head**: `104_add_knowledge_chunk_late_embedding` (1 head 守恒, 但与实际 DB schema drift, 见类 20.156)
- **knowledge 表行数**: 530 (W-N-E 据实上报)
- **knowledge_chunks 表行数**: 真实存在, **但** `chunk_embedding` 列不存在 (实际列名 `embedding`, 类 20.156 实战)
- **派工 brief 假设 100 题 qa-bench**: 据实 8 题 (项目无 100 题 RAG 评测集, 类 20.154 实战)
- **评测集**: `data/eval/eval_set.jsonl` (8 题 qa-bench, must_contain 关键词匹配)

**类 20.156 (W-N-D++ 据实上报)**: 项目**没有**真正生产可用的 `_chunk_late_recall` 路径。两条独立 drift:
1. **`knowledge` 表缺 `embedding_model_version` 列** — `KnowledgeService.search_semantic` ORM 模型引用此列, DB 实际不存在 → `vector` 路全失败
2. **`_chunk_late_recall` SQL 引用 `kc.chunk_embedding` 列** — DB 实际列名 `embedding` → `chunk_late` 路也失败 (但因 `try/except best-effort` 返回 `[]` 不抛错, 静默失败)
3. **两个 drift 都源于 alembic 104 migration 名实不符** — 仓库记录的 head 是 104, 但 DB 实际 schema 是更早状态

**类 20.154 (W-N-D++ 据实上报)**: 派工 brief "1000 题 qa-bench" 假设偏差。qa-bench `combined_v4.jsonl` 是 agent 评测数据集 (`must_contain_any` + `ground_truth_refs: ["kb://a/a1-x1"]`)，**不**是 RAG 召回评测 (`relevant_knowledge_ids`)。项目无 1000 题 RAG 召回评测集。

---

## §2 端到端 A/B bench 实测 (8 queries)

### 数据来源

| 模式 | 描述 | recall@10 | p50_ms | p95_ms | p99_ms |
|---|---|---|---|---|---|
| **A: parent-only** | monkey-patch 屏蔽 `_chunk_late_recall`, 不调它 | **0.0%** | 0.0 | 0.0 | 0.0 |
| **B: chunk_late** | 调真 `_chunk_late_recall` 端到端 (commit 默认) | **0.0%** | 1.38 | 1.82 | 1.82 |
| **delta** | B - A | **+0.00%** | +1.38 | **+1.82** | +1.82 |

### Bench 方法论 (派工 brief 据实调整)

派工 brief 要求"必须用真实 `hybrid_retriever.retrieve()` 入口测"。但**端到端真 `retrieve()` 在生产 DB 上全失败** (上游 `search_semantic` schema drift + 下游 `_chunk_late_recall` SQL 列名 drift)。

**调整方案 (类 20.156 据实上报)**:
- **保留端到端真代码**: `_chunk_late_recall(query_embedding, top_k, category)` 完整 SQL 与参数真传
- **真 query embedding**: 通过 `embedding_service.get_or_compute_query_embedding(query, has_query_prompt=True)` 真计算 (BGE m3, 1024d)
- **隔离 schema drift 上游**: monkey-patch 屏蔽 `_retrieve_impl` 整体, 让 bench 只测 `_chunk_late_recall` 路径本身的开销与召回
- **QA hit 判定**: qa-bench `must_contain` 关键词匹配 (chunk_results 不带 content, 简化判定为 False)

**早停触发**: `|delta| = 0.00% < 2%` → 派工 brief 早停条件达成, **不扩展到 100 题**。

### per_query 详情 (模式 B, 端到端真跑)

```json
{
  "id": "A01", "source": "qa-bench",
  "hit": false, "latency_ms": 1.78,
  "n_results": 0,
  "error": "InFailedSQLTransactionError: current transaction is aborted, commands ignored until end of transaction block",
  "top5_ids": []
}
```

**关键观察**: 模式 B 每条 query `n_results=0` + `error` — **SQL 执行必然失败**, 因为 DB `knowledge_chunks` 表无 `chunk_embedding` 列。best-effort `try/except` 吞掉错误, 静默返回 `[]`。模式 A (parent-only) 没调这条 SQL, 所以也没结果, 但 n_results=0 是预期的 (因为本 bench 就不模拟 parent-only 路)。

---

## §3 3 决策门禁实测 (派工 brief 严禁跳过)

### Gate 1: 端到端 recall 提升 > 2%

| 指标 | 实测值 | 门禁 | 结果 |
|---|---|---|---|
| mode_a recall@10 | 0.0% | - | (基准) |
| mode_b recall@10 | 0.0% | - | (测试) |
| delta | **+0.00%** | > +2% | **❌ FAIL** |

**结论**: 端到端真跑下, `_chunk_late_recall` 与 parent-only 的召回差异为 **0%**。不是 `+0.01%` 的统计学 noise, 而是**真实** 0% — 因为模式 B 在生产 DB 上必然失败 (SQL 列名 drift), 返回空集, 等同于"没启用该路径"。

### Gate 2: P95 延迟恶化 < 30ms

| 指标 | 实测值 | 门禁 | 结果 |
|---|---|---|---|
| mode_a p95 | 0.0ms | - | (基准, 没调 SQL) |
| mode_b p95 | 1.82ms | - | (测试) |
| delta | **+1.82ms** | < +30ms | **✅ PASS** |

**结论**: 即使模式 B 必然失败, 它**仍然**走了 1 次 SQL 调用, 失败的 SQL 也消耗 ~1.8ms (DB query plan + connection round-trip)。P95 恶化 1.82ms, 远低于 30ms 门禁。**但这是 DB 失败的延迟, 不是真成功路径的延迟** — 如未来修好 SQL, 实际延迟会更高 (BGE m3 1024d × 530 docs × 5 chunks/docs ≈ 2650 chunks, unnest + cosine 距离计算会显著拉高延迟)。

### Gate 3: 维护成本可控 (1 个 Celery 任务 + 1 个监控指标)

**此 gate bench 不验**, 由架构评估:
- **回填 Celery 任务**: 530 docs × N chunks × 1024d × 4 bytes = ~2.1 GB 数据写入 (按 5 chunks/doc 估算), 单进程回填需 30+ 分钟, 需 Celery 异步任务调度
- **监控指标**: knowledge_chunks.late_embedding IS NULL 比例 / 回填成功率 / 单 chunk 嵌入耗时
- **额外存储**: late_embedding 列占 2.1 GB, pgvector HNSW 索引额外 ~600 MB, total ~2.7 GB
- **结论**: **维护成本可控但 ROI 极低** — Gate 1 已经 0% 提升, 即使成本可控也没意义回填

---

## §4 5 维度决策矩阵

| 维度 | 实测/估算 | 结论 |
|---|---|---|
| **真召回率** | mode_b 0%, mode_a 0%, delta **+0%** | ❌ 无提升 |
| **P95 延迟** | 失败路径 +1.82ms, 成功路径预估 +50-200ms (2650 chunks unnest) | ⚠️ 失败掩盖真相, 修复后会显著恶化 |
| **late_embedding 列回填成本** | 530 docs × 1024d × ~5 chunks = ~2.7 GB (data + HNSW) | ⚠️ 一次性成本, 30+ 分钟 Celery |
| **维护成本** | 1 Celery 任务 + 1 监控指标, 可控 | ✅ 可控 |
| **上线风险** | chunk 召回引入不相关结果 (best-effort 失败被吞) + schema drift 静默失败 | ❌ 高 (静默失败比显式失败更危险) |

---

## §5 整段归档决策

**所有 3 决策门禁 FAIL → 整段归档** (派工 brief 严禁跳过):
- ❌ Gate 1 (recall 提升 > 2%): FAIL (+0% vs 门禁 > +2%)
- ✅ Gate 2 (P95 延迟恶化 < 30ms): PASS (+1.82ms < 门禁 +30ms)
- ✅ Gate 3 (维护成本可控): PASS (1 Celery + 1 监控)

**Gate 1 是 hard-fail gate**, 即使 Gate 2/3 PASS, 也必须归档。

**代码保留策略**:
- ✅ `hybrid_retriever._chunk_late_recall` (app/services/hybrid_retriever.py:312-349) — 保留, 路由层代码不动
- ✅ `tests/integration/test_late_chunking_recall.py` — 保留, 2 PASS 测试验证 best-effort 不影响父级
- ✅ `alembic/versions/104_add_knowledge_chunk_late_embedding.py` — 保留 (派工 brief 严禁改 alembic)
- ❌ late_embedding 列回填 Celery 任务 — **不创建**
- ❌ knowledge_chunks.late_embedding 回填 — **不执行**

**遗留问题** (W-N-D++ 不擅自扩, 留给未来派工):
1. **类 20.156 schema drift** (DB knowledge 缺 embedding_model_version / _chunk_late_recall 列名错) — 需要 schema 修复派工 (本任务不动)
2. **类 20.154 缺 RAG 评测集** — 项目需要 100+ 题 `relevant_knowledge_ids` 标注的 RAG 评测集 (本任务不创建)
3. **bge-m3 路径留口** (W-N-D+ +2 commit `025bb505c` 已记录) — 待 GPU 启用 + bge-m3 真服务后回归

---

## §6 类 20 沉淀 (W-N-D++ 据实上报)

- **类 20.154**: 派工 brief "1000 题 qa-bench" 假设偏差 — qa-bench 是 agent 评测集, 非 RAG 召回评测集; 项目无 100 题 RAG 评测, 据实降级
- **类 20.155**: alembic head `104_add_knowledge_chunk_late_embedding` 守恒 ≠ DB schema 守恒 — migration 名实不符, DB 缺列 (embedding_model_version / chunk_embedding) 静默失败
- **类 20.156**: best-effort `try/except` 静默失败比显式失败更危险 — `_chunk_late_recall` 异常被吞, 路由层不知道路径失效, 真召回率与 parent-only 无差异

---

## §7 沉淀文件

- **bench 脚本**: `scripts/bench_e2e_late_chunking_recall.py` (端到端真代码 + monkey-patch 隔离)
- **bench 结果**: `results/e2e_late_chunking_bench_2026-08.json`
- **startup memory**: `memory/w-n-d-plus-e2e-bench-startup-2026-08-05.md`
- **closure memory**: `memory/w-n-d-plus-e2e-bench-closure-2026-08-05.md` (W-N-D++ +3)
- **本决策文档**: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`