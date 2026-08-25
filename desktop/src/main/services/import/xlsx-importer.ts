// XLSX Importer — Phase 9-A
// 解析 .xlsx / .xlsm 文件 (依赖 'xlsx' npm 包, 缺失时给出明确错误)

import { createHash } from 'node:crypto'
import { readFileSync, statSync } from 'node:fs'
import type { ImportFormat, RawImportTable } from './types'

const MAX_ROWS = 100_000
const MAX_FILE_BYTES = 50 * 1024 * 1024

function sha256(buf: Buffer): string {
  return createHash('sha256').update(buf).digest('hex')
}

interface XLSXModule {
  read(data: ArrayBuffer, opts?: { type?: string }): { SheetNames: string[]; Sheets: Record<string, { [addr: string]: unknown }> }
  utils?: { sheet_to_json?: (sheet: unknown, opts?: { defval?: string; raw?: boolean }) => Array<Record<string, unknown>> }
}

export async function parseXlsx(filePath: string): Promise<RawImportTable> {
  const stat = statSync(filePath)
  if (stat.size > MAX_FILE_BYTES) throw new Error(`文件超过 50MB 限制 (${stat.size} 字节)`)
  const buf = readFileSync(filePath)
  const sourceHash = sha256(buf)
  const sourceName = filePath.replace(/^.*[\\/]/, '')
  const start = Date.now()

  let xlsx: XLSXModule
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    xlsx = require('xlsx') as XLSXModule
  } catch (err) {
    throw new Error('XLSX 解析需要安装 xlsx 包 (npm i -D xlsx)')
  }
  // xlsx 暴露 buffer 入口; 用 Uint8Array 包裹
  const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength) as ArrayBuffer
  const wb = xlsx.read(ab, { type: 'array' })
  const sheetName = wb.SheetNames[0]
  if (!sheetName) throw new Error('XLSX 文件无工作表')
  const sheet = wb.Sheets[sheetName]
  if (!sheet) throw new Error(`XLSX 工作表 '${sheetName}' 为空`)
  const toJson = xlsx.utils?.sheet_to_json
  if (typeof toJson !== 'function') throw new Error('xlsx.utils.sheet_to_json 不可用')
  const rawRows = toJson(sheet, { defval: '', raw: false }) as Array<Record<string, unknown>>
  if (rawRows.length === 0) throw new Error('XLSX 工作表无数据')
  const columnsSet = new Set<string>()
  for (const r of rawRows) for (const k of Object.keys(r)) columnsSet.add(String(k))
  const columns = Array.from(columnsSet)
  const rows: Array<Record<string, string>> = []
  const limit = Math.min(rawRows.length, MAX_ROWS)
  for (let i = 0; i < limit; i++) {
    const src = rawRows[i]!
    const row: Record<string, string> = {}
    for (const c of columns) row[c] = src[c] == null ? '' : String(src[c])
    rows.push(row)
  }
  return { sourcePath: filePath, sourceHash, sourceName, sourceSize: stat.size, format: 'xlsx' as ImportFormat, columns, rows, parseMs: Date.now() - start }
}
