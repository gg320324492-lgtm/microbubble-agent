// Device Registry — Phase 8-M1-F → [类 20.191] 2026-08-27
//
// 原设计: 9 个 device kind 全部映射到 mock driver (ModbusMockDriver / MqttMockDriver /
// OpcUaMockDriver / SerialMockDriver), 内部用 sin() + Math.random() 生成假 telemetry.
// 真实协议驱动 (modbus-serial / mqtt / node-opcua / serialport) 留 Phase 8-M1-G+.
//
// [类 20.191] 2026-08-27: 删 hardcoded mock driver factory.
// 改为: device-registry 初始为空, 用户/集成代码通过 registerDevice(kind, driver) 显式注册真实驱动.
// 若未注册, createDeviceDriver 抛 NotConnectedDeviceError, UI 看到明确错误而不是假数据.

import type { DeviceKind, CommandAck, TelemetrySample, DeviceConfig } from './device-types'
import type { DeviceDriver, Unsubscribe } from './device-driver'

/** [类 20.191] 设备未注册时抛错. */
export class NotConnectedDeviceError extends Error {
  constructor(kind: DeviceKind) {
    super(
      `[device-registry] 设备类型 '${kind}' 未注册真实 driver. ` +
      `Phase 8-M1-F 时期的 MockDriver (Modbus/MQTT/OPC-UA/Serial) 已在 [类 20.191] 删除 — 之前会返回 Math.random() 假 telemetry. ` +
      `真实协议 driver 待 Phase 8-M1-G+ 实现. 调用 registerDevice('${kind}', realDriver) 注入真实 driver.`
    )
    this.name = 'NotConnectedDeviceError'
  }
}

/** [类 20.191] 未连接设备 stub driver — 所有操作立即报 NotConnectedDeviceError. */
class NotConnectedDriver implements DeviceDriver {
  readonly driverId: string
  private readonly _kind: DeviceKind
  constructor(kind: DeviceKind) {
    this._kind = kind
    this.driverId = `not-connected-${kind}`
  }
  async connect(_config: DeviceConfig): Promise<void> { throw new NotConnectedDeviceError(this._kind) }
  async disconnect(): Promise<void> { /* no-op, 设备从未连接 */ }
  isConnected(): boolean { return false }
  async read(_register: string): Promise<number | null> { throw new NotConnectedDeviceError(this._kind) }
  async write(_register: string, _value: number, _commandId: string): Promise<CommandAck> {
    throw new NotConnectedDeviceError(this._kind)
  }
  subscribe(_callback: (sample: TelemetrySample) => void): Unsubscribe {
    // 返回空 unsubscribe, 不调 callback. UI 侧需要主动检查 isConnected() 判断数据是否真.
    return () => {}
  }
}

// 设备注册表: kind -> driver factory. 初始为空.
const REGISTRY: Map<DeviceKind, () => DeviceDriver> = new Map()

/** [类 20.191] 注册真实 driver. 用户/集成代码在启动时调用. */
export function registerDevice(kind: DeviceKind, factory: () => DeviceDriver): void {
  REGISTRY.set(kind, factory)
}

/** [类 20.191] 取消注册 (用于 hot-swap 测试). */
export function unregisterDevice(kind: DeviceKind): void {
  REGISTRY.delete(kind)
}

/** [类 20.191] 列出当前已注册的设备类型. */
export function listRegisteredDevices(): DeviceKind[] {
  return Array.from(REGISTRY.keys())
}

export function createDeviceDriver(kind: DeviceKind): DeviceDriver {
  const factory = REGISTRY.get(kind)
  if (!factory) {
    // 未注册 → 返回 NotConnectedDriver stub, 调操作时抛 NotConnectedDeviceError
    return new NotConnectedDriver(kind)
  }
  return factory()
}

/** [类 20.191] 检查某 device kind 是否已注册. UI 可用此显示 '未连接' badge. */
export function isDeviceRegistered(kind: DeviceKind): boolean {
  return REGISTRY.has(kind)
}
