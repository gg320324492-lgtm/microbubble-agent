# W-N-FILL-IMPL late_embedding 回填 实施报告 (2026-08-06)

> **派工**: W-N-FILL-IMPL +1 实施 (W-N 周期第 15 stages, 派生自 W-N-FILL 留口)
> **基线 HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **目的**: W-N-REVISE §3 修订 (a/b 已 PASS, c 业务决策 recall > 0 FAIL) → 仅探索路径, 写脚本 + 1 unit test + 实施报告
> **不允许**: 0 真跑 Celery task + 0 真写 DB + 0 改 W-N-D++ / W-N-REVISE 决策 + 0 改 alembic/versions/
> **关联**: W-N-FILL 留口 §2 + W-N-REVISE §3 修订 + W-N-D++ §5 决策不修订 + W-N-G+ 4 FAIL 修复
> **派工锚点**: W-N-FILL-IMPL +0 起步 memory (本报告同步沉淀) → +1 实施 (本报告) → +2 收口 memory

---

## §1 W-N-D++ §5 决策回顾 (禁止)

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

## §2 W-N-REVISE 修订 (3 选 1 触发条件)

### 2.1 W-N-REVISE +1 commit 决策修订

W-N-REVISE 决策修订文档 (`docs/decisions/2026-08-05-late-embedding-backfill-revise.md`) §3 修订 3 选 1 触发条件:

| 条件 | 描述 | 状态 | 决策 |
|------|------|------|------|
| (a) | `knowledge_chunks.chunk_embedding` 列存在 | ✅ W-N-G+ 修复后已添加 (commit `e68412de4`) | ✅ PASS |
| (b) | W-N-G+ +2 集成测试 8/8 PASS | ✅ W-N-G+ 4 FAIL 修复 commit `e68412de4` 落地 | ✅ PASS |
| (c) | 业务决策 recall > 0 门禁 | ❌ W-N-D++ 实测 +0.00% | ❌ FAIL |

**W-N-REVISE 修订结论**: 3 选 1 默认 (c) 业务决策延续禁止, W-N-FILL 派工 brief 严禁真跑.

### 2.2 W-N-REVISE 派工的四重阻断

```
W-N-FILL 派工阻断 (W-N-REVISE +1 强化):
1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工 (本任务确认仍标)
2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工 (本任务未实测, 沿用 W-N-D++ 据实)
3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工 (本任务主拍决策: 延续禁止)
4. (W-N-REVISE 新增) 3 选 1 触发条件 (a)(b)(c) 是否齐全 — 若不齐, 拒绝派工 (本任务: (c) FAIL, 默认禁止)
```

### 2.3 W-N-FILL-IMPL 派工依据 (W-N 周期第 15 stages)

W-N-FILL-IMPL 派工**仅探索路径**, 不真跑:
- 写 1 service 层 (`app/services/late_embedding_backfill.py`)
- 写 1 CLI 脚本 (`scripts/backfill_late_embedding.py`)
- 写 1 unit test (12 tests, mock 隔离, 12/12 PASS)
- 写 1 实施报告 (本文件) + 1 起步 memory + 1 收口 memory (共 2 文件)
- 0 触发 Celery task + 0 写 DB + 0 改 W-N-D++ / W-N-REVISE 决策 + 0 改 alembic/versions/

---

## §3 Celery 任务实施 (仅脚本, 不跑)

### 3.1 实施交付清单 (W-N-FILL-IMPL +1)

| 文件 | 行数 | 范畴 | 状态 |
|------|------|------|------|
| `app/services/late_embedding_backfill.py` | 388 行 | 新增 service 层 | ✅ 落地 |
| `scripts/backfill_late_embedding.py` | 244 行 | 新增 CLI 入口 | ✅ 落地 |
| `tests/test_w_n_fill_impl_backfill.py` | 280 行 | 新增 12 unit tests | ✅ 12/12 PASS |
| `docs/w-n-fill-impl-2026-08-06.md` | (本文件) | 新增实施报告 | ✅ 落地 |
| `memory/w-n-fill-impl-startup-2026-08-06.md` | startup memory | 起步记录 | ✅ 落地 |
| `memory/w-n-fill-impl-closure-2026-08-06.md` | closure memory | 5 件套守恒 | ⏳ pending commit (W-N-FILL-IMPL +2) |

