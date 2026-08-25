// Telemetry Pipeline — Phase 8-M1-F
// 批量写入 device_records: 1 秒窗口 / 100 条样本 flush, 用 better-sqlite3 transaction.

import type { SQLiteDatabase } from '../../database'
import type { TelemetrySample } from './device-types'

const FLUSH_INTERVAL_MS = 1000
const FLUSH_BATCH_SIZE = 100
const MAX_BACKLOG = 10_000

export interface TelemetryPipeline {
  enqueue(sample: TelemetrySample): void
  flush(): number
  pending(): number
  stop(): void
}

class TelemetryPipelineImpl implements TelemetryPipeline {
  private buffer: TelemetrySample[] = []
  private timer: ReturnType<typeof setInterval> | null = null
  private dropped = 0

  constructor(private readonly db: SQLiteDatabase) {
    this.timer = setInterval(() => this.flush(), FLUSH_INTERVAL_MS)
  }

  enqueue(sample: TelemetrySample): void {
    if (this.buffer.length >= MAX_BACKLOG) {
      this.buffer.shift()
      this.dropped += 1
    } else {
      this.buffer.push(sample)
    }
    if (this.buffer.length >= FLUSH_BATCH_SIZE) this.flush()
  }

  flush(): number {
    if (this.buffer.length === 0) return 0
    const batch = this.buffer.splice(0, FLUSH_BATCH_SIZE)
    this.db.transaction(() => {
      const stmt = this.db.prepare(
        'INSERT INTO device_records (device_id, device_type, metric, value, timestamp, unit) VALUES (?, ?, ?, ?, ?, ?)'
      )
      for (const s of batch) {
        stmt.run([s.deviceId, s.deviceType, s.metric, s.value, s.timestamp, s.unit])
      }
    })
    return batch.length
  }

  pending(): number { return this.buffer.length }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    this.flush()
  }
}

export function createTelemetryPipeline(db: SQLiteDatabase): TelemetryPipeline {
  return new TelemetryPipelineImpl(db)
}
