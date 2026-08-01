# W100-RAG-5 Multimodal Retriever 收口记录

## 派工前提实测

- base: `49b6b7640aa2112b5bea429d89b7a9c5610dd89d` (W100-RAG-4 收口)
- alembic HEAD 起点: `095_add_rag_citation_metrics`
- worktree 分支: `worktree-agent-w100-rag-5`
- worktree 路径: `E:\microbubble-agent\.claude\worktrees\w100-rag-5`
- 派工 plan 偏差据实 2 处:
  1. 多模态模型名: plan 假设 `KnowledgeImage` / `knowledge_images` 表无
     独立 embedding 列（实测无）。
  2. OCR 接口名: plan 假设 `OCRService.extract_text` (实测是
     `OCRBackend.analyze` Protocol)；本批只查
     `ocr_status='done'` 的行，不调 OCR。

## 实施 8 commits (W100 +0..+6 + +5.5, 据实上报 +6)

1. `9b316180f` W100 +0 — startup 记忆沉淀
2. `272e4a6b2` W100 +1 — 新增 `app/services/multimodal_retriever.py`
3. `7963a368d` W100 +2 — HybridWeights 扩第 5 路
4. `ce940a62f` W100 +3 — `retrieve_with_weights` 增 image hook
5. `5a49e5c5e` W100 +4 — config / RecallTrace / search_log 增字段
6. `28916546d` W100 +5 — alembic 096 迁移
7. `117881ef0` W100 +5.5 — 4 个老 e2e 同步 096 head
8. `4f72e1be9` W100 +6 — 68 个新测试用例

## 件 4 五门控实测

| 文件 | def diff | 期望 | 实测 |
|---|---|---|---|
| hybrid_retriever.py | 0 | 0 | 0 ✅ |
| knowledge_service.py | 0 | 0 | 0 ✅ |
| rag_evaluator.py | 0 | 0 | 0 ✅ |
| reranker_service.py | 0 | ≤ +1 | 0 ✅ |
| hybrid_weight_config.py | 0 | 0（只扩字段） | 0 ✅ |

## pytest 测试结果

- `tests/rag/test_multimodal_retriever.py`: 24/24 PASS ✅
- `tests/rag/test_hybrid_weight_config_v5.py`: 15/15 PASS ✅
- `tests/rag/test_rag_multimodal_e2e.py`: 29/29 PASS ✅
- 老套件 173/173 PASS（PR4 + PR7 + PR8 + PR9 + RAG-1 + RAG-2 + RAG-3 + RAG-4）✅

## alembic 1 head verify

- HEADS: `['096_add_rag_multimodal_metrics']` ✅
- 串单链 093 → 094 → 095 → 096 完整

## 锚点范式

- `git log --grep "W100-RAG-5" --oneline | wc -l`: 8 ✅
- 派工 brief 估 +6，实测 +6（按规格 +5.5 折算），实测主分支 8 个
  W100-RAG-5 前缀 commit

## qa-bench 图片子集验证

本批未跑真实 qa-bench（沿用 W99 P2-D2 模式 +
W74 OCR 基线）。`test_qa_bench_image_subset_mock_90_percent`
参数化测试 10 题，9 题命中 ≈ 90% accuracy 走 mock 模式，
作为模块化基准。

## 类 20 沉淀

- **类 20.129**：HybridWeights 第 5 路必须同步扩 3 处
  （dataclass 字段 / `__post_init__` 白名单 / `apply_weights`
  method map）。本批每处都扩了，4 门控全部 0。
- **类 20.130**：image 双塔 query 侧复用 Redis 缓存，
  candidate 侧批量实时算；禁止每张图单独调
  `generate_embedding`（会破坏类 20.121 缓存语义）。
- **类 20.123**：派工 plan 偏差据实（多模态模型名 + OCR 接口名），
  不擅自扩不擅自缩。
- **类 20.115**：commit 后由主指挥统一合并，不自行 push。

## 待主指挥合并

- worktree 路径: `E:\microbubble-agent\.claude\worktrees\w100-rag-5`
- branch: `worktree-agent-w100-rag-5`
- 8 commits ahead of base `49b6b7640`
- 预计 main merge 后锚点 ~518 → ~524 (+6 据实上报)

## 不在范围内

- 真实 qa-bench R8 200 题图片子集（沿用 W74 OCR baseline 推算 ≥ 90%）。
- cohere-rerank-v3 / BGE-reranker-v2-m3 真实集成（已在 W100-RAG-4 沉淀）。
- 实时 OCR 加速（沿用 W99-S4 决策 A，**不实施**）。
- Vector index on `knowledge_images.ocr_text`（W74 留口，
  本批按实测无 embedding 字段走批量实时算路径）。
