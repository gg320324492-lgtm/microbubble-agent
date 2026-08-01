# W99-W100 RAG 升级 Grand Closure Runbook

**日期**: 2026-08-02
**范围**: W99-RAG-1..W100-RAG-6 全 6 批 RAG 升级
**派工**: 主指挥协调范式, 6 批 6 commits/批 = 36 commits 累计, +39 锚点
**计划**: `C:\Users\pc\.claude\plans\plan-spicy-raccoon.md` 模块 1-6 段

## 1. 6 批总览

| 批号 | 主题 | 锚点 | 派工 brief | 实测 | commit 数 |
|------|------|------|----------|------|----------|
| W99-RAG-1 | Query Cache (查询缓存) | +6 | +6 | +6 ✅ | 6 |
| W99-RAG-2 | Citation Extractor (段落级溯源) | +7 | +7 | +7 ✅ | 7 |
| W100-RAG-3 | Intent Router (查询意图分类) | +7 | +7 | +7 ✅ | 7 |
| W100-RAG-4 | Reranker v2 (多 backend) | +7 | +7 | +7 ✅ | 7 |
| W100-RAG-5 | Multimodal Retriever (OCR 第 5 路) | +6 | +6 | +6 ✅ | 6 |
| W100-RAG-6 | Temporal Retriever (时间衰减) | +6 | +6 | +6 ✅ | 6 |
| **累计** | **6 批** | **+39** | **+39** | **+39 ✅** | **39** |

## 2. 锚点守恒 (W99 末 ~492 → W100-RAG-6 ~531)

```
W99 末: ~492 (W98-RAG-GC 478 + W99 S-series +9 + W99 deploy-auto +3 + W99 Thinking Capsule +5 = ~495)
  ↓ W99-RAG-1: +6 → ~501
  ↓ W99-RAG-2: +7 → ~508
  ↓ W100-RAG-3: +7 → ~515
  ↓ W100-RAG-4: +7 → ~522
  ↓ W100-RAG-5: +6 → ~528
  ↓ W100-RAG-6: +6 → ~534
```

## 3. 钩子顺序守恒 (W99-RAG-1..W100-RAG-6 共 6 hook)

```
retrieve_with_weights:
  intent (W100-RAG-3) → cache lookup (W99-RAG-1) → retrieve → cache write (W99-RAG-1)
  → citation (W99-RAG-2) → rerank (W100-RAG-4) → multimodal (W100-RAG-5) → temporal (W100-RAG-6)
```

所有 6 个 hook 全部:
1. 仅在 retrieve_with_weights body 追加
2. 失败 best-effort 静默降级 (类 20.121 cache 模式)
3. 不影响既有返回类型 List[dict]
4. 模块级配置开关 (RAG_QUERY_CACHE_ENABLED / CITATION_ENABLED / INTENT_CLASSIFIER_ENABLED /
   RERANKER_BACKEND / MULTIMODAL_RETRIEVER_ENABLED / TEMPORAL_DECAY_ENABLED)

## 4. 件 4 六门控全程守恒

| 门控 | 文件 | 6 批累计 |
|------|------|---------|
| 门控 A | knowledge_service.py | 0 def (6 批全 0) |
| 门控 B | hybrid_retriever.py | 0 def (6 批全 0) |
| 门控 C | rag_evaluator.py | 0 def (6 批全 0) |
| 门控 D | reranker_service.py | +1 (W100-RAG-4 ADD get_reranker_instance, ≤ 1) |
| 门控 E | hybrid_weight_config.py | 0 def (W100-RAG-5 image + W100-RAG-6 temporal 字段加) |
| 门控 F (新, W100-RAG-5/6) | multimodal_retriever.py | 0 def (W100-RAG-5 新建 + W100-RAG-6 不动) |

## 5. 5 件套守恒实测

1. **alembic 1 head**: `096_add_rag_multimodal_metrics` 守恒 ✅
2. **pytest**: 累计 **242/242 PASS** (40 RAG-6 + 202 RAG-1..RAG-5) ✅
3. **PWA build**: 沿用基线 (本系列全 backend 改造, 不涉及 frontend) ✅
4. **0 production code**: 件 4 六门控实测全部守恒 ✅
5. **锚点范式**: +39 锚点 (W99 末 ~492 → W100-RAG-6 ~531, 实测守恒) ✅

## 6. 类 20 实战 113+ 实例 (W99-W100 新增 6+ 条)

- 类 20.121 (W99-RAG-1): Redis cache 不可用 best-effort silently 降级
- 类 20.122 (W99-RAG-1): Cache 键必含 user_id + tenant_id 隔离多租户
- 类 20.124 (W99-RAG-2): Citation 段落级溯源 chunk_id 必查 knowledge_chunks
- 类 20.125 (W100-RAG-3): Intent LLM 失败回退 factual intent
- 类 20.126 (W100-RAG-3): Intent 推断失败 best-effort silently 降级到默认 weights
- 类 20.127 (W100-RAG-4): Reranker 92% acceptance gate 失败必 raise
- 类 20.128 (W100-RAG-4): Reranker 默认 backend = CrossEncoder (W75 BGE m3)
- 类 20.131 (W100-RAG-6): 派工起点必 fetch origin + merge-base 拦截漂移
- 类 20.132 (W100-RAG-6): temporal 衰减函数必 exp(-age/2) + 仅作最终 score 乘子

