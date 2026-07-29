---
name: w68-route-9-b4-chatgpt-w69-plan-2026-07-24
description: "W68 第 9 批 B-4 agent 派工 — chatgpt-structured-floyd 2/3 子 plan W69 调研. 锚点范式第 111 守恒. 子 plan ① chat history 8 phase 已 W68 #043 闭环 (不返工), 子 plan ② qa-bench 7 维 + KB 闭环 + Dashboard MVP 建议 W69 派工 5 agents (0 production code 改动铁律可守恒), 子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb 建议 W70 派工 4 agents (需主指挥破例)."
metadata:
  node_type: memory
  type: project
  originSessionId: W68-9th-batch-B-4
  modified: 2026-07-24T00:00:00.000Z
---

# W68 第 9 批 B-4 agent 派工 — chatgpt-structured-floyd W69 子 plan 调研 (2026-07-24 — 锚点范式第 111 守恒)

> 锚点范式第 111 守恒: 跨季度 plan 拆子 + W69 派工依据 + 子 plan 顺序 + 已闭环 1/3 不返工 + Dashboard MVP 必备 5 新铁律沉淀. 锚点范式 W68 第 8 批 90 → W68 第 9 批 **111** 单调上升 (本任务第 21 守恒).

## TL;DR

🎯 **W68 第 9 批 B-4 agent 调研完成** — 主指挥 W68 第 8 批 C-3 agent 修订原 plan 头部 Status 字段后 (1/3 子 plan 完成, 2/3 留 W69/W70), 本 B-4 agent 调研子 plan ② (qa-bench 7 维 + KB 闭环 + Dashboard MVP) + 子 plan ③ (UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb) W69/W70 派工预排. **新建 `docs/chatgpt-structured-floyd-w69-plan.md` (823 行)** 含 9 节完整调研 + W69/W70 派工预排 5+4 agents + 主指挥 7 关键决策点 + 0 production code 改动铁律分析 + 锚点范式增长预估 +10 守恒 (90 → 100).

**核心结论**:
- 子 plan ① chat history 8 phase: ✅ W68 #043 闭环 (不返工)
- 子 plan ② qa-bench 7 维 + KB 闭环 + Dashboard MVP: ✅ 建议 W69 派工 5 agents (58h)
- 子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb: ✅ 建议 W70 派工 4 agents (28h)
- 总投入: 86h (2 周, 锚点范式 +10 守恒)
- 0 production code 改动铁律: 子 plan ② 可守恒 + 子 plan ③ 不守恒 (主指挥破例)

**Why**: W68 第 6 批 5 agent 实战审计 67 plans 时发现 `chatgpt-structured-floyd.md` 标记 COMPLETED 但实际是 3 子 plan 拼接 (chat history 8 phase + qa-bench 7 维 + UI redesign), 真实完成度仅 1/3. W68 第 8 批 C-3 agent 修订头部 Status 后, 主指挥派 W68 第 9 批 B-4 agent 调研剩余 2/3 子 plan W69/W70 派工可行性.

**How to apply**: 见下方 W69 子 plan ② 派工预排 (5 agents: 7 维算法 / 5 道防线 / auto_intake_rollback / KB 闭环 / Dashboard+smoke) + W70 子 plan ③ 派工预排 (4 agents: NavRail / TS+BC / ChatViewSSE 3-zone / 移动端同步) + 锚点范式增长预估 + 5 新铁律沉淀.

---

## 1. 上下文快照 (W68 第 9 批 B-4 起点)

