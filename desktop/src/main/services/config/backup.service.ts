// Backup Service — Phase 8-M1-G
// SQLite 在线备份 (better-sqlite3 backup API) + 清单 + 恢复 (atomic swap).

import { copyFileSync, existsSync, statSync, unlinkSync, readFileSync, mkdirSync, renameSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { createHash } from 'node:crypto'
import type { DatabaseService } from '../database.service'
import { resolveDatabaseConfig } from '../../database/database-config'

export interface BackupEntry {
  id: string
  filename: string
  sizeBytes: number
  schemaVersion: number
  schemaVersionsJson: string
  applicationVersion: string | null
  commitHash: string | null
  createdAt: number
  createdBy: string | null
  note: string | null
  checksum: string
  verifiedAt: number | null
}

export interface BackupService {
  create(opts?: { createdBy?: string; note?: string }): Promise<BackupEntry>
  list(): BackupEntry[]
  restore(backupId: string): boolean
  delete(backupId: string): boolean
  verify(backupId: string): boolean
}

class BackupServiceImpl implements BackupService {
  constructor(private readonly getService: () => DatabaseService | null) {}

  private backupDir(): string {
    // R6: derive from resolveDatabaseConfig().path so backups live next to
    // the live DB under the same dataDir (was: process.cwd()/.microbubble-data/...).
    const cfg = resolveDatabaseConfig()
    const appDir = join(dirname(cfg.path), '..')
    return join(appDir, 'backups')
  }

  async create(opts: { createdBy?: string; note?: string } = {}): Promise<BackupEntry> {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const dir = this.backupDir()
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
    const ts = Date.now()
    const id = `bk-${ts}-${Math.random().toString(36).slice(2, 8)}`
    const filename = `${id}.db`
    const filepath = join(dir, filename)
    // better-sqlite3 backup API: 返回 Promise, 必须 await 才能拿到完整副本.
    // 旧实现把 Promise 丢掉, statSync 紧跟着读不到文件.
    const raw = svc.db.raw() as unknown as { backup?: (p: string) => Promise<unknown> | void }
    const result = raw.backup?.(filepath)
    if (result && typeof (result as Promise<unknown>).then === 'function') {
      await (result as Promise<unknown>)
    }
    const stat = statSync(filepath)
    const checksum = createHash('sha256').update(readFileSync(filepath)).digest('hex')
    const versionRow = svc.db.queryOne<{ v: number }>('SELECT COALESCE(MAX(version), 0) AS v FROM schema_version')
    const versions = svc.db.query<{ filename: string; version: number; applied_at: number }>(
      'SELECT filename, version, applied_at FROM schema_version ORDER BY version ASC'
    )
    const schemaVersion = Number(versionRow?.v ?? 1)
    const schemaVersionsJson = JSON.stringify(versions)
    svc.db.execute(
      `INSERT INTO backup_manifest (id, filename, size_bytes, schema_version, schema_versions_json, created_at, created_by, note, checksum)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
      [id, filename, stat.size, schemaVersion, schemaVersionsJson, ts, opts.createdBy ?? null, opts.note ?? null, checksum]
    )
    svc.audit.record({ action: 'backup.create', module: 'config', metadata: { id, sizeBytes: stat.size, schemaVersion } })
    return { id, filename, sizeBytes: stat.size, schemaVersion, schemaVersionsJson, applicationVersion: null, commitHash: null, createdAt: ts, createdBy: opts.createdBy ?? null, note: opts.note ?? null, checksum, verifiedAt: null }
  }

  list(): BackupEntry[] {
    const svc = this.getService()
    if (!svc) return []
    return svc.db.query<Record<string, unknown>>('SELECT * FROM backup_manifest ORDER BY created_at DESC').map((r) => this.mapRow(r))
  }

  restore(backupId: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const row = svc.db.queryOne<{ filename: string; checksum: string }>('SELECT filename, checksum FROM backup_manifest WHERE id = ?', [backupId])
    if (!row) return false
    const filepath = join(this.backupDir(), String(row.filename))
    if (!existsSync(filepath)) return false

    // R6 hardening: refuse to restore a tampered backup. Without this check
    // a corrupted file could silently overwrite the live database.
    const expected = String(row.checksum)
    const actual = createHash('sha256').update(readFileSync(filepath)).digest('hex')
    if (actual !== expected) {
      svc.audit.record({
        action: 'backup.restore.tamper',
        module: 'config',
        metadata: { backupId, expected, actual }
      })
      return false
    }

    try {
      const dbRaw = svc.db.raw() as unknown as { close?: () => void }
      try { dbRaw.close?.() } catch { /* noop */ }
      copyFileSync(filepath, filepath + '.restoring')
      const existing = this.findCurrentDb()
      if (existing) {
        try { unlinkSync(existing) } catch { /* noop */ }
      }
      renameSync(filepath + '.restoring', existing ?? filepath)
      svc.audit.record({ action: 'backup.restore', module: 'config', metadata: { backupId } })
      return true
    } catch (err) {
      svc.audit.record({ action: 'backup.restore.error', module: 'config', metadata: { backupId, error: String(err) } })
      return false
    }
  }

  delete(backupId: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const row = svc.db.queryOne<{ filename: string }>('SELECT filename FROM backup_manifest WHERE id = ?', [backupId])
    if (!row) return false
    const filepath = join(this.backupDir(), String(row.filename))
    if (existsSync(filepath)) try { unlinkSync(filepath) } catch { /* noop */ }
    svc.db.execute('DELETE FROM backup_manifest WHERE id = ?', [backupId])
    svc.audit.record({ action: 'backup.delete', module: 'config', metadata: { backupId } })
    return true
  }

  verify(backupId: string): boolean {
    const svc = this.getService()
    if (!svc) return false
    const row = svc.db.queryOne<{ filename: string; checksum: string }>('SELECT filename, checksum FROM backup_manifest WHERE id = ?', [backupId])
    if (!row) return false
    const filepath = join(this.backupDir(), String(row.filename))
    if (!existsSync(filepath)) return false
    const actual = createHash('sha256').update(readFileSync(filepath)).digest('hex')
    const ok = actual === String(row.checksum)
    svc.db.execute('UPDATE backup_manifest SET verified_at = ? WHERE id = ?', [Date.now(), backupId])
    return ok
  }

  private findCurrentDb(): string | null {
    // R6: drive restore() from the same config resolver used by backupDir().
    return resolveDatabaseConfig().path
  }

  private mapRow(r: Record<string, unknown>): BackupEntry {
    return {
      id: String(r['id']),
      filename: String(r['filename']),
      sizeBytes: Number(r['size_bytes']),
      schemaVersion: Number(r['schema_version']),
      schemaVersionsJson: String(r['schema_versions_json']),
      applicationVersion: r['application_version'] == null ? null : String(r['application_version']),
      commitHash: r['commit_hash'] == null ? null : String(r['commit_hash']),
      createdAt: Number(r['created_at']),
      createdBy: r['created_by'] == null ? null : String(r['created_by']),
      note: r['note'] == null ? null : String(r['note']),
      checksum: String(r['checksum']),
      verifiedAt: r['verified_at'] == null ? null : Number(r['verified_at'])
    }
  }
}

export function createBackupService(getService: () => DatabaseService | null): BackupService {
  return new BackupServiceImpl(getService)
}