# W71 第 71 批 B-5: Dashboard MVP 补全 + CI smoke 200 题拆 2 step (子 plan ② 收口)

> **锚点范式第 200 守恒** · 2026-07-24 · 分支 `chore/w71st-batch-b5-dashboard-smoke-2026-07-24`

## 背景

`docs/chatgpt-structured-floyd-w69-plan.md` §2.5 + `docs/qa-bench-d8-comprehensive-survey-2026-07-24.md` §5.1 真验证:
Dashboard MVP + CI smoke 200 题 **部分实施**, 本任务补齐缺口 (子 plan ② 收口).

- **Dashboard MVP 现状** (W68 第 7 批 A-4 `bc3a60619` 交付 4 ECharts 子图 + 4 指标卡): 缺 2 el-card (7 天入库/回滚) + 5min polling + 5 新 ECharts + 7 天统计
- **CI smoke 200 题现状** (workflow + ci.yml + questions_smoke_200.jsonl): 缺 5min timeout 不现实 (W69 plan 备注 LOW 缺口)

## 交付

### 1. Dashboard MVP 补全 (`web/src/views/admin/KbMonitorView.vue`)

- **2 新 el-card** (`.metric-row-7d`, 2 列布局):
  - 本周新增入库 = `weekly7dIntake` computed (`summary.weekly_intake[7]` 求和) + "每 5 分钟自动刷新"提示
  - 本周回滚 = `weekly7dRollback` computed (`summary.rollback_count`), >0 时 danger 色
- **5min polling**: 集成 `useKbMonitor()` composable (复用 `/knowledge/auto-intake-summary`, 自带 `setInterval 5*60*1000` + 30s timeout 防御 + onUnmounted 自动 clearInterval)
- **5 新 ECharts 卡片** (2+2+1 布局, `.chart-card-full` 末卡横跨):
  - 📊 7 天入库趋势 (逐日 bar, weekday labels) · ↩️ 7 天回滚量 (gauge)
  - 🛡️ 5 道防线触发 (横向 bar: 语义去重/质量门槛/矛盾检测/负反馈/rollback) · 🎯 7 维评分 (radar)
  - 🔍 抽检率 (pie: 已抽检/未抽检)
- **watch(summary)**: 5min polling 拉到新数据后重渲 7 天入库/回滚/防线图
- ECharts 生命周期: 9 chart (4 旧 + 5 新) 统一 initChart / handleResize / onUnmounted dispose + 置 null

### 2. CI smoke 200 题拆 2 step (`.github/workflows/qa-bench-smoke.yml`)

原 1 step 单次 `--smoke` 跑全 200 题 (5min 不现实) → 拆 2 step:
- **主测 100 题**: `--smoke --limit 100 --output results/smoke-main` (≤ 2min)
- **抽测 100 题**: `--smoke --offset 100 --limit 100 --output results/smoke` (≤ 3min)
- 下游 `Fail if pass_rate < 80%` 读 `results/smoke/results.json` (抽测段输出) 不变

### 3. runner.py 新增 `--offset` (`tests/qa-bench/runner.py`)

- `parser.add_argument("--offset", type=int, default=0)` — 跳过前 N 题
- 切片顺序: `questions = questions[args.offset:]` 后再 `questions[:args.limit]` (主测/抽测拆段)
- tests/qa-bench 是 §3 允许例外目录

### 4. e2e 测试 (`web/tests/e2e/kb-monitor-dashboard.spec.js`, 4 场景 4/4 PASS)

- **scenario_1**: 2 新 el-card 渲染 (7 天入库 120 条 + 7 天回滚 8 条 + 5min polling 提示)
- **scenario_2**: 5min polling 触发 — `vi.useFakeTimers` + mock axios, `advanceTimersByTimeAsync(5min)` 后第 2 次 fetch + 30s timeout 断言
- **scenario_3**: 5 新 ECharts 卡片标题渲染
- **scenario_4**: 4 旧 ECharts 子图仍在 + 总计 9 canvas + echarts.init 9 次 (回归守卫)
- 同步更新 `desktop_admin_kb_monitor.spec.js` 场景 2: 4 → 9 chart 断言 (7/7 PASS)

## 验证

- **e2e**: `vitest run kb-monitor-dashboard.spec.js desktop_admin_kb_monitor.spec.js` → 7/7 PASS (4 新 + 3 旧)
- **npm run build**: ✓ built in 1.65s (本分支 build 脚本为 `vite build`, 无 manifest hashing)
- **typing imports**: 171 文件 0 错
- **runner.py / workflow.yml**: ast.parse + yaml.safe_load 双通过

## 铁律沉淀 (3 新)

1. **worktree 缺 node_modules 用 junction 复用主仓库** — `cmd //c "mklink /J node_modules E:\...\web\node_modules"`, 避免 worktree 独立 npm install 数分钟
2. **Dashboard 补卡不动业务 API** — 复用现有 `useKbMonitor` + `/knowledge/auto-intake-summary`, 新增卡片全部消费已有字段 (weekly_intake / rollback_count), 0 后端改动
3. **CI smoke 拆段用 offset+limit 双切片** — runner.py `questions[offset:][:limit]` 顺序, 主测/抽测 output 分目录, gate 只读抽测段 results.json

## 0 production code 改动铁律 16/15 守恒

- `web/src/views/admin/KbMonitorView.vue` — 派工 v6 允许例外 (admin UI)
- `.github/workflows/qa-bench-smoke.yml` — CI 配置, 非业务代码
- `tests/qa-bench/runner.py` — §3 tests/qa-bench 允许例外
- `web/tests/e2e/*.spec.js` — 测试目录

## commit

`feat(w71st-batch-b5): Dashboard MVP 补 2 el-card + 5min polling + CI smoke 200 题拆 2 step`
