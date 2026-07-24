# KB 自动入库监控 (admin-kb-monitor)

> qa-bench v3.1 决策 D5 (Dashboard KB 监控) — W68 第 7 批 A-4 (2026-07-24)
> 锚点范式第 78 守恒.

## 背景

plan `.claude/plans/qa-bench-v3.1-decisions.md` 的 D1-D8 决策中, **D5 (Dashboard KB 监控)** 一直缺失核心实现:

- 核心前端 `web/src/views/admin/KbMonitorView.vue` 不存在 (admin 目录仅 AgentTracesView / AnalyticsView / AuditLogView 三个)
- 配套后端 endpoint 缺失

W68 第 6 批 Plan 深度审计 #4 定位到此缺口 (7/8 决策项已闭环, D5 单项缺). 本 PR 补齐:
1. 后端 `app/api/v1/admin_kb_monitor.py` (3 endpoint)
2. 前端 API `web/src/api/kbMonitor.js`
3. 前端 dashboard `web/src/views/admin/KbMonitorView.vue` (4 ECharts 子图)
4. 路由 `/admin/kb-monitor` + MainLayout 侧边栏 "KB 监控" 入口 (admin/leader only)
5. e2e `web/tests/e2e/desktop_admin_kb_monitor.spec.js` (3 场景)

## 数据源

监控页数据来自 **knowledge 表的 `analysis_status` 列** (pending/analyzing/done/failed) 与后台轮询服务:

- `app/services/knowledge_polling_service.py` — Celery beat 每 `KB_POLLING_INTERVAL_SEC` (默认 300s = 5 分钟) 后台批处理 pending 行 (每批 50 条, `DEFAULT_LIMIT`)
- 失败的行 rollback 后**保持 pending**, 下一轮重试 (`MAX_ATTEMPTS=3`, 指数退避)
- 因此 "滞留 pending 且 `created_at` 早于 `MAX_ATTEMPTS × interval` 前" 近似 = 多次失败、需人工介入的项

监控页**不依赖 Celery inspect** — 队列深度以 DB 计数为准, worker 未连时也能返回 (避免 500).

## 4 子图说明

| 子图 | 类型 | 含义 |
|------|------|------|
| **入库趋势** | 折线 (ingested / done) | 逐小时新入库数 + 成功分析数, 看吞吐量 |
| **失败率** | 折线 (failed / ingested %) | 逐小时失败占比, 突增说明 LLM 分析服务异常 |
| **成功 / 失败 / 重试对比** | 柱状 | 窗口内 done / failed / retrying 三态总量对比 |
| **队列堆积** | 饼图 (pending / analyzing) | 当前待处理 + 分析中, 空队列显示"队列为空" |

4 核心指标卡: 窗口内入库数 / 成功率 (≥90% 良好, <70% 需关注) / 失败数 / 重试滞留数.

底部失败列表: `analysis_status='failed'` + 超轮次仍 pending 的滞留项 (id / 标题 / 状态 / 质量分 / 入库时间, 滞留项带"滞留" tag).

## API

全部 **admin/leader only** (`Depends(get_current_admin)` 兜底, 普通用户 403), **write tier 30/min** (`app/core/rate_limit.py` `/api/v1/admin/kb-monitor` 前缀匹配).

### `GET /api/v1/admin/kb-monitor/overview?hours=24`

`hours` 1-168 (默认 24, 最长 7 天). 返回:

```json
{
  "hours": 24,
  "ingested": 42,
  "done": 38,
  "failed": 3,
  "retrying": 1,
  "queue_depth": 6,
  "success_rate": 0.9048,
  "status_counts": {"done": 38, "failed": 3, "pending": 1},
  "polling_interval_sec": 300.0,
  "trend": [
    {"hour": "2026-07-24T08:00:00", "ingested": 10, "done": 9, "failed": 1}
  ]
}
```