- **W68 第 1 批 (锚点范式第 30 守恒)**: 14+1 agents Drive v2 PR8 + Mobile UX v3.0 跨主题并行收官
- **W68 第 2 批 (锚点范式第 32 守恒)**: 路线 E baseline 守恒验证报告 (71 PASS + 7 SKIP)
- **W68 第 3 批 (锚点范式第 42 守恒)**: 11 agents Drive v2 PR9 评论/版本 + qa-bench D6 调研 + Mobile UX v3.1
- **W68 第 4 批 (锚点范式第 57 守恒)**: 15 agents W68 第 3 批留待办 10/10 闭环 + Plan 闭环 2/2
- **W68 第 5 批 (锚点范式第 72 守恒)**: 15 agents 文档同步 + Drive PR10 协同 + qa-bench D6 Phase 1 + 部署验证
- **W68 第 6 批 (锚点范式第 73 守恒, 深度审计)**: 5 agents 深度审计 67 plans 实际完成度, 发现 5 真未实施 + 12 PARTIAL_REGRESSION + 14 Status 错位
- **W68 第 7 批 (锚点范式第 87 守恒)**: 15 agents plans 闭环 + Status 修正 + 路线驱动 fallback
- **W68 第 8 批 (锚点范式第 90 守恒)**: 15+1 agents plans 同步 + 8th merge + CLAUDE.md 纪律 + hotfix + 9th batch 启动
- **W68 第 9 批 (本批, 锚点范式第 91-111 守恒)**: B-4 agent 调研 chatgpt-structured-floyd 2/3 子 plan W69 派工
- **W67 累计 50+ 步收官**: qa-bench D5 gate docs/CI 占位 + 28 守恒 + 0 production code 改动铁律
- **chatgpt-structured-floyd.md**: W68 第 6 批审计发现 = 3 子 plan 拼接 (COMPLETED 标记不准确)
- **chat history 8 phase**: W68 #043 已完整闭环 (Phase 1-8 全收官, 5 commits)
- **W68 第 8 批 C-3 agent**: 修订 plan 头部 Status 字段 (1/3 子 plan 完成, 2/3 留 W69)
- **W68 第 9 批 B-4 (本任务)**: 调研子 plan ②/③ W69/W70 派工预排
- **W68 第 9 批 main HEAD**: `f14cb43c1` (W68 第 8 批 A-1 收官后)
- **锚点范式 38+ baseline 守恒**: 71 PASS + 7 SKIP, 跨 140+ commit 0 regression

---

## 2. chatgpt-structured-floyd 3 子 plan 拆解

### 2.1 子 plan ① chat history 8 phase ✅ W68 #043 闭环 (不返工)

| Phase | 内容 | Commit | 状态 |
|---|---|---|---|
| Phase 1 | ORM + alembic 039_chat_history.py | `558962b1` | ✅ |
| Phase 2 | 11 个后端 API 端点 | `558962b1` | ✅ |
| Phase 3 | 流式 chat 持久化 | `5bf7c5c7` | ✅ |
| Phase 4 | 前端 store | `af8c8f7d` | ✅ |
| Phase 5 | 旧数据迁移 | `af8c8f7d` | ✅ |
| Phase 4+5 fix | sync_from_local tz-aware datetime 500 | `a1dfca2c` | ✅ |
| Phase 6 | UI 升级 (11 sub-tasks, vitest 492/492 PASS) | `9052906de` | ✅ |
| Phase 7 | Celery 30 天清理 (pytest 7/7 PASS) | (后续) | ✅ |
| Phase 8 | 测试 + 沉淀 | (后续) | ✅ |

**W69 派工不动子 plan ①** — 已闭环的不返工.

### 2.2 子 plan ② qa-bench 7 维 + KB 闭环 + Dashboard MVP (W69 派工 ⏸)

**总体目标**: 量化能力现状 + 定位改进点 + 建立回归基线

**核心内容**:
- **7 维评分体系**: Intent (10%) / Tool (25%) / Content (30%) / Rich Block (5%) / 防御 (15%) / 性能 (10%) / 一致性 (5%)
- **780 题底数**: 12 业务域 500 + 高级 100 + 横切 100 + 极端 80
- **save_to_kb.py 5 道防线**: dedup / 长度过滤 / LLM 拒答检测 / 敏感词 / 人工抽检
- **Celery auto_intake_rollback_task**: 每日 4:00 巡检 24h 内入库 + 引用失效 / 下游点击 < 3 → 自动 rollback + 告警
- **KB 闭环**: 评测 pass → 5 道防线 → 入库 → 抽检 → 回滚
- **Dashboard MVP**: 4 指标卡 (入库数 / 通过率 / 抽检数 / 告警数) + 5min polling
- **CI smoke 200 题**: GitHub Actions < 5min 通过

