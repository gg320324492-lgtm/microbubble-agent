// Database Audit Logger — Phase 8-M1-B
// 每次 db mutation 都写一条 audit_logs. logger 写入失败 MUST NOT block db 操作.

import type { SQLiteDatabase } from '../database'

export interface AuditEntry {
  action: string
  module: string
  timestamp?: number
  metadata?: Record<string, unknown>
}

export interface DatabaseAuditLogger {
  record(entry: AuditEntry): void
}

class DatabaseAuditLoggerImpl implements DatabaseAuditLogger {
  constructor(
    private readonly db: SQLiteDatabase,
    private readonly fallbackWrite: (entry: AuditEntry) => void = () => undefined
  ) {}

  record(entry: AuditEntry): void {
    const ts = entry.timestamp ?? Date.now()
    const metadata = entry.metadata ? JSON.stringify(entry.metadata) : null
    try {
      this.db.execute(
        `INSERT INTO audit_logs (action, module, timestamp, metadata)
         VALUES (?, ?, ?, ?)`,
        [entry.action, entry.module, ts, metadata]
      )
    } catch (err) {
      // 严禁阻塞业务: 失败时通过 fallback (ScientificLogger) 兜底
      this.fallbackWrite({ ...entry, timestamp: ts, metadata: entry.metadata })
    }
  }
}

export function createDatabaseAuditLogger(db: SQLiteDatabase, fallbackWrite?: (entry: AuditEntry) => void): DatabaseAuditLogger {
  return new DatabaseAuditLoggerImpl(db, fallbackWrite)
}