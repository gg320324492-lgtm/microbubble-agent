// SQLite 薄适配层 — 主进程用 better-sqlite3，测试用 node:sqlite（ABI 互不干扰）
// 服务层只依赖此接口，方便未来切换 sqlite 实现（如 Electron 升级后换 node:sqlite）
export interface SqlStatement {
  run(...params: unknown[]): { changes: number; lastInsertRowid: number | bigint }
  get(...params: unknown[]): unknown
  all(...params: unknown[]): unknown[]
}

export interface SqlDatabase {
  exec(sql: string): void
  prepare(sql: string): SqlStatement
  close(): void
}

/** 测试专用 — node:sqlite (Node ≥22.5) 实现，API 与 better-sqlite3 子集同形 */
export function openNodeSqlite(file: string): SqlDatabase {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  const { DatabaseSync } = require('node:sqlite') as typeof import('node:sqlite')
  const db = new DatabaseSync(file)
  return {
    exec: (sql) => db.exec(sql),
    prepare: (sql) => {
      const st = db.prepare(sql)
      const cast = (p: unknown[]) => p as never[] // node:sqlite 参数类型窄化（null/bigint/string/number 子集）
      return {
        run: (...p) => st.run(...cast(p)) as { changes: number; lastInsertRowid: number | bigint },
        get: (...p) => st.get(...cast(p)),
        all: (...p) => st.all(...cast(p))
      }
    },
    close: () => db.close()
  }
}