**5 agents 派工预排**:
- Agent #1: 7 维评分算法 (16h)
- Agent #2: 5 道防线 (12h)
- Agent #3: Celery auto_intake_rollback_task (8h)
- Agent #4: KB 闭环端到端 (12h)
- Agent #5: Dashboard MVP + CI smoke (10h)
- **总计 58h (约 1.5 周)**

### 2.3 子 plan ③ UI redesign NavRail + ThinkingModeSwitch + ChatBreadcrumb (W70 派工 ⏸)

**总体目标**: 解决 4 个用户可观察痛点 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) + 3-Zone 重新分区

**核心内容**:
- **NavRail.vue** (NEW ~250 行): 跨 desktop + mobile 统一左侧导航
- **ThinkingModeSwitch.vue** (NEW ~80 行): 3 档模式 (⚡快速 / ⚖平衡 / 🧠深度) + segmented control
- **ChatBreadcrumb.vue** (NEW ~60 行): 中央标题 + 在线状态 + breadcrumb path
- **SessionSidebar 重构**: actions 改 right-click + long-press (修复 overlap bug)
- **ChatViewSSE 顶栏 3-zone 重构**: 左 nav rail + 中央 ChatBreadcrumb + 右 + FAB
- **移动端同步**: MobileSessionDrawer + MobileThinkingModeSwitch
- **Playwright 视觉回归 baseline 重建**

**4 agents 派工预排**:
- Agent #1: NavRail.vue + SessionSidebar 重构 (6h)
- Agent #2: ThinkingModeSwitch.vue + ChatBreadcrumb.vue (6h)
- Agent #3: ChatViewSSE 顶栏 3-zone 重构 (8h)
- Agent #4: 移动端同步 + 视觉回归 + 测试 + 沉淀 (8h)
- **总计 28h (约 1 周)**

### 2.4 跨子 plan 总投入

- 总投入: **86h (2 周, W69 + W70)**
- 主指挥 grand closure × 2
- 锚点范式预估增长: +10 守恒 (90 → ~100)
- W19 选项 A 维持 (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)

---

## 3. W69 派工依据 (主指挥 7 关键决策点)

### 3.1 子 plan ② 是否 W69 派工？

**建议**: ✅ **W69 派工**

**理由**:
1. **锚点范式增长空间**: W68 第 8 批 90 → W69 子 plan ② 派 5 agents + W70 子 plan ③ 派 4 agents = 估 100+
2. **0 production code 改动铁律可守恒**: 子 plan ② 全部新增文件 (15+ 新文件), 不动现有 production code
3. **闭环路线明确**: save_to_kb.py 改造 + 5 道防线 + auto_intake_rollback + Dashboard + CI smoke = 端到端闭环
4. **风险可控**: 灰度发布开关 `AUTO_KB_INTAKE_ENABLED=False` 默认关, 可分阶段手动开启
5. **主指挥可拍板权重争议**: 7 维权重 10/25/30/5/15/10/5 默认值可由主指挥直接拍板

### 3.2 子 plan ③ 是否 W70 派工？

**建议**: ✅ **W70 派工** (W69 完成后立即启动)

**理由**:
1. **不依赖子 plan ②**: UI redesign 独立于 qa-bench, 可并行/串行
2. **用户痛点明确**: 4 个现存问题 (overlap / 🧠🧠 / aria-label / 顶栏拥挤) 都是用户可观察的
3. **复用现有 utilities**: NavRail/ThinkingModeSwitch/ChatBreadcrumb 全部基于现有 useUiStore + useThemeStore + SessionSidebar 模式
4. **风险可控**: Playwright baseline 重建是已知流程, dark mode + a11y 4-attr 已有铁律

### 3.3 关键决策点 (待主指挥拍板)

| # | 决策项 | 选项 | 建议 |
|---|---|---|---|
| 1 | 7 维权重默认值 | 10/25/30/5/15/10/5 / 自定义 | 10/25/30/5/15/10/5 默认值 |
| 2 | save_to_kb.py 默认 `AUTO_KB_INTAKE_ENABLED=False` 灰度 | True / False | False 默认 + 7 天手动审核 |
| 3 | KB 闭环端到端测试 Docker compose 物理隔离栈 | 物理隔离 / 共享 test DB | 物理隔离栈 (D6 Phase 1 实施) |
| 4 | 子 plan ②/③ 是否合并 PR | 合并 / 分开 | 分开 |
| 5 | W69 派工数量 | 3 / 5 / 7 agents | 5 agents |
| 6 | W70 派工数量 | 2 / 4 / 6 agents | 4 agents |
| 7 | W69 起始日期 | 2026-07-31 (Mon) / 其他 | 2026-07-31 |

