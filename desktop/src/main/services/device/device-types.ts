// Device Types — Phase 8-M1-F
// 实验设备统一类型契约: 8 种环保工程设备 + 标准化遥测样本 + 命令 + ACK.

export type DeviceKind =
  | 'ozone-generator'
  | 'pump'
  | 'reactor'
  | 'sensor'
  | 'ph-meter'
  | 'do-meter'
  | 'orp-meter'
  | 'flow-meter'
  | 'power-meter'

export const DEVICE_KINDS: ReadonlyArray<DeviceKind> = [
  'ozone-generator', 'pump', 'reactor', 'sensor',
  'ph-meter', 'do-meter', 'orp-meter', 'flow-meter', 'power-meter'
]

export type DeviceConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error' | 'offline'

export type SampleQuality = 'good' | 'questionable' | 'bad'

export interface TelemetrySample {
  deviceId: string
  deviceType: DeviceKind
  metric: string
  value: number
  unit: string
  timestamp: number
  quality: SampleQuality
}

export interface DeviceConfig {
  deviceId: string
  deviceType: DeviceKind
  endpoint: string
  pollIntervalMs?: number
  calibrationAt?: number
  alarmLow?: number | null
  alarmHigh?: number | null
}

export type CommandKind = 'set-setpoint' | 'start' | 'stop' | 'calibrate' | 'reset-alarm'

export interface DeviceCommand {
  deviceId: string
  kind: CommandKind
  metric?: string
  value?: number
  reason?: string
  operator?: string
  timestamp: number
}

export type CommandAckStatus = 'ok' | 'failed' | 'timeout' | 'rejected'

export interface CommandAck {
  commandId: string
  status: CommandAckStatus
  message: string
  appliedValue?: number
  timestamp: number
}

export interface DeviceStatus {
  deviceId: string
  deviceType: DeviceKind
  state: DeviceConnectionState
  endpoint: string
  lastSampleAt: number | null
  calibrationAt: number | null
  alarmLow: number | null
  alarmHigh: number | null
  pendingAlarmCount: number
}

export interface AlarmEvent {
  id: number
  deviceId: string
  metric: string
  level: 'low' | 'high' | 'offline'
  value: number
  threshold: number
  triggeredAt: number
  acknowledgedAt: number | null
  acknowledgedBy: string | null
  reason: string | null
}