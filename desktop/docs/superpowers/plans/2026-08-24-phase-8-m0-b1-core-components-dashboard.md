# Phase 8-M0-B1 核心组件与科研驾驶舱实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 为 Scientific Research OS 实现七个无业务依赖的研究展示组件，并将 Dashboard 升级为仅使用现有 research stores 的科研驾驶舱。

**架构：** 组件层放在 `renderer/src/components/research/`，只接受 props、派生展示状态和 slots；`Dashboard.vue` 是唯一把 project、knowledge、dataset、manuscript store 组合为视图模型的位置。不会产生实验、设备或数字孪生虚构值：没有已知来源的数据使用清楚的中文空状态。

**技术栈：** Vue 3 `<script setup lang="ts">`、Pinia、Vitest、M0-A CSS 令牌、现有 ResearchPageHeader/ResearchPanel/ResearchState。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `src/renderer/src/components/research/ResearchMetricPanel.vue` | 指标栅格与科学数字语义。 |
| `src/renderer/src/components/research/ResearchTimeline.vue` | AI/研究事件时间线与状态。 |
| `src/renderer/src/components/research/AgentStatusPanel.vue` | 研究 Agent 的当前状态、队列和动作。 |
| `src/renderer/src/components/research/EvidencePanel.vue` | 证据与引用摘要。 |
| `src/renderer/src/components/research/DeviceStatusPanel.vue` | research/scada 两种设备状态卡。 |
| `src/renderer/src/components/research/SCADAChartPanel.vue` | real-time metric 的只读 SCADA 折线。 |
| `src/renderer/src/components/research/PredictionPanel.vue` | research/scada 两种数字孪生预测/空状态。 |
| `src/renderer/src/layouts/HeaderBar.vue` | 添加纯展示的全局 AI 状态占位区域。 |
| `src/renderer/src/pages/research/Dashboard.vue` | 用既有四个 Store 组装科研驾驶舱。 |
| `tests/unit/phase-8-m0-b1-core-dashboard.dom.test.ts` | 至少 150 条 B1 视觉、边界与可访问性契约。 |
| `tests/unit/research-*.test.ts` | 只在 M0-A 既有硬编码文案/结构受影响时更新契约。 |

### 任务 1：定义 B1 失败契约

**文件：**
- 创建：`desktop/tests/unit/phase-8-m0-b1-core-dashboard.dom.test.ts`

- [ ] **步骤 1：编写失败的测试**

```ts
const componentPaths = [
  'ResearchMetricPanel.vue', 'ResearchTimeline.vue', 'AgentStatusPanel.vue',
  'EvidencePanel.vue', 'DeviceStatusPanel.vue', 'SCADAChartPanel.vue', 'PredictionPanel.vue'
]

test.each(componentPaths)('%s 是纯 props 展示组件', (name) => {
  const source = readResearchComponent(name)
  expect(source).toContain('defineProps')
  expect(source).not.toMatch(/from\s+['"].*stores\//)
  expect(source).not.toMatch(/from\s+['"].*services\//)
})

test('科研驾驶舱组合既有四个 Store 与全部真实状态', () => {
  const source = readDashboard()
  expect(source).toContain('科研驾驶舱')
  expect(source).toContain('useProjectStore')
  expect(source).toContain('useKnowledgeStore')
  expect(source).toContain('useDatasetStore')
  expect(source).toContain('useManuscriptStore')
  expect(source).toContain('ResearchMetricPanel')
})
```

- [ ] **步骤 2：运行测试验证失败**

运行：`npm run test:unit -- phase-8-m0-b1-core-dashboard.dom.test.ts`
预期：FAIL，缺少七个 B1 组件和 Dashboard 的 `ResearchMetricPanel` 组合。

- [ ] **步骤 3：扩展为不少于 150 条断言**

使用 `test.each` 分别生成中文标签、props 名称、状态、aria、reduced-motion、1440/1920 断点、SCADA 信号语义、Dashboard 空/加载/错误状态与 Header AI 状态断言。最终用 `expect(contractCount).toBeGreaterThanOrEqual(150)` 明确保护数量。

- [ ] **步骤 4：在实现前再次运行红灯测试**

运行：`npm run test:unit -- phase-8-m0-b1-core-dashboard.dom.test.ts`
预期：FAIL，失败原因仍是缺失的 B1 页面/组件标志，而不是 TypeScript 或 Vitest 配置错误。

