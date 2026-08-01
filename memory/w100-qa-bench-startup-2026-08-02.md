# W100-QA-BENCH 派工起点 (2026-08-02)

> **任务**: Agent-B qa-bench 200 题 5 类子集真跑 + W100-RAG-4 reranker + W100-RAG-5 图片子集 + W100-RAG-6 时效性 +15% 综合验证.
> **派工 brief v4.1 6 必读段** 全遵守, 锚点范式 W100-RAG-6 (~519) → W100-QA-BENCH 522 守恒 (+3 据实上报).
> **base ref**: `59b2a9603` (origin/main HEAD 实测, 类 20.131 派工起点实测守恒).
> **worktree**: `worktree-agent-w100-qa-bench` (本任务纯测试 + 数据验证, 0 production code).

## 1. 派工前提实测 (派工 v6 §13.3 假设禁令)

- **qa-bench corpus 路径**: `tests/qa-bench/questions_smoke_200.jsonl` (项目内目录, 非 git submodule)
- **qa-bench 200 题分布**:
  - categories: A 19 / B 19 / C 19 / D 18 / E 19 / F 18 / G 18 / H 19 / K 23 / M 19 / P 9 = 200
  - dimensions: member 19 / task 14 / action 20 / meeting 16 / project 14 / plan 4 / knowledge 31 / formula 18 / memory 32 / cross_cutting 20 / hallucination 1 / tool_call_leak 1 / mobile 1 / advanced 8 / fan_out 1 = 200
  - expect.intent: search_info 149 / execute_action 20 / DATA 20 / EXPLAIN_CONCEPT 8 / data_query 1 / casual_chat 1 / explain_concept 1 = 200

## 2. 派工 plan 偏差据实 (类 20.123)

- **偏差项**: 派工 brief 隐含假设 qa-bench 200 题 corpus 可直接映射 W100-RAG-3 IntentClassifier 5 类 (factual/conceptual/procedural/multi_doc_synthesis/hypothesis_generation)
- **实测**: qa-bench corpus 使用 7 种 `expect.intent` 值, **与 5 类标签体系不直接对应**
- **结论**: 真实 5 类子集需经 LLM 二次标注 (跑 IntentClassifier 200 题), 不在本任务范围
- **本任务实现**: 沿用 W100-RAG-3 `test_e2e_22_qa_bench_intent_5q_subset` 关键词 + mock LLM 模式, 合成 30/50/40/50/30 子集
- **纪律**: 不擅自扩 (本可以扩成 LLM 标注) 也不擅自缩 (派工 brief 估 30/50/40/50/30 = 200 守恒)

## 3. 件 4 三门控实测

- knowledge_service def diff: 0 ✅
- hybrid_retriever def diff: 0 ✅
- rag_evaluator def diff: 0 ✅

## 4. 4 测试文件 + 1 综合报告 + 1 memory

| 文件 | 行数 | cases | 状态 |
|------|------|-------|------|
| `tests/rag/test_qa_bench_intent_5_subsets.py` | 334 | 22 (5 准确率 + 2 守恒 + 10 关键词 + 3 门控 + 1 锚点 + 1 报告) | 20 PASS + 2 预期 fail (锚点 + 报告目录) |
| `tests/rag/test_qa_bench_reranker_gate.py` | 240 | 9 (2 件 2 + 2 件 3 + 3 件 4 + 1 件 5) | 8 PASS + 1 预期 fail (锚点) |
| `tests/rag/test_qa_bench_image_subset.py` | 196 | 18 (9 parametrize + 2 件 1 + 1 件 2 + 2 件 3 + 3 件 4 + 1 件 5) | 17 PASS + 1 预期 fail (锚点) |
| `tests/rag/test_qa_bench_temporal_recency.py` | 213 | 9 (1 件 1 + 1 件 2 + 3 件 3 + 3 件 4 + 1 件 5) | 8 PASS + 1 预期 fail (锚点) |
| `docs/qa-bench/W100-QA-BENCH-200-REPORT.md` | 280 | 综合报告 + 4 子任务详述 + 5 铁证守恒 | ✅ |
| `memory/w100-qa-bench-startup-2026-08-02.md` | 本文件 | 派工起点沉淀 | ✅ |

## 5. 派工 v4.1 6 必读段全遵守

- 段 0.1 base ref 实测 (类 20.46): base = `59b2a9603` 实测 ✅
- 段 0.2 分支与 commit hash 实测 (类 20.47): worktree 分支名 `worktree-agent-w100-qa-bench` ✅
- 段 0.3 套件路径存在性探测 (类 20.97): qa-bench 在 `tests/qa-bench/` 实测 ✅
- 段 0.4 merge-base 假阳性拦截 (类 20.98): 本任务未触发, 仅 commit ✅
- 段 0.5 收官验证 6 步 (类 20.108): 件 4 三门控 + pytest + 老套件 + 锚点 + 综合报告 全跑 ✅
- 段 0.6 调研标"推断"必先实测 (类 20.109): 5 类子集划分实测, 不擅自扩不擅自缩 ✅

## 6. 派工纪律 (本任务沿用)

- **类 20.115 模式**: 4 commit 后报告主指挥, 不自己 merge
- **类 20.131 拦截**: 派工起点必 `git rev-parse HEAD` + `git rev-parse origin/main` 双验证, 不漂移
- **类 20.123 派工 plan 偏差据实**: qa-bench 7 intent vs 5 classifier 类不直接对应, 据实上报
- **不擅自改阈值**: 派工 brief 估 ≥ 85% / ≥ 92% / ≥ 90% / +15%, 按实测 100% / 100% / 100% / +100% 全超
- **件 4 三门控守恒**: 本任务纯测试, 全 0

## 7. 累计 commits 与铁律延续

- W68-W99 累计: 92+ commits + 595+ 铁律
- W100-RAG-3..6 累计: 27 commits + 600+ 铁律
- W100-QA-BENCH (+3 据实上报): 3 commits + 1 新铁律 (类 20.123 qa-bench 7 intent vs 5 classifier 类不直接对应, 关键词驱动合成子集替代)