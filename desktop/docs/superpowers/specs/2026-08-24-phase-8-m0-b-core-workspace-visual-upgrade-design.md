# Phase 8-M0-B 核心科研工作区视觉升级设计

**状态：** 已获视觉与架构批准（2026-08-24）  
**范围：** 仅 `desktop/**`；不修改 `backend/`、`web/`、`app/`。

## 目标

在 Phase 8-M0-A 的研究设计系统之上，把五个高频科研页面升级为统一的“科研指挥中心”体验：信息密度适中、证据优先、面向桌面研究决策。实验控制中心是唯一的深色仪器 SCADA 视图，但使用同一层级、字重、间距和可访问性语言。

用户批准的关键决策：

- 日常页面采用原型 A「科研指挥中心」。
- Assistant 仅默认展开“结论”；证据、推理摘要、引用、下一步按需展开。
- 使用共享的 props-only 组件组合层，而不是分别复制五套 UI。

## 已审计的边界

| 页面 | 既有数据边界 | M0-B 处理 |
| --- | --- | --- |
| `Dashboard.vue` | project、knowledge、dataset、manuscript stores | 保持当前加载、错误和真实洞察；重组为焦点、阶段、AI 时间线、实验、设备与洞见面板。 |
| `Assistant.vue` | agent store 的 sessions、messages、events、citations、evidence、发送/会话错误 | 不改变发送与重试行为；将助手回复可读地分区，提供执行时间线与 Agent 状态。 |
| `AgentCenter.vue` | agent store、project store 与既有 Agent 数据 | 显示五个研究角色，使用当前队列/事件承载协作与工具执行状态。 |
| `ProjectWorkspace.vue` | project、knowledge、dataset、experiment、manuscript stores | 不重建状态；项目目标、进度、里程碑、风险、AI 当前动作在概览层可读。 |
| `ExperimentControlCenter.vue` | `useExperimentControlStore()` 的 devices、metrics、timeline、recommendations、alerts、dashboards；已有 Device/Digital Twin 层类型 | 仅呈现 store 当前数据。预测区只显示传入的真实 `TwinPrediction[]`；没有真实预测时显示空状态，绝不制造数值或告警。 |

共享展示组件禁止导入 Pinia Store 或 service。页面是唯一允许把已有状态转换为视图 props 的位置。

## 信息架构

### 1. 科研驾驶舱

顶部使用 `ResearchPageHeader` 和当前项目焦点带：项目名称、领域、研究目标、阶段和项目进度。第一行是可比较的研究指标；第二行包含 AI 活动时间线、实验状态/设备健康度和近期洞见。所有洞见仍仅来自 dataset/knowledge/manuscript 的真实状态，加载、局部失败和无数据状态保留且可重试。

### 2. AI 科研助手

每条助手回复采用五个语义区块：结论、证据、推理摘要、引用、下一步。结论区初始展开，其余区块以原生 `details/summary` 或可访问的按钮面板折叠。工具事件由时间线呈现，当前 Agent 与会话状态通过状态面板呈现；沿用已有 session/send 错误重试，不吞没失败。

### 3. AI 研究团队

固定研究角色为：文献智能体、实验智能体、分析智能体、写作智能体、审稿智能体。卡片不是伪造运行记录：状态、队列数量、协作活动和工具历史来自当前 Agent store 事件或明确空状态。各 Agent 的图标、状态色和最近动作共享同一语义。

### 4. 研究工作区

项目概览升为项目指挥中心：研究目标、阶段、进度、里程碑、风险、AI 当前动作、模块导航。其现有键盘可操作 tablist 继续保留；模块内容仍由原来的 documents、design、statistics、models 和 manuscript 数据渲染。

### 5. 实验控制中心

根节点使用 `data-research-theme="scada"` 的暗色仪器语言：信号色、网格背景、科学数字和告警等级来自 M0-A 令牌。实时指标由当前 `RealtimeMetric[]` 计算；设备卡由当前 `DeviceStatusPanel[]` 计算；告警直接来自 `alerts`；推荐直接来自 `recommendations`。数字孪生面板使用实际 `TwinPrediction[]`，无数据时透明地显示“暂无数字孪生预测”。设备可视化是明确标注的 reactor / pump / ozone generator / sensor 图形占位，不进行控制或模拟。

## 共享组件契约

所有新组件放在 `desktop/src/renderer/src/components/research/`，仅使用 `defineProps`、`computed` 和展示性 Vue API。

| 组件 | 职责与核心 props |
| --- | --- |
| `ResearchMetricPanel` | 科学数字栅格；`items: { label, value, unit?, trend?, status? }[]`，空项目给出可访问空状态。 |
| `ResearchTimeline` | 研究/工具/协作事件；`items: { id, title, description, timestamp?, status, actor? }[]`。 |
| `AgentStatusPanel` | Agent 身份、当前状态、队列和最近动作；`agents: AgentStatusItem[]`。 |
| `EvidencePanel` | 证据、置信度和 citation 摘要；`evidence: EvidenceItem[]`、`citations: CitationItem[]`。 |
| `DeviceStatusPanel` | 设备卡片；`devices: DeviceStatusPanel[]`、`variant?: 'research' | 'scada'`。 |
| `SCADAChartPanel` | 实时指标轨迹；`metrics: RealtimeMetric[]`、`metricName`、`label?`。 |
| `PredictionPanel` | 数字孪生预测、空状态和可信度；`predictions: TwinPrediction[]`、`variant?: 'research' | 'scada'`。 |

组件的状态文本均为中文；根节点含有明确的 `aria-label`；装饰图标为 `aria-hidden`；纯视觉动画遵从 `prefers-reduced-motion`。

## 视觉与响应式规则

- 1440×900：Dashboard/Workspace 保持 2–3 个主要列，侧边信息变为下一行，禁止内容遮挡或横向主区域溢出。
- 1920×1080：指标可扩展为 4–5 个等宽列，主要工作区保持充足留白而不是把文字放大。
- SCADA：暗色面板不混入日常白色卡片；状态使用 signal-green、signal-amber、signal-red，不能只依赖颜色表达。
- 焦点样式使用 M0-A `:focus-visible` 令牌；键盘 tab、会话列表、可折叠 Assistant 区块和时间线中的可操作项均可到达。

## 错误、空状态与真实性

- 只扩展展示层，保留现有 store/service 错误重试路径。
- 无设备、无指标、无预测、无 Agent 事件时显示明确中文空状态。
- 严禁为了美观在页面中加入虚构实验读数、设备心跳、预测结果、告警、文献、任务或 AI 事件。
- 没有真实数字孪生模型和输入数据时，预测区显示空状态而不是推断示例值。

## 测试与验证

新增一个 M0-B DOM/源码契约套件，最少 300 个 Vitest 断言，覆盖：

1. 7 个共享组件的 props-only 边界（无 store/service 导入）、中文标签和空/加载/错误/成功状态；
2. 五条路由、五个页面的核心标题和各页面的数据边界；
3. Assistant 的默认结论展开与四个可访问区块；
4. 5 个固定 Agent 角色、队列、协作/工具时间线；
5. SCADA 主题、实时指标、设备、预测空状态、告警及 reactor/pump/ozone generator/sensor 语义；
6. 1440 与 1920 的断点、focus-visible、aria、reduced-motion。

最终门禁：`npm run test:unit`、`npx tsc --noEmit -p tsconfig.node.json`、`npx vue-tsc --noEmit -p tsconfig.web.json`、`npm run build`。构建连续运行两次并比较哈希资产清单。
