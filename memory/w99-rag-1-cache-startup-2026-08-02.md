# W99-RAG-1 Query Cache 结果层 — Startup

**派工时间**: 2026-08-02
**主拍**: W99-RAG-1 (Query Cache 结果层)
**Plan ref**: [C:\Users\pc\.claude\plans\plan-spicy-raccoon.md](C:\Users\pc\.claude\plans\plan-spicy-raccoon.md) 模块 1 段

## 派工前提实测 (类 20.46 加固, 必查)

- **base ref**: `2ebf8f1d5ffc50ad2a7e11a3c81cf95d39c3c382` (实测 origin/main HEAD)
- **本地 HEAD**: `2ebf8f1d5` (与 origin/main 同步)
- **worktree 分支名**: `worktree-agent-w99-rag-1`
- **worktree 路径**: `E:\microbubble-agent\.claude\worktrees\w99-rag-1`
- **alembic HEAD**: `093_add_search_log_answer_rating` (1 head 守恒, 094 必须接 093 串单链)

## 现状底座 (实测)

- `app/services/hybrid_retriever.py` (713 行) — 11 instance methods + 5 module-level functions
  - instance: __init__(22) / retrieve(25) / _retrieve_impl(42) / _vector_search(132) / _bm25_search(147) / _refresh_bm25_index(166) / _merge_results(200) / _graph_search(239) / _normalize_scores(290) / evaluate(305)  → 实际 **10 instance methods** (含 __init__)
  - module: retrieve_chunks_by_vector(380) / get_hybrid_retriever(461) / _apply_weights(475) / _apply_synonyms(517) / retrieve_with_weights(535) / ENTITY_LINK_DEFAULT_WEIGHT(610) / retrieve_with_entity_link(613) / count_kg_entities(704)  → 实际 7 module-level + 1 constant
- `app/services/recall_observability.py` — RecallTrace 已有 22 字段 (PR7 已扩 19 + W98 +3 推导), 沿用 ADD 模式
- `app/models/search_log.py` — 已有 25 字段 (老 + W93 PR7 B-7 加 19 + W98 answer_rating), 沿用 ADD 模式
- `app/rag/config.py` — 框架级开关, 风格 = bool + env
- `app/services/embedding_service.py:243` `get_or_compute_query_embedding` — best-effort Redis pattern 模板
- `app/core/redis.py:34` `get_redis()` — async redis client
- `tests/rag/test_pr4_e2e.py` — 22 case e2e 模板 (件 1-6 + 22/22 PASS 自检)

## 派工 v6 §13.3 假设禁令 — 实测 5 个

1. ✅ embedding_service 已有 `get_or_compute_query_embedding` (line 243), 不重新造
2. ✅ hybrid_retriever 实际 10 instance + 5 module-level function (派工 brief 估"10 个 def"偏差据实)
3. ✅ alembic 当前 1 head = `093_add_search_log_answer_rating` (派工 brief 估"094 接 093"正确)
4. ✅ recall_observability RecallTrace 字段追加沿用 dataclass field 默认值模式
5. ✅ search_log 字段追加沿用 Column(nullable=True) 模式

## 实施路径 (锚点 +6 据实)

1. **commit 1**: `app/services/rag_query_cache.py` (RAGQueryCache class ~180 行)
2. **commit 2**: `app/services/hybrid_retriever.py` 在 `retrieve_with_weights` 头部加 cache hook (line 567 之前, 仅追加)
3. **commit 3**: `app/rag/config.py` 加 3 配置 + `app/services/recall_observability.py` 2 字段 + `app/models/search_log.py` 2 列
4. **commit 4**: `alembic/versions/094_add_rag_query_cache_metrics.py` 迁移
5. **commit 5**: `tests/rag/test_query_cache.py` 单测 + `tests/rag/test_rag_query_cache_e2e.py` 22 case e2e
6. **commit 6**: `docs/rag/W99-RAG-1-cache.md` runbook + memory 收口

## 件 4 双门控 (守恒实测)

- 门控 A: `git diff base..HEAD -- app/services/knowledge_service.py | grep -c "^[+-]def"` = 0
- 门控 B: `git diff base..HEAD -- app/services/hybrid_retriever.py | grep -c "^[+-]def"` = 0

## 类 20 沉淀 (W99-RAG-1 新增 2)

- **类 20.121**: Redis 不可用 best-effort silently 降级, 不抛错 (沿用 embedding_service:243 模式)
- **类 20.122**: query→answer 缓存键必须含 user_id+tenant_id, 多租户不可串数据 (避免幽灵用户)

## 派工 v11 §0.5 收官 6 步 (必跑)

1. alembic 1 head verify: `094_add_rag_query_cache_metrics` ✅
2. pytest 22/22 e2e PASS ✅
3. pytest 老套件 PR4/PR7/PR8/PR9 不回归 ✅
4. 件 4 双门控实测 = 0 ✅
5. 锚点范式 ≥ 6 commits ✅
6. 5 件套守恒 ✅
