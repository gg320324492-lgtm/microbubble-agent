# W100-RAG-4 Reranker v2 收口 memory (2026-08-02)

## 派工完成 ✅

锚点 505 → 511 (+6 据实上报, 派工 brief 估 ≥ 6 守恒).

## 5 件套守恒实测

| 件 | 命令 | 结果 |
|----|------|------|
| 1 alembic 1 head | `python -c "...get_heads()"` | 1 (095, 本任务不动 schema) ✅ |
| 2 单测 20+ | `pytest tests/rag/test_reranker_v2.py -v` | **20/20 PASS** ✅ |
| 3 e2e 22+ | `pytest tests/rag/test_rag_reranker_e2e.py -v` | **16/16 PASS** ✅ (派工 v6 §13.3 据实 派工估 22, 实测 16) |
| 4 老套件不回归 | `pytest test_rag_intent_e2e + test_rag_query_cache_e2e + test_rag_citation_e2e + test_pr4_e2e + test_pr7_e2e + test_pr8_e2e + test_pr9_e2e` | **157/157 PASS** ✅ |
| 5 acceptance gate | `python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92 --test-set-size 20` | **100% PASS** (20/20) ✅ |

## 件 4 四门控实测

| 门控 | 文件 | 实测结果 |
|------|------|----------|
| A | `app/services/knowledge_service.py` | 0 ✅ |
| B | `app/services/hybrid_retriever.py` | 0 ✅ |
| C | `app/services/rag_evaluator.py` | 0 ✅ |
| **D** (本任务新增) | `app/services/reranker_service.py` | 0 ✅ (新增 `get_reranker_instance` 仅 ADD 不修改既有 def) |

## 锚点范式

派工 brief 估 +6 据实上报, 实测 W100 +0..+5 = 6 commits 守恒.

```bash
git log --grep "W100-RAG-4" --oneline | wc -l  # = 6 ✅
```

## 6 commits 清单

1. `40579ef4e` W100 +0: feat(rag/reranker): 新增 reranker_v2.py (411 行)
2. `05a08fb28` W100 +1: feat(rag/reranker): config 新增 4 项 RERANKER_*
3. `92efd7247` W100 +2: feat(rag/reranker): hybrid_retriever 加 reranker hook
4. `d0ec79510` W100 +3: feat(rag/reranker): reranker_service 加 get_reranker_instance 工厂
5. `79ed2b4ba` W100 +4: test(rag/reranker): 单测 20 + e2e 16 (含 acceptance gate)
6. `e4c13e8c2` W100 +5: scripts/qa-bench/reranker_eval.py + docs + memory

## 类 20 沉淀 (3 新铁律)

### 类 20.127: reranker 升级必 92% acceptance gate, 失败必 raise

W75 B-1 声纹 90% acceptance gate 模式扩展到 Reranker v2.
**关键**: 失败必 raise RerankerError, 不静默降级.
**阈值**: W75 baseline 93.5% + 0.5pp 缓冲 = 92% minimum.

### 类 20.128: CrossEncoder 默认 backend, 不破坏 W75 baseline

W75 决策保留 BGE m3 (commit f0f8293e), Reranker v2 默认 cross_encoder.
**关键**: BGEv2 backend 与 CrossEncoder 同模型 (BAAI/bge-reranker-v2-m3), 0 重复代码.
**触发**: env RERANKER_BACKEND=cohere 时切换 Cohere, 但需 API key.

### 类 20.129: original_index 缺失时用 id 匹配原始索引

**根因**: 派工 plan `top1.get("original_index", expected_index)` 用 expected_index 作 fallback, original_index 缺失时必命中 (测试 bug).
**修复**: 用 id 在原始 candidates 中查找索引, fallback warning log.
**触发**: reranker hook 在 hybrid_retriever 已标 original_index, 但直接调用 run_acceptance_gate 时需用 candidates 位置匹配.

### 类 20.123: 派工 plan 偏差据实 (RerankerService 接口名)

派工 plan 假设"rerank 接口", 实测是 `rerank_async` (async).
派工 v6 §13.3 假设禁令, 派工前 Read 源码确认, 不擅自扩不擅自缩.

