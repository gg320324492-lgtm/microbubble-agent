# Phase 8-M0-B3：科研工作区、实验控制中心与数字孪生 SCADA 设计

**日期：** 2026-08-25  
**范围：** 仅 `desktop/**`  
**前置版本：** Phase 8-M0-B2

## 目标

将科研工作区升级为项目指挥中心，并将实验控制中心升级为深色 SCADA 工作面。界面只呈现既有 Store 能证明的数据；无数据时使用明确的中文加载、空或错误状态，绝不生成演示项目、实时读数、预测、告警、运行状态或 AI 建议。

## 已确认的视觉方向

采用 B「数字孪生主视图」：

- 科研工作区在首屏聚合项目目标、项目阶段、进度、里程碑、风险、AI 当前行动与模块入口。
- 控制中心以 `data-research-theme="scada"` 启用仪器深色令牌，将数字孪生拓扑和模型预测置于首屏主视图；实验运行、设备状态、实时指标、告警和 AI 建议围绕主视图组织。
- 数字孪生以反应器为拓扑中心，泵、臭氧发生器与传感器围绕连接；设备仅从真实 `DeviceStatusPanel` 的精确类型映射，缺失则显示空状态。

## 数据边界

### 科研工作区

页面仅使用既有 `useResearchWorkspaceStore()`：`workspace`、`overview`、`progress`、`modules`、`activities`、`summary`、`isLoading` 与 `errorMessage`。原页面中的 `ResearchWorkspaceService` 和页面内演示 `loadWorkspace()` 初始化被移除，页面不创建业务状态或模拟活动。

| 展示区域 | 允许来源 | 无数据行为 |
| --- | --- | --- |
| 项目目标、领域、阶段 | `overview` | 中文项目空状态 |
| 任务、实验、论文、知识进度 | `progress` | 中文进度空状态 |
| 里程碑 | `progress` 的真实汇总 | 未加载时不派生“已完成”结论 |
| 风险 | 真实 `modules` 中 `failed`、`paused`、`disabled` 状态 | 显示“暂无风险信号”而非虚构风险 |
| AI 当前行动 | 最近一条 `activities` 中 `kind === 'agent'` | “暂无 AI 当前行动” |
| 模块导航 | `modules` | 中文模块空状态 |

“研究阶段”只展示真实 `overview.status`；不从百分比、模块状态或时间推断阶段。风险面板只表达实际模块状态，且不把没有风险记录误称为安全评估。

### 实验控制中心

页面只使用既有 `useExperimentControlStore()`：`devices`、`metrics`、`timeline`、`recommendations`、`alerts`、`dashboards`、`actions` 及其现有 getters。B3 不扩展 Store、不调用服务、不在 `onMounted` 写入告警，亦不传入硬编码空预测数组。

| 展示区域 | 允许来源 | 无数据行为 |
| --- | --- | --- |
| 实验状态 | 最新 `timeline` / `dashboards` | “暂无实验状态” |
| Run 状态 | 最新真实 `timeline` | “暂无 Run 记录” |
| 实时指标 | `metrics` | “暂无实时指标” |
| 设备状态与拓扑 | `devices` | “暂无设备接入数据” |
| 报警 | `alerts` | “暂无报警” |
| AI 建议 | `recommendations` | “暂无 AI 建议” |
| 数字孪生预测 | 仅从既有 Store 暴露的真实预测字段（当前未暴露） | “暂无数字孪生预测” |

现有 `experiment-control.store` 未提供 `TwinPrediction[]`。因此 B3 的预测面板固定接收一个页面派生的空数组，明确显示“暂无数字孪生预测”；不新增 Store 字段、服务调用或任何预测数值。该数组是“数据源当前不存在”的表示，不是伪造业务数据。

## 页面架构

### `ResearchWorkspace.vue`

- `ResearchPageHeader`：真实项目标题、领域、状态；没有项目时使用科研工作区标题和空态。
- 项目焦点区：目标（`overview.description`）、研究领域和真实阶段。
- 真实进度区：任务、实验、论文、知识四项计数和整体百分比。
- 指挥区：左侧里程碑，右侧风险和最新 AI 行动。
- 模块导航区：以现有 `modules` 作为可访问按钮/链接语义展示；不创建新路由或新导航状态。
- 状态切换：`isLoading`、`errorMessage` 和 workspace 空态使用 `ResearchState`；不在页面加载时创建 workspace。

### `ExperimentControlCenter.vue`

