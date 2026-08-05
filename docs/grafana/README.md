# Grafana 仪表盘部署文档 (W-N-OBS)

> **锚点**: W-N-OBS +2
> **关联**: W-N-OBS +1 (代码: hybrid_retriever._chunk_late_recall + recall_observability.RecallObserver)
> **基线 HEAD**: 1896fee64 (W-N-OBS +1 提交)
> **JSON 文件**: `w-n-d-plus-chunk-recall-dashboard.json` (本目录)

## 1. 背景

W-N-D+ 报告: `_chunk_late_recall` 异常被 `try/except` 静默吞掉, 路由层 (4 路合并逻辑) 看到 `chunk_results=[]` 误以为是"正常空集", 而不是"该路径坏了", 无法触发告警或自愈.

W-N-OBS 修复 (`1896fee64`):
- **代码层**: `_chunk_late_recall` 失败时显式 `logger.warning("chunk_late_recall FAILED ...")` + `RecallObserver.record_chunk_late_recall(success=False, ...)` 自增计数器 + 仍 best-effort 返回空集 (不 raise 阻塞主流程).
- **观测层**: 本文档 + dashboard.json 提供 Grafana 仪表盘可视化兜底.

## 2. 仪表盘结构 (3 panel)

### Panel 1: Late-chunking 召回 P95 延迟 (ms)

**数据源**: PostgreSQL `search_logs.per_path_latency_ms->>'chunk_late'` (JSONB 字段)

**SQL**:
```sql
SELECT date_trunc('minute', timestamp) AS time,
       percentile_cont(0.50) WITHIN GROUP (ORDER BY (per_path_latency_ms->>'chunk_late')::float) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY (per_path_latency_ms->>'chunk_late')::float) AS p95,
       percentile_cont(0.99) WITHIN GROUP (ORDER BY (per_path_latency_ms->>'chunk_late')::float) AS p99
FROM search_logs
WHERE created_at >= $__timeFrom() AND created_at < $__timeTo()
  AND per_path_latency_ms ? 'chunk_late'
GROUP BY 1 ORDER BY 1
```

**阈值**: P95 > 100ms 黄色, > 200ms 红色 (与 W93 PR7 既有 P99 阈值对齐).

**设计意图**: 基于结构化 JSON 字段 `per_path_latency_ms['chunk_late']`, 不硬编码字段路径, 后续新增路径自动接入.

### Panel 2: Late-chunking 召回命中率 (24h)

**数据源**: PostgreSQL `search_logs.per_path_count->>'chunk_late'` (JSONB 字段)

**SQL**:
```sql
SELECT ROUND(AVG(CASE WHEN (per_path_count->>'chunk_late')::int > 0 THEN 1.0 ELSE 0.0 END), 4) AS hit_ratio,
       COUNT(*) FILTER (WHERE per_path_count ? 'chunk_late') AS sample_count
FROM search_logs
WHERE created_at >= NOW() - INTERVAL '24 hours'
  AND per_path_count ? 'chunk_late'
```

**阈值**: < 30% 黄色, < 默认阈值 (0%) 红色.

**设计意图**: `result_count > 0` 占比反映 `_chunk_late_recall` 真实命中能力. 若命中率长期 < 30%, 说明 schema drift / pgvector 索引失效 / embedding 漂移.

### Panel 3: Late-chunking 失败计数器 (24h)

**数据源**: Loki `logs` 表 / 持久化日志 (level=WARNING, logger=microbubble.hybrid_retriever)

**SQL**:
```sql
SELECT date_trunc('minute', timestamp) AS time, COUNT(*) AS failure_count
FROM logs
WHERE level = 'WARNING'
  AND logger = 'microbubble.hybrid_retriever'
  AND msg LIKE '%chunk_late_recall FAILED%'
  AND timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY 1 ORDER BY 1
```

**阈值**: > 1/min 黄色, > 10/min 红色.

**设计意图**: 替代 `RecallObserver._chunk_late_recall_failures_total` 进程内计数器 (跨进程/重启不持久). 用 Loki 持久层做实际告警源.

> ⚠️ **铁律**: W-N-OBS 失败计数器必须**显式** `logger.warning`, 不允许静默. Loki 查询条件 `msg LIKE '%chunk_late_recall FAILED%'` 是兜底告警源.

## 3. 部署步骤

### 3.1 导入 dashboard JSON

