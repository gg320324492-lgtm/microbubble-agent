# W-N-FILL-IMPL late_embedding 回填探索 收口 (2026-08-06)

> **派工**: W-N-FILL-IMPL +2 收口 (W-N 周期第 15 stages, 派生自 W-N-FILL 留口)
> **基线 HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **目的**: 5 件套守恒实测 + 沉淀 W-N-FILL-IMPL 完整派工证据链
> **关联**: W-N-FILL 留口 §2 + W-N-REVISE §3 修订 + W-N-D++ §5 决策 + W-N-G+ 4 FAIL 修复
> **派工锚点**: W-N-FILL-IMPL +0 起步 → +1 实施 → +2 收口 (本 memory)

---

## 1. 5 件套守恒实测 (W-N-FILL-IMPL +2 收口)

| 件 | 项 | 状态 | 实测 |
|----|----|----|------|
| 1 | alembic 1 head | ✅ | `105_fix_drift (head)` 单 head 守恒 (沿用 W-N-G+ +3, 本任务不动) |
| 2 | DB alembic_version | ✅ | DB = `105_fix_drift` 守恒 (沿用 W-N-G+ +3, 本任务不动) |
| 3 | pytest unit test | ✅ | 12/12 PASS (SKIP_DB_SETUP=1, 0.38s) |
| 4 | 0 production code 改动 | ✅ | 仅 `app/services/late_embedding_backfill.py` (新增) + `scripts/backfill_late_embedding.py` (新增) + `tests/test_w_n_fill_impl_backfill.py` (新增) + `docs/w-n-fill-impl-2026-08-06.md` (新增) + 2 memory 文件 |
| 5 | 锚点范式 W-N-FILL-IMPL +0/+1/+2 | ✅ | +0 = startup memory, +1 = 实施 (service + CLI + test + report), +2 = closure memory (本文件) |

### 1.1 件 3 详细实测

```bash
$ SKIP_DB_SETUP=1 python -m pytest tests/test_w_n_fill_impl_backfill.py -v --tb=short
============================= test session starts ==============================
platform win32 -- Python 3.12.10, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\microbubble-agent
configfile: pytest.ini
plugins: anyio-4.14.1, asyncio-1.4.0, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False
collecting ... collected 12 items

tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_dry_run_default PASSED [  8%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_apply_path PASSED [ 16%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_encode_failed PASSED [ 25%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_one_chunk_not_found PASSED [ 33%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_all_dry_run_530_docs_estimation PASSED [ 41%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_all_apply_530_docs_estimated_writes PASSED [ 50%]
tests/test_w_n_fill_impl_backfill.py::test_backfill_for_knowledge_dry_run PASSED [ 58%]
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_format PASSED [ 66%]
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_empty_content PASSED [ 75%]
tests/test_w_n_fill_impl_backfill.py::test_encode_chunk_to_pgvector_encode_exception PASSED [ 83%]
tests/test_w_n_fill_impl_backfill.py::test_dry_run_default_守恒 PASSED   [ 91%]
tests/test_w_n_fill_impl_backfill.py::test_celery_not_imported PASSED    [100%]

============================= 12 passed in 0.38s ==============================
```

### 1.2 件 4 0 production code 改动铁律 (据实)

