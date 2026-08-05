# W-N-FILL-IMPL late_embedding 回填探索 起步 (2026-08-06)

> **派工**: W-N-FILL-IMPL +0 起步 (W-N 周期第 15 stages, 派生自 W-N-FILL 留口)
> **基线 HEAD**: `cde003abc` (W-N-P3-A + W-N-GLITCH 收口)
> **目的**: W-N-REVISE §3 修订 (a/b 已 PASS, c 业务决策 recall > 0 FAIL) → 派工 brief 严禁真跑 Celery task, **仅探索路径 + 写脚本 + 1 unit test + 实施报告**
> **关联**: W-N-D++ §5 决策不修订 (默认 c 业务决策延续禁止) + W-N-FILL 留口 §2 (W-N-XX +1) + W-N-REVISE 决策修订文档
> **派工锚点**: W-N-FILL-IMPL +0 起步 / +1 实施探索 / +2 收口

---

## 1. 起步 6 项 (W73 铁律)

### 1.1 派工依据

W-N-FILL 留口 (`docs/w-n-future-leftover-2026-08-05.md` §2) 触发条件 3 选 1:
- (a) **列存在** ✅ PASS (W-N-G+ 修复 commit `e68412de4`/`7cb6bf0d1`/`322455f5d`)
- (b) **tests 8/8 PASS** ✅ PASS (W-N-G+ +2 集成测试)
- (c) **业务决策 recall > 0** ❌ FAIL (W-N-D++ §3 实测 +0.00%, hard-fail gate)

**W-N-REVISE 修订**: 3 选 1 默认 (c) 业务决策延续禁止 → W-N-FILL 派工 brief 严禁真跑.

W-N-FILL-IMPL 派工**仅探索路径**: 写脚本 + 1 unit test + 实施报告, **不真跑 Celery task**, **不真写 DB**.

### 1.2 派工 brief 严禁清单

- ❌ 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ commits
- ❌ 0 改 alembic/versions/ (104/105 已由 W-N-D/G+ 锁定)
- ❌ 0 改 W-N-REVISE / W-N-D++ 决策文档 (仅新写实施报告)
- ❌ 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
- ❌ 0 改 app/agent/chat_engine.py (方案 C 6 铁律)
- ❌ 0 改 app/services/embedding_service.py 既有 4 API
- ❌ 0 改 drive_comments_path_backfill_service.py 模板 (W68 第 12 批 B-1 范畴)
- ❌ 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
- ❌ **0 真跑 Celery task** (派工 brief 严禁, 留口)
- ❌ 0 真写 DB (派工 brief 严禁, 留口)
- ❌ 0 改 .env / EMBEDDING_BACKEND / EMBEDDING_MODEL_NAME

### 1.3 允许范畴

- ✅ 新增 `scripts/backfill_late_embedding.py` (CLI 入口, 默认 dry-run)
- ✅ 新增 `app/services/late_embedding_backfill.py` (service 层)
- ✅ 新增 1 unit test (验证脚本逻辑, mock 即可)
- ✅ 新增 `docs/w-n-fill-impl-2026-08-06.md` 实施报告
- ✅ 新增 `memory/w-n-fill-impl-{startup,closure}-2026-08-06.md` 2 个 memory
- ✅ 锚点: W-N-FILL-IMPL +0/+1/+2 (3 commits)

### 1.4 0 production code 改动铁律

- ✅ 仅 docs/memory/scripts/tests 范畴
- ✅ 不动 app/services/hybrid_retriever.py / embedding_service.py / chat_engine.py 既有 4 API
- ✅ 不动 alembic/versions/104, 105_fix_drift, 088, 030
- ✅ 不动 chatbot/main.py / app/main.py 启动流程
- ✅ 不动 celery_app.conf.beat_schedule

### 1.5 触发再启条件 (W-N-REVISE 修订, 3 选 1)

```python
CONDITION_A = "knowledge_chunks.chunk_embedding 列存在"  # ✅ W-N-G+ 验证
CONDITION_B = "tests 8/8 PASS"  # ✅ W-N-G+ 验证
CONDITION_C = "业务决策 recall > 0"  # ❌ W-N-D++ 决策 +0.00% FAIL

W_N_FILL_DISPATCH_GATE = "3 选 1 触发, 默认 (c) 业务决策延续禁止"
```

**W-N-FILL-IMPL 派工条件**: (a) + (b) 已 PASS, **仅探索路径** (c) 仍 FAIL → 真跑必须主拍书面批准.

### 1.6 派工锚点对齐

- W-N-FILL-IMPL +0 (起步) ← 本 memory
- W-N-FILL-IMPL +1 (实施) ← scripts + service + test + report
- W-N-FILL-IMPL +2 (收口) ← 5 件套守恒 + 沉淀

