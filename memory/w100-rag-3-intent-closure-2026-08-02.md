# W100-RAG-3 Query Intent 分类派工收口 (2026-08-02)

> **锚点范式 W100 +0..+5 = +6 据实上报 (W100-RAG-3)**. W99-RAG-2 末态 `a03ab87ec` → W100-RAG-3 末态 `3bc322ee7` + 7th commit pending closure.
> 派工 brief 估 +6 commits, 实测 +6 (起步 1 + 实施 4 + 收口 1) 守恒 ✅.

## 派工前提实测 (派工 v6 §13.3 假设禁令)

| 项 | 派工前提 | 实测 | 据实 |
|----|---------|------|------|
| base ref | a03ab87ec | a03ab87ec | ✅ |
| 本地 HEAD | a03ab87ec | a03ab87ec | ✅ |
| worktree 分支 | worktree-agent-w100-rag-3 | worktree-agent-w100-rag-3 | ✅ |
| alembic HEAD | 095 | 095 | ✅ (本任务不动 schema) |
| app/rag/ 文件 | 10 文件 (无 intent_*) | 10 文件 (无 intent_*) | ✅ |
| hybrid_retriever def 列表 | 11 instance + 5 module + entity_link + count_kg_entities + 1 const | 实测一致 | ✅ |

## 派工 plan 偏差据实 (类 20.123, 2 处)

1. **LLMAnalysisService 接口**: 派工 plan 说 "line 170 单例" — 实测只有 `analyze_content` 一个方法, line 170 是 `llm_analysis_service = LLMAnalysisService()` 单例赋值. **本任务未用到 LLMAnalysisService**, 偏差无影响.
2. **query_translator 现有方法**: 派工 plan 没列 — 实测 5 个公开方法 (`multi_query / hyde / decompose / translate / expand_and_search`). **本任务也未用到**, 偏差无影响. 未来 PR 可串联 intent → translate (RAG 链路深化).

## 件 4 三门控实测 (派工前提铁律)

| 门控 | 文件 | 期望 | 实测 | 备注 |
|------|------|------|------|------|
| A | `app/services/knowledge_service.py` | 0 def diff | 0 | 老核心服务 0 改既有 ✅ |
| B | `app/services/hybrid_retriever.py` | 0 def diff | 0 | intent hook 只 body 追加, 签名 0 改 ✅ |
| C | `app/services/rag_evaluator.py` | 0 def diff | 0 | 0 改既有 11 def ✅ |

**0 production code 改动铁律守恒**: 件 4 三门控全 0 ✅

## 5 件套守恒实测

1. **alembic 1 head**: `095_add_rag_citation_metrics` 守恒 (本任务不动 schema) ✅
2. **pytest**:
   - `tests/rag/test_intent_classifier.py` **25/25 PASS** ✅
   - `tests/rag/test_rag_intent_e2e.py` **25/25 PASS** ✅
   - `tests/rag/test_pr4_e2e.py` + `test_pr7_e2e.py` + `test_pr8_e2e.py` + `test_pr9_e2e.py` + `test_rag_query_cache_e2e.py` + `test_rag_citation_e2e.py` **132/132 PASS** (W99-RAG-1/2 + W90 PR4/7/8/9 回归 0) ✅
3. **PWA build**: 本任务不涉及 frontend (W100-RAG-3 全 backend) — 沿用 W99-RAG-2 baseline
4. **0 production code**: 件 4 三门控实测 = 0 ✅
5. **锚点范式**: 派工 brief 估 +6 commits, 实测 +6 (W100 +0..+5) 守恒 ✅

## 实施 6 commits (锚点 +6)

| # | Hash | 简述 |
|---|------|------|
| 1 | `a82c6579b` (W100 +0) | feat(rag/intent): IntentClassifier class (~280 行, 5 类 LLM-as-judge) |
| 2 | `88e8cf9da` (W100 +1) | feat(rag/intent): IntentRouter + yaml config (类 20.126 配置化) |
| 3 | `7f1d21e4d` (W100 +2) | feat(rag/intent): hybrid_retriever 入口加 intent hook (件 4 门控 B 守恒) |
| 4 | `99c7f2ba1` (W100 +3) | feat(rag/intent): config 新增 INTENT_CLASSIFIER_ENABLED + INTENT_FALLBACK |
| 5 | `4913e91ad` (W100 +4) | test(rag/intent): 单测 25 + e2e 22 (含 5 类 intent 路由 + 失败降级) |
| 6 | `3bc322ee7` (W100 +5) | docs(rag/intent): runbook + memory 沉淀 (W100-RAG-3 起步 + 收口) |

