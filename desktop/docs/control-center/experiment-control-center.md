# 实验控制中心

## 概述

统一实验控制中心 — 集成设备监控、实时指标、AI 推荐、数字孪生预测、时间线于一体,提供一站式科研操作界面。

## 数据模型

### ControlDashboard

```
ControlDashboard
  id              仪表盘 ID
  experimentId    关联实验 ID
  title           标题
  deviceIds       设备 ID 数组
  metrics         关注的指标名数组
  createdAt       创建时间
  updatedAt       更新时间
```

### DeviceStatusPanel

```
DeviceStatusPanel
  deviceId        设备 ID
  name            设备名
  type            设备类型
  status          状态字符串
  lastSeen        最近活跃时间
  recentReadings  近期读数数量
```

### RealtimeMetric

```
RealtimeMetric
  metric        指标名
  value         数值
  unit          单位
  timestamp     时间戳
  deviceId      设备 ID
```

### ExperimentTimelineEntry

```
ExperimentTimelineEntry
  id            ID
  experimentId  实验 ID
  timestamp     时间戳
  event         事件名
  description   描述
```

### AIRecommendation

```
AIRecommendation
  id            ID
  experimentId  实验 ID
  kind          类型 (optimize / adjust / switch / record / ...)
  title         标题
  rationale     推理依据
  confidence    置信度 (0..1)
  createdAt     创建时间
```

### ControlAction

```
ControlAction
  id            ID
  dashboardId   仪表盘 ID
  kind          动作类型 (start/pause/stop/adjust/switch/record)
  target        目标
  parameters    参数键值对
  issuedAt      签发时间
```

## 核心组件

### ExperimentMonitor

实时监控服务:

- `createDashboard(input)` — 创建仪表盘
- `getDashboard(id)` / `subscribeExperiment(experimentId)` — 获取
- `pushMetric(metric)` / `getRealtimeMetrics(deviceId, metricName?)` — 指标
- `registerDevicePanel(panel)` / `updateDeviceStatus(...)` / `listDeviceStatuses()` — 设备面板
- `appendTimeline(entry)` / `getTimeline(experimentId)` — 时间线
- 指标 + 时间线均自动环形缓冲

### ExperimentAdvisor

AI 推荐引擎:

- 4 条默认规则 (optimize-ozone-flow / adjust-pressure / change-sampling-interval / record-baseline)
- `advise(ctx)` 返回 `AIRecommendation[]`
- `ctx` 包含 experimentId + metrics + 可选 twinConfidence + experimentStatus
- 数字孪生置信度 < 0.5 时,推荐置信度自动下调 0.2

### ExperimentControlStore (Pinia)

状态: devices / metrics / timeline / recommendations / alerts / dashboards / actions

Getters: deviceCount / onlineDeviceCount / criticalAlertCount 等

Actions: setDevices / pushMetric / latestMetric / appendTimeline / setRecommendations / pushAlert / recordAction / reset

## UI 页面

`ExperimentControlCenter.vue` — 主页面包含 5 个区域:

1. 设备仪表盘 — DeviceCard 列表
2. 实时图表 — RealtimeChart 列表 (按 metric 分组)
3. 实验时间线 — ExperimentTimeline
4. 数字孪生预测 — PredictionPanel
5. AI 推荐 — AIAdviceCard

UI 风格: 现代科学 OS,珊瑚橙主色 (#FF7A5C), 12px 圆角, 渐变背景。

## 集成示例

```ts
import { ExperimentMonitor } from './services/control/experiment-monitor'
import { ExperimentAdvisor } from './services/control/experiment-advisor'

const monitor = new ExperimentMonitor()
const advisor = new ExperimentAdvisor()

const dash = monitor.createDashboard({
  experimentId: 'exp-1',
  title: 'O3-MNB 实验',
  deviceIds: ['pump-1', 'ozone-1', 'sensor-1'],
  metrics: ['ozone_dose', 'pressure', 'temperature']
})

monitor.pushMetric({
  metric: 'ozone_dose', value: 2, unit: 'mg/L',
  timestamp: Date.now(), deviceId: 'ozone-1'
})

const recs = advisor.advise({
  experimentId: 'exp-1',
  metrics: monitor.getRealtimeMetrics('ozone-1'),
  twinConfidence: 0.85
})
```

## 安全边界

- ControlAction.parameters 仅允许 string|number|boolean
- AIRecommendation.confidence 严格 0..1
- 所有 getter 返回防御性拷贝
- 数字孪生预测无后端调用
- AI 推荐纯确定性规则, 无 LLM 直连
- 无密钥存储