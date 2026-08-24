// Device Adapter Schema — 设备适配器接口契约。

import type { ScientificDevice, SensorReading, DeviceParameter, DeviceStatus } from './device-schema'

export interface DeviceAdapter {
  /** 设备唯一标识 */
  readonly id: string
  /** 设备类型 */
  readonly type: string
  /** 当前状态 */
  status(): DeviceStatus
  /** 连接设备 */
  connect(): Promise<boolean>
  /** 断开连接 */
  disconnect(): Promise<boolean>
  /** 读取单个传感器读数 */
  read(metric: string): Promise<SensorReading | null>
  /** 写入参数 */
  write(parameter: DeviceParameter): Promise<boolean>
  /** 获取设备元信息 */
  describe(): ScientificDevice
}

export interface AdapterHealth {
  connected: boolean
  uptime: number
  reads: number
  writes: number
  errors: number
}

export const __testHelpers = {}