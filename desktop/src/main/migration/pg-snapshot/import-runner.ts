// Import Runner — Phase 11 Stage 0
// 主入口: 读取 PG 单表 → 调用 transformer → 分批写入 desktop SQLite.
// 维护 pg_snapshot_meta + pg_snapshot_table_state 进度跟踪.

import type { DatabaseService } from '../../services/database.service'
import { DEFAULT_PG_CONTAINER, DEFAULT_PG_DATABASE, PG_BATCH_LIMIT, paginatedSql, pgDescribeTable, pgQuery, type PgConnectorOptions } from './pg-connector'
import { applyTransformers, type TransformerMap } from './transform-pipeline'

export type TransformerFunction = (raw: unknown) => unknown

export interface ImportTaskSpec {
  /** web PG 表名 */
  pgTable: string
  /** desktop SQLite 表名 (e.g. 'desktop_tasks') */
  desktopTable: string
  /** SQL SELECT 基础子句 (不含 LIMIT/OFFSET) */
  selectSql: string
  /** { desktopColumnName: transformer } */
  transformerMap: TransformerMap
}

export interface ImportRunnerOptions {
  /** snapshot_id (UUID). 自动生成如未传. */
  snapshotId?: string
  /** 任务列表 (可空: 仅探测 schema) */
  tasks?: ImportTaskSpec[]
  /** 强制 PG connector 选项 */
  pgOptions?: PgConnectorOptions
  /** 单 batch LIMIT (默认 10000) */
  batchLimit?: number
}

export interface ImportRunnerResult {
  ok: boolean
  snapshotId: string
  tasksTotal: number
  tasksDone: number
  rowsTotal: number
  rowsWritten: number
  errors: string[]
  startedAt: string
  endedAt: string | null
}

/**
 * 执行 snapshot. 返回 ImportRunnerResult.
 * 失败不抛, 写到 pg_snapshot_meta.error_message + ImportRunnerResult.errors.
 */
