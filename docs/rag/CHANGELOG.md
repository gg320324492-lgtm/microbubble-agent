# RAG 大改造 CHANGELOG（10 PR 汇总）

> 格式: `[PRn W8x +N] <type>(rag): <desc>`。PR1-PR9 为规划态条目（收口后回填真 commit hash）; PR10 为本次实施据实条目。

## PR1 — 嵌入一致化 + query prefix 生效（W88 +0 → +7, 规划）

- `[PR1 W88 +0]` feat(rag): 新增 embedding_truncation_policy (MAX_EMBED_INPUT_CHARS=6000)
- `[PR1 W88 +1]` feat(rag): 新增 embedding_query_policy (路径白名单)
- `[PR1 W88 +2]` feat(rag): 新增 embedding_consistency_check (CI 自检)
- `[PR1 W88 +3]` refactor(rag): embedding_service 加 has_query_prompt 透传 (前置修复)
- `[PR1 W88 +4]` refactor(rag): embedding_service 顶部接入 truncate + policy
- `[PR1 W88 +5]` refactor(rag): embedding_recalc 去除硬截
- `[PR1 W88 +6]` test(rag): 截断边界 + 路径白名单 + 一致性单测 (22/22 PASS)
- `[PR1 W88 +7]` docs(rag): CHANGELOG + CLAUDE.md 锚点段 + 5 件套守恒验证

## PR2 — knowledge_chunk 子表 + parent-child（W88 +8 → +21, 规划）

- 新增 `app/models/knowledge_chunk.py` + `alembic/versions/088_add_knowledge_chunk.py`（idempotent guard 复用 087 模式）
- 新增 `app/services/chunking_service.py`（预处理强制走 truncate_for_embedding）
- 门禁: chunk 行数 ∈ [1.5x, 6x] parent + 召回 P95 ≤ 80ms（10w chunk）+ FK 100%

## PR3 — BM25 增量 + pg_trgm + tsvector（W89 +0 → +16, 规划）

- 新增 `alembic/versions/089_add_gin_trgm_tsvector.py`（CONCURRENTLY + 离线窗口）
- 新增 `app/services/bm25_incremental.py`（消灭 N 次全量重建）
- 门禁: 1000 条入库 P95 ≤ 30s + GIN ≤ 120s + tsvector hit ±5% vs BM25

## PR4 — HybridRetriever 召回侧量化（W90 +0 → +14, 规划）

- 新增 `app/services/hybrid_weight_config.py` + `app/services/synonym_dict.py`（≥ 200 条）
- RRF 归一化 + CrossEncoder rerank（保留 ≥ 70%, 异常回退双路）
- 不改 `hybrid_retriever.py` 原函数签名（0 production code 非例外 PR）

## PR5 — RAGEvaluator 真召回率激活（W91 +0 → +18, 规划）

- 新增 `app/services/rag_eval_runner.py` + `app/models/rag_eval_report.py` + `alembic/versions/090_add_rag_eval_report.py`
- 新增 `tests/rag/test_recall_quality.py` + `tests/rag/test_faithfulness.py`（评估 10 件套件 5/6）
- ground-truth ≥ 100（双人标注）+ NDCG@10 ≥ 0.65, MRR ≥ 0.55 + 夜间 P95 ≤ 10min + 前端评分面板

## PR6 — SearchLog 前端接通（W92 +0 → +12, 规划）

- 新增 `app/api/v1/search_logs_admin.py` + 前端 `/admin/search-logs` ≥ 7 维分析页
- 门禁: 回收率 ≥ 30% + 慢查询 ≤ 5% + 锚点 0 regression; 前端 `npm run build` 唯一合法

## PR7 — 全链路 observability（W93 +0 → +14, 规划）

- 新增 `app/services/recall_observability.py` + `observability/grafana/rag_dashboard.json`（≥ 6 面板）
- 门禁: 按路耗时覆盖 100% + P99 ≤ 200ms + 结构化日志字段 ≥ 12

## PR8 — 知识图谱深度联动（W94 +0 → +20, 规划）

- 新增 `app/models/kg_entity.py` + `alembic/versions/091_add_kg_entity.py` + `app/services/entity_link_recall.py`
- input validation 复用 `kg_query_service.py` 白名单范式
- 门禁: 实体链 hit ≥ 25% + 图谱召回 P95 ≤ 100ms + 实体数 ≥ 5000 + qa-bench ≥ 96%

## PR9 — auto-research 升级（W95 +0 → +16, 规划）

- 新增 `app/services/auto_research_v2.py` + `app/services/dedup_cross_doc.py`
- LLM-as-judge 入 KB 质量门（确定性门禁）+ 人工抽检
- 门禁: 自动入 KB ≥ 70% + 跨文档去重 ≥ 95% + 同义改写 ≥ 50% + qa-bench ≥ 96.5%

## PR10 — docs/deploy/eval 三件套沉淀（W96 +0 → +10, 本次实施据实）

- `[W96 +0]` docs(rag): README.md RAG 系统总览 12 节 + 起步 memory
- `[W96 +1]` docs(rag): ROADMAP.md PR1-10 时间线 + 月度里程碑
- `[W96 +2]` docs(rag): 主仓 README/ROADMAP/CHANGELOG 加 RAG 章节链接 + 10 PR 一行摘要
- `[W96 +3]` docs(rag): RUNBOOK.md 部署/回滚/排错（alembic 第 0 节风险 + 12 项排错速查）
- `[W96 +4]` docs(rag): SCHEMAS.md 7 件套 schema 完整文档
- `[W96 +5]` test(rag): test_pr10_docs_e2e.py 文档存在性 + 章节数断言 + tests/rag/ 目录初建
- `[W96 +6]` docs(rag): RISKS.md 10 项风险详解 + 缓解 + 覆盖矩阵
- `[W96 +7]` docs(rag): EVAL.md 10 件套评估框架实操
- `[W96 +8]` docs(rag): CHANGELOG.md 10 PR changelog 汇总（本文件）
- `[W96 +9]` docs(rag): 派工 v11 模板落库（v10 补 6 项）+ CHECKLIST.md
- `[W96 +10]` docs(rag): FAQ.md + 据实上报 + memory 沉淀 + 5 件套守恒验证

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
