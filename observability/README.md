# `observability/` — Grafana 仪表盘配置

> **目录边界（结构重构批次 6，2026-10-10 补）**：本目录是 **Grafana 仪表盘资产**
> （provisioning + 查询 SQL）。
> ⚠️ **`docker-compose.yml` 对本目录零引用是正常状态，不是孤儿目录** —— 见下方说明。

## 内容清单

```
observability/grafana/
├─ provisioning/
│   ├─ dashboards/default.yaml   # 仪表盘自动加载 (Grafana 启动时读)
│   └─ datasources/default.yaml  # 数据源定义 (PostgreSQL)
├─ queries/                      # 6 个配套查询 SQL (W93 PR7 B-7)
│   ├─ README.md
│   ├─ 01_recall_latency_percentiles.sql
│   ├─ 02_per_path_latency.sql
│   ├─ 03_candidate_topk.sql
│   ├─ 04_ctr.sql
│   ├─ 05_error_rate.sql
│   └─ 06_slow_query.sql
└─ rag_dashboard.json            # 7 面板仪表盘定义
```

## 面板内容

| # | 面板 | 用途 |
|---|---|---|
| 1 | 召回延迟 P50/P95/P99 | 总耗时分布，**P99 ≤ 200ms 硬门禁** |
| 2 | 按路召回耗时 (vector/bm25/graph/rerank) | 四路耗时分解 |
| 3 | 召回候选数 (candidate_k vs top_k) | 候选 → 实际返回的收敛比 |
| 4 | 召回 CTR (24h 滚动) | 目标 ≥ 30% |
| 5 | 召回错误率 (24h) | `error_count > 0` |
| 6 | 慢查询分布 (P99 > 200ms) | 超时自动告警 |
| 7 | 召回总量 + 错误 (24h 趋势) | 总量走势 |

**数据源**：表 `search_logs`（PostgreSQL），时间字段 `created_at`（**UTC 存储**，
类 20.221：DB 存 UTC、主机 +0800，跨系统比对时间必须显式换算）。
结构化字段含 `latency_ms` / `retrieval_method` / `candidate_k` / `top_k_actual` /
`caller_path` / `per_path_latency_ms` / `slow_query` / `error_count` 等。

---

## ⚠️ 为什么 compose 里找不到它 —— 这是**约定路径**消费，不是死代码

Grafana 容器按 Grafana 生态的**标准约定**读取这些文件，配置写在
`provisioning/dashboards/default.yaml` 里：

```yaml
providers:
  - name: default
    type: file
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards   # ← 容器内路径，不是仓库路径
      foldersFromFilesStructure: true
```

仓库里这份 `default.yaml` 的作用是**告诉 Grafana 去哪读**；真正的
`rag_dashboard.json` 与 provisioning 目录由 Grafana 容器按挂载/拷贝约定落到
`/var/lib/grafana/` 下。因此：

- `docker-compose.yml` 里**grep 不到**本目录路径，不是漏挂载；
- **不要**为了"让 compose 引用它"而改 compose —— 那是在给一个已经工作的链路
  加一层无意义的耦合；
- 反过来说，本目录**也不该被移动或改名**：provisioning 路径是外部工具的契约，
  动了要同步改 Grafana 侧的挂载。

详细的面板 ↔ SQL 对照见 [`grafana/queries/README.md`](grafana/queries/README.md)。
