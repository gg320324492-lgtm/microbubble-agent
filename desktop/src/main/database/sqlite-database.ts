// SQLiteDatabase — Phase 8-M1-B
// 同步 better-sqlite3 封装. 严禁渲染进程访问.
// 设计要点:
//   - 单一 connection (主进程启动一次, 整个生命周期复用)
//   - 同步 API 性能远高于 async wrapper; IPC 调用方在 transaction 内批量操作
//   - 自动 PRAGMA: WAL + foreign_keys = on + synchronous = normal
//   - graceful shutdown: process.on('exit') 关闭, Electron app.on('will-quit') 关闭

import Database, { type Database as DatabaseType, type Statement } from 'better-sqlite3'
import { existsSync, mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import type { DatabaseConfig } from './database-config'

export type SqlParam = string | number | bigint | Buffer | null | undefined
export type SqlParams = unknown[]

export interface PreparedStatement {
  run(params?: SqlParams): { changes: number; lastInsertRowid: number | bigint }
  get(params?: SqlParams): unknown
  all(params?: SqlParams): unknown[]
}

export interface TransactionOptions {
  /** 失败时回滚 (默认 true) */
  rollbackOnError?: boolean
}

export interface SQLiteDatabase {
  open(): void
  close(): void
  isOpen(): boolean
  execute(sql: string, params?: SqlParams): { changes: number; lastInsertRowid: number | bigint }
  query<T = unknown>(sql: string, params?: SqlParams): T[]
  queryOne<T = unknown>(sql: string, params?: SqlParams): T | undefined
  prepare(sql: string): PreparedStatement
  transaction<T>(fn: () => T, opts?: TransactionOptions): T
  raw(): DatabaseType
}

class SQLiteDatabaseImpl implements SQLiteDatabase {
  private db: DatabaseType | null = null
  private readonly config: DatabaseConfig

  constructor(config: DatabaseConfig) {
    this.config = config
  }

  open(): void {
    if (this.db) return
    const dir = dirname(this.config.path)
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true })
    this.db = new Database(this.config.path)
    // PRAGMA 安全 + 性能优化
    this.db.pragma('journal_mode = WAL')
    this.db.pragma('foreign_keys = ON')
    this.db.pragma('synchronous = NORMAL')
    this.db.pragma('busy_timeout = 5000')
  }

  close(): void {
    if (!this.db) return
    try {
      this.db.close()
    } finally {
      this.db = null
    }
  }

  isOpen(): boolean {
    return this.db !== null
  }

  private ensure(): DatabaseType {
    if (!this.db) throw new Error('SQLiteDatabase not opened; call open() first')
    return this.db
  }

  execute(sql: string, params?: SqlParams): { changes: number; lastInsertRowid: number | bigint } {
    const stmt = this.ensure().prepare(sql)
    try {
      const result = stmt.run(...(params ?? []))
      return { changes: result.changes, lastInsertRowid: result.lastInsertRowid }
    } finally {
      // better-sqlite3 自动回收; finalize 是可选 API
    }
  }

  query<T = unknown>(sql: string, params?: SqlParams): T[] {
    const stmt = this.ensure().prepare(sql)
    try {
      return stmt.all(...(params ?? [])) as T[]
    } finally {
      // auto-finalize
    }
  }

  queryOne<T = unknown>(sql: string, params?: SqlParams): T | undefined {
    const stmt = this.ensure().prepare(sql)
    try {
      const result = stmt.get(...(params ?? []))
      return result as T | undefined
    } finally {
      // auto-finalize
    }
  }

  prepare(sql: string): PreparedStatement {
    const db = this.ensure()
    const stmt = db.prepare(sql)
    return {
      run(params?: SqlParams) {
        return stmt.run(...(params ?? []))
      },
      get(params?: SqlParams) {
        return stmt.get(...(params ?? []))
      },
      all(params?: SqlParams) {
        return stmt.all(...(params ?? []))
      }
    }
  }

  transaction<T>(fn: () => T, opts?: TransactionOptions): T {
    const db = this.ensure()
    const rollback = opts?.rollbackOnError ?? true
    const wrapped = rollback ? db.transaction(fn) : db.transaction(fn).immediate
    return wrapped()
  }

  raw(): DatabaseType {
    return this.ensure()
  }
}

export function createSQLiteDatabase(config: DatabaseConfig): SQLiteDatabase {
  return new SQLiteDatabaseImpl(config)
}

export type { Statement }