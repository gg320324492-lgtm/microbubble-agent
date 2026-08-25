// MeasurementRepository — Phase 8-M1-B
// 含时间序列: insertMany / queryRange / aggregate
// 设计: SCADA 1Hz × 24h = 86400 records; 用 idx_measurements_metric_ts 索引 + WAL 模式保证吞吐.

import type { SQLiteDatabase, SqlParams } from '../database'

export type MetricName = 'O3' | 'DO' | 'ORP' | 'pH' | 'temperature' | 'pressure' | 'flow' | 'power'

export const SUPPORTED_METRICS: ReadonlyArray<MetricName> = ['O3', 'DO', 'ORP', 'pH', 'temperature', 'pressure', 'flow', 'power']

export interface Measurement {
  id?: number
  experimentId: string
  timestamp: number
  metric: MetricName | string
  value: number
  unit: string | null
}

export interface MeasurementAggregate {
  bucketStart: number
  bucketEnd: number
  count: number
  avg: number
  min: number
  max: number
  metric: string
}

export interface MeasurementRepository {
  insert(m: Omit<Measurement, 'id'>): Measurement
  insertMany(records: Array<Omit<Measurement, 'id'>>): number
  findById(id: number): Measurement | undefined
  list(): Measurement[]
  update(id: number, patch: Partial<Omit<Measurement, 'id'>>): Measurement | undefined
  delete(id: number): boolean
  /** 时间区间查询 (默认按 timestamp ASC) */
  queryRange(experimentId: string, startTime: number, endTime: number, metric?: string): Measurement[]
  /** 桶聚合: interval 为毫秒 (如 60000 = 1min, 3600000 = 1h) */
  aggregate(experimentId: string, startTime: number, endTime: number, metric: string, interval: number): MeasurementAggregate[]
  count(): number
}

class MeasurementRepositoryImpl implements MeasurementRepository {
  constructor(private readonly db: SQLiteDatabase) {}

  insert(m: Omit<Measurement, 'id'>): Measurement {
    const result = this.db.execute(
      `INSERT INTO measurements (experiment_id, timestamp, metric, value, unit)
       VALUES (?, ?, ?, ?, ?)`,
      [m.experimentId, m.timestamp, m.metric, m.value, m.unit]
    )
    return { ...m, id: Number(result.lastInsertRowid) }
  }

  insertMany(records: Array<Omit<Measurement, 'id'>>): number {
    if (records.length === 0) return 0
    let count = 0
    this.db.transaction(() => {
      const stmt = this.db.prepare('INSERT INTO measurements (experiment_id, timestamp, metric, value, unit) VALUES (?, ?, ?, ?, ?)')
      for (const m of records) {
        stmt.run([m.experimentId, m.timestamp, m.metric, m.value, m.unit])
        count += 1
      }
    })
    return count
  }

  findById(id: number): Measurement | undefined {
    const row = this.db.queryOne<Record<string, unknown>>('SELECT * FROM measurements WHERE id = ?', [id])
    return row ? this.mapRow(row) : undefined
  }

  list(): Measurement[] {
    return this.db.query<Record<string, unknown>>('SELECT * FROM measurements ORDER BY timestamp DESC LIMIT 1000').map((r) => this.mapRow(r))
  }

  update(id: number, patch: Partial<Omit<Measurement, 'id'>>): Measurement | undefined {
    const fields: string[] = []
    const values: SqlParams = []
    if (patch.experimentId !== undefined) { fields.push('experiment_id = ?'); values.push(patch.experimentId) }
    if (patch.timestamp !== undefined) { fields.push('timestamp = ?'); values.push(patch.timestamp) }
    if (patch.metric !== undefined) { fields.push('metric = ?'); values.push(patch.metric) }
    if (patch.value !== undefined) { fields.push('value = ?'); values.push(patch.value) }
    if (patch.unit !== undefined) { fields.push('unit = ?'); values.push(patch.unit) }
    if (fields.length === 0) return this.findById(id)
    values.push(id)
    this.db.execute(`UPDATE measurements SET ${fields.join(', ')} WHERE id = ?`, values)
    return this.findById(id)
  }

  delete(id: number): boolean {
    const result = this.db.execute('DELETE FROM measurements WHERE id = ?', [id])
    return result.changes > 0
  }

  queryRange(experimentId: string, startTime: number, endTime: number, metric?: string): Measurement[] {
    const params: SqlParams = [experimentId, startTime, endTime]
    let sql = 'SELECT * FROM measurements WHERE experiment_id = ? AND timestamp BETWEEN ? AND ?'
    if (metric) {
      sql += ' AND metric = ?'
      params.push(metric)
    }
    sql += ' ORDER BY timestamp ASC LIMIT 100000'
    return this.db.query<Record<string, unknown>>(sql, params).map((r) => this.mapRow(r))
  }

  aggregate(experimentId: string, startTime: number, endTime: number, metric: string, interval: number): MeasurementAggregate[] {
    // 桶: floor(timestamp / interval) * interval
    const sql = `
      SELECT
        (timestamp / ?) * ? AS bucketStart,
        ((timestamp / ?) * ?) + ? - 1 AS bucketEnd,
        COUNT(*) AS count,
        AVG(value) AS avg,
        MIN(value) AS min,
        MAX(value) AS max,
        metric AS metric
      FROM measurements
      WHERE experiment_id = ? AND metric = ? AND timestamp BETWEEN ? AND ?
      GROUP BY bucketStart
      ORDER BY bucketStart ASC`
    const rows = this.db.query<Record<string, unknown>>(sql, [interval, interval, interval, interval, interval, experimentId, metric, startTime, endTime])
    return rows.map((r) => ({
      bucketStart: Number(r['bucketStart']),
      bucketEnd: Number(r['bucketEnd']),
      count: Number(r['count']),
      avg: Number(r['avg']),
      min: Number(r['min']),
      max: Number(r['max']),
      metric: String(r['metric'])
    }))
  }

  count(): number {
    const row = this.db.queryOne<{ c: number }>('SELECT COUNT(*) AS c FROM measurements')
    return Number(row?.c ?? 0)
  }

  private mapRow(row: Record<string, unknown>): Measurement {
    return {
      id: row['id'] == null ? undefined : Number(row['id']),
      experimentId: String(row['experiment_id']),
      timestamp: Number(row['timestamp']),
      metric: String(row['metric']),
      value: Number(row['value']),
      unit: row['unit'] == null ? null : String(row['unit'])
    }
  }
}

export function createMeasurementRepository(db: SQLiteDatabase): MeasurementRepository {
  return new MeasurementRepositoryImpl(db)
}