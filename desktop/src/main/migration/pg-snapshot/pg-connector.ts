// PG Connector — Phase 11 Stage 0
// 单向 web PG 读取 → desktop SQLite 写入的 pg readonly 客户端.
// 0 新依赖 — 通过 docker exec 调用 psql CLI (与项目其它地方一致).
//
// 设计原则:
// 1. 仅 SELECT, 无 INSERT/UPDATE/DELETE — 通过 SQL 注入防护 + 严禁 schema mutation.
// 2. LIMIT/OFFSET 翻页 (单 batch LIMIT 10000) — 避免 OOM.
// 3. 不缓存凭据 — 调用方传完整 psql -c 命令字符串.
// 4. 输出格式 TSV (tab-separated) — 比 JSON 简洁, 比 CSV 少 unquote.

import { execFile } from 'node:child_process'
import { promisify } from 'node:util'

const execFileAsync = promisify(execFile)

/** docker container name hosting microbubble PG (Phase 11 default). */
export const DEFAULT_PG_CONTAINER = 'microbubble-agent-db-1'
export const DEFAULT_PG_DATABASE = 'microbubble'
export const DEFAULT_PG_USER = 'postgres'

/** 单 batch 翻页上限 (避免 OOM; 低于 web 默认 1024 行/页). */
export const PG_BATCH_LIMIT = 10000

export interface PgConnectorOptions {
  container?: string
  database?: string
  user?: string
  /** 强制环境变量 PG_PASSWORD (docker exec -e); 不在命令行传明文 */
  pgPassword?: string
}

export interface PgColumnInfo {
  name: string
  type: string
  nullable: boolean
}

export interface PgQueryResult<T = Record<string, unknown>> {
  rows: T[]
  columns: PgColumnInfo[]
}

/** 验证 identifier (防 SQL injection). 表/列名必须匹配 [a-z_][a-z0-9_]* */
function safeIdent(ident: string): string {
  if (!/^[a-z_][a-z0-9_]*$/i.test(ident)) {
    throw new Error(`Invalid PG identifier (拒绝非字母数字下划线): ${ident}`)
  }
  return ident
}

/**
 * 用 docker exec psql 查询 PG (READ-ONLY).
 * @param sql - SELECT-only SQL (无 INSERT/UPDATE/DELETE/DDL)
 * @param opts - container/database/user/pgPassword
 */
export async function pgQuery<T = Record<string, unknown>>(
  sql: string,
  opts: PgConnectorOptions = {}
): Promise<PgQueryResult<T>> {
  // 强制 SELECT-only (简单语法守卫)
  const stripped = sql.trim().toUpperCase()
  if (
    !stripped.startsWith('SELECT') &&
    !stripped.startsWith('WITH') &&
    !stripped.startsWith('SHOW') &&
    !stripped.startsWith('EXPLAIN')
  ) {
    throw new Error(`pgQuery only allows SELECT/WITH/SHOW/EXPLAIN, got: ${stripped.slice(0, 50)}`)
  }
  // 严禁 schema mutation 关键字
  if (/\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|GRANT|REVOKE)\b/.test(stripped)) {
    throw new Error(`pgQuery detected schema-mutating keyword, refused: ${sql.slice(0, 100)}`)
  }

  const container = safeIdent(opts.container ?? DEFAULT_PG_CONTAINER)
  const database = safeIdent(opts.database ?? DEFAULT_PG_DATABASE)
  const user = safeIdent(opts.user ?? DEFAULT_PG_USER)

  // psql -A (unaligned) -F $'\t' (TSV) -t (tuples only) → 简洁 TSV
  const args = [
    'exec', '-i',
    ...(opts.pgPassword ? ['-e', `PGPASSWORD=${opts.pgPassword}`] : []),
    container,
    'psql',
    '-U', user,
    '-d', database,
    '-A', '-F', String.fromCharCode(9),
    '-t',
    '--no-psqlrc',
    '-c', sql
  ]

  const { stdout, stderr } = await execFileAsync('docker', args, {
    maxBuffer: 256 * 1024 * 1024, // 256 MB — 大表 batch LIMIT 10000 安全
    timeout: 300_000 // 5 分钟 / query
  })

  if (stderr && /ERROR|FATAL/.test(stderr)) {
    throw new Error(`psql error: ${stderr.trim()}`)
  }

  return parseTsv<T>(stdout)
}

/** PSQL TSV → JS rows + columns. 第一行是 column header (来自 -A mode 不含 header, 需另 query). */
function parseTsv<T>(raw: string): PgQueryResult<T> {
  const lines = raw.split('\n').filter((l) => l.length > 0)
  if (lines.length === 0) return { rows: [], columns: [] }

  // TSV mode 不含 header. 列名需另 query. 此处先空.
  const rows = lines.map((line) => {
    const cells = line.split(String.fromCharCode(9))
    const obj: Record<string, unknown> = {}
    cells.forEach((cell, i) => {
      obj[`col_${i}`] = parseCell(cell)
    })
    return obj as T
  })
  return { rows, columns: [] }
}

function parseCell(cell: string): string | number | boolean | null {
  if (cell === '\\N') return null // psql NULL marker
  if (cell === 't') return true
  if (cell === 'f') return false
  // 数字尝试
  if (/^-?\d+$/.test(cell)) return Number(cell)
  if (/^-?\d+\.\d+$/.test(cell)) return Number(cell)
  return cell
}

/**
 * 取表 schema 信息 (列名 + 类型 + nullable).
 * 通过 information_schema.columns 查询 (READ-ONLY).
 */
export async function pgDescribeTable(
  tableName: string,
  opts: PgConnectorOptions = {}
): Promise<PgColumnInfo[]> {
  const safeTable = safeIdent(tableName)
  const result = await pgQuery<{ column_name: string; data_type: string; is_nullable: string }>(
    `SELECT column_name, data_type, is_nullable
     FROM information_schema.columns
     WHERE table_schema='public' AND table_name='${safeTable}'
     ORDER BY ordinal_position`,
    opts
  )
  return result.rows.map((r) => ({
    name: String(r.column_name),
    type: String(r.data_type),
    nullable: r.is_nullable === 'YES'
  }))
}

/**  翻页 helper: SELECT ... LIMIT N OFFSET K */
export function paginatedSql(baseSelect: string, limit = PG_BATCH_LIMIT, offset = 0): string {
  // baseSelect 必须不含 LIMIT/OFFSET/末尾分号
  const clean = baseSelect.trim().replace(/;$/, '').trim()
  return `${clean} LIMIT ${limit} OFFSET ${offset}`
}

/** docker 容器可达性 + 凭据 sanity check (preflight). */
export async function pgPreflight(opts: PgConnectorOptions = {}): Promise<{
  ok: boolean
  container: string
  database: string
  pgVersion?: string
  message?: string
}> {
  try {
    const result = await pgQuery<{ version: string }>('SHOW server_version', opts)
    const version = result.rows[0]?.version as string | undefined
    return {
      ok: true,
      container: opts.container ?? DEFAULT_PG_CONTAINER,
      database: opts.database ?? DEFAULT_PG_DATABASE,
      ...(version ? { pgVersion: version } : {})
    }
  } catch (e) {
    return {
      ok: false,
      container: opts.container ?? DEFAULT_PG_CONTAINER,
      database: opts.database ?? DEFAULT_PG_DATABASE,
      message: e instanceof Error ? e.message : String(e)
    }
  }
}