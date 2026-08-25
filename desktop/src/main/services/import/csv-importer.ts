// CSV Importer — Phase 9-A
// RFC 4180 CSV 解析 (无依赖). 支持引号转义 / 转义引号 / 多行字段.

import { createHash } from 'node:crypto'
import { readFileSync, statSync } from 'node:fs'
import type { ImportFormat, RawImportTable } from './types'

const MAX_ROWS = 100_000
const MAX_FILE_BYTES = 50 * 1024 * 1024

function sha256(buf: Buffer): string {
  return createHash('sha256').update(buf).digest('hex')
}

/** 解析单条 CSV 记录 (RFC 4180). */
function parseCsvLine(line: string): string[] {
  const fields: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]!
    if (inQuotes) {
      if (c === '"') {
        if (line[i + 1] === '"') { current += '"'; i++ }
        else { inQuotes = false }
      } else { current += c }
    } else {
      if (c === ',') { fields.push(current); current = '' }
      else if (c === '"' && current === '') { inQuotes = true }
      else { current += c }
    }
  }
  fields.push(current)
  return fields
}

export async function parseCsv(filePath: string): Promise<RawImportTable> {
  const stat = statSync(filePath)
  if (stat.size > MAX_FILE_BYTES) throw new Error(`文件超过 50MB 限制 (${stat.size} 字节)`)
  const buf = readFileSync(filePath)
  const text = buf.toString('utf8')
  const sourceHash = sha256(buf)
  const sourceName = filePath.replace(/^.*[\\/]/, '')
  const start = Date.now()

  // 拆分行 (支持 \r\n / \n / 多行引号)
  const lines: string[] = []
  let cur = ''
  let inQ = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]!
    if (c === '"') inQ = !inQ
    if ((c === '\n' || c === '\r') && !inQ) {
      if (cur.length > 0) { lines.push(cur); cur = '' }
      if (c === '\r' && text[i + 1] === '\n') i++
    } else {
      cur += c
    }
  }
  if (cur.length > 0) lines.push(cur)
  if (lines.length === 0) throw new Error('CSV 文件为空')

  const headerLine = lines[0]!
  const columns = parseCsvLine(headerLine).map((c) => c.trim())
  const rows: Array<Record<string, string>> = []
  const limit = Math.min(lines.length - 1, MAX_ROWS)
  for (let i = 1; i <= limit; i++) {
    const values = parseCsvLine(lines[i]!)
    const row: Record<string, string> = {}
    for (let c = 0; c < columns.length; c++) row[columns[c]!] = (values[c] ?? '').trim()
    rows.push(row)
  }
  return {
    sourcePath: filePath, sourceHash, sourceName, sourceSize: stat.size, format: 'csv' as ImportFormat,
    columns, rows, parseMs: Date.now() - start
  }
}