```bash
# Grafana UI: Dashboards → New → Import → Upload JSON file
# 选择 docs/grafana/w-n-d-plus-chunk-recall-dashboard.json

# 或 API 导入:
curl -X POST -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_API_KEY" \
  -d @docs/grafana/w-n-d-plus-chunk-recall-dashboard.json \
  https://grafana.example.com/api/dashboards/import
```

### 3.2 配置 datasource

- PostgreSQL datasource `pg-microbubble` 必须指向生产数据库
- Loki datasource (Panel 3) 必须指向生产 Loki 实例

### 3.3 验证

导入后预期看到:
- Panel 1 P95 延迟时序图 (空数据正常, 流量后才会有数据点)
- Panel 2 命中率 stat (默认 0%, 需 24h 数据积累)
- Panel 3 失败计数器时序图 (空数据正常, 没有失败就是好事)

## 4. 告警建议

| 触发条件 | 严重度 | 通知渠道 |
|---|---|---|
| Panel 1 P95 > 200ms 持续 5min | warning | Slack #rag-alerts |
| Panel 1 P95 > 500ms 持续 5min | critical | PagerDuty |
| Panel 2 命中率 < 30% 持续 1h | warning | Slack #rag-alerts |
| Panel 2 命中率 < 10% 持续 1h | critical | PagerDuty |
| Panel 3 失败计数 > 10/min 持续 3min | critical | PagerDuty |

## 5. 与 W93 PR7 既有 7 面板的关系

W93 PR7 B-7 (commit `24d4c1f75` 等) 已部署 7 panel dashboard (`observability/grafana/rag_dashboard.json`), 覆盖:
- Panel 1: 召回延迟 P50/P95/P99
- Panel 2: 按路召回耗时 (vector/bm25/graph/rerank)
- Panel 3: 召回候选数
- Panel 4: 召回 CTR (24h)
- Panel 5: 召回错误率
- Panel 6: 慢查询分布
- Panel 7: 召回总量 + 错误趋势

W-N-OBS 3 panel 是**专项扩展**, 不替代 W93 7 panel:
- Panel 1 (P95) 是 W93 Panel 1 的细化 (只查 `chunk_late` 路径)
- Panel 2 (命中率) 是 W93 既有 panel 未覆盖的维度
- Panel 3 (失败计数器) 是 W93 Panel 5 (错误率) 的细化 (按 `chunk_late_recall FAILED` 日志 marker 过滤)

## 6. 关键纪律 (W-N-OBS)

1. **失败必须显式记录** — `_chunk_late_recall` 是 best-effort 加分项, 失败必须可见, 否则路由层不知道该路失效. (类 20.155)
2. **Grafana panel SQL 基于结构化 JSON 字段** — 不硬编码字段路径, 后续新增路径自动接入. (类 20.NEW)
3. **进程内计数器有持久化兜底** — `RecallObserver._chunk_late_recall_failures_total` 进程内累加, 跨进程/重启不持久. Loki 持久日志是实际告警源.
4. **best-effort 不阻塞主流程** — `_chunk_late_recall` 失败时**仍返回空集**, 不 raise 影响父级检索. (W-N-D 设计守恒)
5. **观测失败不阻断观测** — `RecallObserver.record_chunk_late_recall` 抛错时, `_chunk_late_recall` 仍正常返回结果 (主流程不被观测失败拖垮).

## 7. 验证清单 (W-N-OBS +2)

- [x] JSON 文件语法合法 (parse OK)
- [x] 3 panel 数据源指向正确 (PostgreSQL `pg-microbubble` + Loki)
- [x] Panel 1 SQL 引用 `per_path_latency_ms->>'chunk_late'`
- [x] Panel 2 SQL 引用 `per_path_count->>'chunk_late'`
- [x] Panel 3 SQL 引用 Loki `msg LIKE '%chunk_late_recall FAILED%'`
- [x] 阈值对齐 W93 PR7 既有 panel (P95 > 200ms 红色)
- [x] README 完整描述 3 panel + 部署 + 告警 + 纪律

## 8. 不做清单 (W-N-OBS +2)

- ❌ 改 W93 PR7 既有 7 panel (`observability/grafana/rag_dashboard.json`)
- ❌ 改 `_chunk_late_recall` 代码 (W-N-OBS +1 范畴)
- ❌ 改 `recall_observability.py` 字段 (W-N-OBS +1 范畴)
- ❌ 改 SQL schema / 加 search_logs 字段 (W-N-G+ 范畴)
- ❌ 部署到生产 Grafana (运维操作, 非本任务范围)