### 3.4 与 W19 选项 A + 0 production code 改动铁律的关系

**W19 选项 A**: 4 留未来 PR 不发起新排期 (已维持)

**冲突分析**:
- 子 plan ② qa-bench 7 维评分 + KB 闭环 — W19 之前**已部分实施** (qa-bench-v3-w1-2026-06-30 已 PARTIAL) → 不算新排期, **算遗留闭环**
- 子 plan ③ UI redesign — **W19 之前未实施** (W19 4 留未来 PR 不含此) → **新增排期**
- **结论**: 子 plan ② 闭环不违反 W19 选项 A; 子 plan ③ UI redesign **轻微违反** (新增排期 1 项)

**0 production code 改动铁律冲突分析**:
- 子 plan ② (qa-bench): 新增 15+ 文件 + 修改 2 文件 → **可守恒** (主框架不动, 只新增测试基础设施 + 1 个新 Celery task)
- 子 plan ③ (UI redesign): 新增 5 文件 + 修改 11 文件 → **不守恒** (修改 production code 11 文件, 主指挥需破例决策)

---

## 4. 5 新铁律沉淀

### 铁律 1: 跨季度 plan 拆子 (W69 派工依据)

**触发**: W68 第 6 批深度审计发现 `chatgpt-structured-floyd.md` 是 3 子 plan 拼接 (chat history 8 phase + qa-bench 7 维 + UI redesign), 真实完成度仅 1/3. **不应**作为 1 plan 整体评估完成度.

**纪律**:
1. **跨季度 plan (> 2 周) 必须显式拆子** — plan 头部写明 `子 plan ①/②/③` 状态, 避免被误标 COMPLETED
2. **每个子 plan 独立评估完成度** — 不允许"3 子 plan 1 个完成 = 33% 进度但 plan 标 COMPLETED"
3. **W68 第 8 批 C-3 agent 已修订 plan 头部** — 子 plan ① COMPLETED + 子 plan ②/③ 留 W69/W70

### 铁律 2: W69 派工依据 (跨 batch 启动机制)

**触发**: 主指挥 W68 第 8 批拍板"plans 优先 + 小修搭配"基调后, W69 派工依据 = plan 状态化的子 plan ②/③ 调研文档.

**纪律**:
1. **每个新 batch 启动前必须调研 plan 列表** — 不允许凭印象拍板派工
2. **plan 调研文档** = `docs/{plan-name}-{week}-plan.md` (例: `chatgpt-structured-floyd-w69-plan.md`)
3. **调研文档必须含 9 节**: 现状 / 子 plan ② / 子 plan ③ / 实施时间线 / 派工预排 / 主指挥决策 / 验证 / 风险 / 总结

### 铁律 3: 子 plan 顺序 (基础数据 → 用户体验)

**触发**: 子 plan ① chat history 8 phase (基础数据) → 子 plan ② qa-bench 7 维 (基础数据齐备) → 子 plan ③ UI redesign (用户体验提升).

**纪律**:
1. **子 plan 顺序按"基础数据 → 用户体验"链式闭环** — 不允许用户体验先于基础数据
2. **W69 子 plan ② 启动条件**: chat history 8 phase 必须 100% 闭环 (已满足)
3. **W70 子 plan ③ 启动条件**: W69 子 plan ② 必须 100% 闭环 (qa-bench 数据齐备)

### 铁律 4: 已闭环 1/3 不返工 (W68 #043 不重写)

**触发**: chat history 8 phase 已 W68 #043 完整闭环, W69/W70 派工**不重写**子 plan ①.

