# Phase 8-M0-B3 工作区、SCADA 与数字孪生实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `superpowers:executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 仅在 `desktop/**` 内交付 Store 驱动的科研项目指挥中心、数字孪生优先的 SCADA 控制中心和可复用 props-only 面板。

**架构：** `ResearchWorkspace.vue` 仅读取 `useResearchWorkspaceStore()`，不再初始化演示数据。`ExperimentControlCenter.vue` 仅读取 `useExperimentControlStore()`；该 Store 保存真实设备、指标、报警、建议、时间线和预测记录。页面将数据映射给 B3 props-only 数字孪生/SCADA 组件，缺失数据由组件以中文空态表达。

**技术栈：** Vue 3、TypeScript、Pinia、Vitest、Phase 8-M0 设计令牌与共享研究组件。

---

## 文件结构

- 修改：`src/stores/experiment-control.store.ts` — 持有真实 `TwinPrediction[]`，不产生预测数值。
- 修改：`src/renderer/src/pages/research/ResearchWorkspace.vue` — Store 驱动项目指挥中心。
- 修改：`src/renderer/src/pages/research/ExperimentControlCenter.vue` — 深色、数字孪生优先的 SCADA。
- 创建：`src/renderer/src/components/research/digital-twin/ReactorTwinPanel.vue`、`PumpTwinPanel.vue`、`OzoneGeneratorTwinPanel.vue`、`SensorTwinPanel.vue` — props-only 孪生面板。
- 创建：`src/renderer/src/components/research/SCADAMetricGrid.vue`、`SCADAAlertPanel.vue`、`SCADADeviceTopology.vue` — props-only SCADA 组合组件。
- 创建：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts` — 至少 320 个 B3 UI 合同。
- 修改：`tests/unit/scientific-research-workspace.test.ts`、`tests/unit/scientific-experiment-control.test.ts` — 删除旧演示初始化/旧控制卡断言。

### 任务 1：先锁定 B3 真实数据合同

**文件：**

- 创建：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts`
- 修改：`tests/unit/scientific-research-workspace.test.ts`
- 修改：`tests/unit/scientific-experiment-control.test.ts`

- [ ] **步骤 1：写会失败的页面边界测试**

```ts
const workspace = pageSource('ResearchWorkspace.vue')
expect(workspace).toContain("import { useResearchWorkspaceStore }")
expect(workspace).not.toContain('ResearchWorkspaceService')
expect(workspace).not.toContain('loadWorkspace(')
expect(workspace).not.toContain("projectId: 'demo-project'")

const control = pageSource('ExperimentControlCenter.vue')
expect(control).toContain('data-research-theme="scada"')
expect(control).toContain('store.predictions')
expect(control).not.toContain(':predictions="[]"')
expect(control).not.toContain('store.pushAlert(')
```

使用 `it.each()` 建立 320 个最小合同：工作区 100、SCADA 页面 95、数字孪生 60、组件边界 35、可访问性/响应式 30。每项分别检查中文标签、Store 来源、中文空态、无 Store/Service import、ARIA、`focus-visible`、`prefers-reduced-motion`、`min-width: 0` 或 `minmax(0, …)`。

- [ ] **步骤 2：运行测试确认红灯**

运行：`npm run test:unit -- tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts --reporter=dot`

预期：失败原因包含缺失 B3 文件、`ResearchWorkspaceService` 仍在页面中，或控制中心仍传入 `:predictions="[]"`。

- [ ] **步骤 3：迁移旧测试的过时断言**

```ts
expect(page).not.toContain('ResearchWorkspaceService')
expect(page).not.toContain('service.loadWorkspace')
expect(page).toContain('ResearchState')
expect(controlPage).toContain('SCADADeviceTopology')
expect(controlPage).toContain('SCADAMetricGrid')
expect(controlPage).toContain('SCADAAlertPanel')
expect(controlPage).toContain(':predictions="store.predictions"')
```

- [ ] **步骤 4：再次运行 B3 测试**

运行任务 1 步骤 2 的命令。预期：只因尚未实现的 B3 组件/页面而失败，旧测试不再要求演示初始化或旧浅色控制卡。

