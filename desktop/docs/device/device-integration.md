# 设备集成层

## 概述

科研设备接入层 — 为科研系统提供统一的设备抽象,支持真实硬件接入与本地仿真,并通过流式数据管道将设备读数接入实验闭环与数字孪生。

## 数据模型

### ScientificDevice

```
ScientificDevice
  id          唯一标识
  name        设备名
  type        类型: pump | ozone-generator | sensor | reactor | controller
  protocol    协议字符串 (例: sim://local, modbus://192.168.1.10)
  status      状态: offline | connecting | online | error
  parameters  参数数组 (DeviceParameter)
  lastSeen    最近活跃时间戳
  createdAt   创建时间戳
```

### SensorReading

```
SensorReading
  deviceId    设备 ID
  timestamp   时间戳
  metric      指标名
  value       数值
  unit        单位
```

### DeviceParameter

```
DeviceParameter
  name        参数名
  value       值 (string | number | boolean)
  unit        单位
```

## 核心组件

### DeviceAdapter (接口契约)

所有设备实现的统一接口:

- `status()` — 返回当前 DeviceStatus
- `connect()` — 异步连接
- `disconnect()` — 异步断开
- `read(metric)` — 异步读单个指标
- `write(parameter)` — 异步写参数
- `describe()` — 返回 ScientificDevice 元信息

### SimulatedDevice

本地确定性模拟器 (实现 DeviceAdapter):

- 基于 name 的 hash 生成 seed,确定性伪随机
- 支持 `drift` + `noise` 参数控制噪声
- 内部维护 reads / writes / errors 计数

工厂函数:

- `createPumpSimulator(name, options)` — 泵模拟器
- `createOzoneSimulator(name, options)` — 臭氧发生器
- `createSensorSimulator(name, options)` — 多参数传感器

### DeviceStreamManager

数据流管理器:

- `subscribe(deviceId, metric, listener)` — 订阅
- `unsubscribeAll(deviceId)` — 取消某设备全部订阅
- `collectReading(deviceId, metric)` — 主动采集
- `bufferData(reading)` — 写入环形缓冲
- `flush(deviceId)` — 取出并清空缓冲
- `emit(event)` — 触发事件
- 5 种事件: reading / buffer-flush / error / subscribed / unsubscribed

环形缓冲默认 100 条,溢出自动丢弃最旧。

### DeviceExperimentAdapter

连接 SensorReading 与 Phase 8-K0 ExperimentRecord:

- `readingToRecord(reading, operator, experimentId)` — 单读数转记录
- `readingsToDataset(readings, name)` — 多读数转 Phase 8-H2 ScientificDataset
- `aggregateReadings(readings, metric)` — 聚合 (count/min/max/mean/unit)

### DeviceTwinAdapter

连接 SensorReading 与 Phase 8-K1 DigitalTwinModel:

- `readingsToFeatures(readings)` — 读数转特征向量
- `predictFromReadings(input)` — 基于最新特征预测, 返回 TwinPrediction[]
- `predictLatestReading(reading, twinModel)` — 单点预测
- `streamPredict(input, onPrediction)` — 流式预测, 每次触发回调

### DeviceTemplates

3 套预定义设备系统 (Object.freeze):

- `o3-mnb-reactor` — O3-MNB 反应器 (5 设备)
- `cfd-experiment` — CFD 实验 (4 设备)
- `water-treatment-monitoring` — 水处理监控 (4 设备)

通过 `getDeviceTemplate(kind)` 获取, `listDeviceTemplates()` 列出全部。

## 工作流示例

```ts
import { createPumpSimulator, createOzoneSimulator, createSensorSimulator } from './services/device/simulated-device'
import { DeviceStreamManager } from './services/device/device-stream-manager'
import { readingToRecord } from './services/device/device-experiment-adapter'
import { predictLatestReading } from './services/device/device-twin-adapter'

const pump = createPumpSimulator('main-pump')
const ozone = createOzoneSimulator('ozone-gen')
const sensor = createSensorSimulator('ph-sensor')

await pump.connect()
await ozone.connect()
await sensor.connect()

const mgr = new DeviceStreamManager()
mgr.registerAdapter(pump)
mgr.registerAdapter(ozone)
mgr.registerAdapter(sensor)

const reading = await mgr.collectReading(sensor.id, 'ph')
if (reading) {
  const rec = readingToRecord(reading, 'alice', 'exp-1')
  console.log(rec.observations)
}
```

## 安全边界

- 协议字符串仅作标识, 不存任何凭证
- DeviceParameter.value 类型限定 string/number/boolean
- 所有 getter 返回防御性拷贝
- 模板 Object.freeze, 只读访问通过 getDeviceTemplate 返回拷贝
- 无 LLM 直连, 无后端调用, 无密钥存储