// MigrationManager — Phase 8-M1-B
// 顺序执行 src/main/database/schema/*.sql, 用 schema_version 表追踪.
// 失败回滚 (better-sqlite3 transaction 自动 ROLLBACK); 任何失败抛错, 启动失败.

import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import type { SQLiteDatabase } from './sqlite-database'

export interface MigrationRecord {
  version: number
  filename: string
  appliedAt: number
  checksum: string
}

export interface MigrationManager {
  initialize(): void
  currentVersion(): number
  appliedMigrations(): MigrationRecord[]
  migrate(): void
  rollback(targetVersion: number): void
  /** 暴露所有 schema 文件清单 (供诊断) */
  availableMigrations(): Array<{ filename: string; sql: string; checksum: string }>
}

const SCHEMA_VERSION_TABLE = `
CREATE TABLE IF NOT EXISTS schema_version (
  version INTEGER PRIMARY KEY,
  filename TEXT NOT NULL,
  applied_at INTEGER NOT NULL,
  checksum TEXT
);`

function listMigrations(schemaDir: string): Array<{ version: number; filename: string; sql: string; checksum: string }> {
  const files = readdirSync(schemaDir)
    .filter((f) => f.endsWith('.sql'))
    .sort((a, b) => a.localeCompare(b, 'en', { numeric: true }))
  return files.map((filename) => {
    const sql = readFileSync(join(schemaDir, filename), 'utf8')
    const versionMatch = filename.match(/^0*(\d+)/)
    const version = versionMatch ? Number.parseInt(versionMatch[1], 10) : 0
    const checksum = simpleChecksum(sql)
    return { version, filename, sql, checksum }
  })
}

/**
 * 拆分 SQL 文件为单条 statement. 跳过空行 + 行注释 (-- 开头).
 * 简易拆分器: 不支持 PL/pgSQL 函数体, 我们的 migrations 都是单条 DDL.
 */
function splitSqlStatements(sql: string): string[] {
  return sql
    .split('\n')
    .map((l) => l.replace(/^\s*--.*$/, '').trimEnd())
    .filter((l) => l.length > 0)
    .join('\n')
    .split(';')
    .map((s) => s.trim())
    .filter((s) => s.length > 0)
}

function simpleChecksum(text: string): string {
  let hash = 0
  for (let i = 0; i < text.length; i++) {
    hash = ((hash << 5) - hash + text.charCodeAt(i)) | 0
  }
  return Math.abs(hash).toString(16).padStart(8, '0')
}

function resolveSchemaDir(): string {
  // ESM 兼容: __dirname / fileURLToPath 双模式
  try {
    const here = fileURLToPath(import.meta.url)
    return join(here, '..', 'schema')
  } catch {
    // CJS 环境 / 测试环境
    return join(__dirname, '..', 'schema')
  }
}

class MigrationManagerImpl implements MigrationManager {
  private readonly db: SQLiteDatabase
  private readonly schemaDir: string

  constructor(db: SQLiteDatabase) {
    this.db = db
    this.schemaDir = resolveSchemaDir()
  }

  initialize(): void {
    if (!this.db.isOpen()) throw new Error('SQLiteDatabase not opened')
    this.db.execute(SCHEMA_VERSION_TABLE)
  }

  currentVersion(): number {
    const rows = this.db.query<{ version: number }>('SELECT MAX(version) AS version FROM schema_version')
    if (!rows[0] || rows[0].version === null || rows[0].version === undefined) return 0
    return Number(rows[0].version) || 0
  }

  appliedMigrations(): MigrationRecord[] {
    return this.db.query<MigrationRecord>(
      'SELECT version, filename AS filename, applied_at AS appliedAt, checksum FROM schema_version ORDER BY version ASC'
    )
  }

  migrate(): void {
    const all = this.availableMigrations()
    const applied = new Map<number, MigrationRecord>()
    for (const m of this.appliedMigrations()) applied.set(m.version, m)
    for (const mig of all) {
      if (applied.has(mig.version)) continue
      this.db.transaction(() => {
        // ALTER TABLE duplicate-column errors are tolerated (idempotent augment)
        for (const stmt of splitSqlStatements(mig.sql)) {
          try {
            this.db.execute(stmt)
          } catch (err) {
            const msg = err instanceof Error ? err.message : String(err)
            // 忽略 ALTER 重复列错误; 其他错误向上抛
            if (stmt.trim().toUpperCase().startsWith('ALTER TABLE') && /duplicate column|already exists/i.test(msg)) {
              continue
            }
            throw err
          }
        }
        this.db.execute(
          'INSERT INTO schema_version (version, filename, applied_at, checksum) VALUES (?, ?, ?, ?)',
          [mig.version, mig.filename, Date.now(), mig.checksum]
        )
      })
    }
  }

  rollback(targetVersion: number): void {
    const applied = this.appliedMigrations()
    const sorted = [...applied].sort((a, b) => b.version - a.version)
    for (const m of sorted) {
      if (m.version <= targetVersion) break
      // Phase 8-M1-B 简化: rollback 不执行反向 SQL, 仅从 schema_version 移除
      // 完整 rollback 需要 schema 携带 down.sql; 当前支持开发阶段使用
      this.db.execute('DELETE FROM schema_version WHERE version = ?', [m.version])
    }
  }

  availableMigrations() {
    return listMigrations(this.schemaDir)
  }
}

export function createMigrationManager(db: SQLiteDatabase): MigrationManager {
  return new MigrationManagerImpl(db)
}

export { listMigrations, simpleChecksum }