### 任务 2：控制 Store 中加入真实预测记录容器

**文件：**

- 修改：`src/stores/experiment-control.store.ts`
- 测试：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts`

- [ ] **步骤 1：写失败的 Store 合同**

```ts
const source = storeSource('experiment-control.store.ts')
expect(source).toContain("import type { TwinPrediction }")
expect(source).toContain('predictions: [] as TwinPrediction[]')
expect(source).toContain('setPredictions(predictions: TwinPrediction[])')
expect(source).toContain('addPrediction(prediction: TwinPrediction)')
expect(source).toContain('this.predictions = []')
```

- [ ] **步骤 2：运行 B3 测试确认红灯**

运行任务 1 步骤 2 的命令。预期：提示 `predictions`、`setPredictions`、`addPrediction` 尚未实现。

- [ ] **步骤 3：实现最小 Store 容器**

```ts
import type { TwinPrediction } from '../shared/digital-twin/digital-twin-schema'

predictions: [] as TwinPrediction[]
setPredictions(predictions: TwinPrediction[]) { this.predictions = [...predictions] }
addPrediction(prediction: TwinPrediction) { this.predictions.push(prediction) }
this.predictions = []
```

不调用数字孪生 Service，不在 Store 内计算预测，也不写入示例记录。

- [ ] **步骤 4：运行 B3 测试确认 Store 合同转绿**

运行任务 1 步骤 2 的命令。预期：预测来源合同通过，其余未实现页面/组件合同仍可失败。

### 任务 3：以 TDD 创建 props-only 数字孪生和 SCADA 组件

**文件：**

- 创建：`src/renderer/src/components/research/digital-twin/ReactorTwinPanel.vue`
- 创建：`src/renderer/src/components/research/digital-twin/PumpTwinPanel.vue`
- 创建：`src/renderer/src/components/research/digital-twin/OzoneGeneratorTwinPanel.vue`
- 创建：`src/renderer/src/components/research/digital-twin/SensorTwinPanel.vue`
- 创建：`src/renderer/src/components/research/SCADAMetricGrid.vue`
- 创建：`src/renderer/src/components/research/SCADAAlertPanel.vue`
- 创建：`src/renderer/src/components/research/SCADADeviceTopology.vue`
- 测试：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts`

- [ ] **步骤 1：写失败的 props-only 和类型映射合同**

```ts
for (const file of twinFiles) {
  const source = componentSource(file)
  expect(source).toMatch(/defineProps|withDefaults\(defineProps/)
  expect(source).not.toMatch(/from\s+['"][^'"]*(stores|services)[^'"]*['"]/) 
  expect(source).toContain('aria-label')
  expect(source).toContain('暂无')
}

const topology = componentSource('SCADADeviceTopology.vue')
expect(topology).toContain("device.type === 'reactor'")
expect(topology).toContain("device.type === 'pump'")
expect(topology).toContain("device.type === 'ozone-generator'")
expect(topology).toContain("device.type === 'sensor'")
```

- [ ] **步骤 2：运行 B3 测试确认红灯**

运行任务 1 步骤 2 的命令。预期：七个新组件文件缺失。

- [ ] **步骤 3：实现四个数字孪生面板**

单设备面板使用：

```ts
import type { DeviceStatusPanel } from '../../../../../shared/control/experiment-control-schema'

defineProps<{
  device?: DeviceStatusPanel
  ariaLabel?: string
}>()
```

`SensorTwinPanel` 使用真实数组：

```ts
defineProps<{
  devices?: DeviceStatusPanel[]
  ariaLabel?: string
}>()
```

所有组件使用 `section`、中文 `aria-label`、`role="status"` 空态、真实状态文字和 `data-status`；在线动画只在真实在线状态出现，并在 `prefers-reduced-motion` 下停用。

- [ ] **步骤 4：实现三项 SCADA 组合组件**