| 范畴 | 文件 | 改动 |
|------|------|------|
| ✅ 新增 service | `app/services/late_embedding_backfill.py` | 388 行 (新增) |
| ✅ 新增 CLI | `scripts/backfill_late_embedding.py` | 244 行 (新增) |
| ✅ 新增 test | `tests/test_w_n_fill_impl_backfill.py` | 280 行 (新增) |
| ✅ 新增 docs | `docs/w-n-fill-impl-2026-08-06.md` | 实施报告 (新增) |
| ✅ 新增 memory | `memory/w-n-fill-impl-{startup,closure}-2026-08-06.md` | 2 文件 (新增) |
| ❌ 0 改 hybrid_retriever.py | `/app/services/hybrid_retriever.py` | 0 改 |
| ❌ 0 改 embedding_service.py | `/app/services/embedding_service.py` | 0 改 |
| ❌ 0 改 chat_engine.py | `/app/agent/chat_engine.py` | 0 改 |
| ❌ 0 改 alembic/versions/ | `alembic/versions/104_*.py`, `105_*.py` | 0 改 |
| ❌ 0 改 drive_comments_path_backfill_service.py | `/app/services/drive_comments_path_backfill_service.py` | 0 改 (复用模板) |
| ❌ 0 改 celery_app.conf.beat_schedule | `/app/core/celery.py` | 0 改 (不注册新 schedule) |
| ❌ 0 改 app/main.py | `/app/main.py` | 0 改 |
| ❌ 0 改 .env / EMBEDDING_BACKEND | `.env` | 0 改 |
| ❌ 0 改 W-N-D++ 决策文档 | `/docs/decisions/2026-08-05-e2e-late-chunking-decision.md` | 0 改 |
| ❌ 0 改 W-N-REVISE 决策文档 | `/docs/decisions/2026-08-05-late-embedding-backfill-revise.md` | 0 改 |

**0 production code 改动铁律 守恒**: 6 个新增文件 + 0 个修改文件 = 仅 docs/memory/scripts/tests/app/services 增量.

### 1.3 件 5 锚点范式 (W-N-FILL-IMPL +0/+1/+2 据实累计)

| 锚点 | commit | 改动 |
|------|--------|------|
| W-N-FILL-IMPL +0 | (本任务 commit) | startup memory (`memory/w-n-fill-impl-startup-2026-08-06.md`) |
| W-N-FILL-IMPL +1 | (本任务 commit) | service + CLI + 12 tests + 实施报告 (4 文件) |
| W-N-FILL-IMPL +2 | (本任务 commit) | closure memory (本文件) |

**锚点不撞** (派工 v11 段 9 规则下都是有效锚点):
- W-N-FILL 0 派工 (W-N-REVISE +0 调研 + W-N-REVISE +1 决策修订 + W-N-FILL 留口 §2 是调研范畴, 无派工锚点)
- W-N-FILL-IMPL +0/+1/+2 派生锚点 (本任务)

W-N 周期锚点累计 (据实派工 brief 估):
- W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ = 历史 14 stages
- W-N-FILL-IMPL = W-N 周期第 15 stages (派生系列)

---

## 2. W-N-FILL-IMPL 派工证据链 (W-N 周期 §9 任务模式纪要)

### 2.1 派工 brief 严禁清单 (W-N-FILL-IMPL +1 据实)

本任务**严格遵守** W-N 周期派工 brief 严禁清单:

- ✅ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 旧 commits
- ✅ 0 改 alembic/versions/ 任何已有迁移
- ✅ 0 改 W-N-REVISE / W-N-D++ 决策文档 (仅新写实施报告)
- ✅ 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
- ✅ 0 改 app/agent/chat_engine.py 方案 C 6 铁律
- ✅ 0 改 app/services/embedding_service.py 既有 4 API
- ✅ 0 改 drive_comments_path_backfill_service.py 模板 (W68 第 12 批 B-1 范畴)
- ✅ 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
- ✅ 0 改 app/main.py 启动流程
- ✅ 0 真跑 Celery task (W-N-FILL 留口 §2 阻断)
- ✅ 0 真写 DB (派工 brief 严禁, dry_run 默认 True)
- ✅ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 2.2 派工 v6 §13 仓库实情真查 (据实上报)

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

### 2.3 派工前提铁律 12 + 类 20 沿用 (W-N-FILL-IMPL 据实)