- 根节点设置 `data-research-theme="scada"` 与中文 `aria-label`。
- 顶部显示真实仪表盘标题（如存在）、实验状态、Run 状态和 Store 聚合计数；未知数据保留为中文缺失态。
- 主视图由 `SCADADeviceTopology` 和 `PredictionPanel` 构成，二者只接收真实 `devices` 与真实可用预测；预测未接入时明确保持中文空态。
- `DeviceStatusPanel` 以逐设备状态辅助主视图；`SCADAMetricGrid` 在主视图下展示 `metrics` 按 metric 名称分组后的真实实时曲线或中文空态。
- `SCADAAlertPanel` 呈现真实 `alerts`，保留严重度与时间戳，不制造默认“系统就绪”告警。
- 既有 `AIAdviceCard` 接收真实 `recommendations`；数字孪生预测区使用共享 `PredictionPanel` 的空态，直到 Store 实际接入预测。
- 时间线只显示真实 `timeline`，不按页面逻辑合成实验或 Run 记录。

## 新共享组件

所有新组件只能通过 props 接收数据，禁止导入 Pinia、Store 或 Service。它们遵守设计令牌、`focus-visible` 与 `prefers-reduced-motion`。

### 数字孪生面板

路径：`src/renderer/src/components/research/digital-twin/`。

| 组件 | props | 职责 |
| --- | --- | --- |
| `ReactorTwinPanel` | `device?: DeviceStatusPanel`, `ariaLabel?` | 展示真实反应器身份、状态和读数数目；无设备时空态。 |
| `PumpTwinPanel` | `device?: DeviceStatusPanel`, `ariaLabel?` | 展示真实泵状态；无设备时空态。 |
| `OzoneGeneratorTwinPanel` | `device?: DeviceStatusPanel`, `ariaLabel?` | 展示真实臭氧发生器状态；无设备时空态。 |
| `SensorTwinPanel` | `devices?: DeviceStatusPanel[]`, `ariaLabel?` | 展示真实传感器集合；无设备时空态。 |

组件不会用名称猜测设备类型。页面仅按 `device.type` 的精确值 `reactor`、`pump`、`ozone-generator` 和 `sensor` 传入匹配对象。

### SCADA 组件

| 组件 | props | 职责 |
| --- | --- | --- |
| `SCADAMetricGrid` | `metrics: RealtimeMetric[]` | 从真实指标按名称分组，渲染 `SCADAChartPanel`；无数据时中文空态。 |
| `SCADAAlertPanel` | `alerts: ControlAlert[]` | 以 severity、message、timestamp 呈现真实报警；无数据时中文空态。 |
| `SCADADeviceTopology` | `devices: DeviceStatusPanel[]` | 使用真实 `type` 归位设备，组合四个数字孪生 props-only 面板；不发明未知设备。 |

`ControlAlert` 是 Store 已有匿名报警项的本地展示类型：`id`、`severity`、`message`、`timestamp`。它只描述现有 Store 数据，不修改 schema 或新增业务状态。

## 无障碍、响应式与运动

- 所有页面和面板具有准确的中文 `aria-label`、标题层级与状态播报；装饰性信号点设为 `aria-hidden`。
- 原生 `details/summary`（如需展开报警）和可聚焦模块入口保留键盘语义；禁止自建不可聚焦点击区。
- 1440×900 使用紧凑网格：反应器拓扑与预测仍在首屏，设备、指标和告警安全换行；1920×1080 展示扩展的孪生主视图与并列可观测面板。所有容器使用 `min-width: 0`、`minmax(0, …)`，根容器 `overflow-x: clip`。
- 运行信号、孪生流线和图表入场动画使用研究运动令牌；`prefers-reduced-motion: reduce` 下全部停用。

## 测试与验证

新增至少 300 个 B3 UI 契约，覆盖：

- 科研工作区真实 Store 边界、项目目标/阶段/进度/里程碑/风险/AI 行动/模块导航，以及加载、错误和空态；
- 控制中心 SCADA 根主题、实验与 Run 状态、实时指标、设备、报警、AI 建议、预测空态和无伪造实时值；
- 四个数字孪生组件和三个 SCADA 组件的 props-only 边界、中文空态、精确类型映射、ARIA、键盘焦点和 reduced motion；
- 1440×900、1920×1080 的网格与无横向溢出契约；
- 禁止页面内演示初始化、禁止新 Store/Service 导入、禁止硬编码预测/实时指标/报警。

最终验证命令：

```text
npm run test:unit
npx tsc --noEmit -p tsconfig.node.json
npx vue-tsc --noEmit -p tsconfig.web.json
npm run build
```

最终实现提交信息：

```text
Phase 8-M0-B3 Research Workspace Experiment Control Center Digital Twin SCADA Upgrade
```
