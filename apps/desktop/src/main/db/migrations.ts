// 数据库迁移链 — 001-002 起步（骨架设计 §2），SQL 内联便于 asar 打包与测试复用
import type { SqlDatabase } from './adapters'

export interface Migration {
  id: number
  name: string
  sql: string
}

export const MIGRATIONS: Migration[] = [
  {
    id: 1,
    name: 'users-and-sessions',
    sql: `
      CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        display_name TEXT,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'researcher',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
      );
      CREATE TABLE IF NOT EXISTS user_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash TEXT NOT NULL,
        issued_at INTEGER NOT NULL,
        expires_at INTEGER NOT NULL,
        last_seen_at INTEGER,
        revoked_at INTEGER
      );
      CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON user_sessions(token_hash);
    `
  },
  {
    id: 2,
    name: 'settings',
    sql: `
      CREATE TABLE IF NOT EXISTS settings (
        user_id TEXT NOT NULL DEFAULT '',
        key TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at INTEGER NOT NULL,
        PRIMARY KEY (user_id, key)
      );
    `
  }
]

/** 幂等迁移 — 每个迁移单事务，失败回滚并抛出 */
export function runMigrations(db: SqlDatabase): void {
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations (id INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at INTEGER NOT NULL)')
  const applied = new Set(
    (db.prepare('SELECT id FROM schema_migrations').all() as { id: number }[]).map((r) => r.id)
  )
  for (const m of MIGRATIONS) {
    if (applied.has(m.id)) continue
    db.exec('BEGIN')
    try {
      db.exec(m.sql)
      db.prepare('INSERT INTO schema_migrations (id, name, applied_at) VALUES (?, ?, ?)').run(m.id, m.name, Date.now())
      db.exec('COMMIT')
    } catch (err) {
      db.exec('ROLLBACK')
      throw err
    }
  }
}