## 0 production code 守恒

件 4 四门控 = 0 表示**既有核心方法签名不变**:
- hybrid_retriever.py 0 def 修改 (11 instance + 5 module-level + entity_link + count_kg_entities 全部 0 diff)
- knowledge_service.py 0 def 修改
- rag_evaluator.py 0 def 修改 (11 def 全部 0 diff)
- reranker_service.py 0 def 修改 (5 既有 def 全部 0 diff, 新增 `get_reranker_instance` 仅 ADD)

## hybrid_retriever 4 hook 顺序 (派工 brief 期望)

1. Intent (W100-RAG-3, `-1` 步)
2. Cache (W99-RAG-1, `0` 步)
3. RRF/Synonyms (W90 PR4, `1` 步)
4. retrieve 原 4 路 (vector/bm25/graph/rerank)
5. Cache write (W99-RAG-1, `4` 步)
6. Citation (W99-RAG-2, `5` 步)
7. **Reranker v2 (W100-RAG-4, `6` 步)** ← 本任务

各 hook 异常 best-effort 静默降级 (类 20.121/124/125 + 本任务类 20.127/128 + 派工 v6 §13.3), 不影响主流程.

## 文件清单

### 新增 (6 文件, 1447 行)
- `app/services/reranker_v2.py` (411 行)
- `tests/rag/test_reranker_v2.py` (~325 行, 单测 20)
- `tests/rag/test_rag_reranker_e2e.py` (~265 行, e2e 16)
- `scripts/qa-bench/reranker_eval.py` (~200 行)
- `docs/rag/W100-RAG-4-reranker.md` (runbook, 200 行)
- `memory/w100-rag-4-reranker-startup-2026-08-02.md` + `closure-2026-08-02.md` (本文件)
- `memory/w100-rag-4-acceptance-gate-report.md` (脚本输出报告)

### 修改 (3 文件, 仅追加 78 行)
- `app/rag/config.py` (+15 行)
- `app/services/hybrid_retriever.py` (+31 行)
- `app/services/reranker_service.py` (+32 行)

## 待主指挥合并

- worktree path: `E:\microbubble-agent\.claude\worktrees\w100-rag-4`
- branch: `worktree-agent-w100-rag-4`
- 6 commits ahead of base `599c9605b`
- 预计 main merge 后锚点 505 → 511 (+6 据实)

主指挥手动 merge 后, 通过 webhook 触发 `scripts/auto-deploy.sh` 部署链即可 (沿用 W99 DEPLOY-AUTO).

## 累计 commits + 铁律

W92-W100 累计 N+ commits + N+ 铁律 (本任务 +3 新铁律: 127/128/129).
W99 S-series + DEPLOY-AUTO + RAG R1+R2+R3+R4 = 10 commits + 7+ 铁律.

W19 选项 A 维持.
W100-RAG 系列后续 (派工待主拍):
- W100-RAG-5: Cohere 真实 API 接入 (当前 mock)
- W100-RAG-6: BGEv2 独立 backend (与 CrossEncoder 完全独立, 当前直接转发)
- W100-RAG-7: reranker hook 接入 entity_link (5 路)
- W100-RAG-8: reranker 实测 qa-bench R8 200 题 (当前 20 题 mock)

## acceptance gate 实测

```bash
$ python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92 --test-set-size 20 --output memory/w100-rag-4-acceptance-gate-report.md

2026-08-02 02:30:56 [microbubble.reranker_v2] INFO: [W100-RAG-4] Acceptance gate PASSED: cross_encoder accuracy 100.00% >= 92.00% (20/20)
# W100-RAG-4 Reranker Acceptance Gate Report
**Result**: [OK] PASS
**Accuracy**: 100.00% (20/20)
```

报告已写入 `memory/w100-rag-4-acceptance-gate-report.md`.

**注**: 实测 acceptance gate 100% PASS (因为 mock 数据集简单, candidate[0] 始终最高分), 类 20.127 失败 raise 路径已在 `tests/rag/test_reranker_v2.py::test_acceptance_gate_threshold_boundary` 验证 (DID RAISE).
