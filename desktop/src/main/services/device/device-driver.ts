// DeviceDriver Interface — Phase 8-M1-F
// 所有协议适配器实现此接口. M1-F 阶段全部 4 个驱动是 mock (sin 生成 + 正弦),
// 真实 wire (modbus-serial / mqtt / node-opcua / serialport) 留 Phase 8-M1-G+.

import type {
  CommandAck,
  DeviceConfig,
  TelemetrySample
} from './device-types'

export type Unsubscribe = () => void

export interface DeviceDriver {
  readonly driverId: string
  connect(config: DeviceConfig): Promise<void>
  disconnect(): Promise<void>
  isConnected(): boolean
  read(register: string): Promise<number | null>
  write(register: string, value: number, commandId: string): Promise<CommandAck>
  subscribe(callback: (sample: TelemetrySample) => void): Unsubscribe
}