趋势按小时 bucket (`date_trunc('hour', created_at)`) 单条 SQL GROUP BY 聚合.

### `GET /api/v1/admin/kb-monitor/queue-depth`

轻量快照 (可高频轮询):

```json
{
  "pending": 5,
  "analyzing": 1,
  "queue_depth": 6,
  "polling_interval_sec": 300.0,
  "batch_size": 50,
  "eta_minutes": 5.0
}
```

`eta_minutes = ceil(queue_depth / batch_size) × interval / 60` — 估算清空时间.

### `GET /api/v1/admin/kb-monitor/failures?limit=50&include_stuck=true`

失败 / 滞留列表. `include_stuck=true` (默认) 时额外纳入超 `MAX_ATTEMPTS` 轮仍 pending 的滞留项:

```json
{
  "items": [
    {"id": 101, "title": "...", "analysis_status": "failed",
     "quality_score": null, "created_at": "...", "is_stuck": false}
  ],
  "total": 1
}
```

## 主指挥 SSH 部署必做

**本 PR 无数据库迁移** (纯读 knowledge 表现有列), 无需 alembic. 但新增后端 endpoint 必须重启 Python 进程 (CLAUDE.md 752 行铁律):

```bash
# 1. 拉取代码 (主指挥本地 PC, 云 server 走 FRP)
git pull

# 2. 重启后端 (新 router 生效)
docker compose restart app

# 3. 前端重新 build (唯一合法命令, 见 CLAUDE.md 2026-07-11 铁律)
cd web && npm run build
git add -f web/dist/manifest.*.webmanifest   # hashed manifest 需 force-add
# (postbuild-fix-manifest.js 自动处理)

# 4. 验证 endpoint (需 admin token)
curl -sk -H "Authorization: Bearer <admin_token>" \
  "https://<SITE_DOMAIN>/api/v1/admin/kb-monitor/queue-depth"
# 期望返回 {"pending":...,"analyzing":...,"queue_depth":...}
# 普通用户 token → 403 需要管理员权限
```

## Alert 阈值 (建议)

监控页仅展示, 不主动告警. 主指挥人工巡检建议阈值:

| 指标 | 良好 | 关注 | 告警 |
|------|------|------|------|
| 成功率 (success_rate) | ≥ 90% | 70%-90% | < 70% |
| 队列深度 (queue_depth) | ≤ 50 | 50-200 | > 200 (轮询追不上) |
| 重试/滞留 (retrying) | 0 | 1-10 | > 10 (LLM 服务持续异常) |
| 失败率 (逐小时) | < 5% | 5%-20% | > 20% |

**队列深度 > 200 且持续增长** = 后台轮询处理不过来, 排查:
1. `docker logs microbubble-agent-celery-worker-1 --tail 100 | grep knowledge_polling`
2. LLM 分析服务 (`llm_analysis_service`) 是否连通 (Claude API / 本地模型)
3. `KB_POLLING_INTERVAL_SEC` 是否被调太大, 或 `celery-beat` 未运行

## 相关文件

- 后端: `app/api/v1/admin_kb_monitor.py`
- 前端 API: `web/src/api/kbMonitor.js`
- 前端 dashboard: `web/src/views/admin/KbMonitorView.vue`
- 路由: `web/src/router/index.js` (`/admin/kb-monitor`)
- 侧边栏入口: `web/src/layouts/MainLayout.vue` (`isAdmin` 守卫)
- 限流: `app/core/rate_limit.py` (`/api/v1/admin/kb-monitor` → write tier)
- 注册: `app/main.py`
- e2e: `web/tests/e2e/desktop_admin_kb_monitor.spec.js`
- 数据源: `app/services/knowledge_polling_service.py`
- plan: `.claude/plans/qa-bench-v3.1-decisions.md` (D5)
- memory: `memory/w68-route-7-a4-qa-bench-d5-kb-monitor-2026-07-24.md`
