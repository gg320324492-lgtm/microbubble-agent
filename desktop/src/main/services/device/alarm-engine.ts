// Alarm Engine — Phase 8-M1-F
// 阈值检查 (low / high) + 告警去重 (deviceId+metric+hour bucket).

import type { DatabaseService } from '../database.service'
import type { AlarmEvent, DeviceConfig, SampleQuality, TelemetrySample } from './device-types'

export interface AlarmEngine {
  check(sample: TelemetrySample, config: DeviceConfig): AlarmEvent | null
  list(deviceId?: string): AlarmEvent[]
  acknowledge(alarmId: number, operator: string, reason: string): boolean
  pending(deviceId?: string): number
}

class AlarmEngineImpl implements AlarmEngine {
  constructor(private readonly getService: () => DatabaseService | null) {}

  check(sample: TelemetrySample, config: DeviceConfig): AlarmEvent | null {
    if (sample.quality === 'bad') return null
    let level: 'low' | 'high' | null = null
    let threshold = 0
    if (config.alarmLow !== undefined && config.alarmLow !== null && sample.value < config.alarmLow) {
      level = 'low'; threshold = config.alarmLow
    } else if (config.alarmHigh !== undefined && config.alarmHigh !== null && sample.value > config.alarmHigh) {
      level = 'high'; threshold = config.alarmHigh
    }
    if (!level) return null
    const hourBucket = Math.floor(sample.timestamp / 3_600_000)
    const existing = this.listWithinHour(sample.deviceId, sample.metric, level, hourBucket)
    if (existing.length > 0) return null
    const id = this.persist(sample, level, threshold, hourBucket)
    return {
      id, deviceId: sample.deviceId, metric: sample.metric, level, value: sample.value,
      threshold, triggeredAt: sample.timestamp, acknowledgedAt: null, acknowledgedBy: null, reason: null
    }
  }

  private persist(sample: TelemetrySample, level: 'low' | 'high', threshold: number, hourBucket: number): number {
    const svc = this.getService()
    if (!svc) return -1
    const result = svc.db.execute(
      `INSERT INTO device_records (device_id, device_type, metric, value, timestamp, unit) VALUES (?, ?, ?, ?, ?, ?)`,
      [sample.deviceId, sample.deviceType, `alarm.${level}.bucket`, threshold, sample.timestamp, '']
    )
    svc.audit.record({
      action: 'device.alarm',
      module: 'device',
      metadata: { deviceId: sample.deviceId, metric: sample.metric, level, hourBucket, alarmRowId: Number(result.lastInsertRowid) }
    })
    return Number(result.lastInsertRowid)
  }

  private listWithinHour(deviceId: string, _metric: string, level: 'low' | 'high', hourBucket: number): Array<{ id: number }> {
    const svc = this.getService()
    if (!svc) return []
    return svc.db.query<{ id: number }>(
      `SELECT id FROM device_records WHERE device_id = ? AND metric = ? AND timestamp >= ? AND timestamp < ? LIMIT 1`,
      [deviceId, `alarm.${level}.bucket`, hourBucket * 3_600_000, (hourBucket + 1) * 3_600_000]
    )
  }

  list(deviceId?: string): AlarmEvent[] {
    const svc = this.getService()
    if (!svc) return []
    const where = deviceId ? 'WHERE device_id = ?' : ''
    const params = deviceId ? [deviceId] : []
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT id, device_id, metric, value, timestamp FROM device_records ${where} AND metric LIKE 'alarm.%' ORDER BY timestamp DESC LIMIT 100`,
      params
    )
    return rows.map((r) => {
      const metric = String(r['metric'] ?? '')
      const level: 'low' | 'high' | 'offline' = metric.includes('low') ? 'low' : metric.includes('high') ? 'high' : 'offline'
      return {
        id: Number(r['id']),
        deviceId: String(r['device_id']),
        metric: metric.replace(/^alarm\.(low|high|offline)\.bucket$/, '$1'),
        level,
        value: Number(r['value']),
        threshold: Number(r['value']),
        triggeredAt: Number(r['timestamp']),
        acknowledgedAt: null,
        acknowledgedBy: null,
        reason: null
      }
    })
  }

  acknowledge(alarmId: number, operator: string, reason: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    if (!operator || operator.length < 1) throw new Error('acknowledge: operator 必填')
    if (!reason || reason.length < 10) throw new Error('acknowledge: reason 必须 ≥ 10 字符')
    const result = svc.db.execute(
      `DELETE FROM device_records WHERE id = ? AND metric LIKE 'alarm.%'`,
      [alarmId]
    )
    svc.audit.record({
      action: 'device.alarm.ack',
      module: 'device',
      metadata: { alarmId, operator, reason }
    })
    return result.changes > 0
  }

  pending(deviceId?: string): number {
    return this.list(deviceId).filter((a) => a.acknowledgedAt === null).length
  }
}

export function createAlarmEngine(getService: () => DatabaseService | null): AlarmEngine {
  return new AlarmEngineImpl(getService)
}

export type { SampleQuality }
