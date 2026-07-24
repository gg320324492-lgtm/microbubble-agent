# W68 第 7 批 A-4: qa-bench v3.1 D5 (Dashboard KB 监控) 补齐

> 2026-07-24 · 锚点范式第 78 守恒 · 分支 `feat/qa-bench-d5-kb-monitor-2026-07-24`

## 一句话

plan `qa-bench-v3.1-decisions.md` 的 D5 (Dashboard KB 监控) 核心前端 `KbMonitorView.vue` + 配套后端一直缺失 (7/8 决策项已闭环, D5 单项缺, W68 第 6 批 Plan 深度审计 #4 定位). 本任务补齐 8 文件 (1 view + 1 api + 1 endpoint + router/layout 改动 + e2e + docs + memory), e2e 3 场景 PASS.

## 交付清单 (8 文件)

| # | 文件 | 类型 | 说明 |
|---|------|------|------|
| 1 | `web/src/views/admin/KbMonitorView.vue` | 新建 | 4 核心指标卡 + 4 ECharts 子图 + 失败列表, token 化 dark mode |
| 2 | `web/src/api/kbMonitor.js` | 新建 | 3 函数封装 (overview / queue-depth / failures) |
| 3 | `app/api/v1/admin_kb_monitor.py` | 新建 | 3 endpoint, admin only, write tier 30/min |
| 4a | `web/src/router/index.js` | 改动 | `/admin/kb-monitor` 路由 (直接 import, 无移动变体) |
| 4b | `web/src/layouts/MainLayout.vue` | 改动 | sidebar-bottom 加 "KB 监控" (isAdmin 守卫) |
| 4c | `app/main.py` | 改动 | import + include_router 注册 |
| 4d | `app/core/rate_limit.py` | 改动 | `/api/v1/admin/kb-monitor` → write tier |
| 5 | `web/tests/e2e/desktop_admin_kb_monitor.spec.js` | 新建 | 3 场景 (加载/4 图/dark mode) |
| 6 | `docs/admin-kb-monitor.md` | 新建 | 4 子图 + API + 部署 + alert 阈值 |
| 7 | `memory/w68-route-7-a4-...md` | 新建 | 本文件 |

## 4 ECharts 子图

- **入库趋势** (折线 ingested/done, 逐小时)
- **失败率** (折线 failed/ingested %, 逐小时)
- **成功/失败/重试对比** (柱状)
- **队列堆积** (饼图 pending/analyzing, 空队列显示"队列为空")

## 3 后端 endpoint

- `GET /admin/kb-monitor/overview?hours=24` — 核心统计 + 逐小时趋势 (单条 SQL `date_trunc('hour')` GROUP BY)
- `GET /admin/kb-monitor/queue-depth` — 队列快照 + eta_minutes (轻量, 可高频轮询)
- `GET /admin/kb-monitor/failures?limit=50&include_stuck=true` — 失败/滞留列表

全部 `Depends(get_current_admin)` (admin/leader), write tier 30/min.

## 数据源复用

- **knowledge 表 `analysis_status`** (pending/analyzing/done/failed)
- **`app/services/knowledge_polling_service.py`** (W68 第 6 批已建) — `MAX_ATTEMPTS=3` / `KB_POLLING_INTERVAL_SEC=300` / `DEFAULT_LIMIT=50`
- 队列深度以 **DB 计数** 为准, 不依赖 Celery inspect (worker 未连时也返回, 避免 500)
- "重试/滞留" 估算: 仍 pending 且 `created_at < now - MAX_ATTEMPTS × interval`

## 关键决策 / 踩坑

1. **KbMonitorView 无移动端变体** — 直接 `() => import('@/views/admin/KbMonitorView.vue')`, 不走 `resolveMobileComponent` (对齐 admin dashboard 性质, ECharts 响应式收窄即可). 与 AgentTracesView 有移动变体不同, 因为 KB 监控是低频 admin 巡检页.
2. **侧边栏入口 admin 守卫** — `isAdmin = ['admin','leader'].includes(userStore.userInfo?.role)` (用 raw role, 非 `userRole` 展示名 computed). 加在 `.sidebar-bottom` (项目动态旁), 因为 admin 路由无 `meta.icon` → 不进 `menuRoutes`.
3. **tz-aware → naive cutoff** — 复用 analytics.py 同款 `.replace(tzinfo=None)` (CLAUDE.md 2026-06-05 教训: knowledge.created_at server_default now() 为 naive).
4. **rate_limit 前缀匹配** — `path.startswith("/api/v1/admin/kb-monitor")` 放在 drive tier 判定后、analytics 判定前.
5. **e2e el-table stub 踩坑** — el-table-column 的 `#default="{ row }"` scoped slot 在 stub 下拿不到 row → 用 **provide/inject**: el-table `provide({ tableRows: () => data })`, el-table-column `inject` 后 `v-for` 注入 `:row`. 第一版直接 stub 空 slot 导致 `Cannot read properties of undefined (reading 'analysis_status')`.

## 验证

- **e2e**: `npx vitest run tests/e2e/desktop_admin_kb_monitor.spec.js` → **3 passed** (worktree 无 node_modules, 临时 cp 到 main checkout 跑, 跑完删除, main checkout git 干净)
- **Python 语法**: `ast.parse` 3 文件 (admin_kb_monitor / main / rate_limit) OK
- **settings.KB_POLLING_INTERVAL_SEC** 确认存在 (`app/config.py:120`)

## 部署必做 (主指挥 SSH)

无 alembic 迁移 (纯读现有列). 但新 endpoint 必须:
```bash
docker compose restart app     # 新 router 生效
cd web && npm run build         # 前端唯一合法 build (postbuild manifest hash)
```
详见 `docs/admin-kb-monitor.md` 部署段 + alert 阈值表.

## 纪律守恒

- **0 production code 改动铁律**: 本任务全部为**新增独立功能** (新 view/api/endpoint + router/layout 挂载点 + docs/memory), 不动老路径逻辑. 后端 endpoint 是新功能, 符合派工"后端 endpoint 不算老路径改动".
- **W19 选项 A 维持**.
- 不 merge (主指挥来 merge), push 到 origin.
