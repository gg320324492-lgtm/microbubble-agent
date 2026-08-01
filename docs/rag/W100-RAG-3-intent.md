# W100-RAG-3 Query Intent 分类 runbook

> **派工 brief v4.1 6 必读段** 全遵守, 锚点范式 W99-RAG-2 (~498) → W100-RAG-3 504 守恒 (+6 据实上报).
> 派工 plan: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 3 段 (2026-08-02 W100-RAG-3 主拍批).
> worktree: `worktree-agent-w100-rag-3` (本任务不动 schema, 无 alembic 迁移).

## 1. 5 类 Intent 枚举 (类 20.125 铁律)

| Intent | 含义 | 典型 query |
|--------|------|-----------|
| `factual` | 寻求具体事实/数据/定义 | "臭氧微气泡的粒径是多少?" |
| `conceptual` | 寻求概念解释/原理理解 | "微气泡为什么能提高臭氧溶解效率?" |
| `procedural` | 寻求操作步骤/方法流程 | "微气泡发生装置怎么搭建?" |
| `multi_doc_synthesis` | 跨多文档综合分析/对比 | "比较 3 种臭氧微气泡发生器的优缺点" |
| `hypothesis_generation` | 科研假设/方案设计 | "微气泡能否用于去除重金属?" |

## 2. 模块清单

| 模块 | 路径 | 作用 |
|------|------|------|
| Intent Classifier | `app/rag/intent_classifier.py` (~280 行) | LLM-as-judge 分类 5 类 intent |
| Intent Router | `app/rag/intent_router.py` (~180 行) | classify + 查表 → HybridWeights |
| Config 扩展 | `app/rag/config.py` | 加 INTENT_CLASSIFIER_ENABLED + INTENT_FALLBACK |
| YAML 路由策略 | `config/intent_routing.yaml` | 5 类默认 weights (参考 + 未来 yaml/DB override 留口) |
| Hook 接入 | `app/services/hybrid_retriever.py` | retrieve_with_weights 入口加 intent hook (W99-RAG-1 cache 之前) |
| 单测 | `tests/rag/test_intent_classifier.py` (25 case) | 5 类 / LLM 失败 / parse / 边界 / 路由 / 配置 |
| E2E | `tests/rag/test_rag_intent_e2e.py` (22 case) | 5 类 e2e + 失败降级 + 串联 W99-RAG-1/2 |

## 3. 5 类 Intent 路由策略 (类 20.126 铁律: 配置化不硬编码)

| Intent | vector | bm25 | graph | rerank | 设计思路 |
|--------|--------|------|-------|--------|---------|
| factual | 0.6 | 0.2 | 0.0 | 0.2 | 重向量 (具体事实查 recall), 弱图 |
| conceptual | 0.4 | 0.3 | 0.1 | 0.2 | 4 路相对均衡, 略重向量 |
| procedural | 0.2 | 0.4 | 0.2 | 0.2 | 重 BM25 (操作步骤, 关键词匹配强) |
| multi_doc_synthesis | 0.3 | 0.2 | 0.3 | 0.2 | 重图 (跨文档关联) |
| hypothesis_generation | 0.25 | 0.25 | 0.25 | 0.25 | 4 路均衡 (无明确倾向) |

- **配置化落地点**: `app/rag/intent_router.py` 的 `DEFAULT_INTENT_WEIGHTS` (module-level dict)
- **测试可覆盖**: `IntentRouter(weights_map=custom_dict)` 或 `patch DEFAULT_INTENT_WEIGHTS`
- **未来 PR**: yaml 文件 + DB override (本任务只埋点 `config/intent_routing.yaml` 参考)

## 4. Hook 串联顺序 (W99-RAG-1/2/3 三 hook 共存)

```
retrieve_with_weights(query, ...)
  │
  ├─ [-1] W100-RAG-3 Intent hook   ← NEW
  │      - INTENT_CLASSIFIER_ENABLED=True + weights=None → 调 IntentRouter.route
  │      - 失败 best-effort 静默降级到默认 weights
  │      - 留口: weights 暂不直接传 _retrieve_impl (W90 PR4 留口未来 PR 接)
  │
  ├─ [0]  W99-RAG-1 Query Cache hook
  │      - cache 命中 → 直接 return (跳过 intent 已推断的 weights 应用, 节省 LLM)
  │
  ├─ [1]  synonym 改写 (W90 PR4 _apply_synonyms)
  │
  ├─ [2]  HybridRetriever.retrieve (原签名, 不动)
  │
  ├─ [4]  W99-RAG-1 cache 写回
  │
  └─ [5]  W99-RAG-2 Citation hook
         - raw_results.citations 挂载
```

