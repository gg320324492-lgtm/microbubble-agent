# 实时实验流程

## 概述

实时设备数据 → 实验记录 → 数据集 → 数字孪生预测 的完整链路,实现"设备一动,实验跟着动"的实时科研反馈。

## 流程图

```
┌──────────────────────────────────────────────────────────────┐
│                                                              │
│  ScientificDevice (物理/仿真)                                │
│       ↓ SensorReading                                        │
│  DeviceStreamManager.collectReading()                        │
│       ↓ emit 'reading' event                                 │
│  ┌────────────────┬─────────────────┐                       │
│  ↓                ↓                 ↓                         │
│  Buffer          Subscribers      Event Log                  │
│  ↓                                                          │
│  DeviceExperimentAdapter.readingToRecord()                   │
│       ↓ ExperimentRecord                                     │
│  ExperimentManager.addRecord() (Phase 8-K0)                  │
│       ↓                                                      │
│  DeviceExperimentAdapter.readingsToDataset()                 │
│       ↓ ScientificDataset (Phase 8-H2)                       │
│  DeviceTwinAdapter.predictFromReadings()                     │
│       ↓                                                      │
│  DigitalTwinEngine.predict() (Phase 8-K1)                    │
│       ↓ TwinPrediction                                       │
│  ResearchEventBus.emit('experiment.recorded')                │
│       ↓                                                      │
│  UI 实时反馈                                                  │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

## 数据流细节

### Step 1 — 设备采集

`SimulatedDevice.read(metric)` 返回 SensorReading:

```ts
{
  deviceId, timestamp, metric, value, unit
}
```

### Step 2 — 流式分发

`DeviceStreamManager` 三路分发:

1. **缓冲** — `bufferData(reading)`, 环形 buffer (默认 100 条)
2. **订阅** — `subscribe(deviceId, metric, listener)`, 触发即时回调
3. **事件** — `emit('reading', payload)`, 全局事件流

### Step 3 — 转实验记录

`DeviceExperimentAdapter.readingToRecord(reading, operator, experimentId)` 产出 ExperimentRecord (Phase 8-K0 类型), 不修改其契约。

### Step 4 — 转数据集

`readingsToDataset(readings, name)` 产出 ScientificDataset (Phase 8-H2 类型), 不修改其契约。

### Step 5 — 数字孪生预测

`DeviceTwinAdapter.predictFromReadings({deviceId, readings, twinModel})`:

1. `readingsToFeatures(readings)` — 按 metric 分组, 提取数值数组
2. `normalize(feature)` — 归一化到 [0, 1]
3. 取每组最新归一化值
4. `DigitalTwinEngine.predict(spec, input)` — 路由到 linear/polynomial/kinetic
5. 返回 TwinPrediction[]

### Step 6 — 事件广播

触发 `experiment.recorded` 事件 (Phase 8-J2 ResearchEventBus), UI 层可订阅并显示。

## 集成示例

```ts
import { DeviceStreamManager } from './services/device/device-stream-manager'
import { readingToRecord, readingsToDataset } from './services/device/device-experiment-adapter'
import { predictFromReadings } from './services/device/device-twin-adapter'

// 订阅某设备的某指标
const unsub = mgr.subscribe(deviceId, 'ph', (event) => {
  if (event.type === 'reading') {
    const reading = event.payload.reading as SensorReading
    const rec = readingToRecord(reading, 'alice', 'exp-1')
    experimentManager.addRecord('exp-1', {
      operator: rec.operator,
      parameters: rec.parameters,
      observations: rec.observations,
      notes: rec.notes
    })
  }
})

// 批量预测
const readings = mgr.getBuffer(deviceId)
const predictions = predictFromReadings({ deviceId, readings, twinModel })
```

## 复用现有 Phase 8 类型

| 复用源 | 用途 |
|--------|------|
| Phase 8-K0 `ExperimentRecord` | readingToRecord 输出 |
| Phase 8-K0 `ExperimentManager` | 实验记录管理 |
| Phase 8-H2 `ScientificDataset` | readingsToDataset 输出 |
| Phase 8-K1 `TwinPrediction` | 设备预测输出 |
| Phase 8-K1 `DigitalTwinModel` | 设备孪生输入 |
| Phase 8-J2 `ResearchEventBus` | 事件广播 |

设备层**仅消费**这些类型, 不修改其契约。

## 安全边界

- 协议字符串仅作标识, 无凭证存储
- 所有读数 value 必须 Number.isFinite
- DeviceParameter 类型限定
- bufferData 自动截断, 不爆内存
- emit 异常隔离, listener 错误不阻塞
- 无 LLM 直连, 无后端调用, 无密钥存储