// Device Registry — Phase 8-M1-F
// Factory: DeviceKind -> DeviceDriver. 真实协议驱动 (modbus-serial / mqtt / node-opcua) 留 Phase 8-M1-G+.

import type { DeviceKind } from './device-types'
import { ModbusMockDriver } from './modbus-driver'
import { MqttMockDriver, OpcUaMockDriver, SerialMockDriver } from './mock-drivers'
import type { DeviceDriver } from './device-driver'

const FACTORY: Record<DeviceKind, () => DeviceDriver> = {
  'ozone-generator': () => new ModbusMockDriver(),
  'pump': () => new MqttMockDriver(),
  'reactor': () => new OpcUaMockDriver(),
  'sensor': () => new ModbusMockDriver(),
  'ph-meter': () => new MqttMockDriver(),
  'do-meter': () => new ModbusMockDriver(),
  'orp-meter': () => new OpcUaMockDriver(),
  'flow-meter': () => new SerialMockDriver(),
  'power-meter': () => new SerialMockDriver()
}

export function createDeviceDriver(kind: DeviceKind): DeviceDriver {
  const factory = FACTORY[kind]
  if (!factory) throw new Error(`[device-registry] 未知设备类型 '${kind}'`)
  return factory()
}