## 5. 失败降级矩阵 (类 20.125 铁律)

| 失败点 | 降级行为 |
|--------|---------|
| LLM 抛异常 (网络/超时) | classify 返 INTENT_FALLBACK (默认 factual) |
| LLM 返回乱码 | regex 兜底, 失败 → INTENT_FALLBACK |
| LLM 返回不合法 intent | 5 类校验失败 → INTENT_FALLBACK |
| Router 异常 | 整个 hook try/except 兜底, weights 留 None (走原默认) |
| INTENT_CLASSIFIER_ENABLED=False | hook 直接跳过, weights 保持原样 |
| 空 query | 不调 LLM, 直接返 INTENT_FALLBACK |

## 6. 件 4 三门控实测

| 门控 | 数值 | 含义 |
|------|------|------|
| A | `git diff -- app/services/knowledge_service.py \| grep -c "^[+-]def"` = 0 | 老核心服务 0 改既有 |
| B | `git diff -- app/services/hybrid_retriever.py \| grep -c "^[+-]def"` = 0 | hybrid_retriever def 0 改 (intent hook 只 body 追加) |
| C | `git diff -- app/services/rag_evaluator.py \| grep -c "^[+-]def"` = 0 | rag_evaluator 0 改既有 |

**0 production code 守恒**: 件 4 三门控实测全 0 ✅

## 7. 测试覆盖

- **件 1 (单测)**: 25/25 PASS (5 类基础 / 3 LLM 失败 / 3 parse / 4 边界 / 5 路由 / 3 配置 / 2 签名)
- **件 2 (e2e)**: 22/22 PASS (5 类 e2e / 3 LLM 失败 / 4 weights 验证 / 3 W99-RAG-1 串联 / 3 W99-RAG-2 串联 / 2 边界 / 2 qa-bench 子集)
- **回归**: W99-RAG-1/2 + W90 PR4/7/8/9 e2e 132/132 PASS, 0 regression ✅

## 8. 派工 plan 偏差据实 (类 20.123)

| 偏差项 | 派工 plan 假设 | 实测 |
|--------|---------------|------|
| LLMAnalysisService 接口 | "line 170 单例" | 实际只有 `analyze_content` 一个方法, 单例在 line 170 (`llm_analysis_service = LLMAnalysisService()`) — 沿用可行 |
| query_translator 现有方法 | plan 没列 | 实测 5 个公开方法: `multi_query / hyde / decompose / translate / expand_and_search` — 全部沿用 |

**纪律**: 不擅自扩也不擅自缩, 派工 plan 假设与实测不符时据实上报 (本任务 LLMAnalysisService 没用到, query_translator 沿用即可)

## 9. 类 20 沉淀 (W100-RAG-3)

- **类 20.125 (新)**: intent 分类必 5 类 + 失败回退 INTENT_FALLBACK (默认 factual)
- **类 20.126 (新)**: intent 路由 weights 配置化 (module-level dict DEFAULT_INTENT_WEIGHTS, 不硬编码到 body)
- **类 20.123 (W100-RAG-3 实战)**: 派工 plan 偏差据实上报, 不擅自扩不擅自缩
- **类 20.115 实战 (W100-RAG-3 沿用)**: LLM 客户端不可假设, 必须先 Read 源码确认 (llm_analysis_service.py 实际只有 analyze_content)

## 10. 未来 PR 留口

1. **PR-A**: yaml 文件 + DB override 接入 (本任务只埋点 `config/intent_routing.yaml` 参考)
2. **PR-B**: weights 实际传给 `_retrieve_impl` 做 per-intent 调参 (本任务只埋点, HybridRetriever.retrieve 内部按 weights 调权重)
3. **PR-C**: recall_observability 集成 (RecallTrace 加 intent 字段, 串联 PR7)
4. **PR-D**: qa-bench R8 200 题 5 子集真跑 (本任务只 5 题 fixture 子集)
5. **PR-E**: RAG 路由 A/B test (factual vs multi_doc 命中率对比)
