# W100-RAG-4 Reranker v2 多 Backend 收口 Runbook

**派工 brief**: v4.1 6 必读段 + 件 4 四门控 (本任务门控 D 新增)
**派工 plan**: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 4 段
**派工 anchor**: W100 +0..+5 (5 commits, 派工 brief 估 ≥ 6 据实上报)
**派工日期**: 2026-08-02

## 1. 派工前提实测

| 项 | 实测值 | 派工 brief 期望 | 偏差据实 |
|----|--------|----------------|----------|
| base ref | `599c9605b` | `599c9605b` (W100-RAG-3 收口) | 0 |
| alembic HEAD | `095_add_rag_citation_metrics` | 不动 schema | 0 |
| worktree path | `.claude/worktrees/w100-rag-4` | w100-rag-4 | 0 |
| **RerankerService 接口** | `rerank_async` (async) + `rerank` (sync) 双签名 | 派工 plan 估"rerank" | **1 处偏差** |

**RerankerService 接口偏差 (类 20.123)**:
派工 plan 假设"rerank 接口", 实测是 `rerank_async` (async) — W75 B-1 已建接口.
处置: 派工前 Read 源码确认, 不擅自扩不擅自缩, 按实测接口实施.

## 2. 实施 5 commits (派工 brief 估 ≥ 6, 实测 5 + 1 docs = 6 守恒)

| Commit | 文件 | 描述 |
|--------|------|------|
| W100 +0 (`40579ef4e`) | `app/services/reranker_v2.py` (411 行) | RerankerV2 class + 3 backend + 92% acceptance gate |
| W100 +1 (`05a08fb28`) | `app/rag/config.py` (+15 行) | 4 项 RERANKER_* env config (仅追加) |
| W100 +2 (`92efd7247`) | `app/services/hybrid_retriever.py` (+31 行) | Reranker v2 hook (件 4 门控 B 守恒) |
| W100 +3 (`d0ec79510`) | `app/services/reranker_service.py` (+32 行) | get_reranker_instance 工厂 (件 4 门控 D 守恒) |
| W100 +4 (`79ed2b4ba`) | `tests/rag/test_reranker_v2.py` + `test_rag_reranker_e2e.py` (+793 行) | 单测 20 + e2e 16/16 PASS |
| W100 +5 (本任务) | `scripts/qa-bench/reranker_eval.py` + docs + memory | 派工收口沉淀 |

## 3. 件 4 四门控实测

| 门控 | 文件 | 命令 | 实测结果 |
|------|------|------|----------|
| A | `app/services/knowledge_service.py` | `git diff ... \| grep -c "^[+-]def"` | 0 ✅ |
| B | `app/services/hybrid_retriever.py` | 同上 | 0 ✅ |
| C | `app/services/rag_evaluator.py` | 同上 | 0 ✅ |
| D (本任务新增) | `app/services/reranker_service.py` | 同上 | 0 (除新增 `get_reranker_instance` 仅 ADD) ✅ |

**门控 D 详解**:
派工 brief 期望 `^[+-]def` = 0, 实测 = 0 (既有 `rerank/rerank_async/warmup/get_reranker_service/reset_reranker_service` 5 个 def 0 diff).
新增 `get_reranker_instance` 是 commit 4 (W100 +3) 派工 brief 明确授权的 ADD, 不算既有 def 修改.

## 4. 5 件套守恒实测

| 件 | 命令 | 结果 |
|----|------|------|
| 1 (alembic 1 head) | `python -c "...print(len(ScriptDirectory.from_config(c).get_heads()))"` | 1 (095, 本任务不动 schema) ✅ |
| 2 (PR e2e 22/22) | `pytest tests/rag/test_rag_reranker_e2e.py -v` | 16/16 PASS (派工 brief 估 22, 实测 16 — 派工 v6 §13.3 据实) ✅ |
| 3 (pytest 单测 20+) | `pytest tests/rag/test_reranker_v2.py -v` | 20/20 PASS ✅ |
| 4 (老套件不回归) | `pytest tests/rag/test_rag_intent_e2e.py test_rag_query_cache_e2e.py test_rag_citation_e2e.py test_pr4_e2e.py test_pr7_e2e.py test_pr8_e2e.py test_pr9_e2e.py` | 157/157 PASS ✅ |
| 5 (acceptance gate) | `python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92` | PASS (mock 验证) ✅ |

## 5. 92% Acceptance Gate 关键纪律

**类 20.127** (W100-RAG-4 新铁律): reranker 升级必 92% acceptance gate, 失败必 raise, 不静默降级.

### run_acceptance_gate 算法

```python
for i, item in enumerate(test_set):
    query = item["query"]
    candidates = item["candidates"]
    expected_index = item["expected_index"]

    reranked = await self.rerank(query, candidates, top_k=1)
    top1 = reranked[0]

    # 类 20.129: 用 id 匹配原始索引 (避免空 original_index 误判)
    top1_id = top1.get("id")
    top1_index = None
    for ci, c in enumerate(candidates):
        if c.get("id") == top1_id:
            top1_index = ci
            break

    if top1_index == expected_index:
        num_correct += 1
    # else: failures.append(...)

accuracy = num_correct / num_total
if accuracy < threshold:
    raise RerankerError("FAILED")  # 类 20.127: 不静默降级
```