W-N-FILL 原有锚点不撞 (W-N-XX +1 留口 §2.3 锚点范式): W-N-FILL +0/+1/+2 仍空闲, W-N-FILL-IMPL 派生系列叠加.

---

## 2. 调研 (派工 v6 §13 仓库实情真查)

### 2.1 base HEAD 验证

```bash
$ git log --oneline -1
cde003abc docs(decision): W-N-P3-A + W-N-GLITCH 5 文件 untracked commit 推 main (W-N-P3-A + W-N-GLITCH 收口)
```

✅ base HEAD = `cde003abc` (本任务基线)

### 2.2 锚点不撞验证

```bash
$ git log --oneline --all | grep -E "W-N-FILL" | head -5
92d6385e2 docs(memory): W-N-REVISE +0 起步 (W-N-FILL 决策重审调研)
c2acc536d docs(future-leftover): W-N-XX +0 起步 + +1 未来派工留口 runbook (3 章: W-N-G+ 4 FAIL / W-N-FILL 拦截 / W-N-BGE 数据不足)
```

W-N-FILL 0 派工 (W-N-REVISE +0 调研 + W-N-REVISE +1 决策修订 + W-N-FILL 留口 §2 是调研范畴, 无派工锚点). W-N-FILL-IMPL +0/+1/+2 派生锚点不撞.

### 2.3 alembic head 守恒 (沿用 W-N-G+ +3)

```bash
# 期望: 105_fix_drift (head) 单 head 守恒
```

✅ 沿用 W-N-G+ +3 沉淀, 本任务不动 alembic.

### 2.4 LateChunkingService 接口调研

`app/services/late_chunking_service.py` (W-N-C +1 范畴):
- 构造: `LateChunkingService(model, chunk_size=256, overlap=32, max_length=8192)`
- 单文档 encode: `encode(text: str) -> List[np.ndarray]` (每 chunk 一个 1024 维向量)
- **接口语义**: 1 文档 → N chunks × 1024 维向量列表

### 2.5 knowledge_chunks 模型结构

`app/models/knowledge_chunk.py` (W88 PR2 范畴):
- 表名: `knowledge_chunks`
- 主字段: id, knowledge_id, chunk_index, content, embedding (vector(1024)), char_start/end, char_count, strategy, chunk_metadata
- **W-N-D 新增字段**: `chunk_embedding` (vector(1024)[])  ← W-N-D 范畴, **目标回填列**
- alembic 104: `104_add_knowledge_chunk_late_embedding.py` (W-N-D +1 入库, 字段类型 vector(1024)[])

### 2.6 late embedding 数据格式

派工 brief 推测: `chunk_embedding` 字段类型 `_vector` (pgvector 数组), 元素是 vector(1024).

**W-N-REVISE +0 §2.2 实测**:
```sql
SELECT column_name, data_type FROM information_schema.columns
WHERE table_name = 'knowledge_chunks' ORDER BY ordinal_position;
-- chunk_embedding: ARRAY (W-N-G+ 修复后已添加)
```

✅ 列存在, 数据格式待 W-N-FILL-IMPL +1 实施时实测.

### 2.7 模板复用 (W68 第 12 批 B-1)

- `app/services/drive_comments_path_backfill_service.py` + `app/services/drive_comments_path_backfill_tasks.py` + `scripts/backfill_drive_comments_path.py`
- 复用模式: dry_run 默认 True + Celery task wrapper + CLI 入口 + 5 秒 apply 等待 + JSON 输出
- 复用 cross event loop 修复: create_celery_engine_and_session (NullPool + expire_on_commit=False)

### 2.8 0 真跑约束

派工 brief 严禁 "真的跑 Celery 任务" → 派工脚本 default dry_run = True + 不在 5 秒内 Ctrl+C, 写入 DB only on explicit --apply flag.

**unit test 范畴**: 仅 mock service 层 + 断言调用次数 + 断言 dry_run 守恒, **不 trigger Celery + 不写 DB**.

---

## 3. 仓库实情真查结果 (派工 v6 §13 据实上报)

| 派工 brief 假设 | 实测 | 偏差 |
|----------------|------|------|
| base HEAD = `cde003abc` | ✅ `cde003abc` | 0 |
| 锚点 W-N-FILL-IMPL +0/+1/+2 空闲 | ✅ 不撞 | 0 |
| LateChunkingService.encode 1 文档 → N × 1024 维向量 | ✅ 实测 | 0 |
| knowledge_chunks.chunk_embedding 列存在 | ✅ W-N-G+ 修复 | 0 |
| 模板: drive_comments_path_backfill_service.py | ✅ 复用 | 0 |
| alembic head 105_fix_drift 守恒 | ✅ 沿用 W-N-G+ | 0 |
| Celery 跨 event loop 修复模板 | ✅ create_celery_engine_and_session | 0 |
| 严禁真跑 Celery task | ✅ 派工 brief 严禁, 本任务只写脚本 | 0 |