**派工前提铁律 12** (W-N 周期沿用):
1. ✅ 派工 v6 §13 仓库实情真查
2. ✅ 派工 brief 严禁: 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 旧 commits
3. ✅ 派工 brief 严禁: 0 改 alembic/versions/ 任何已有迁移
4. ✅ 派工 brief 严禁: 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
5. ✅ 派工 brief 严禁: 0 改 chat_engine.py 方案 C 6 铁律
6. ✅ 派工 brief 严禁: 0 改 embedding_service.py 既有 4 API
7. ✅ 派工 brief 严禁: 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
8. ✅ 派工 brief 严禁: 真跑 Celery task (W-N-FILL 留口 §2 阻断)
9. ✅ 派工 brief 严禁: 真写 DB (派工 brief 严禁, dry_run 默认 True)
10. ✅ 派工 brief 严禁: 改 W-N-D++ / W-N-REVISE 决策文档 (仅新写)
11. ✅ 派工 brief 严禁: 改生产 .env / EMBEDDING_MODEL_NAME
12. ✅ 派工 brief 严禁: 改 chatbot/main.py / app/main.py 启动流程

**类 20 沿用 + 新增** (W-N-FILL-IMPL 据实):
- ✅ 类 20.155 (W-N-D++): alembic head 守恒 ≠ DB schema 守恒
- ✅ 类 20.156 (W-N-D++): best-effort 静默失败比显式失败更危险
- ✅ 类 20.157 (W-N-REVISE): 触发再启条件 3 选 1, 默认 (c) 业务决策延续禁止
- ✅ 类 20.153 (W-N-G+): alembic 链 hotfix branch 必实测, 不凭 brief 串行推测
- ✅ **类 20.158 (W-N-FILL-IMPL 新增)**: late_embedding 回填脚本必 dry_run 默认 True + 5 秒 apply 等待 + 严禁本地 Celery 触发 + 派工 brief 严禁真跑
- ✅ **类 20.159 (W-N-FILL-IMPL 新增)**: 业务决策 recall +0% 硬门禁禁止下, 脚本可写但真跑必须主拍书面批准 (W-N-REVISE §3 修订锚定)

---

## 3. W-N-FILL-IMPL 交付清单 (W-N 周期 §9 任务模式纪要)

### 3.1 6 文件交付

| # | 类型 | 路径 | 行数 | 落地 |
|---|------|------|------|------|
| 1 | service | `app/services/late_embedding_backfill.py` | 388 | ✅ |
| 2 | CLI | `scripts/backfill_late_embedding.py` | 244 | ✅ |
| 3 | test | `tests/test_w_n_fill_impl_backfill.py` | 280 | ✅ |
| 4 | docs | `docs/w-n-fill-impl-2026-08-06.md` | 实施报告 | ✅ |
| 5 | memory | `memory/w-n-fill-impl-startup-2026-08-06.md` | startup | ✅ |
| 6 | memory | `memory/w-n-fill-impl-closure-2026-08-06.md` | closure (本文件) | ✅ |