```ts
const metricNames = computed(() => [...new Set(props.metrics.map((metric) => metric.metric))])
const sortedAlerts = computed(() => [...props.alerts].sort((left, right) => right.timestamp - left.timestamp))
const reactor = computed(() => props.devices.find((device) => device.type === 'reactor'))
const pump = computed(() => props.devices.find((device) => device.type === 'pump'))
const ozoneGenerator = computed(() => props.devices.find((device) => device.type === 'ozone-generator'))
const sensors = computed(() => props.devices.filter((device) => device.type === 'sensor'))
```

`SCADAMetricGrid` 渲染既有 `SCADAChartPanel`，`SCADADeviceTopology` 只传入精确类型的真实结果，`SCADAAlertPanel` 显示真实 severity、message、timestamp。三者均有中文空态，不推导报警、设备或指标。

- [ ] **步骤 5：运行 B3 测试确认组件合同转绿**

运行任务 1 步骤 2 的命令。预期：组件 props、空态、类型映射、ARIA 和 reduced-motion 合同通过。

### 任务 4：重建只读科研项目指挥中心

**文件：**

- 修改：`src/renderer/src/pages/research/ResearchWorkspace.vue`
- 测试：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts`

- [ ] **步骤 1：写失败的数据流合同**

```ts
expect(workspace).toContain('store.overview')
expect(workspace).toContain('store.progress')
expect(workspace).toContain('store.modules')
expect(workspace).toContain("activity.kind === 'agent'")
expect(workspace).toContain("module.status === 'failed'")
expect(workspace).toContain('项目目标')
expect(workspace).toContain('风险状态')
expect(workspace).toContain('模块入口')
```

- [ ] **步骤 2：运行 B3 测试确认红灯**

运行任务 1 步骤 2 的命令。预期：页面仍使用 Service 和演示对象，缺少 B3 指挥区。

- [ ] **步骤 3：删除初始化并实现只读派生状态**

```ts
const latestAgentAction = computed(() => [...store.activities]
  .filter((activity) => activity.kind === 'agent')
  .sort((left, right) => right.timestamp - left.timestamp)
  .at(0) ?? null)

const riskModules = computed(() => store.modules
  .filter((module) => module.status === 'failed' || module.status === 'paused' || module.status === 'disabled'))

const progressItems = computed(() => store.progress ? [
  { label: '任务进度', value: `${store.progress.completedTasks} / ${store.progress.totalTasks}` },
  { label: '实验进度', value: `${store.progress.completedExperiments} / ${store.progress.totalExperiments}` },
  { label: '论文进度', value: `${store.progress.publishedManuscripts} / ${store.progress.totalManuscripts}` },
  { label: '知识进度', value: `${store.progress.indexedKnowledge} / ${store.progress.totalKnowledge}` }
] : [])
```

使用 `ResearchPageHeader`、`ResearchPanel`、`ResearchMetricPanel`、`ResearchTimeline`、`ResearchState`。以 `store.isLoading`、`store.errorMessage`、`!store.workspace` 区分加载、错误、空态；不调用任何 Service 或 Store action。

- [ ] **步骤 4：实现宽屏和可访问布局**

```css
.research-workspace { min-width: 0; max-width: var(--research-content-max-width); overflow-x: clip; }
.research-workspace__command-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(280px, .8fr); gap: var(--research-grid-gap); }
.research-workspace__module-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); gap: var(--research-grid-gap); }
@media (prefers-reduced-motion: reduce) { .research-workspace *, .research-workspace *::before, .research-workspace *::after { animation: none; transition: none; } }
```

模块入口采用原生 `button` 或链接并有中文 `aria-label` 和 `:focus-visible`。

- [ ] **步骤 5：运行 B3 测试确认工作区合同转绿**

运行任务 1 步骤 2 的命令。预期：真实来源、无初始化、中文状态与响应式合同通过。

### 任务 5：以数字孪生主视图重建 Store 驱动 SCADA

**文件：**

- 修改：`src/renderer/src/pages/research/ExperimentControlCenter.vue`
- 测试：`tests/unit/phase-8-m0-b3-workspace-scada.dom.test.ts`

- [ ] **步骤 1：写失败的 SCADA 合同**

```ts
expect(control).toContain('data-research-theme="scada"')
expect(control).toContain('SCADADeviceTopology')
expect(control).toContain('SCADAMetricGrid')
expect(control).toContain('SCADAAlertPanel')
expect(control).toContain(':devices="store.devices"')
expect(control).toContain(':metrics="store.metrics"')
expect(control).toContain(':alerts="store.alerts"')
expect(control).toContain(':recommendations="store.recommendations"')
expect(control).toContain(':predictions="store.predictions"')
```

- [ ] **步骤 2：运行 B3 测试确认红灯**

运行任务 1 步骤 2 的命令。预期：页面缺少 SCADA 主题、新组件，仍存在硬编码预测数组与 mounted 告警。

- [ ] **步骤 3：实现 Store 只读的 SCADA 派生展示**

```ts
const latestTimelineEntry = computed(() => [...store.timeline]
  .sort((left, right) => right.timestamp - left.timestamp)
  .at(0) ?? null)
