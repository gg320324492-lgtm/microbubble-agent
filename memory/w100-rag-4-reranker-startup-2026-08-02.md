# W100-RAG-4 Reranker v2 起步 memory (2026-08-02)

## 任务标识

- **任务**: W100-RAG-4 Reranker v2 多 backend 派工
- **派工 plan**: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 4 段
- **派工 brief v4.1**: 6 必读段 + 件 4 四门控 (本任务新增门控 D)
- **派工 anchor**: W100 +0..+5 (5 commits + 1 docs = 6 commits)
- **派工日期**: 2026-08-02
- **任务模式**: 主指挥协调范式第 N+1 次派工 (W100-RAG 系列 第 4 个)

## 派工前提实测

| 项 | 实测值 | 派工 brief 期望 | 偏差据实 |
|----|--------|----------------|----------|
| base ref | `599c9605b` (W100-RAG-3 收口后) | `599c9605b` | 0 |
| alembic HEAD | `095_add_rag_citation_metrics` | 不动 schema | 0 |
| worktree path | `E:\microbubble-agent\.claude\worktrees\w100-rag-4` | w100-rag-4 | 0 |
| worktree branch | `worktree-agent-w100-rag-4` | worktree-agent-w100-rag-4 | 0 |
| **RerankerService 接口名** | `rerank` (sync) + `rerank_async` (async) 双签名 | 派工 plan 估"rerank" | **1 处偏差据实** |

## 派工 plan 偏差 1 处 (类 20.123)

派工 plan 假设"RerankerService 接口名是 rerank", 实测是 `rerank` (sync) + `rerank_async` (async) 双签名.
派工前 Read `app/services/reranker_service.py` 全文确认, 沿用现有 `rerank_async` async 接口.

## 派工纪律 (CLAUDE.md 已落库)

1. **派工 v6 §13.3 假设禁令**: 派工前 Read 源码 (RerankerService 接口偏差已据实)
2. **类 20.115 实战 (W99 S-series)**: commit + 报告主指挥, 不自己 merge
3. **类 20.127 (本任务新增)**: 92% acceptance gate 失败必 raise, 不静默降级
4. **类 20.128 (本任务新增)**: CrossEncoder 默认 backend, 不破坏 W75 baseline (93.5%)
5. **类 20.129 (本任务新增)**: acceptance gate 用 id 匹配原始索引, 避免空 original_index 误判
6. **件 4 四门控守恒**: hybrid_retriever + knowledge_service + rag_evaluator + reranker_service def diff 全 0
7. **0 production code 守恒**: 件 4 四门控实测 = 0 (新增 def 不计入既有 def 修改)
8. **类 20.123**: 派工 plan 偏差据实 (RerankerService 接口名)

## 实施 6 commits (锚点 +6 据实)

1. `40579ef4e` W100 +0: feat(rag/reranker): 新增 reranker_v2.py (411 行, 3 backend + 92% gate)
2. `05a08fb28` W100 +1: feat(rag/reranker): config 新增 RERANKER_BACKEND/MODEL/API_KEY/ACCEPTANCE_GATE 4 项
3. `92efd7247` W100 +2: feat(rag/reranker): hybrid_retriever 入口加 reranker v2 hook
4. `d0ec79510` W100 +3: feat(rag/reranker): reranker_service 加 get_reranker_instance 工厂
5. `79ed2b4ba` W100 +4: test(rag/reranker): 单测 20 + e2e 16 (含 acceptance gate 验证)
6. W100 +5: scripts/qa-bench/reranker_eval.py + docs + memory (本 commit)

派工 brief 估 6 commits, 实测 6 守恒.

## 文件清单

### 新增 (5 文件)
- `app/services/reranker_v2.py` (411 行)
- `tests/rag/test_reranker_v2.py` (单测 20, 实测 20/20 PASS)
- `tests/rag/test_rag_reranker_e2e.py` (e2e 16, 实测 16/16 PASS)
- `scripts/qa-bench/reranker_eval.py` (派工 brief 估 100 行, 实测 200 行)
- `docs/rag/W100-RAG-4-reranker.md` (runbook)
- `memory/w100-rag-4-reranker-startup-2026-08-02.md` (本文件)

### 修改 (3 文件, 仅追加)
- `app/rag/config.py` (+15 行, RERANKER_* 4 项配置)
- `app/services/hybrid_retriever.py` (+31 行, reranker hook)
- `app/services/reranker_service.py` (+32 行, get_reranker_instance 工厂)

### 件 4 四门控实测 (本任务新增门控 D)

| 门控 | 文件 | 实测结果 |
|------|------|----------|
| A | `app/services/knowledge_service.py` | 0 ✅ |
| B | `app/services/hybrid_retriever.py` | 0 ✅ |
| C | `app/services/rag_evaluator.py` | 0 ✅ |
| D (本任务新增) | `app/services/reranker_service.py` | 0 ✅ (新增 `get_reranker_instance` 仅 ADD 不修改既有 def) |

## 待主指挥合并

- worktree path: `E:\microbubble-agent\.claude\worktrees\w100-rag-4`
- branch: `worktree-agent-w100-rag-4`
- 6 commits ahead of base `599c9605b`
- 预计 main merge 后锚点 505 → 511 (+6 据实)