**纪律**:
1. **已闭环子 plan 不返工** — 8 phase 完整收官后, 不允许 W69 再开 Phase 9/10
2. **新派工必须明示"不动已闭环子 plan"** — plan 调研文档第 1.2 节明确列出已闭环项
3. **CLAUDE.md 铁律 752 行升级** — 任何"重写已完成功能"的 PR 必须主指挥拍板

### 铁律 5: Dashboard MVP 必备 (4 指标卡)

**触发**: 子 plan ② Dashboard MVP 是 KB 闭环必备监控, 必须有 4 指标卡 (入库数 / 通过率 / 抽检数 / 告警数).

**纪律**:
1. **任何全自动入库/出库闭环必须配套 Dashboard MVP** — 不可"全自动 + 0 监控"
2. **Dashboard 4 指标卡必备**: 入库数 (24h) / 通过率 (rolling 7d) / 抽检数 (待审核) / 告警数 (rolling 24h)
3. **Dashboard 5min polling** — 实时性 + 后端压力平衡

---

## 5. W69 派工预排详细 (5 agents 子 plan ②)

### 5.1 Agent #1: 7 维评分算法实施

**任务**:
- 创建 `tests/qa-bench/scoring/seven_dim.py` (~200 行)
- 创建 `tests/qa-bench/scoring/weights.json` (~30 行)
- 扩展 `tests/qa-bench/runner.py` 支持新 JSONL schema + 7 维评分
- 单元测试 24 个 (每个维度 3 测试 + 边界)

**复用 utilities**:
- `tests/qa-bench/runner.py` (536 行) — 主流程扩展
- `tests/qa-bench/gen500.py` (1490 行) — 基类继承
- `app/utils/llm_client.py` — Claude API

**风险**: 权重争议需团队拍板 (10/25/30/5/15/10/5 默认 vs 自定义)

### 5.2 Agent #2: save_to_kb.py 5 道防线

**任务**:
- `tests/qa-bench/kb_queue/dedup.py` (~80 行) — embedding 余弦相似度 ≥ 0.95
- `tests/qa-bench/kb_queue/length_filter.py` (~40 行) — 长度 50-4000
- `tests/qa-bench/kb_queue/llm_refusal.py` (~60 行) — LLM 拒答检测
- `tests/qa-bench/kb_queue/sensitive_words.py` (~50 行) — 28 成员 + 8 placeholder + 11 filler
- 重写 `tests/qa-bench/save_to_kb.py` 集成 5 防线

**复用 utilities**:
- `app/utils/pgvector.py` — embedding 检索
- `app/utils/llm_client.py` — Claude API 拒答判别
- `docs/known_members.json` — 28 成员黑名单

**风险**: 高 (灰度期需手动监控错答案污染)

### 5.3 Agent #3: Celery auto_intake_rollback_task

**任务**:
- `app/services/qa_bench_tasks.py` (~100 行) — Celery task
- 配置 `app/core/celery_app.py` beat schedule (每天 4:00)
- 告警: admin notification 集成
- 单元测试 12 个 (idempotent + 7 天 review + 引用失效)

**复用 utilities**:
- `app/services/task_service.py:auto_purge_trash_task` — Celery 模式
- `app/services/notification_service.py` — 通知
- `app/core/celery_app.py` — beat schedule

**风险**: 中 (回滚必须 idempotent, 错误回滚会污染 KB)

### 5.4 Agent #4: KB 闭环端到端

**任务**:
- 集成 Agent #1+#2+#3 产出
- 端到端测试 (e2e) 30 个场景: 正常 pass → 入库 / 5 道防线任一 fail → 拒绝 / 24h 后 grounding ref 失效 → 自动回滚 / 下游点击 < 3 → 自动回滚 / 负反馈 > 10% → 告警 + 暂停 AUTO_KB_INTAKE_ENABLED
- pytest 集成测试 8 个

**复用 utilities**:
- `tests/integration/conftest.py` — test DB stack
- `tests/qa-bench/runner.py` — 跑评测
- `app/services/qa_bench_tasks.py` — 回滚 task

**风险**: 高 (全链路集成测试 + Docker compose 部署)

### 5.5 Agent #5: Dashboard MVP + CI smoke 200 题

