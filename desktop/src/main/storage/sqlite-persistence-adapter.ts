// SQLitePersistenceAdapter — Phase 8-M1-B
// LocalPersistenceAdapter 的 SQLite 实现版.
// 接口与 LocalPersistenceAdapter 完全一致 (save / load / remove) + namespace 隔离,
// 业务 store 无感知切换.
//
// 通过 APP_STORAGE_DRIVER 环境变量控制:
//   - 'json' (开发默认): 用 LocalPersistenceAdapter (JSON per namespace)
//   - 'sqlite' (生产默认): 用 SQLitePersistenceAdapter (单表 per namespace)

import type { SQLiteDatabase } from '../database'

export interface PersistenceAdapter {
  save(namespace: string, key: string, value: unknown): Promise<void>
  load<T = unknown>(namespace: string, key: string): T | undefined
  remove(namespace: string, key: string): Promise<void>
}

interface PersistenceRow {
  key: string
  value: string
  updated_at: number
}

const SCHEMA = `
CREATE TABLE IF NOT EXISTS persistence (
  namespace TEXT NOT NULL,
  key TEXT NOT NULL,
  value TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  PRIMARY KEY (namespace, key)
);
CREATE INDEX IF NOT EXISTS idx_persistence_ns ON persistence (namespace);`

class SQLitePersistenceAdapterImpl implements PersistenceAdapter {
  constructor(private readonly db: SQLiteDatabase) {}

  init(): void {
    this.db.execute(SCHEMA)
  }

  async save(namespace: string, key: string, value: unknown): Promise<void> {
    const serialized = JSON.stringify(value)
    this.db.execute(
      `INSERT INTO persistence (namespace, key, value, updated_at)
       VALUES (?, ?, ?, ?)
       ON CONFLICT(namespace, key) DO UPDATE SET
         value = excludedCLUDed.value,
         updated_at = excludedCLUDed.updated_at`,
      [namespace, key, serialized, Date.now()]
    )
  }

  load<T = unknown>(namespace: string, key: string): T | undefined {
    const row = this.db.queryOne<PersistenceRow>(
      'SELECT key, value, updated_at FROM persistence WHERE namespace = ? AND key = ?', [namespace, key]
    )
    if (!row || !row.value) return undefined
    try {
      return JSON.parse(row.value) as T
    } catch {
      return undefined
    }
  }

  async remove(namespace: string, key: string): Promise<void> {
    this.db.execute('DELETE FROM persistence WHERE namespace = ? AND key = ?', [namespace, key])
  }
}

export function createSQLitePersistenceAdapter(db: SQLiteDatabase): SQLitePersistenceAdapterImpl {
  const adapter = new SQLitePersistenceAdapterImpl(db)
  adapter.init()
  return adapter
}

export function getStorageDriver(): 'json' | 'sqlite' {
  const env = process.env['APP_STORAGE_DRIVER']
  if (env === 'json' || env === 'sqlite') return env
  // 默认: production=sqlite, development=json
  return process.env['NODE_ENV'] === 'production' ? 'sqlite' : 'json'
}

export { SCHEMA as PERSISTENCE_SCHEMA }