// Device index — Phase 8-M1-F → [类 20.191] 2026-08-27
// 移除 ModbusMockDriver / MqttMockDriver / OpcUaMockDriver / SerialMockDriver 4 个 mock 类的 re-export
// (这些类内部用 sin() + Math.random() 假 telemetry, 已在 [类 20.191] 2026-08-27 删除).
// 真实协议驱动 (modbus-serial / mqtt / node-opcua / serialport) 待 Phase 8-M1-G+ 实现.
export * from './device-types'
export type { DeviceDriver, Unsubscribe } from './device-driver'
export {
  createDeviceDriver,
  registerDevice,
  unregisterDevice,
  listRegisteredDevices,
  isDeviceRegistered,
  NotConnectedDeviceError
} from './device-registry'
export { createTelemetryPipeline, type TelemetryPipeline } from './telemetry-pipeline'
export { createAlarmEngine, type AlarmEngine } from './alarm-engine'
export { createCommandPipeline, type CommandPipeline } from './command-pipeline'
export {
  bootstrapDeviceService,
  getDeviceService,
  resetDeviceService,
  type DeviceService,
  type DeviceEvent,
  type DeviceEventListener
} from './device.service'
