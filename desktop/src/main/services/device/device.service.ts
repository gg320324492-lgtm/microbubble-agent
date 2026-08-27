// Device Service — Phase 8-M1-F
// 单例编排: 设备连接管理 + 驱动选择 + 遥测 + 告警 + 命令 + 事件广播.

import type { DatabaseService } from '../database.service'
import type { SQLiteDatabase } from '../../database'
import { createDeviceDriver } from './device-registry'
import type { DeviceDriver } from './device-driver'
import type {
  AlarmEvent,
  CommandAck,
  DeviceConfig,
  DeviceKind,
  DeviceStatus,
  TelemetrySample
} from './device-types'
import { createTelemetryPipeline, type TelemetryPipeline } from './telemetry-pipeline'
import { createAlarmEngine, type AlarmEngine } from './alarm-engine'
import { createCommandPipeline, type CommandPipeline } from './command-pipeline'

export type DeviceEvent =
  | { type: 'telemetry'; payload: TelemetrySample }
  | { type: 'alarm'; payload: AlarmEvent }
  | { type: 'connection'; payload: { deviceId: string; state: string } }

export type DeviceEventListener = (event: DeviceEvent) => void

export interface DeviceService {
  connect(config: DeviceConfig): Promise<void>
  disconnect(deviceId: string): Promise<void>
  status(deviceId?: string): DeviceStatus[]
  telemetry(deviceId: string, sinceMs?: number): TelemetrySample[]
  alarms(deviceId?: string): AlarmEvent[]
  command(config: DeviceConfig, cmd: { kind: 'set-setpoint' | 'start' | 'stop' | 'calibrate' | 'reset-alarm'; metric?: string; value?: number; reason?: string; operator?: string }): Promise<CommandAck>
  subscribe(listener: DeviceEventListener): () => void
  shutdown(): void
}

interface ManagedDevice {
  config: DeviceConfig
  driver: DeviceDriver
  unsubscribe: () => void
  lastSampleAt: number
  pendingAlarmCount: number
}

class DeviceServiceImpl implements DeviceService {
  private readonly devices: Map<string, ManagedDevice>
  private readonly listeners: Set<DeviceEventListener>
  private _pipeline?: TelemetryPipeline
  private _alarm?: AlarmEngine
  private _cmdPipeline?: CommandPipeline

  constructor(private readonly getService: () => DatabaseService | null) {
    // Phase 10.6 hotfix: 延迟 requireDb() — 构造时 service 还未注入, 立即调用必抛 '数据库未就绪'
    // 把 telemetry/alarm/cmd pipeline 初始化延迟到第一次方法调用
    this.devices = new Map()
    this.listeners = new Set()
  }

  /** Phase 10.6 hotfix: 懒加载 service, 第一次调用时初始化 pipeline */
  private getOrInit(): { pipeline: TelemetryPipeline; alarm: AlarmEngine; cmdPipeline: CommandPipeline } {
    const db = this.requireDb()
    if (!this._pipeline) {
      this._pipeline = createTelemetryPipeline(db)
      this._alarm = createAlarmEngine(this.getService)
      this._cmdPipeline = createCommandPipeline(this.getService)
    }
    return { pipeline: this._pipeline, alarm: this._alarm!, cmdPipeline: this._cmdPipeline! }
  }

  private requireDb(): SQLiteDatabase {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    return svc.db
  }

  async connect(config: DeviceConfig): Promise<void> {
    const existing = this.devices.get(config.deviceId)
    if (existing) await this.disconnect(config.deviceId)
    const driver = createDeviceDriver(config.deviceType)
    await driver.connect(config)
    const unsubscribe = driver.subscribe((sample) => this.handleSample(sample, config))
    this.devices.set(config.deviceId, {
      config, driver, unsubscribe,
      lastSampleAt: 0, pendingAlarmCount: 0
    })
    this.emit({ type: 'connection', payload: { deviceId: config.deviceId, state: 'connected' } })
  }

  async disconnect(deviceId: string): Promise<void> {
    const managed = this.devices.get(deviceId)
    if (!managed) return
    managed.unsubscribe()
    await managed.driver.disconnect()
    this.devices.delete(deviceId)
    this.emit({ type: 'connection', payload: { deviceId, state: 'disconnected' } })
  }