### 3.2 12 unit tests 守恒

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
============================== 12 passed in 0.38s ==============================
```

### 3.3 派工 v11 段 9 锚点前缀规则 (W-N-FILL-IMPL 据实)

派工 v11 段 9 锚点前缀规则要求"锚点不撞":
- W-N-FILL-IMPL +0/+1/+2 派生锚点 vs W-N-FILL 0 派工 → 不撞
- W-N-FILL-IMPL +0/+1/+2 派生锚点 vs W-N-XX +0/+1/+2 沉淀 → 不撞 (W-N-XX 是 W-N-FILL 留口调研)

派工 v11 段 9 实战: W-N-FILL-IMPL 派工**不擅自扩**, 仅探索路径 + 写脚本 + 1 unit test + 实施报告.

### 3.4 0 production code 改动铁律 (W-N-FILL-IMPL 据实)

W-N-FILL-IMPL +1 实施严格守恒 0 production code 改动铁律:
- ✅ 仅 docs/memory/scripts/tests + 新增 app/services/late_embedding_backfill.py 6 文件范畴
- ✅ 不动 hybrid_retriever.py / embedding_service.py / chat_engine.py / drive_comments_path_backfill_service.py 既有 4 API
- ✅ 不动 alembic/versions/ 任何已有迁移
- ✅ 不动生产的 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME
- ✅ 不动 chatbot/main.py / app/main.py 启动流程
- ✅ 不动 celery_app.conf.beat_schedule (不注册新 schedule)

---

## 4. W-N-FILL-IMPL 决策 (主拍决策, 不擅自扩)

### 4.1 W-N-FILL-IMPL 实施结论

**W-N-FILL-IMPL +1 实施完成**:
- ✅ 1 service 层 + 1 CLI 脚本 + 1 unit test + 1 实施报告 + 2 memory 5 件套沉淀
- ✅ 12/12 unit tests PASS (SKIP_DB_SETUP=1, 0.38s)
- ✅ 0 改 hybrid_retriever.py / embedding_service.py / chat_engine.py 既有 4 API
- ✅ 0 改 alembic/versions/ 任何已有迁移
- ✅ 0 改 W-N-D++ / W-N-REVISE 决策文档
- ✅ 0 真跑 Celery task (派工 brief 严禁)
- ✅ 0 真写 DB (派工 brief 严禁)
- ✅ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 4.2 W-N-FILL 真派工决策 (主拍决策, 不擅自扩)

W-N-FILL-IMPL 实施完成仅是**探索路径**, 不代表 W-N-FILL 真派工决定.

**W-N-FILL 真派工**由**主拍决策**:
- 主拍需重新评估 W-N-D++ 3 门禁 + 新数据来源
- 主拍需新写决策文档 (派工 brief 严禁, 必须主拍书面批准)
- 主拍需明确书面批准 (CLAUDE.md / W-N-XX +1 留口 §2.4 三重阻断 + W-N-REVISE §4 (4) 阻断)

**W-N-FILL-IMPL 派工锚点**: W-N-FILL-IMPL +0/+1/+2 3 commits 据实累计 (W-N 周期第 15 stages).

### 4.3 锚点范式 (W-N 周期, 据实累计)

W-N 周期 14 stages 累计 ~35 commits 推 main, 锚点 W100 +75 ~537 → W-N-P3-A + W-N-GLITCH 收口 5 文件 untracked commit 推 main → W-N-FILL-IMPL +0/+1/+2 3 commits 据实累计.

锚点不撞 (派工 v11 段 9 规则下都是有效锚点):
- W-N-FILL-IMPL +0/+1/+2 (本任务)
- W-N-FILL +0/+1/+2 (未来派工, 仍空闲, 不撞 W-N-FILL-IMPL)

---

## 5. 沉淀文件清单 (W-N-FILL-IMPL 完整证据链)

| 类型 | 路径 | 状态 |
|------|------|------|
| 实施报告 | `docs/w-n-fill-impl-2026-08-06.md` | ✅ W-N-FILL-IMPL +1 commit |
| 起步 memory | `memory/w-n-fill-impl-startup-2026-08-06.md` | ✅ W-N-FILL-IMPL +0 commit |
| 收口 memory | `memory/w-n-fill-impl-closure-2026-08-06.md` | ✅ pending commit (W-N-FILL-IMPL +2) |
| Service 层 | `app/services/late_embedding_backfill.py` | ✅ W-N-FILL-IMPL +1 commit |
| CLI 脚本 | `scripts/backfill_late_embedding.py` | ✅ W-N-FILL-IMPL +1 commit |
| Unit test | `tests/test_w_n_fill_impl_backfill.py` | ✅ W-N-FILL-IMPL +1 commit |

---

## 6. 关联文件

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

**W-N-FILL-IMPL +2 收口完成. 5 件套守恒守恒 (alembic 1 head / DB version 守恒 / 12/12 PASS / 0 production code 改动 / 锚点 W-N-FILL-IMPL +0/+1/+2 据实累计). W-N-D++ §5 决策不修订, W-N-FILL 继续拦截. 派工 brief 严禁真跑. W-N-FILL 真派工由主拍决策, 不擅自扩. W19 选项 A 维持.**