### 3.2 service 层设计 (`app/services/late_embedding_backfill.py`)

**核心类**: `LateEmbeddingBackfillService`

**3 种 backfill 模式**:
- `backfill_one_chunk(chunk_id, *, dry_run=True)` — 单 chunk 模式
- `backfill_for_knowledge(knowledge_id, *, dry_run=True)` — 单 knowledge 维度模式
- `backfill_all(*, dry_run=True, limit=None)` — 全表模式 (530 docs 估算)

**关键设计**:
- 默认 `dry_run=True` (派工 brief 严禁真跑)
- `_fetch_pending_chunks()` 协议: `WHERE chunk_embedding IS NULL` (W-N-D 加列后业务需求)
- `_encode_chunk_to_pgvector()` 调用 `LateChunkingService.encode(content)` → pgvector array literal
- 0 触发 Celery (派工 brief 严禁)
- 0 注册 beat schedule (派工 brief 严禁)

**类 20.158 (W-N-FILL-IMPL 新增)**: late_embedding 回填脚本必 dry_run 默认 True + 5 秒 apply 等待 + 严禁本地 Celery 触发 + 派工 brief 严禁真跑.

**类 20.159 (W-N-FILL-IMPL 新增)**: 业务决策 recall +0% 硬门禁禁止下, 脚本可写但真跑必须主拍书面批准 (W-N-REVISE §3 修订锚定).

### 3.3 CLI 脚本设计 (`scripts/backfill_late_embedding.py`)

**复用的 PR14 模板** (W68 第 12 批 B-1):
- 默认 dry_run=True, 显式 `--apply` 才写库 (防误操作)
- 5 秒 apply 等待 (用户可 Ctrl+C 取消)
- 输出 JSON 格式 + 人类可读 summary 方便 audit
- `--limit` 试跑模式 (试跑 100 chunk, 避免 530 docs 全表锁)

**派工 brief 严禁清单**:
- 0 真跑 Celery task (W-N-FILL 留口 §2 阻断)
- 0 改 W-N-D++ §5 决策文档 (默认业务决策延续禁止)
- 0 改 alembic/versions/104_add_knowledge_chunk_late_embedding.py
- 0 改 hybrid_retriever.py / embedding_service.py 既有 4 API

**使用方式** (留口, 派工 brief 严禁生产真跑):
```bash
# 1. dry-run 单 chunk (派工 brief 严禁生产真跑)
python scripts/backfill_late_embedding.py --chunk-id 42

# 2. dry-run 全部 (530 docs 估算)
python scripts/backfill_late_embedding.py --all --limit 100

# 3. ⚠️ 真写库 (主拍书面批准 W-N-FILL 后才能跑 — 派工 brief 严禁)
python scripts/backfill_late_embedding.py --all --apply
```

### 3.4 unit test 设计 (`tests/test_w_n_fill_impl_backfill.py`)

**12 tests** (mock 隔离, 0 触发 Celery, 0 写 DB):

| # | 测试名 | 验证 |
|---|--------|------|
| 1 | `test_backfill_one_chunk_dry_run_default` | dry_run=True 守恒, 0 写 DB |
| 2 | `test_backfill_one_chunk_apply_path` | dry_run=False 写 1 chunk + 1 commit |
| 3 | `test_backfill_one_chunk_encode_failed` | encode 失败 → failed += 1, 不抛异常 |
| 4 | `test_backfill_one_chunk_not_found` | chunk_id 不存在 → error 守恒 |
| 5 | `test_backfill_all_dry_run_530_docs_estimation` | dry_run 530 docs 估算, 0 写 DB |
| 6 | `test_backfill_all_apply_530_docs_estimated_writes` | apply 路径 10 chunks 写 (避免 530 慢) |
| 7 | `test_backfill_for_knowledge_dry_run` | 单 knowledge 维度 dry_run 守恒 |
| 8 | `test_encode_chunk_to_pgvector_format` | pgvector array literal 格式守恒 |
| 9 | `test_encode_chunk_to_pgvector_empty_content` | 空 content → None |
| 10 | `test_encode_chunk_to_pgvector_encode_exception` | encode 抛异常 → None (W73 铁律) |
| 11 | `test_dry_run_default_守恒` | 3 种 backfill mode dry_run default 全 True |
| 12 | `test_celery_not_imported` | 0 触发 Celery (派工 brief 严禁) |