### 任务 2：实现指标、时间线、Agent 与证据组件

**文件：**
- 创建：`desktop/src/renderer/src/components/research/ResearchMetricPanel.vue`
- 创建：`desktop/src/renderer/src/components/research/ResearchTimeline.vue`
- 创建：`desktop/src/renderer/src/components/research/AgentStatusPanel.vue`
- 创建：`desktop/src/renderer/src/components/research/EvidencePanel.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b1-core-dashboard.dom.test.ts`

- [ ] **步骤 1：实现可导出的展示 props 类型和最少呈现逻辑**

```ts
export interface ResearchMetricItem {
  label: string
  value: string | number
  unit?: string
  trend?: 'up' | 'down' | 'stable'
  status?: 'success' | 'warning' | 'danger' | 'neutral'
}

defineProps<{ items: ResearchMetricItem[]; ariaLabel?: string }>()
```

`ResearchTimeline` 的状态只允许 `pending | running | completed | error | neutral`；`AgentStatusPanel` 显示 `queue ?? 0` 和 `action ?? '暂无当前动作'`；`EvidencePanel` 消费已存在的 agent-service `EvidenceItem` / `CitationItem` 兼容结构或最小本地 props 接口。四个空列表均以 `role="status"` 和中文状态文本呈现。

- [ ] **步骤 2：使用 M0-A 令牌完成无障碍样式**

```css
.research-timeline__item:focus-visible {
  outline: none;
  box-shadow: var(--research-shadow-focus-primary);
}
@media (prefers-reduced-motion: reduce) {
  .research-timeline__marker { animation: none; }
}
```

避免硬编码新色值；研究状态使用 M0-A 的 semantic token。

- [ ] **步骤 3：运行目标测试验证通过**

运行：`npm run test:unit -- phase-8-m0-b1-core-dashboard.dom.test.ts`
预期：四个已实现组件对应契约通过；尚未实现的三个 SCADA/设备组件仍失败。

### 任务 3：实现设备、SCADA 图表与预测组件

**文件：**
- 创建：`desktop/src/renderer/src/components/research/DeviceStatusPanel.vue`
- 创建：`desktop/src/renderer/src/components/research/SCADAChartPanel.vue`
- 创建：`desktop/src/renderer/src/components/research/PredictionPanel.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b1-core-dashboard.dom.test.ts`

- [ ] **步骤 1：实现真实数据的 props-only 映射**

```ts
import type { DeviceStatusPanel as DevicePanel, RealtimeMetric } from '../../../../shared/control/experiment-control-schema'
import type { TwinPrediction } from '../../../../shared/digital-twin/digital-twin-schema'

withDefaults(defineProps<{
  devices: DevicePanel[]
  variant?: 'research' | 'scada'
}>(), { variant: 'research' })
```

`SCADAChartPanel` 对 `metricName` 过滤 `metrics`，计算 min/max/latest 和 SVG points；没有数据时输出“暂无实时指标”。`PredictionPanel` 只渲染传入 `TwinPrediction[]` 的最后项；空数组输出“暂无数字孪生预测”，不创建演示预测。`DeviceStatusPanel` 把 reactor、pump、ozone generator、sensor 映射为中文设备类型和 aria 标签，但只显示 props 提供的设备。

- [ ] **步骤 2：实现 research/scada 视觉变体**

```css
.device-status-panel--scada {
  background: var(--research-instrument-900);
  border-color: var(--research-instrument-line);
  color: var(--research-instrument-text);
}
.scada-chart-panel__trace { background-image: linear-gradient(var(--research-scada-grid) 1px, transparent 1px); }
```

告警、在线、离线和错误同时用中文文本和 signal color 表达；SCADA 动画由 `prefers-reduced-motion` 禁用。

- [ ] **步骤 3：运行目标测试验证通过**

运行：`npm run test:unit -- phase-8-m0-b1-core-dashboard.dom.test.ts`
预期：B1 契约全绿，数量不少于 150。

### 任务 4：升级 Header AI 状态与 Dashboard

