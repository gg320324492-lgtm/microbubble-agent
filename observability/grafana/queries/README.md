# RAG 召回可观测性 SQL 查询集 (W93 PR7 B-7)

按路召回耗时分解覆盖 100% 检索请求, 7 面板配套 SQL.

## 文件清单

| 文件 | grafana 面板 | 用途 |
|------|-------------|------|
| `01_recall_latency_percentiles.sql` | Panel 1: 召回延迟 P50/P95/P99 | 总耗时分布, P99 ≤ 200ms 硬门禁 |
| `02_per_path_latency.sql` | Panel 2: 按路召回耗时分解 | vector / bm25 / graph / rerank 四路 |
| `03_candidate_topk.sql` | Panel 3: 召回候选数 | candidate_k vs top_k 比例 |
| `04_ctr.sql` | Panel 4: CTR | 24h 滚动, 目标 ≥ 30% |
| `05_error_rate.sql` | Panel 5: 错误率 | 24h 滚动, error_count > 0 |
| `06_slow_query.sql` | Panel 6: 慢查询分布 | P99 > 200ms 自动告警 |

## 数据源

- 表: `search_logs` (PostgreSQL)
- 时间字段: `created_at`
- 12+ 结构化字段: `latency_ms` / `retrieval_method` / `candidate_k` / `top_k_actual` / `caller_path` / `for_query` / `has_query_prompt` / `vector_score` / `bm25_score` / `graph_score` / `rerank_score` / `per_path_latency_ms` / `slow_query` / `error_count`

## grafana 接入

导入 `../rag_dashboard.json` 即可 (PostgreSQL 数据源 uid=`pg-microbubble`).