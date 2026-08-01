# W101 P1 RAG 索引重建工具起步确认 (2026-08-01)

## 起步 6 项 (W73 铁律 + W74 铁律)

### S1 git fetch origin + alembic heads verify
- HEAD: `f5acce8822d740f56c516e266487900e76cee712` (W100 P1 merge base)
- alembic 1 head: `093_add_search_log_answer_rating` (head) ✅ 单链守恒
- SyntaxWarning: alembic 028 file `\d` escape 不影响 (历史遗留, 非新引入)

### S2 CLAUDE.md §3 + 派工 v10.2 §13 必填 6 段
- §3 派工前提铁律 12 条 + 类 20 实战 20 实例
- §13 必填 6 段: 起步/范围/测试/守恒/反馈/据实上报

### S3 worktree 已切
- 路径: `E:/agent-w101-p1-reindex`
- branch: `chore/w101-p1-reindex` (基于 main f5acce882)

### S4 pytest 基线 (paper-pass)
- 现状: 228 个 test 文件, baseline 测试 a11y 报 fixture 错误 (与 W99/W100 派工预期一致 — 该 fixture 链不在 worktree 直跑必坏)
- **纪律**: 件 2 baseline pytest 6/6 PASS 针对**新测试 + 不破现有 mock 测试** (W99/W100 P1 派工 v10 §3 既有口径)

### S5 现有 scripts/ 真查
- ✅ `scripts/recompute_embeddings.py` 137 行 (同步单进程, 4 张表)
- ✅ `app/services/embedding_recalc.py` 236 行 (Celery 异步, 单条 + 全表 + 进度)
- ❌ 无 `scripts/reindex_*` / `scripts/recalc_*` / `scripts/embedding_recalc.py` (项 4 不变)
- ✅ `app/services/bm25_service.py` (BM25Service 类 + 6 函数)
- ✅ `app/services/bm25_incremental.py` (BM25IncrementalIndex 类 + 5 函数)
- ✅ alembic 089 加 `knowledge.content_tsvector` (GENERATED ALWAYS AS, 入库自动)

### S6 起步确认 (本文件)

## 派工目标 — W101 P1 RAG 索引重建工具

3 commits 拆分:
- [W101 +0] `scripts/reindex_all.py` 一键重建 CLI (embedding + BM25 + tsvector)
- [W101 +1] `scripts/reindex_monitor.py` 进度监控 + 失败重试
- [W101 +2] `tests/test_reindex_tools.py` 6/6 PASS + runbook

## 范围边界
- ❌ 不动 alembic schema (089 已加 tsvector, 093 head 守恒)
- ❌ 不动前端
- ✅ 仅新增 `scripts/reindex_*.py` + `tests/test_reindex_tools.py` + `docs/w101-p1-reindex-tools-2026-08-01.md`

## 现有工具复用 (派工 v10 段 5 反馈 #4a 老核心 unchanged)
- `app/services/embedding_recalc.py` 库不动 — `_get_embedding_text` + `_setup_independent_async_env` + `recalc_one_embedding` 复用
- `app/services/bm25_service.py` + `bm25_incremental.py` 库不动 — `get_bm25_service()` + `build_index()` 复用
- `scripts/recompute_embeddings.py` 保留 — 不破坏, 用户可继续用

## 关键文件
- `app/services/embedding_recalc.py:104` `_update_progress` 写 `embedding_recompute:progress:{table}` (24h TTL)
- `app/services/bm25_service.py:58` `build_index(documents)` — 接收 `List[dict]` 重置 BM25 索引
- alembic 089 → `knowledge.content_tsvector` GENERATED 列, 入库自动重算, **不需要单独 tsvector 重建**

