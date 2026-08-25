// DeviceRepository — Phase 8-M1-B
// 数字孪生 / SCADA 设备记录 (高频, 单设备 86400 条/天)

import type { SQLiteDatabase, SqlParams } from '../database'

export interface DeviceRecord {
  id?: number
  deviceId: string
  deviceType: string | null
  metric: string
  value: number
  timestamp: number
}

export interface DeviceRepository {
  insert(rec: Omit<DeviceRecord, 'id'>): DeviceRecord
  insertMany(records: Array<Omit<DeviceRecord, 'id'>>): number
  findById(id: number): DeviceRecord | undefined
  list(deviceId?: string, limit?: number): DeviceRecord[]
  update(id: number, patch: Partial<Omit<DeviceRecord, 'id'>>): DeviceRecord | undefined
  delete(id: number): boolean
  deleteOlderThan(timestamp: number): number
  count(deviceId?: string): number
}

class DeviceRepositoryImpl implements DeviceRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  insert(rec: Omit<DeviceRecord, 'id'>): DeviceRecord {
    const result = this.db.execute(
      `INSERT INTO device_records (device_id, device_type, metric, value, timestamp)
       VALUES (?, ?, ?, ?, ?)`,
      [rec.deviceId, rec.deviceType, rec.metric, rec.value, rec.timestamp]
    )
    return { ...rec, id: Number(result.lastInsertRowid) }
  }

  insertMany(records: Array<Omit<DeviceRecord, 'id'>>): number {
    if (records.length === 0) return 0
    let count = 0
    this.db.transaction(() => {
      const stmt = this.db.prepare('INSERT INTO device_records (device_id, device_type, metric, value, timestamp) VALUES (?, ?, ?, ?, ?)')
      for (const r of records) {
        stmt.run([r.deviceId, r.deviceType, r.metric, r.value, r.timestamp])
        count += 1
      }
    })
    return count
  }

  findById(id: number): DeviceRecord | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM device_records WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  list(deviceId?: string, limit: number = 1000): DeviceRecord[] {
    let sql = 'SELECT * FROM device_records'
    const params: SqlParams = []
    if (deviceId) {
      sql += ' WHERE device_id = ?'
      params.push(deviceId)
    }
    sql += ' ORDER BY timestamp DESC LIMIT ?'
    params.push(limit)
    return this.db.query<Record<string, unknown>>(sql, params).map((r) => this.mapRow(r))
  }

  update(id: number, patch: Partial<Omit<DeviceRecord, 'id'>>): DeviceRecord | undefined {
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.deviceId !== undefined) { fields.push('device_id = ?'); values.push(patch.deviceId) }
    if (patch.deviceType !== undefined) { fields.push('device_type = ?'); values.push(patch.deviceType) }
    if (patch.metric !== undefined) { fields.push('metric = ?'); values.push(patch.metric) }
    if (patch.value !== undefined) { fields.push('value = ?'); values.push(patch.value) }
    if (patch.timestamp !== undefined) { fields.push('timestamp = ?'); values.push(patch.timestamp) }
    if (fields.length === 0) return this.findById(id)
    values.push(id)
    this.db.execute(`UPDATE device_records SET ${fields.join(', ')} WHERE id = ?`, values)
    return this.findById(id)
  }

  delete(id: number): boolean {
    const result = this.db.execute('DELETE FROM device_records WHERE id = ?', [id])
    return result.changes > 0
  }

  deleteOlderThan(timestamp: number): number {
    const result = this.db.execute('DELETE FROM device_records WHERE timestamp < ?', [timestamp])
    return result.changes
  }

  count(deviceId?: string): number {
    if (deviceId) {
      const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM device_records WHERE device_id = ?', [deviceId])
      return Number(row?.c ?? 0)
    }
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM device_records')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): DeviceRecord {
    return {
      id: row['id'] == null ? undefined : Number(row['id']),
      deviceId: String(row['device_id']),
      deviceType: row['device_type'] == null ? null : String(row['device_type']),
      metric: String(row['metric']),
      value: Number(row['value']),
      timestamp: Number(row['timestamp'])
    }
  }
}

export function createDeviceRepository(db: SQLiteDatabase): DeviceRepository {
  return new DeviceRepositoryImpl(db)
}