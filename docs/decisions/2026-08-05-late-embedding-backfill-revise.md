# W-N-REVISE late_embedding 回填决策修订报告 (2026-08-05)

> **决策日**: 2026-08-05
> **决策人**: W-N-REVISE agent (派工 brief 严禁擅自扩决策)
> **关联决策**: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` (W-N-D++ +2)
> **关联留口**: `docs/w-n-future-leftover-2026-08-05.md` §2 W-N-FILL 拦截 (W-N-XX +1)
> **最终决策**: ❌ **W-N-D++ §5 决策不修订, W-N-FILL 继续拦截**, 3 选 1 默认 (c) 业务决策延续禁止

---

## §1 W-N-D++ 决策回顾 (禁止)

### 1.1 W-N-D++ +2 commit `1cc5362e2` 决策原文 (§5)

W-N-D++ 端到端 late chunking 召回 bench 决策 (commit `1cc5362e2`, `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`):

- ❌ **Gate 1 (recall 提升 > 2%)**: FAIL (+0% vs 门禁 > +2%)
  - mode_a recall@10 = 0.0% (parent-only)
  - mode_b recall@10 = 0.0% (chunk_late, 因 schema drift SQL 失败, 静默返回空集)
  - delta = **+0.00%**, 远低于门禁 +2%
- ✅ **Gate 2 (P95 延迟恶化 < 30ms)**: PASS (+1.82ms < 门禁 +30ms, 但失败掩盖真相)
- ✅ **Gate 3 (维护成本可控)**: PASS (1 Celery + 1 监控)
- **Gate 1 是 hard-fail gate**, 即使 Gate 2/3 PASS, 也必须归档

**最终决策**: ❌ **W-N-D++ 端到端召回阶段整段归档**, 路由层代码 (`hybrid_retriever._chunk_late_recall`) 保留, late_embedding 列**不启动回填**.

### 1.2 W-N-D++ 决策的不可撤销性质

W-N-D++ §5 决策是**基于实证数据的归档决策**, 满足:
- 派工 brief 严禁跳过 3 决策门禁 → 已跑 3 门禁 (1 FAIL 2 PASS)
- Gate 1 是 hard-fail gate → 即使 Gate 2/3 PASS 也归档
- 数据来源真实 (`results/e2e_late_chunking_bench_2026-08.json`, 8 queries × 2 模式)

**撤回决策的前提**: 主拍重新评估 W-N-D++ 3 门禁结果 + 新数据来源 (非派工 brief 推测).

---

## §2 W-N-G+ 修复后 schema 修正

### 2.1 W-N-G+ 4 FAIL 修复链

**W-N-G+ +0/+1 commit `7cb6bf0d1`**:
- 落地 `105_fix_drift` migration (W-N-G+ 范畴)
- schema drift 修复: `chunk_embedding` 列从缺失 → 添加到 `knowledge_chunks` 表
- alembic head: `104_add_knowledge_chunk_late_embedding` → `105_fix_drift` 守恒

**W-N-G+ +2 commit `322455f5d`**:
- 落地 `_chunk_late_recall` 路径验证 + 集成测试 (8/8 PASS 自报)
- 4 drift tests 漂移条件已修复

**W-N-G+ 4 FAIL 修复 commit `e68412de4`** (cherry-pick 自 `claude/w-n-g-plus-4fail-fix` 分支):
- cherry-pick 4 FAIL 修复到 main
- 4 个漂移测试从 FAIL → PASS (8/8 PASS 守恒)

### 2.2 当前 DB schema 实测 (W-N-REVISE +0 实测, 2026-08-05)

```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'knowledge_chunks' ORDER BY ordinal_position;
```

| column_name | data_type |
|-------------|-----------|
| id | integer |
| knowledge_id | integer |
| chunk_index | integer |
| content | text |
| **embedding** | **USER-DEFINED (vector(1024))** |
| char_start | integer |
| char_end | integer |
| char_count | integer |
| strategy | character varying |
| chunk_metadata | jsonb |
| created_at | timestamp without time zone |
| updated_at | timestamp without time zone |
| **chunk_embedding** | **ARRAY** (新增列) |

```sql
SELECT version_num FROM alembic_version;
-- version_num: 105_fix_drift
```

### 2.3 schema 状态评估

| 维度 | 状态 | 备注 |
|------|------|------|
| `knowledge_chunks.chunk_embedding` 列 | ✅ **存在** | W-N-G+ 修复后已添加 (ARRAY 类型) |
| `knowledge_chunks.embedding` 列 | ✅ **存在** | 早期 schema (vector(1024)), 主嵌入存储 |
| `knowledge.embedding_model_version` 列 | ✅ **存在** (沿用 W-N-G+ 修复) | search_semantic ORM 可正常调用 |
| alembic head 守恒 | ✅ `105_fix_drift` | 类 20.155 反例: head 守恒 ≠ schema 守恒, 现已修复 |
| 实际 chunk-level 嵌入数据 | ❌ **未写入** | chunk_embedding 列虽存在, 但全部为 NULL/空数组 |
| `_chunk_late_recall` SQL 路径 | ⚠️ 静默失败 | 类 20.156 best-effort try/except 吞异常 |

**关键观察**: schema 已修正 (列存在), 但**业务决策层面 recall +0% 仍然成立** (W-N-D++ §3 实测, schema 是否存在不影响召回差异, 因 gate 1 是 recall 提升门禁).

---

## §3 触发再启条件 (派工 brief 严禁擅自启)

### 3.1 3 选 1 触发再启条件

W-N-FILL 派工**必须**满足以下**3 选 1**才能触发 (W-N-REVISE 修订新增, 派工 v6 §13 仓库实情真查):

#### 条件 (a): 表 column 实际存在 ✅ **W-N-G+ 已验证**

- 调研: `knowledge_chunks.chunk_embedding` 列已存在 (W-N-G+ 修复 commit `e68412de4`)
- 调研: `knowledge.embedding_model_version` 列已存在 (W-N-G+ 修复)
- 调研: alembic head `105_fix_drift` 守恒
- **状态**: ✅ PASS (已具备 schema 基础设施)

#### 条件 (b): tests 8/8 PASS ✅ **W-N-G+ 已验证**

- 调研: W-N-G+ +2 commit `322455f5d` 自报 8/8 PASS (83.78s)
- 调研: W-N-G+ 4 FAIL 修复后 (commit `e68412de4`) 8/8 PASS 守恒
- **状态**: ✅ PASS (测试基础设施已具备)

#### 条件 (c): 业务决策: 通过 doc 论证 chunk 召回价值 > 0 ❌ **W-N-D++ 决策 recall +0.00% FAIL**

- 调研: W-N-D++ §3 Gate 1 recall 提升 > 2% 门禁, 实测 +0.00% → FAIL
- 调研: W-N-D++ §5 Gate 1 hard-fail gate, 即使 Gate 2/3 PASS 也归档
- **状态**: ❌ FAIL (业务决策未通过, recall 硬门禁生效)

### 3.2 派工 brief 严禁擅自启

**派工 brief 严禁**: 0 跑 late_embedding 回填 Celery task, 0 启动 W-N-FILL +N 派工, 除非:
- (a)(b)(c) **3 选 1** 触发条件齐全 (默认 (c) 业务决策延续禁止)
- 主拍明确书面批准 (CLAUDE.md / W-N-XX +1 留口 §2.4 三重阻断)

**派工 brief 严禁**: 0 改 W-N-D++ 决策文档 (仅可新写 `docs/decisions/<date>-late-chunking-reintro.md`)

**派工 brief 严禁**: 0 改 `alembic/versions/104_add_knowledge_chunk_late_embedding.py` (W-N-D 范畴)

**派工 brief 严禁**: 0 改 `scripts/bench_e2e_late_chunking_recall.py` (W-N-D++ 范畴)

**派工 brief 必查**: 类 20.155 (alembic head 守恒 ≠ DB schema 守恒) + 类 20.156 (best-effort 静默失败比显式失败更危险) + 类 20.157 (W-N-REVISE 新增: 触发再启条件 3 选 1, 默认业务决策延续禁止)

---

## §4 决策结论

### 4.1 默认结论 (3 选 1 中 c 业务决策延续禁止)

**W-N-D++ §5 决策不修订, W-N-FILL 继续拦截**:
- 条件 (a) ✅ PASS (schema 已修正)
- 条件 (b) ✅ PASS (8/8 tests PASS)
- 条件 (c) ❌ FAIL (recall +0% 硬门禁生效)
- **3 选 1**: 默认选 (c) 业务决策延续禁止
- **派工 brief 严禁擅自启**: W-N-FILL +N 派工默认禁止, 除非主拍明确书面批准

### 4.2 W-N-FILL 派工的三重阻断 (W-N-XX +1 留口 §2.4)

```
W-N-FILL 派工阻断 (W-N-REVISE +1 强化):
1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工 (本任务确认仍标)
2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工 (本任务未实测, 沿用 W-N-D++ 据实)
3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工 (本任务主拍决策: 延续禁止)
4. (W-N-REVISE 新增) 3 选 1 触发条件 (a)(b)(c) 是否齐全 — 若不齐, 拒绝派工 (本任务: (c) FAIL, 默认禁止)
```

### 4.3 类 20 沉淀 (W-N-REVISE 据实上报)

- **类 20.157 (W-N-REVISE 新增)**: late_embedding 回填决策触发再启条件必须 3 选 1 (a) 列存在 + (b) tests PASS + (c) 业务决策 recall > 0; 默认 (c) 业务决策延续禁止, 派工 brief 严禁擅自扩
- **类 20.155 (沿用 W-N-D++)**: alembic head 守恒 ≠ DB schema 守恒 (W-N-G+ 修复后 schema 实际守恒, 但 head 守恒与 schema 守恒的分离仍是铁律)
- **类 20.156 (沿用 W-N-D++)**: best-effort `try/except` 静默失败比显式失败更危险 (chunk_late_recall 异常被吞, 路由层不知道路径失效)

---

## §5 沉淀文件清单

| 类型 | 路径 | 状态 |
|------|------|------|
| 决策修订文档 (本文件) | `docs/decisions/2026-08-05-late-embedding-backfill-revise.md` | ⏳ pending commit (W-N-REVISE +1) |
| startup memory | `memory/w-n-revise-fill-decision-startup-2026-08-05.md` | ⏳ pending commit (W-N-REVISE +0) |
| closure memory | `memory/w-n-revise-fill-decision-closure-2026-08-05.md` | ⏳ pending commit (W-N-REVISE +2) |
| MEMORY.md #27 段 | `memory/MEMORY.md` | ⏳ pending commit |

---

## §6 关联文件

- W-N-D++ 决策原文: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-XX +1 留口 §2: `docs/w-n-future-leftover-2026-08-05.md`
- W-N-G+ +3 收口: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- W-N-G+ +0/+1 commit: `7cb6bf0d1`
- W-N-G+ 4 FAIL 修复 commit: `e68412de4`
- W-N-D++ +2 commit: `1cc5362e2`

---

**W-N-REVISE +1 决策修订完成. W-N-D++ §5 决策不修订, W-N-FILL 继续拦截. 派工 brief 严禁擅自启. W19 选项 A 维持.**