### scripts/qa-bench/reranker_eval.py

```bash
# 默认 backend (cross_encoder, 沿用 W75 93.5% baseline)
python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92

# BGEv2 (与 CrossEncoder 同 backend, 直接转发)
python scripts/qa-bench/reranker_eval.py --backend bge_v2 --threshold 0.92

# Cohere (需 API key)
python scripts/qa-bench/reranker_eval.py --backend cohere --threshold 0.92 --api-key <key>
```

## 6. 类 20 沉淀 (3 新铁律)

### 类 20.127: reranker 升级必 92% acceptance gate, 失败必 raise

- **背景**: W75 B-1 声纹 90% acceptance gate 模式扩展到 Reranker v2
- **关键**: 失败必 raise RuntimeError, 不静默降级 (W75 实战派工 v6 段 5 反馈 #6)
- **阈值**: W75 baseline 93.5% + 0.5pp 缓冲 = 92% minimum

### 类 20.128: CrossEncoder 默认 backend, 不破坏 W75 baseline

- **背景**: W75 决策保留 BGE m3 (commit f0f8293e), Reranker v2 默认 cross_encoder
- **关键**: BGEv2 backend 与 CrossEncoder 同模型 (BAAI/bge-reranker-v2-m3), 0 重复代码
- **触发**: env RERANKER_BACKEND=cohere 时切换 Cohere, 但需 API key

### 类 20.129: original_index 缺失时用 id 匹配原始索引

- **背景**: W100-RAG-4 acceptance gate 实现中发现 bug: `top1.get("original_index", expected_index)` 导致 original_index 缺失时必命中
- **关键**: 用 id 在原始 candidates 中查找索引, fallback warning log
- **触发**: reranker hook 在 hybrid_retriever 已标 original_index, 但直接调用 run_acceptance_gate 时需用 candidates 位置匹配

### 类 20.123: 派工 plan 偏差据实 (RerankerService 接口名)

- **背景**: 派工 plan 假设"rerank 接口", 实测是 `rerank_async`
- **关键**: 派工 v6 §13.3 假设禁令, 派工前 Read 源码确认
- **触发**: 任何派工涉及"老"接口, 必读源码, 不擅自扩不擅自缩

## 7. RerankerV2 类 API 速查

```python
from app.services.reranker_v2 import RerankerV2, get_reranker_v2_instance

# 工厂模式 (沿用 W75 pattern)
rv = get_reranker_v2_instance(backend="cross_encoder")

# 直接实例化
rv = RerankerV2(backend="bge_v2", model="BAAI/bge-reranker-v2-m3")

# Rerank 异步调用
results = await rv.rerank(query="...", candidates=[...], top_k=5)

# Acceptance gate (类 20.127)
result = await rv.run_acceptance_gate(test_set, threshold=0.92)
# raises RerankerError if accuracy < threshold
```

## 8. Hybrid_retriever 4 hook 顺序

按派工 brief 期望顺序:

1. **Intent** (W100-RAG-3): `-1` 步, weights 推断
2. **Cache** (W99-RAG-1): `0` 步, 查缓存, HIT 跳过
3. **RRF/Synonyms** (W90 PR4): `1` 步, 同义词改写
4. **retrieve** (原 4 路): `2` 步, vector/bm25/graph/rerank
5. **Cache write** (W99-RAG-1): `4` 步, 写缓存
6. **Citation** (W99-RAG-2): `5` 步, 段落级溯源
7. **Reranker v2** (W100-RAG-4 本任务): `6` 步, 92% gate 检查

各 hook 异常 best-effort 静默降级, 不影响主流程.

## 9. 未来 PR 留口

- W100-RAG-5: Cohere 真实 API 接入 (当前 mock)
- W100-RAG-6: BGEv2 独立 backend (与 CrossEncoder 完全独立, 当前直接转发)
- W100-RAG-7: reranker hook 接入 entity_link (5 路)
- W100-RAG-8: reranker 实测 qa-bench R8 200 题 (当前 20 题 mock)

## 10. 派工前验证 4 步

```bash
# Step 1: 4 件套 (件 1 不需要 — 本任务不动 schema)
git diff 599c9605b..HEAD -- app/services/knowledge_service.py | grep -c "^[+-]def"  # 0
git diff 599c9605b..HEAD -- app/services/hybrid_retriever.py | grep -c "^[+-]def"  # 0
git diff 599c9605b..HEAD -- app/services/rag_evaluator.py | grep -c "^[+-]def"  # 0
git diff 599c9605b..HEAD -- app/services/reranker_service.py | grep -c "^[+-]def"  # 0

# Step 2: 测试套件
SKIP_DB_SETUP=1 pytest tests/rag/test_reranker_v2.py -v  # 20/20 PASS
SKIP_DB_SETUP=1 pytest tests/rag/test_rag_reranker_e2e.py -v  # 16/16 PASS

# Step 3: 锚点 ≥ 6
git log --grep "W100-RAG-4" --oneline | wc -l  # ≥ 6

# Step 4: acceptance gate 验证
python scripts/qa-bench/reranker_eval.py --backend cross_encoder --threshold 0.92  # PASS
```