  status(deviceId?: string): DeviceStatus[] {
    const all = Array.from(this.devices.values())
    const filtered = deviceId ? all.filter((d) => d.config.deviceId === deviceId) : all
    return filtered.map((m) => {
      const state = this.computeState(m)
      return {
        deviceId: m.config.deviceId,
        deviceType: m.config.deviceType,
        state,
        endpoint: m.config.endpoint,
        lastSampleAt: m.lastSampleAt || null,
        calibrationAt: m.config.calibrationAt ?? null,
        alarmLow: m.config.alarmLow ?? null,
        alarmHigh: m.config.alarmHigh ?? null,
        pendingAlarmCount: m.pendingAlarmCount
      }
    })
  }

  private computeState(m: ManagedDevice): 'disconnected' | 'connecting' | 'connected' | 'error' | 'offline' {
    if (m.driver.isConnected()) {
      if (m.lastSampleAt && Date.now() - m.lastSampleAt > 30_000) return 'offline'
      return 'connected'
    }
    return 'disconnected'
  }

  telemetry(deviceId: string, sinceMs: number = 0): TelemetrySample[] {
    const svc = this.getService()
    if (!svc) return []
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT device_id, device_type, metric, value, timestamp, unit FROM device_records WHERE device_id = ? AND metric NOT LIKE 'alarm.%' AND timestamp >= ? ORDER BY timestamp ASC LIMIT 1000`,
      [deviceId, sinceMs]
    )
    return rows.map((r) => ({
      deviceId: String(r['device_id']),
      deviceType: String(r['device_type']) as DeviceKind,
      metric: String(r['metric']),
      value: Number(r['value']),
      unit: r['unit'] == null ? '' : String(r['unit']),
      timestamp: Number(r['timestamp']),
      quality: 'good'
    }))
  }

  alarms(deviceId?: string): AlarmEvent[] {
    return this.getOrInit().alarm.list(deviceId)
  }

  async command(config: DeviceConfig, cmd: {
    kind: 'set-setpoint' | 'start' | 'stop' | 'calibrate' | 'reset-alarm'
    metric?: string; value?: number; reason?: string; operator?: string
  }): Promise<CommandAck> {
    const managed = this.devices.get(config.deviceId)
    if (!managed) {
      return { commandId: `cmd-${Date.now()}`, status: 'rejected', message: '设备未注册', timestamp: Date.now() }
    }
    return this.getOrInit().cmdPipeline.execute(
      { ...cmd, deviceId: config.deviceId, timestamp: Date.now() } as never,
      managed.driver,
      managed.config
    )
  }

  subscribe(listener: DeviceEventListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  shutdown(): void {
    for (const m of this.devices.values()) {
      m.unsubscribe()
      void m.driver.disconnect()
    }
    this.devices.clear()
    if (this._pipeline) this._pipeline.stop()
    this.listeners.clear()
  }

  private handleSample(sample: TelemetrySample, config: DeviceConfig): void {
    const managed = this.devices.get(config.deviceId)
    if (managed) managed.lastSampleAt = sample.timestamp
    const { pipeline, alarm } = this.getOrInit()
    pipeline.enqueue(sample)
    const a = alarm.check(sample, config)
    if (a) {
      if (managed) managed.pendingAlarmCount += 1
      this.emit({ type: 'alarm', payload: a })
    }
    this.emit({ type: 'telemetry', payload: sample })
  }

  private emit(event: DeviceEvent): void {
    for (const l of this.listeners) l(event)
  }
}

let serviceInstance: DeviceService | null = null

export function bootstrapDeviceService(getService: () => DatabaseService | null): DeviceService {
  if (serviceInstance) return serviceInstance
  serviceInstance = new DeviceServiceImpl(getService)
  return serviceInstance
}

export function getDeviceService(): DeviceService | null {
  return serviceInstance
}

export function resetDeviceService(): void {
  if (serviceInstance) serviceInstance.shutdown()
  serviceInstance = null
}
