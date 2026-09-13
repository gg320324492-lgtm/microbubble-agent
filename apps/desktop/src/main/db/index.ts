// 主进程数据库入口 — better-sqlite3 打开 + WAL + 迁移。
// 注意: 测试不 import 本文件（Electron ABI），测试走 adapters.openNodeSqlite。
import Database from 'better-sqlite3'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import type { SqlDatabase } from './adapters'
import { runMigrations } from './migrations'

export function openDatabase(file: string): SqlDatabase {
  mkdirSync(dirname(file), { recursive: true })
  const db = new Database(file)
  db.pragma('journal_mode = WAL')
  db.pragma('foreign_keys = ON')
  const wrapped: SqlDatabase = {
    exec: (sql) => db.exec(sql),
    prepare: (sql) => {
      const st = db.prepare(sql)
      return {
        run: (...p) => st.run(...p),
        get: (...p) => st.get(...p),
        all: (...p) => st.all(...p)
      }
    },
    close: () => db.close()
  }
  runMigrations(wrapped)
  return wrapped
}