const runStatus = computed(() => latestTimelineEntry.value?.event ?? '暂无 Run 记录')
const experimentStatus = computed(() => store.dashboards.at(-1)?.title ?? latestTimelineEntry.value?.description ?? '暂无实验状态')
const statusItems = computed(() => [
  { label: '设备在线', value: `${store.onlineDeviceCount} / ${store.deviceCount}` },
  { label: '实时指标', value: String(store.metricCount) },
  { label: '报警', value: String(store.alertCount), status: store.criticalAlertCount ? 'error' : undefined },
  { label: '预测记录', value: String(store.predictions.length) }
])
```

根节点为：

```vue
<main class="experiment-control-center" data-research-theme="scada" aria-label="实验控制中心 SCADA">
```

首屏顺序为真实实验/Run 状态、`SCADADeviceTopology`、`PredictionPanel variant="scada"`；随后展示设备状态、`SCADAMetricGrid`、`SCADAAlertPanel`、真实 AI 建议与实验时间线。删除 `onMounted` 与 `store.pushAlert()`。

- [ ] **步骤 4：实现 B 向响应式、焦点与 reduced-motion**

```css
.experiment-control-center { min-width: 0; min-height: 100%; overflow-x: clip; padding: var(--research-page-gutter); background: var(--research-bg-main); }
.experiment-control-center__twin-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(300px, .65fr); gap: var(--research-grid-gap); }
.experiment-control-center__observability-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--research-grid-gap); }
@media (max-width: 1180px) { .experiment-control-center__twin-grid, .experiment-control-center__observability-grid { grid-template-columns: minmax(0, 1fr); } }
@media (prefers-reduced-motion: reduce) { .experiment-control-center *, .experiment-control-center *::before, .experiment-control-center *::after { animation: none; transition: none; } }
```

所有可交互元素保留 `:focus-visible`；装饰性拓扑连线设为 `aria-hidden="true"`。

- [ ] **步骤 5：运行 B3 测试确认页面合同转绿**

运行任务 1 步骤 2 的命令。预期：所有 B3 合同通过，总数不少于 320。

### 任务 6：全量验证与 B3 交付提交

**文件：**

- 修改：任务 1–5 列出的文件

- [ ] **步骤 1：运行全量单元测试**

运行：`npm run test:unit`

预期：所有测试通过，包含 B3 新增不少于 320 项合同。

- [ ] **步骤 2：运行类型检查**

运行：`npx tsc --noEmit -p tsconfig.node.json`，然后运行 `npx vue-tsc --noEmit -p tsconfig.web.json`。

预期：两个命令均以退出码 0 完成。

- [ ] **步骤 3：生产构建和范围检查**

运行：`npm run build`，随后检查提交差异没有空白错误、且文件名均以 `desktop/` 开头。

预期：构建成功、差异检查无问题、没有 `backend/`、`web/` 或 `app/` 变更。

- [ ] **步骤 4：提交 B3 实现**

```text
git add desktop
git commit -m "Phase 8-M0-B3 Research Workspace Experiment Control Center Digital Twin SCADA Upgrade"
```

预期：只有 B3 的 `desktop/**` 实现、测试与计划文件进入提交。