export async function runSnapshot(
  svc: DatabaseService,
  opts: ImportRunnerOptions = {}
): Promise<ImportRunnerResult> {
  const startedAt = new Date().toISOString()
  const snapshotId = opts.snapshotId ?? `snap-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
  const tasks = opts.tasks ?? []
  const batchLimit = opts.batchLimit ?? PG_BATCH_LIMIT
  const errors: string[] = []
  let rowsTotal = 0
  let rowsWritten = 0
  let tasksDone = 0

  // init meta
  upsertMeta(svc, {
    snapshot_id: snapshotId,
    started_at: startedAt,
    ended_at: null,
    rows_total: 0,
    tables_done: 0,
    tables_total: tasks.length,
    status: 'running',
    error_message: null
  })

  // preflight: container reachable?
  const pre = await pgQuery<{ version: string }>('SHOW server_version', opts.pgOptions)
  if (pre.rows.length === 0) {
    errors.push('PG preflight failed (no server_version)')
    finalizeMeta(svc, snapshotId, startedAt, 'failed', 'PG preflight failed', rowsTotal, tasksDone, tasks.length)
    return { ok: false, snapshotId, tasksTotal: tasks.length, tasksDone, rowsTotal, rowsWritten, errors, startedAt, endedAt: new Date().toISOString() }
  }

  for (const task of tasks) {
    try {
      const tableState = await runOne(svc, task, snapshotId, batchLimit, opts.pgOptions)
      rowsTotal += tableState.rowsRead
      rowsWritten += tableState.rowsWritten
      tasksDone += 1
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      errors.push(`[${task.pgTable}] ${msg}`)
      updateTableState(svc, snapshotId, task.desktopTable, { last_error: msg })
    }
  }

  const endedAt = new Date().toISOString()
  const status: 'completed' | 'failed' = errors.length === 0 ? 'completed' : 'failed'
  finalizeMeta(svc, snapshotId, startedAt, status, errors.length > 0 ? errors.join('; ') : null, rowsTotal, tasksDone, tasks.length)

  return {
    ok: errors.length === 0,
    snapshotId,
    tasksTotal: tasks.length,
    tasksDone,
    rowsTotal,
    rowsWritten,
    errors,
    startedAt,
    endedAt
  }
}

interface TableRunState {
  rowsRead: number
  rowsWritten: number
  rowsSkipped: number
}

async function runOne(
  svc: DatabaseService,
  task: ImportTaskSpec,
  snapshotId: string,
  batchLimit: number,
  pgOptions: PgConnectorOptions | undefined
): Promise<TableRunState> {
  // init table state row
  upsertTableState(svc, { snapshot_id: snapshotId, table_name: task.desktopTable, rows_read: 0, rows_written: 0, rows_skipped: 0, last_error: null })

  // describe table for safety (TODO cross-check vs transformerMap keys)
  void pgDescribeTable(task.pgTable, pgOptions)

  let offset = 0
  let rowsRead = 0
  let rowsWritten = 0
  let rowsSkipped = 0
  while (true) {
    const sql = paginatedSql(task.selectSql, batchLimit, offset)
    const result = await pgQuery<Record<string, unknown>>(sql, pgOptions)
    if (result.rows.length === 0) break
    rowsRead += result.rows.length
    for (const row of result.rows) {
      try {
        const transformed = applyTransformers(row, task.transformerMap)
        const insertPayload: Record<string, unknown> = { ...transformed, web_id: (row['id'] as number | null | undefined) ?? null }
        const insertCols = Object.keys(insertPayload)
        const placeholders = insertCols.map(() => '?').join(', ')
        const values = insertCols.map((k) => insertPayload[k] ?? null)
        svc.db.execute(
          `INSERT OR REPLACE INTO ${task.desktopTable} (${insertCols.join(', ')}) VALUES (${placeholders})`,
          values
        )
        rowsWritten += 1
      } catch (e) {
        rowsSkipped += 1
      }
    }
    offset += batchLimit
    if (result.rows.length < batchLimit) break
  }

  updateTableState(svc, snapshotId, task.desktopTable, { rows_read: rowsRead, rows_written: rowsWritten, rows_skipped: rowsSkipped })
  return { rowsRead, rowsWritten, rowsSkipped }
}

function upsertMeta(svc: DatabaseService, row: Record<string, unknown>): void {
  const cols = Object.keys(row)
  const placeholders = cols.map(() => '?').join(', ')
  const values = cols.map((k) => row[k] ?? null)
  const updates = cols.filter((k) => k !== 'snapshot_id').map((k) => `${k} = excluded.` + k).join(', ')
  svc.db.execute(
    `INSERT INTO pg_snapshot_meta (${cols.join(', ')}) VALUES (${placeholders})
     ON CONFLICT(snapshot_id) DO UPDATE SET ${updates}`,
    values
  )
}

function finalizeMeta(
  svc: DatabaseService,
  snapshotId: string,
  startedAt: string,
  status: 'completed' | 'failed',
  errorMessage: string | null,
  rowsTotal: number,
  tablesDone: number,
  tablesTotal: number
): void {
  const endedAt = new Date().toISOString()
  svc.db.execute(
    `UPDATE pg_snapshot_meta
     SET ended_at = ?, status = ?, error_message = ?, rows_total = ?, tables_done = ?, tables_total = ?
     WHERE snapshot_id = ? AND started_at = ?`,
    [endedAt, status, errorMessage, rowsTotal, tablesDone, tablesTotal, snapshotId, startedAt]
  )
}

function upsertTableState(svc: DatabaseService, row: Record<string, unknown>): void {
  const cols = Object.keys(row)
  const placeholders = cols.map(() => '?').join(', ')
  const values = cols.map((k) => row[k] ?? null)
  const updates = cols.filter((k) => k !== 'snapshot_id' && k !== 'table_name').map((k) => `${k} = excluded.` + k).join(', ')
  svc.db.execute(
    `INSERT INTO pg_snapshot_table_state (${cols.join(', ')}) VALUES (${placeholders})
     ON CONFLICT(snapshot_id, table_name) DO UPDATE SET ${updates}`,
    values
  )
}

function updateTableState(
  svc: DatabaseService,
  snapshotId: string,
  tableName: string,
  patch: { rows_read?: number; rows_written?: number; rows_skipped?: number; last_error?: string | null }
): void {
  const sets: string[] = []
  const values: unknown[] = []
  if (patch.rows_read !== undefined) { sets.push('rows_read = ?'); values.push(patch.rows_read) }
  if (patch.rows_written !== undefined) { sets.push('rows_written = ?'); values.push(patch.rows_written) }
  if (patch.rows_skipped !== undefined) { sets.push('rows_skipped = ?'); values.push(patch.rows_skipped) }
  if (patch.last_error !== undefined) { sets.push('last_error = ?'); values.push(patch.last_error) }
  if (sets.length === 0) return
  svc.db.execute(
    `UPDATE pg_snapshot_table_state SET ${sets.join(', ')} WHERE snapshot_id = ? AND table_name = ?`,
    [...values, snapshotId, tableName]
  )
}

/** 列出最近 N 个 snapshot (UI 显示). */
export function listSnapshots(svc: DatabaseService, limit = 20): Array<{
  snapshot_id: string
  started_at: string
  ended_at: string | null
  rows_total: number
  tables_done: number
  tables_total: number
  status: string
  error_message: string | null
}> {
  return svc.db.query<{
    snapshot_id: string
    started_at: string
    ended_at: string | null
    rows_total: number
    tables_done: number
    tables_total: number
    status: string
    error_message: string | null
  }>(
    'SELECT * FROM pg_snapshot_meta ORDER BY started_at DESC LIMIT ?',
    [limit]
  )
}

export { DEFAULT_PG_CONTAINER, DEFAULT_PG_DATABASE, PG_BATCH_LIMIT }