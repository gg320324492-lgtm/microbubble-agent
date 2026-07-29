# W93 PR7 B-7 RAG Observability Runbook

> **创建**: 2026-07-30
> **锚点范式**: W93 +0 → +14 (15 commits)
> **主指挥协调范式**: 第 67 次派工

## 1. PR7 概述

PR7 B-7 (W93) 实施 RAG 召回全链路 observability. 不动老路径, 仅添加观测.

## 2. 文件清单

### 2.1 新增 (8 个核心)

| 路径 | 作用 |
|------|------|
| `app/services/recall_observability.py` | RecallTrace dataclass + RecallObserver + per_path 聚合 |
| `observability/grafana/rag_dashboard.json` | 7 块 grafana 面板 (延迟/按路/候选/CTR/错误率/慢查询) |
| `observability/grafana/queries/01_recall_latency_percentiles.sql` | P50/P95/P99 分布 |
| `observability/grafana/queries/02_per_path_latency.sql` | 按路耗时分解 |
| `observability/grafana/queries/03_candidate_topk.sql` | candidate_k vs top_k |
| `observability/grafana/queries/04_ctr.sql` | CTR 24h 滚动 |
| `observability/grafana/queries/05_error_rate.sql` | 错误率 |
| `observability/grafana/queries/06_slow_query.sql` | 慢查询分布 |
| `observability/grafana/queries/README.md` | SQL 配套说明 |
| `scripts/check_observability_coverage.sh` | 5 件套自检脚本 |
| `tests/rag/__init__.py` | tests/rag 目录初始化 |
| `tests/rag/test_pr7_e2e.py` | 22 case e2e 测试 |
| `memory/w93-rag-pr7-start-2026-07-30.md` | 起步 memory |

### 2.2 修改 (2 个, 严守 0 production code 例外)

| 路径 | 修改内容 |
|------|---------|
| `app/services/hybrid_retriever.py` | 提取 `_retrieve_impl` 包裹原 logic body 字面照搬; retrieve() 签名不变; 4 路开关默认 = True 不动 |
| `app/models/search_log.py` | 仅 ADD 19 nullable 字段 (不动老字段) |

## 3. 部署清单

PR7 不涉及 alembic 迁移, 不涉及前端构建. 部署步骤:

```bash
# 1. 代码 pull
git pull origin chore/w93-rag-pr7-observability-2026-07-30

# 2. 重启 app (recall_observability 加载)
docker compose restart app

# 3. (可选) 导入 grafana 面板
#    Grafana UI → Dashboards → Import → 上传 observability/grafana/rag_dashboard.json
#    数据源: PostgreSQL (uid=pg-microbubble)
```

## 4. 慢查询告警配置

```bash
# 环境变量 (默认 200ms)
RECALL_P99_LATENCY_MS=200
RECALL_SLOW_QUERY_MS=150
RECALL_OBSERVABILITY_ENABLED=1  # 1=开 (默认), 0=关 (返回 NullTrace)
```

## 5. 验证脚本

```bash
# 5 件套自检
bash scripts/check_observability_coverage.sh

# 仅 e2e 测试
SKIP_DB_SETUP=1 python -m pytest tests/rag/test_pr7_e2e.py -v --ignore=tests/test_w79_commercial_private_deployment_e2e.py
```

## 6. 监控面板字段对照

| grafana 面板 | 数据源 SQL | 关键指标 |
|------------|-----------|---------|
| 1. 召回延迟 P50/P95/P99 | 01_recall_latency_percentiles.sql | P99 ≤ 200ms |
| 2. 按路召回耗时 | 02_per_path_latency.sql | vector / bm25 / graph / rerank |
| 3. 召回候选数 | 03_candidate_topk.sql | candidate_k vs top_k |
| 4. CTR | 04_ctr.sql | 24h 滚动, 目标 ≥ 30% |
| 5. 错误率 | 05_error_rate.sql | error_count > 0 占比 |
| 6. 慢查询 | 06_slow_query.sql | P99 > 200ms 占比 |
| 7. 总览 (dashboard 顶部) | — | 各面板 gridPos 布局 |

## 7. 铁律沉淀

详见 `CHANGELOG.md` W93 PR7 段 — 8 条铁律:

1. observability hook 仅添加包裹, 不改原 logic
2. search_log 扩展字段全 nullable=True
3. RecallTrace 字段 ≥ 12 是硬门禁
4. grafana 面板数 ≥ 6 是硬门禁
5. 按路召回耗时覆盖 100%
6. 慢查询阈值 P99 > 200ms 触发 WARNING
7. e2e 测试 22/22 PASS 是硬门禁
8. 不向 alembic/versions 添加新迁移

## 8. 回滚预案

PR7 无 alembic 迁移, 回滚简单:

```bash
# 单 commit 回滚 (推荐)
git revert <merge_commit>

# 紧急短路 observability (零代码回滚)
RECALL_OBSERVABILITY_ENABLED=0 docker compose restart app
```

## 9. 与 PR6 衔接

PR7 复用 `app/models/search_log.py` + `app/api/v1/analytics.py` 埋点样板 (plan §11.1). PR6 已落 SearchLog 前端接通, PR7 在此基础上扩展 backend observability, 不破坏 PR6 已有路径.

## 10. 派工前提铁律应用

- 段 6 据实上报铁律: W82/W84/W85 实战沉淀 (禁止凑锚点/纸面 PASS/脑补 head)
- 件 1-5 守恒: W73/W74 起步纪律 6 项 + 派工 v10 必填段
- 件 9 0 production code: hybrid_retriever 仅提取 _retrieve_impl, 原 logic body 字面照搬, 算法不变; search_log 仅 ADD 字段, 不破坏老 schema