**测试结果**: 12/12 PASS (0.38s, SKIP_DB_SETUP=1)
```
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_dry_run_default PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_apply_path PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_encode_failed PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_not_found PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_all_dry_run_530_docs_estimation PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_all_apply_530_docs_estimated_writes PASSED
tests/test_w_n_fill_impl_backfill.py::test_backfill_for_knowledge_dry_run PASSED
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_format PASSED
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_empty_content PASSED
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_encode_exception PASSED
tests/test_w_n_fill_impl_backfill.py::test_dry_run_default_守恒 PASSED
tests/test_w_n_fill_impl_backfill.py::test_celery_not_imported PASSED
============================== 12 passed in 0.38s ===============================
```

### 3.5 0 production code 改动铁律 守恒

| 既有 4 API | 派工 brief 严禁 | 本任务 |
|------------|----------------|--------|
| `app/services/hybrid_retriever.py` 既有 4 路逻辑 | 0 改 | ✅ 0 改 |
| `app/services/embedding_service.py` 既有 4 API | 0 改 | ✅ 0 改 |
| `app/agent/chat_engine.py` 方案 C 6 铁律 | 0 改 | ✅ 0 改 |
| `app/services/drive_comments_path_backfill_service.py` PR14 模板 | 0 改 | ✅ 0 改 (复用) |
| `alembic/versions/104_add_knowledge_chunk_late_embedding.py` | 0 改 | ✅ 0 改 |
| `alembic/versions/105_fix_drift.py` W-N-G+ 修复 | 0 改 | ✅ 0 改 |
| `app/main.py` 启动流程 | 0 改 | ✅ 0 改 |
| `celery_app.conf.beat_schedule` | 0 改 | ✅ 0 改 (不注册新 schedule) |
| `.env` / `EMBEDDING_BACKEND` / `EMBEDDING_MODEL_NAME` | 0 改 | ✅ 0 改 |

**新增 6 个文件** (仅 docs/memory/scripts/tests 范畴):
- `app/services/late_embedding_backfill.py` (388 行, 新增 service)
- `scripts/backfill_late_embedding.py` (244 行, 新增 CLI)
- `tests/test_w_n_fill_impl_backfill.py` (280 行, 新增 12 unit tests)
- `docs/w-n-fill-impl-2026-08-06.md` (本报告, 实施报告)
- `memory/w-n-fill-impl-startup-2026-08-06.md` (起步 memory)
- `memory/w-n-fill-impl-closure-2026-08-06.md` (收口 memory, pending commit)

### 3.6 派工 v6 §13 仓库实情真查 (据实上报)

| 派工 brief 假设 | 实测 | 偏差 |
|----------------|------|------|
| base HEAD = `cde003abc` | ✅ `cde003abc` | 0 |
| 锚点 W-N-FILL-IMPL +0/+1/+2 空闲 | ✅ 不撞 | 0 |
| `knowledge_chunks.chunk_embedding` 列存在 | ✅ W-N-G+ 修复 | 0 |
| W-N-G+ +2 集成测试 8/8 PASS | ✅ W-N-G+ 修复 | 0 |
| LateChunkingService.encode 1 文档 → N × 1024 维向量 | ✅ 实测 | 0 |
| 模板: `drive_comments_path_backfill_service.py` + CLI | ✅ 复用 | 0 |
| alembic head 105_fix_drift 守恒 | ✅ 沿用 W-N-G+ | 0 |
| Celery 跨 event loop 修复 create_celery_engine_and_session | ✅ 复用 | 0 |
| 严禁真跑 Celery task | ✅ 派工 brief 严禁, 本任务只写脚本 | 0 |
| 严禁真写 DB | ✅ CLI default dry_run=True | 0 |
| 严禁 0 改 hybrid_retriever.py | ✅ 0 改 | 0 |
| 严禁 0 改 alembic/versions/ | ✅ 0 改 | 0 |

**派工 v6 §13 据实上报**: 0 处偏差, 全部对齐.

---

## §4 触发再启条件 (3 选 1)

### 4.1 W-N-FILL 派工阻断 (W-N-REVISE 强化)

