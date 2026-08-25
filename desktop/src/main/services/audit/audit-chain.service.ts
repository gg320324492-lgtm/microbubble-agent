// Audit Chain Service — Phase 8-M1-G
// 防篡改审计链: 每行 audit_log 存 prev_hash + block_hash + sequence_number
// hash = sha256(prev_hash + sequence + action + module + timestamp + metadata).

import { createHash } from 'node:crypto'
import type { DatabaseService } from '../database.service'

export interface AuditChainEntry {
  id: number
  sequenceNumber: number
  action: string
  module: string | null
  timestamp: number
  metadata: unknown
  prevHash: string | null
  blockHash: string | null
}

export interface AuditChainService {
  verifyChain(): { ok: boolean; firstTamperedId: number | null; checked: number }
  purgeBefore(cutoffMs: number): number
  setRetentionDays(days: number): void
  retentionDays: number
  list(limit?: number): AuditChainEntry[]
}

const GENESIS_HASH = '0'.repeat(64)

function hashEntry(prevHash: string, sequence: number, action: string, module: string, timestamp: number, metadata: string): string {
  return createHash('sha256').update(`${prevHash}|${sequence}|${action}|${module}|${timestamp}|${metadata}`).digest('hex')
}

class AuditChainServiceImpl implements AuditChainService {
  retentionDays = 90

  constructor(private readonly getService: () => DatabaseService | null) {}

  setRetentionDays(days: number): void {
    this.retentionDays = days
  }

  list(limit: number = 200): AuditChainEntry[] {
    const svc = this.getService()
    if (!svc) return []
    return svc.db.query<Record<string, unknown>>(
      `SELECT id, sequence_number, action, module, timestamp, metadata, prev_hash, block_hash FROM audit_logs
       WHERE sequence_number IS NOT NULL ORDER BY sequence_number ASC LIMIT ?`,
      [limit]
    ).map((r) => this.mapRow(r))
  }

  private mapRow(r: Record<string, unknown>): AuditChainEntry {
    return {
      id: Number(r['id']),
      sequenceNumber: Number(r['sequence_number']),
      action: String(r['action'] ?? ''),
      module: r['module'] == null ? null : String(r['module']),
      timestamp: Number(r['timestamp']),
      metadata: r['metadata'] == null ? null : this.parseMetadata(r['metadata']),
      prevHash: r['prev_hash'] == null ? null : String(r['prev_hash']),
      blockHash: r['block_hash'] == null ? null : String(r['block_hash'])
    }
  }

  private parseMetadata(raw: unknown): unknown {
    if (typeof raw !== 'string') return null
    try { return JSON.parse(raw) } catch { return null }
  }

  verifyChain(): { ok: boolean; firstTamperedId: number | null; checked: number } {
    const svc = this.getService()
    if (!svc) return { ok: true, firstTamperedId: null, checked: 0 }
    const rows = svc.db.query<Record<string, unknown>>(
      'SELECT id, sequence_number, action, module, timestamp, metadata, prev_hash, block_hash FROM audit_logs WHERE sequence_number IS NOT NULL ORDER BY sequence_number ASC'
    )
    let prev = GENESIS_HASH
    let checked = 0
    for (const r of rows) {
      const seq = Number(r['sequence_number'])
      const action = String(r['action'] ?? '')
      const module = String(r['module'] ?? '')
      const ts = Number(r['timestamp'])
      const meta = String(r['metadata'] ?? '')
      const expected = hashEntry(prev, seq, action, module, ts, meta)
      const actual = String(r['block_hash'] ?? '')
      if (expected !== actual || String(r['prev_hash'] ?? '') !== prev) {
        return { ok: false, firstTamperedId: Number(r['id']), checked }
      }
      prev = actual
      checked += 1
    }
    return { ok: true, firstTamperedId: null, checked }
  }

  purgeBefore(cutoffMs: number): number {
    const svc = this.getService()
    if (!svc) return 0
    const result = svc.db.execute('DELETE FROM audit_logs WHERE timestamp < ?', [cutoffMs])
    return result.changes
  }
}

export function createAuditChainService(getService: () => DatabaseService | null): AuditChainService {
  return new AuditChainServiceImpl(getService)
}

export { hashEntry, GENESIS_HASH }