**文件：**
- 修改：`desktop/src/renderer/src/layouts/HeaderBar.vue`
- 修改：`desktop/src/renderer/src/pages/research/Dashboard.vue`
- 测试：`desktop/tests/unit/phase-8-m0-b1-core-dashboard.dom.test.ts`
- 测试：`desktop/tests/unit/research-layout.dom.test.ts`
- 测试：`desktop/tests/unit/research-pages.dom.test.ts`

- [ ] **步骤 1：添加 Header 的全局 AI 状态占位区**

保留现有项目选择器、系统状态和命令入口。为 global AI 区补充“当前 AI 任务”“状态”“项目上下文”的中文 label；它不导入服务、不发网络请求、没有虚假工作结果。

```vue
<div class="header-bar__ai-status" aria-label="全局 AI 状态">
  <span>AI 状态</span>
  <strong>等待研究任务</strong>
  <small>{{ projectStore.currentProject.name }}</small>
</div>
```

- [ ] **步骤 2：把 Dashboard 的页面头替换为 `ResearchPageHeader`**

```vue
<ResearchPageHeader
  eyebrow="Scientific Command Center"
  title="科研驾驶舱"
  :description="`${projectStore.currentProject.name} 的研究决策概览`"
  :status="projectStatus"
/>
```

保留 `loadDashboard()`、`loadError`、`isLoading` 和 `hasResearchData`。从四个既有 stores 派生：项目焦点、阶段、进度、文献数、数据质量、论文状态和最近洞察。实验状态仅从 `datasetStore.report` 是否存在及其真实分析状态派生；AI 活动与代理状态在没有既有数据源时传入空列表并显示组件空态。无单独设备 Store 时设备区传入空数组，显示“暂无设备数据”，不能写死健康度。

- [ ] **步骤 3：以共享组件组织内容块**

```vue
<ResearchMetricPanel aria-label="科研关键指标" :items="dashboardMetrics" />
<ResearchTimeline aria-label="AI 研究活动" :items="aiTimelineItems" />
<AgentStatusPanel aria-label="AI 研究团队状态" :agents="dashboardAgents" />
<EvidencePanel :evidence="dashboardEvidence" :citations="dashboardCitations" />
<DeviceStatusPanel :devices="[]" variant="research" />
```

`dashboardEvidence` 仅映射真实 `datasetStore.conclusions`；Dashboard 没有 citation 数据源时 EvidencePanel 显示“暂无引用来源”。避免修改 Store 或 service。

- [ ] **步骤 4：添加 1440/1920、焦点与 reduced-motion 样式**

```css
.dashboard__command-grid { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(280px, .85fr); gap: var(--research-grid-gap); }
@media (min-width: 1720px) { .dashboard__command-grid { grid-template-columns: minmax(0, 1.25fr) minmax(320px, .75fr); } }
@media (max-width: 1480px) { .dashboard__command-grid { grid-template-columns: 1fr; } }
```

任何可点击的重试操作保留键盘默认语义与焦点令牌；页面容器 `min-width: 0`，不产生横向主内容溢出。

- [ ] **步骤 5：运行 B1 与受影响既有 UI 契约**

运行：`npm run test:unit -- phase-8-m0-b1-core-dashboard.dom.test.ts research-layout.dom.test.ts research-pages.dom.test.ts`
预期：通过；若旧文案断言失败，只更新与“科研首页”改为“科研驾驶舱”直接相关的断言。

### 任务 5：全量验证与最终提交

**文件：**
- 修改（如需要）：`desktop/tests/unit/research-*.test.ts`

- [ ] **步骤 1：运行全量测试和类型检查**

依次运行：

```powershell
npm run test:unit
npx tsc --noEmit -p tsconfig.node.json
npx vue-tsc --noEmit -p tsconfig.web.json
```

预期：三条命令均退出 0；如果旧 service 层类型回归，先定位是 B1 变更还是基线错误，再以最小方式修复。

- [ ] **步骤 2：进行两次生产构建**

运行两次 `npm run build`，核对输出的 renderer 资源名与大小一致，确保此 B1 工作树可重复构建。

- [ ] **步骤 3：检查范围并提交**

```powershell
git diff --check
git diff --name-only
git status --short
```

只暂存 `desktop/**` 下的 B1 文件，保留根目录现有未跟踪临时文件。提交：

```powershell
git commit -m "Phase 8-M0-B1 Scientific Research OS Core Components Dashboard Upgrade"
```