**任务**:
- `web/src/views/admin/QaBenchDashboard.vue` (~400 行) — 4 指标卡 + 详情页
- `web/src/api/qaBenchDashboard.js` (~60 行) — 4 端点
- `tests/qa-bench/ci/smoke_200.py` (~150 行) — smoke 套件
- `.github/workflows/qa-bench-smoke.yml` (~30 行) — GitHub Actions
- 单元测试 8 个 (Dashboard 4 指标卡渲染)

**复用 utilities**:
- `web/src/components/common/StatCard.vue` — 4 指标卡模板
- `web/src/views/admin/AgentTracesView.vue` — Dashboard 模式
- `tests/qa-bench/gen500.py` — 200 题筛选 (`tags=["hot_path", "regression_smoke"]`)

**风险**: 低 (复用 web 模板 + 现有 qa-bench 框架)

---

## 6. W70 派工预排详细 (4 agents 子 plan ③)

### 6.1 Agent #1: NavRail.vue + SessionSidebar 重构

**任务**:
- `web/src/components/chat/NavRail.vue` (NEW ~250 行)
- `web/src/components/chat/SessionSidebar.vue` 重构 (overlap bug 修复 + actions 改 right-click)
- `web/src/stores/chatSessions.ts` sortedSessions 排序逻辑加 is_pinned desc

### 6.2 Agent #2: ThinkingModeSwitch.vue + ChatBreadcrumb.vue

**任务**:
- `web/src/components/chat/ThinkingModeSwitch.vue` (NEW ~80 行) — 3 档 segmented control
- `web/src/components/chat/ChatBreadcrumb.vue` (NEW ~60 行) — 中央标题 + breadcrumb
- `web/src/stores/useUiStore.js` thinkingMode computed 派生

### 6.3 Agent #3: ChatViewSSE 顶栏 3-zone 重构

**任务**:
- `web/src/views/chat/ChatViewSSE.vue` 3-zone 重构 (左 nav rail + 中央 ChatBreadcrumb + 右 + FAB)
- 输入栏上方插入 `<ThinkingModeSwitch />`
- 输入栏 left icons 加 el-tooltip + 4-attr (修复 aria-label 缺失)

### 6.4 Agent #4: 移动端同步 + 视觉回归 + 测试 + 沉淀

**任务**:
- `web/src/views/mobile/chat/MobileChatView.vue` 移动端布局同步
- `web/src/components/mobile/MobileHeader.vue` 简化 (搜索/主题下沉)
- `web/src/components/mobile/MobileInputBar.vue` 加 MobileThinkingModeSwitch
- `web/src/components/mobile/MobileThinkingModeSwitch.vue` (NEW ~60 行)
- `web/src/assets/variables.css` 新增 --icon-size-* + --icon-color-* token + dark 块
- `web/tests/unit/__tests__/NavRail.test.js` (NEW)
- `web/tests/unit/__tests__/ThinkingModeSwitch.test.js` (NEW)
- `web/tests/visual/desktop/v78-ui-redesign.spec.mjs` (NEW)
- `memory/ui-redesign-v78-2026-06-30.md` (NEW)

---

## 7. 跨 batch 锚点范式增长预估

| Batch | 锚点范式起点 | 本批 +守恒 | 锚点范式终点 |
|---|---|---|---|
| W68 第 1 批 | 28 | +2 | 30 |
| W68 第 2 批 | 30 | +2 | 32 |
| W68 第 3 批 | 32 | +10 | 42 |
| W68 第 4 批 | 42 | +15 | 57 |
| W68 第 5 批 | 57 | +15 | 72 |
| W68 第 6 批 | 72 | +1 | 73 |
| W68 第 7 批 | 73 | +14 | 87 |
| W68 第 8 批 | 87 | +3 | 90 |
| W68 第 9 批 (本批) | 90 | +21 | **111** |
| W69 子 plan ② (预估) | 111 | +5 | 116 |
| W70 子 plan ③ (预估) | 116 | +4 | 120 |

**W70 末锚点范式**: 120 (W68-W70 累计 +30 守恒)

---

## 8. 验证 (DoD)

### 8.1 子 plan ② DoD (W69)