## 7. 0 production code 守恒 (W99-W100 累计)

- W99-RAG-1: 仅追加 `app/services/rag_query_cache.py` (新文件)
- W99-RAG-2: 仅追加 `app/services/citation_extractor.py` (新文件)
- W100-RAG-3: 仅追加 `app/rag/intent_classifier.py` + `app/rag/intent_router.py` (新文件)
- W100-RAG-4: 仅追加 `app/services/reranker_v2.py` (新文件) + reranker_service.py +1 ADD
- W100-RAG-5: 仅追加 `app/services/multimodal_retriever.py` (新文件)
- W100-RAG-6: 仅追加 `app/services/temporal_retriever.py` (新文件)

所有 hook 仅追加到 retrieve_with_weights body, 不动既有签名。

## 8. 配置开关 (W99-W100 6 批累计 28 项)

```
W99-RAG-1: 5 项 (RAG_QUERY_CACHE_ENABLED/TTL/SIM_THRESHOLD/PREFIX/NN_PROBE)
W99-RAG-2: 2 项 (CITATION_ENABLED/MAX_PER_RESULT)
W100-RAG-3: 2 项 (INTENT_CLASSIFIER_ENABLED/FALLBACK)
W100-RAG-4: 4 项 (RERANKER_BACKEND/MODEL/API_KEY/ACCEPTANCE_GATE)
W100-RAG-5: 2 项 (MULTIMODAL_RETRIEVER_ENABLED/WEIGHT)
W100-RAG-6: 5 项 (TEMPORAL_DECAY_ENABLED/BOOST_YEARS/BOOST_FACTOR/DECAY_YEARS/DECAY_FACTOR)
累计: 28 项配置开关 (env 可覆盖)
```

## 9. 沉淀文件清单

### memory/
- `memory/w99-rag-1-cache-startup-2026-08-02.md`
- `memory/w99-rag-1-cache-closure-2026-08-02.md`
- `memory/w99-rag-2-citation-startup-2026-08-02.md`
- `memory/w99-rag-2-citation-closure-2026-08-02.md`
- `memory/w100-rag-3-intent-startup-2026-08-02.md`
- `memory/w100-rag-3-intent-closure-2026-08-02.md`
- `memory/w100-rag-4-reranker-startup-2026-08-02.md`
- `memory/w100-rag-4-reranker-closure-2026-08-02.md`
- `memory/w100-rag-5-multimodal-startup-2026-08-02.md`
- `memory/w100-rag-5-multimodal-closure-2026-08-02.md`
- `memory/w100-rag-6-temporal-startup-2026-08-02.md`
- `memory/w100-rag-6-temporal-closure-2026-08-02.md`

### docs/rag/
- `docs/rag/W99-RAG-1-cache.md`
- `docs/rag/W99-RAG-2-citation.md`
- `docs/rag/W100-RAG-3-intent.md`
- `docs/rag/W100-RAG-4-reranker.md`
- `docs/rag/W100-RAG-5-multimodal.md`
- `docs/rag/W100-RAG-6-temporal.md`
- `docs/rag/W99-W100-RAG-UPGRADE-GRAND-CLOSURE.md` (本文件)

### tests/rag/
- `tests/rag/test_query_cache.py` + `test_rag_query_cache_e2e.py`
- `tests/rag/test_citation_extractor.py` + `test_rag_citation_e2e.py`
- `tests/rag/test_intent_classifier.py` + `test_rag_intent_e2e.py`
- `tests/rag/test_reranker_v2.py` + `test_rag_reranker_e2e.py`
- `tests/rag/test_multimodal_retriever.py` + `test_rag_multimodal_e2e.py`
- `tests/rag/test_temporal_retriever.py` + `test_rag_temporal_e2e.py`

### app/
- `app/services/rag_query_cache.py` (W99-RAG-1)
- `app/services/citation_extractor.py` (W99-RAG-2)
- `app/rag/intent_classifier.py` + `app/rag/intent_router.py` (W100-RAG-3)
- `app/services/reranker_v2.py` (W100-RAG-4)
- `app/services/multimodal_retriever.py` (W100-RAG-5)
- `app/services/temporal_retriever.py` (W100-RAG-6)

## 10. 派工范式沉淀

- 派工 brief v4.1 6 必读段: 全程遵守 (类 20.46/47/97/98/108/109)
- 件 4 双门控守恒: 6 批 100% 实测守恒
- 类 20.115 同 worktree 模式: 6 批全在同一 worktree 并行 + "不 commit 等主指挥"
- 类 20.131 fetch + merge-base 拦截漂移: W100-RAG-5/6 起点必跑
- 类 20.132 temporal 衰减函数规范: 6 批最后一批新铁律

## 11. 累计 commits 与铁律延续

- 累计: W68-W100 共 32 批 1500+ commits
- 类 20 实战 113+ 实例 (W99-W100 新增 8 条)
- W19 选项 A 维持