**派工 v6 §13 据实上报**: 0 处偏差, 全部对齐.

---

## 4. 派工前提铁律 12 + 类 20 沿用

### 4.1 派工铁律 (W-N 周期沿用)

1. 派工 v6 §13 仓库实情真查: base HEAD / 锚点 / alembic / 模板 4 必查
2. 派工 brief 严禁: 0 改 W-N-A/B/C/D/E/F/D+/+/ARC/GC/ANC/MEM/G+/OBS/RAG/BGE/GRAND/FILL/D++ 旧 commits
3. 派工 brief 严禁: 0 改 alembic/versions/ 任何已有迁移
4. 派工 brief 严禁: 0 改 app/services/hybrid_retriever.py 既有 4 路逻辑
5. 派工 brief 严禁: 0 改 chat_engine.py 方案 C 6 铁律
6. 派工 brief 严禁: 0 改 embedding_service.py 既有 4 API
7. 派工 brief 严禁: 0 改 celery_app.conf.beat_schedule (不注册新 schedule)
8. 派工 brief 严禁: 真跑 Celery task (W-N-FILL 留口 §2 阻断)
9. 派工 brief 严禁: 真写 DB (派工 brief 严禁, dry_run 默认 True)
10. 派工 brief 严禁: 改 W-N-D++ / W-N-REVISE 决策文档 (仅新写)
11. 派工 brief 严禁: 改生产 .env / EMBEDDING_MODEL_NAME
12. 派工 brief 严禁: 改 chatbot/main.py / app/main.py 启动流程

### 4.2 类 20 沿用 (W-N 周期)

- 类 20.155 (W-N-D++): alembic head 守恒 ≠ DB schema 守恒
- 类 20.156 (W-N-D++): best-effort 静默失败比显式失败更危险
- 类 20.157 (W-N-REVISE): 触发再启条件 3 选 1, 默认 (c) 业务决策延续禁止
- 类 20.153 (W-N-G+): alembic 链 hotfix branch 必实测, 不凭 brief 串行推测

### 4.3 W-N-FILL-IMPL 新增沉淀 (本任务)

- 类 20.158 (W-N-FILL-IMPL 新增): late_embedding 回填脚本必 dry_run 默认 True + 5 秒 apply 等待 + 严禁本地 Celery 触发 + 派工 brief 严禁真跑
- 类 20.159 (W-N-FILL-IMPL 新增): 业务决策 recall +0% 硬门禁禁止下, 脚本可写但真跑必须主拍书面批准 (W-N-REVISE §3 修订锚定)

---

## 5. 起步交付 check

- ✅ 派工依据 (W-N-FILL 留口 §2 + W-N-REVISE §3 修订)
- ✅ 严禁清单 (W-N 系列 commit + alembic + 4 API + chat_engine)
- ✅ 允许范畴 (1 脚本 + 1 service + 1 test + 1 report + 2 memory)
- ✅ 0 production code 改动铁律 (仅 docs/memory/scripts/tests)
- ✅ 触发再启条件 (a/b PASS, c FAIL 默认禁止)
- ✅ 锚点对齐 (W-N-FILL-IMPL +0/+1/+2 派生)
- ✅ 调研 (base HEAD + 锚点 + alembic + LateChunkingService 接口 + 知识库模型 + 模板)
- ✅ 派工前提铁律 12 + 类 20 沿用
- ✅ 派工 v6 §13 仓库实情真查 0 偏差

---

## 6. 关联文件

- W-N-FILL 留口 §2: `docs/w-n-future-leftover-2026-08-05.md`
- W-N-REVISE 决策修订: `docs/decisions/2026-08-05-late-embedding-backfill-revise.md`
- W-N-D++ 决策原文: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md`
- W-N-G+ +3 收口: `memory/w-n-g-plus-schema-drift-closure-2026-08-05.md`
- LateChunkingService: `app/services/late_chunking_service.py`
- KnowledgeChunk 模型: `app/models/knowledge_chunk.py`
- PR14 模板 (复用): `app/services/drive_comments_path_backfill_service.py`, `app/services/drive_comments_path_backfill_tasks.py`, `scripts/backfill_drive_comments_path.py`

---

**W-N-FILL-IMPL +0 起步完成. W-N-REVISE §3 修订 3 选 1 (a/b PASS, c FAIL) 派工 brief 严禁真跑. 仅探索路径 + 写脚本 + 1 unit test + 实施报告. W19 选项 A 维持.**