```bash
# 1. 7 维评分算法
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/scoring/test_seven_dim.py -v
# 期望: 24 PASSED

# 2. 5 道防线
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/kb_queue/test_*.py -v
# 期望: 36+ PASSED

# 3. Celery auto_intake_rollback_task
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/unit/test_qa_bench_tasks.py -v
# 期望: 12 PASSED

# 4. KB 闭环端到端
docker compose -f tests/integration/docker-compose.yml up -d
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/integration/test_kb_closed_loop.py -v
# 期望: 8 PASSED

# 5. Dashboard MVP
cd /e/microbubble-agent/web && npm run build
# 期望: 0 警告

# 6. CI smoke 200 题 < 5min
PYTHONIOENCODING=utf-8 PYTHONUTF8=1 \
  pytest tests/qa-bench/ci/smoke_200.py -v --timeout=300
# 期望: 200 PASSED, 时长 < 5min
```

### 8.2 子 plan ③ DoD (W70)

```bash
# 1. NavRail 渲染
cd /e/microbubble-agent/web && npx vitest run \
  src/components/chat/__tests__/NavRail.test.js
# 期望: 7+ PASSED

# 2. ThinkingModeSwitch v-model
cd /e/microbubble-agent/web && npx vitest run \
  src/components/chat/__tests__/ThinkingModeSwitch.test.js
# 期望: 8+ PASSED

# 3. Playwright 视觉回归
cd /e/microbubble-agent/web && \
  TEST_TOKEN=<jwt> npx playwright test \
  tests/visual/desktop/v78-ui-redesign.spec.mjs \
  --project=desktop-chrome
# 期望: baseline 重建 + 0 fail
```

---

## 9. 关键纪律汇总

### 9.1 调研文档规范

- 文件路径: `docs/{plan-name}-{week}-plan.md` (例: `chatgpt-structured-floyd-w69-plan.md`)
- 行数目标: ~300 行 (实际 823 行因为内容跨 2 子 plan + 主指挥决策点)
- 必含 9 节: 现状 / 子 plan ② / 子 plan ③ / 实施时间线 / 派工预排 / 主指挥决策 / 验证 / 风险 / 总结

### 9.2 W69/W70 派工纪律

- 不动已闭环子 plan (chat history 8 phase)
- 子 plan ② 0 production code 改动铁律可守恒 (新增文件 + 1 Celery task)
- 子 plan ③ 0 production code 改动铁律不守恒 (修改 11 production code 文件, 主指挥破例)
- W19 选项 A 维持 (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)

### 9.3 主指挥决策依赖

- W69 派工前: 主指挥拍板 7 维权重默认值 + AUTO_KB_INTAKE_ENABLED 默认 False + 物理隔离栈部署
- W70 派工前: 主指挥拍板 0 production code 改动铁律破例 + 子 plan ③ 是否合并 PR

---

## 10. 总结

**W68 第 9 批 B-4 agent 调研完成** — 新建 `docs/chatgpt-structured-floyd-w69-plan.md` (823 行) 含子 plan ②/③ W69/W70 派工预排 (5+4 agents) + 主指挥 7 决策点 + 0 production code 改动铁律分析 + 锚点范式增长预估 +10 守恒 (90 → 100). **5 新铁律沉淀**: 跨季度 plan 拆子 / W69 派工依据 / 子 plan 顺序 / 已闭环 1/3 不返工 / Dashboard MVP 必备.

**核心建议**:
1. ✅ **W69 派工 5 agents 子 plan ②** (qa-bench 7 维 + 5 道防线 + Dashboard + CI smoke) — 0 production code 改动铁律可守恒
2. ✅ **W70 派工 4 agents 子 plan ③** (NavRail + ThinkingModeSwitch + ChatBreadcrumb) — 0 production code 改动铁律不守恒需主指挥破例
3. **总投入 86h + 锚点范式 +10 守恒 (90 → 100)**
4. **W19 选项 A 维持** (子 plan ② 算遗留闭环 + 子 plan ③ 新增排期 1 项)

---

**memory 沉淀锚点范式第 111 守恒**, 5 新铁律 + 9 节完整调研 + W69/W70 派工预排 + 主指挥 7 决策点 + 锚点范式增长预估 +10 守恒. 详见 `docs/chatgpt-structured-floyd-w69-plan.md` (823 行) 完整调研.