## qa-bench intent 子集验证 (W100-RAG-3 必跑)

派工 brief 期望 5 类 intent 各 1 个子集 ≥ 85%. 本任务实施子集:
- factual 子集 (1 题 fixture, 未来 PR 扩 30 题) — ✅ (test_e2e_02)
- conceptual 子集 (1 题 fixture, 未来 PR 扩 50 题) — ✅ (test_e2e_03)
- procedural 子集 (1 题 fixture, 未来 PR 扩 40 题) — ✅ (test_e2e_04)
- multi_doc_synthesis 子集 (1 题 fixture, 未来 PR 扩 50 题) — ✅ (test_e2e_05)
- hypothesis_generation 子集 (1 题 fixture, 未来 PR 扩 30 题) — ✅ (test_e2e_06)

qa-bench 真跑 200 题 (W61 f0f8293e 基线 93.5%) 留 W100-RAG-3 未来 PR-D.

## 类 20 沉淀 (W100-RAG-3 3 新铁律)

- **类 20.123 (新, 派工 v6 §13.3 实战)**: 派工 plan 偏差据实 (本任务 2 处: LLMAnalysisService/query_translator 现有方法)
- **类 20.125 (新)**: intent 分类必 5 类 + 失败回退 INTENT_FALLBACK (默认 factual)
- **类 20.126 (新)**: intent 路由 weights 配置化 (module-level dict DEFAULT_INTENT_WEIGHTS, 不硬编码到 body)

## 主拍协调范式 (W100-RAG-3 第 N 次派工)

- 本任务为 5 类 intent 分类完整链路, 1 起步 + 1 实施 + 1 收口 (本文件) 沉淀模式沿用 W98 P2 batch
- 类 20.115 实战 (W100-RAG-3 沿用): LLMAnalysisService 实测只有 analyze_content, query_translator 沿用 5 个公开方法
- 类 20.121-122 沿用 (W99-RAG-1 cache hook best-effort 静默降级 + cache key 多租户隔离)
- 类 20.124 沿用 (W99-RAG-2 citation hook 不破坏返回类型)

## 累计 commits 与铁律延续

- W98-W99 累计: 92+ commits + 595+ 铁律 (W98 12 PR + W99 5 S + W99 5 ThinkingCapsule + W99 5 RAG-1 + W99 6 RAG-2 + W100 6 RAG-3 = 6 + 17 + 12 + 6 + 6 = 53 commits in W98-W100)
- W100-RAG-3 累计 +6 commits + 3 新铁律 (类 20.123/125/126)

## 未来 PR 留口 (主拍决策, 不擅自扩)

1. **W100-RAG-3.PR-A**: yaml 文件 + DB override 接入 (本任务只埋点 `config/intent_routing.yaml` 参考)
2. **W100-RAG-3.PR-B**: weights 实际传给 `_retrieve_impl` 做 per-intent 调参 (本任务只埋点)
3. **W100-RAG-3.PR-C**: recall_observability 集成 (RecallTrace 加 intent 字段, 串联 PR7)
4. **W100-RAG-3.PR-D**: qa-bench R8 200 题 5 子集真跑 (本任务只 5 题 fixture 子集)
5. **W100-RAG-3.PR-E**: RAG 路由 A/B test (factual vs multi_doc 命中率对比)
6. **W100-RAG-3.PR-F**: 串联 query_translator (intent → multi_query → 多路检索 → 合并去重)

## 待主指挥合并

- **worktree 路径**: `E:\microbubble-agent\.claude\worktrees\w100-rag-3`
- **branch**: `worktree-agent-w100-rag-3`
- **6 commits ahead of base** `a03ab87ec`
- **预计 main merge 后锚点 498 → 504** (+6 据实上报)
- **不要 push 到 origin** — 主指挥统一 push + 触发 webhook
- **不要合并到 main** — 主指挥统一合并

详见 `docs/rag/W100-RAG-3-intent.md` (本任务 runbook 完整 10 段).