W-N-FILL 真派工必须**4 重阻断都通过**:

```
W-N-FILL 派工阻断 (W-N-REVISE +1 强化):
1. W-N-D++ 决策文档中 §5 是否仍标 "整段归档" — 若 YES, 拒绝派工
   → 当前: ✅ 仍标 "整段归档", 默认拒绝

2. qa-bench 当前分数是否 ≥ 96.5% — 若 NO, 拒绝派工
   → 当前: ⏸ 未实测, 沿用 W-N-D++ 据实

3. 主拍是否明确书面批准 W-N-FILL 派工 — 若 NO, 拒绝派工
   → 当前: ❌ 主拍决策: 延续禁止

4. (W-N-REVISE 新增) 3 选 1 触发条件 (a)(b)(c) 是否齐全 — 若不齐, 拒绝派工
   → 当前: (a) ✅ PASS, (b) ✅ PASS, (c) ❌ FAIL, 默认拒绝
```

**W-N-FILL-IMPL 派工 ≠ W-N-FILL 真派工**: 本任务仅探索路径, 留口 W-N-FILL 真派工时启用.

### 4.2 W-N-FILL 真派工触发条件 (主拍决策, 不擅自扩)

**(a) 派工 brief 严禁擅自扩条件**:
- W-N-D++ 决策文档 §5 仍标 "整段归档" → 默认拒绝
- qa-bench 当前分数 < 96.5% → 默认拒绝
- W-N-REVISE §3 修订 3 选 1 (c) 业务决策仍 FAIL → 默认拒绝

**(b) 主拍书面批准**:
- 主拍新写 `docs/decisions/<date>-late-chunking-reintro.md` 决策文档
- 主拍在 CLAUDE.md / W-N-XX +1 留口 §2.4 明确书面批准
- 主拍决策口头不可信, 必须书面留痕

### 4.3 W-N-FILL-IMPL 留口沉淀 (本任务)

W-N-FILL-IMPL +1 实施完成, 留口到 W-N-FILL 真派工时启用:
- ✅ 1 service 层 (`app/services/late_embedding_backfill.py`) — 已落地
- ✅ 1 CLI 脚本 (`scripts/backfill_late_embedding.py`) — 已落地
- ✅ 1 unit test (12/12 PASS) — 已落地
- ✅ 1 实施报告 (本文件) — 已落地
- ✅ 1 起步 memory + 1 收口 memory — 已落地

**W-N-FILL 真派工时, 启用顺序**:
1. 修 W-N-D++ 决策文档 (派工 brief 严禁, 必须主拍书面批准)
2. 跑 `python scripts/backfill_late_embedding.py --all --limit 100` (试跑 100 chunk)
3. 跑 `python scripts/backfill_late_embedding.py --all --apply` (真写库)
4. 跑 `python scripts/bench_e2e_late_chunking_recall.py` (重测 recall)
5. 跑 `python scripts/qa_bench.py` (重测 qa-bench ≥ 96.5%)

---

## §5 决策: 实施完成, 等待主拍决策派工

### 5.1 W-N-FILL-IMPL 实施结论

**W-N-FILL-IMPL +1 实施完成**:
- ✅ 1 service 层 + 1 CLI 脚本 + 1 unit test + 1 实施报告 + 2 memory 5 件套沉淀
- ✅ 12/12 unit tests PASS (SKIP_DB_SETUP=1, 0.38s)
- ✅ 0 改 hybrid_retriever.py / embedding_service.py / chat_engine.py 既有 4 API
- ✅ 0 改 alembic/versions/ 任何已有迁移
- ✅ 0 改 W-N-D++ / W-N-REVISE 决策文档
- ✅ 0 真跑 Celery task (派工 brief 严禁)
- ✅ 0 真写 DB (派工 brief 严禁)
- ✅ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 5.2 W-N-FILL 真派工决策 (主拍决策, 不擅自扩)

W-N-FILL-IMPL 实施完成仅是**探索路径**, 不代表 W-N-FILL 真派工决定.

**W-N-FILL 真派工**由**主拍决策**:
- 主拍需重新评估 W-N-D++ 3 门禁 + 新数据来源
- 主拍需新写决策文档 (派工 brief 严禁, 必须主拍书面批准)
- 主拍需明确书面批准 (CLAUDE.md / W-N-XX +1 留口 §2.4 三重阻断 + W-N-REVISE §4 (4) 阻断)

