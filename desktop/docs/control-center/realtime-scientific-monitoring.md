# 实时科研监控

## 概述

实时科研监控流程 — 从设备数据到控制面板的端到端链路,实现"设备变化 → UI 即时反馈"的实时科研操作体验。

## 流程图

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  Phase 8-K2 设备层                                              │
│    SimulatedDevice / DeviceAdapter                              │
│       ↓ SensorReading                                           │
│  DeviceStreamManager (collectReading + emit)                    │
│       ↓ emit 'reading' event                                    │
│  ┌────────────────────┐                                         │
│  ↓                    ↓                                         │
│  Buffer           Subscribers                                    │
│  ↓                                                                  │
│  Phase 8-K3 监控层                                               │
│  ExperimentMonitor.pushMetric(RealtimeMetric)                   │
│       ↓ 环形缓冲 + sorted-by-timestamp                           │
│  ExperimentControlStore (Pinia)                                 │
│    - state.devices                                             │
│    - state.metrics                                             │
│    - state.timeline                                            │
│    - state.recommendations                                     │
│    - state.alerts                                              │
│       ↓                                                          │
│  ┌──────────────┬───────────────┬─────────────────┐            │
│  ↓              ↓               ↓                 ↓            │
│  DeviceCard  RealtimeChart   AIAdviceCard  PredictionPanel    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 数据流细节

### Step 1 — 设备采集

`DeviceStreamManager.collectReading(deviceId, metric)`:

```ts
{
  deviceId, timestamp, metric, value, unit
}
```

### Step 2 — 转 RealtimeMetric

`ExperimentMonitor.pushMetric`:

```ts
monitor.pushMetric({
  metric: reading.metric,
  value: reading.value,
  unit: reading.unit,
  timestamp: reading.timestamp,
  deviceId: reading.deviceId
})
```

### Step 3 — 数字孪生 + AI 推荐

```ts
const twinPred = predictAndRecord(spec, modelId, { [metric]: value })
const recs = advisor.advise({
  experimentId,
  metrics: monitor.getRealtimeMetrics(deviceId),
  twinConfidence: twinPred.confidence
})
```

### Step 4 — Pinia 更新

```ts
store.pushMetric(...)
store.addRecommendation(rec)
store.appendTimeline({
  id, experimentId, timestamp, event, description
})
```

### Step 5 — UI 即时渲染

Vue 响应式系统自动触发组件重渲染:

- DeviceCard 显示设备状态 + 最近读数
- RealtimeChart 绘制时间序列
- ExperimentTimeline 追加事件
- PredictionPanel 显示孪生输出
- AIAdviceCard 显示推荐列表

## 实时策略

### 缓冲策略

- 指标环形缓冲: 默认 200 条 (configurable)
- 时间线环形缓冲: 默认 100 条 (configurable)
- 设备面板无环形缓冲 (设备数量固定)

### 更新频率

- 设备采集: 取决于设备协议 (sim 默认每次 read 一次)
- 监控 push: 与采集同步
- UI 重渲染: Vue 自动, 默认 < 16ms

### 告警触发

`store.pushAlert(severity, message)`:

- info: 一般提示
- warning: 偏离工作区间
- critical: 设备离线 / 严重偏离

## 集成示例

```ts
import { ExperimentMonitor } from './services/control/experiment-monitor'
import { ExperimentAdvisor } from './services/control/experiment-advisor'
import { useExperimentControlStore } from './stores/experiment-control.store'

const monitor = new ExperimentMonitor()
const advisor = new ExperimentAdvisor()
const store = useExperimentControlStore()

// 订阅设备流
streamManager.subscribeAll((event) => {
  if (event.type === 'reading') {
    const reading = event.payload.reading
    monitor.pushMetric({
      metric: reading.metric, value: reading.value,
      unit: reading.unit, timestamp: reading.timestamp,
      deviceId: reading.deviceId
    })
    store.pushMetric({ ... })
  }
})

// 定时跑 AI 推荐
setInterval(() => {
  const recs = advisor.advise({ experimentId, metrics: monitor.getRealtimeMetrics('d') })
  store.setRecommendations(recs)
}, 5000)
```

## 复用 Phase 8 类型

| 复用源 | 用途 |
|--------|------|
| Phase 8-K2 `SensorReading` | 转 RealtimeMetric |
| Phase 8-K1 `TwinPrediction` | PredictionPanel 显示 |
| Phase 8-K2 `DeviceStreamManager` | 订阅 reading 事件 |
| Phase 8-J2 `ResearchEventBus` | 事件广播 (可选) |

控制层**仅消费**这些类型, 不修改其契约。

## 安全边界

- RealtimeMetric.value 严格 Number.isFinite
- AIRecommendation.confidence 严格 0..1
- ExperimentMonitor 环形缓冲自动丢弃最旧
- 所有 getter 返回防御性拷贝
- 无 LLM 直连, 无后端调用, 无密钥存储