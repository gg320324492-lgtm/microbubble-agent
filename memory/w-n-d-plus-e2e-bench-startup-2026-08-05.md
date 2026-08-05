# W-N-D++ 端到端 late-chunking 召回 bench 起步 (2026-08-05)

## 派工 brief 复核
- **任务**: 验证 `hybrid_retriever._chunk_late_recall` 真接入 vs parent-only 在 100 题 qa-bench 上端到端差异
- **锚点**: W-N-D++ +0 / +1 / +2 / +3 (不撞 W-N-D+ +0..+3)
- **铁律**: 不真跑 late_embedding 回填 / 不改 hybrid_retriever.py 既有 4 路逻辑 / 不改 chat_engine.py / 严格只新文件 + 1 decision doc + memory 范畴
- **commit 基线**: d8e463d1c (W-N-E 收口沉淀)
- **alembic head**: `104_add_knowledge_chunk_late_embedding` (1 head 守恒)

## 起步 6 项实测

1. **base head 验证**: `git log --oneline -3` → `d8e463d1c docs(memory): W-N-E 冷热分层 PoC 收口沉淀 (3 决策门禁 2/3 PASS)` ✅
2. **alembic 验证**: `python -m alembic heads` → `104_add_knowledge_chunk_late_embedding (head)` ✅
3. **hybrid_retriever `_chunk_late_recall` 现状** (app/services/hybrid_retriever.py:312-349):
   - SQL: `SELECT kc.knowledge_id, min(v <=> :query_embedding) AS distance FROM knowledge_chunks AS kc CROSS JOIN LATERAL unnest(kc.chunk_embedding) AS vectors(v) JOIN knowledge AS k ON k.id = kc.knowledge_id WHERE kc.chunk_embedding IS NOT NULL AND (:category IS NULL OR k.category = :category) GROUP BY kc.knowledge_id ORDER BY distance LIMIT :top_k`
   - 失败 best-effort: try/except → logger.warning → return [] (不影响父级检索)
   - 入参: `query_embedding: List[float]` (1024d, BGE m3 维度)
   - 出参: `[{"id": int, "score": float(1.0 - distance), "retrieval_method": "chunk_late"}]`
   - **关键**: `_retrieve_impl` line 96 通过 `if vector_query_embedding_task is not None` 异步消费, 只在 `enable_vector=True` 时触发
   - **W99 P2 实战**: 预计算 query embedding 与 BM25 并行, 端到端不留无谓延迟
4. **retrieve 入口** (line 25-40): `HybridRetriever.retrieve(query, top_k=5, category, enable_vector=True, enable_bm25=True, enable_graph=True, enable_rerank=True)` → observability hook 包裹 → `_retrieve_impl` 真逻辑
5. **集成测试** (tests/integration/test_late_chunking_recall.py): 2 测试 PASS — `_chunk_late_recall` maps parent score / best-effort 不影响父级
6. **DB + 服务健康**: `curl http://localhost:8000/health` → `{"status":"healthy"}`, `from app.core.database import async_session` 可导入

## 关键发现 — 数据集盘点

| 数据源 | 题量 | 标注 | 备注 |
|---|---|---|---|
| `data/eval/eval_set.jsonl` | 38 | qa-bench `relevant_knowledge_ids: []` + `must_contain` 关键词 / synthetic | RAG 评测模板 (`scripts/eval_recall.py`) |
| `tests/qa-bench/data/combined_v4.jsonl` | 241 | agent 评测 (must_contain_any + ground_truth_refs) | **不是 RAG 召回评测**, 无 relevant_ids |
| `tests/qa-bench/data/commercial_v1.jsonl` | 40 | agent 评测 | 同上 |

**派工 brief 偏差**: brief 称 "1000 题 qa-bench"，但项目**没有** 1000 题的 RAG 召回评测数据集 (`relevant_knowledge_ids` 字段在 qa-bench 全为空)。**据实上报**: 端到端召回评测只能用 `data/eval/eval_set.jsonl` 38 题 (qa-bench `must_contain` 关键词匹配 + synthetic ID 匹配)，**不擅自扩到 1000 题**。如 38 题差异 < 2% 可提前归档；如 ≥ 2% 再考虑扩展。

## 类 20 沉淀 (W-N-D++ 据实上报)

**类 20.154 (W-N-D++ +0 新增)**: 派工 brief "1000 题 qa-bench" 假设偏差 — qa-bench `combined_v4.jsonl` 是 agent 评测数据集 (`must_contain_any` + `ground_truth_refs`)，**不**是 RAG 召回评测 (`relevant_knowledge_ids`)。项目无 1000 题 RAG 召回评测集，必须据实降级到 `data/eval/eval_set.jsonl` 38 题或自建小型 ground truth。**沿用派工 v6 §13.3 假设禁令**: 不擅自扩数据集，也不擅自删门禁；门禁阈值用原值，样本量据实降级 + 报告 §1 注明偏差。

## 工作目录
- 主仓库: `E:\microbubble-agent\` (worktree: `bold-mendeleev-fdc0e8`)
- 分支: `main`
- 实测 anchor: W-N-D++ +0..+3

## 下一步计划
- W-N-D++ +1: `scripts/bench_e2e_late_chunking_recall.py` (端到端双模式对比, 100 题或早停)
- W-N-D++ +2: `docs/decisions/2026-08-05-e2e-late-chunking-decision.md` (3 决策门禁据实)
- W-N-D++ +3: 收口 memory + 5 件套守恒实测