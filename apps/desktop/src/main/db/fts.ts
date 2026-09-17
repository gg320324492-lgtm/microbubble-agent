// FTS 同步共享 helper（M2-2 起）— knowledge / meetings 共用。
// 索引列存 CJK bigram 切词文本（见 services/knowledge/cjk-bigram.ts 选型说明），
// 本 helper 统一「删旧行 + 插切词新行」的同步动作，表名只接受代码内常量。
import type { SqlDatabase } from './adapters'
import { segmentForIndex } from '../services/knowledge/cjk-bigram'

/** 按行同步一条 FTS 记录：columns 为 { 列名: 原文 }，切词在此完成 */
export function ftsSyncRow(db: SqlDatabase, table: string, rowid: number, columns: Record<string, string>): void {
  db.prepare(`DELETE FROM ${table} WHERE rowid = ?`).run(rowid)
  const names = Object.keys(columns)
  if (names.length === 0) return
  const placeholders = names.map(() => '?').join(', ')
  db.prepare(`INSERT INTO ${table} (rowid, ${names.join(', ')}) VALUES (?, ${placeholders})`).run(
    rowid,
    ...names.map((n) => segmentForIndex(columns[n] ?? ''))
  )
}

/** 删除一条 FTS 记录 */
export function ftsDeleteRow(db: SqlDatabase, table: string, rowid: number): void {
  db.prepare(`DELETE FROM ${table} WHERE rowid = ?`).run(rowid)
}