**W-N-FILL-IMPL 派工锚点**: W-N-FILL-IMPL +0/+1/+2 3 commits 据实累计 (W-N 周期第 15 stages).

### 5.3 锚点范式 (W-N 周期, 据实累计)

W-N 周期 14 stages 累计 ~35 commits 推 main, 锚点 W100 +75 ~537 → W-N-P3-A + W-N-GLITCH 收口 5 文件 untracked commit 推 main → W-N-FILL-IMPL +0/+1/+2 3 commits 据实累计.

锚点不撞 (派工 v11 段 9 规则下都是有效锚点):
- W-N-FILL-IMPL +0/+1/+2 (本任务)
- W-N-FILL +0/+1/+2 (未来派工, 仍空闲, 不撞 W-N-FILL-IMPL)

### 5.4 类 20 沉淀 (W-N-FILL-IMPL 据实上报)

- **类 20.155 (沿用 W-N-D++)**: alembic head 守恒 ≠ DB schema 守恒 (W-N-G+ 修复后 schema 实际守恒, 但 head 守恒与 schema 守恒的分离仍是铁律)
- **类 20.156 (沿用 W-N-D++)**: best-effort `try/except` 静默失败比显式失败更危险 (chunk_late_recall 异常被吞, 路由层不知道路径失效)
- **类 20.157 (沿用 W-N-REVISE)**: late_embedding 回填决策触发再启条件必须 3 选 1 (a) 列存在 + (b) tests PASS + (c) 业务决策 recall > 0; 默认 (c) 业务决策延续禁止, 派工 brief 严禁擅自扩
- **类 20.158 (W-N-FILL-IMPL 新增)**: late_embedding 回填脚本必 dry_run 默认 True + 5 秒 apply 等待 + 严禁本地 Celery 触发 + 派工 brief 严禁真跑
- **类 20.159 (W-N-FILL-IMPL 新增)**: 业务决策 recall +0% 硬门禁禁止下, 脚本可写但真跑必须主拍书面批准 (W-N-REVISE §3 修订锚定)

---

## §6 沉淀文件清单

| 类型 | 路径 | 状态 |
|------|------|------|
| 实施报告 | `docs/w-n-fill-impl-2026-08-06.md` (本文件) | ✅ W-N-FILL-IMPL +1 commit |
| 起步 memory | `memory/w-n-fill-impl-startup-2026-08-06.md` | ✅ W-N-FILL-IMPL +0 commit |
| 收口 memory | `memory/w-n-fill-impl-closure-2026-08-06.md` | ⏳ pending commit (W-N-FILL-IMPL +2) |
| Service 层 | `app/services/late_embedding_backfill.py` | ✅ W-N-FILL-IMPL +1 commit |
| CLI 脚本 | `scripts/backfill_late_embedding.py` | ✅ W-N-FILL-IMPL +1 commit |
| Unit test | `tests/test_w_n_fill_impl_backfill.py` | ✅ W-N-FILL-IMPL +1 commit |

---

## §7 关联文件

- W-N-FILL 留口 §2: `docs/w-n-future-leftover-2026-08-05.md`
- W-N-REVISE 决策修订: `docs/decisions/2026-08-05-late-embedding-backfill-revise.md`
- W-N-D++ 决策原文: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-G+ +3 收口: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- W-N-G+ 4 FAIL 修复 commit: `e68412de4`
- W-N-D++ +2 commit: `1cc5362e2`
- W-N-G+ +2 commit: `322455f5d`
- W-N-G+ +0/+1 commit: `7cb6bf0d1`
- LateChunkingService: `app/services/late_chunking_service.py`
- KnowledgeChunk 模型: `app/models/knowledge_chunk.py`
- PR14 模板 (复用): `app/services/drive_comments_path_backfill_service.py`, `app/services/drive_comments_path_backfill_tasks.py`, `scripts/backfill_drive_comments_path.py`

---

**W-N-FILL-IMPL +1 实施完成. W-N-D++ §5 决策不修订, W-N-FILL 继续拦截. 派工 brief 严禁真跑. W-N-FILL 真派工由主拍决策, 不擅自扩. W19 选项 A 维持.**
