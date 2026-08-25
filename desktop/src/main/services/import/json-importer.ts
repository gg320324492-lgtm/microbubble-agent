// JSON Importer — Phase 9-A
// 支持 2 种 JSON 布局: (a) array-of-objects (e.g. [{time: ..., O3: ...}, ...])
//                   (b) columnar (e.g. {time: [...], O3: [...], ...})

import { createHash } from 'node:crypto'
import { readFileSync, statSync } from 'node:fs'
import type { ImportFormat, RawImportTable } from './types'

const MAX_ROWS = 100_000
const MAX_FILE_BYTES = 50 * 1024 * 1024

function sha256(buf: Buffer): string {
  return createHash('sha256').update(buf).digest('hex')
}

export async function parseJson(filePath: string): Promise<RawImportTable> {
  const stat = statSync(filePath)
  if (stat.size > MAX_FILE_BYTES) throw new Error(`文件超过 50MB 限制 (${stat.size} 字节)`)
  const buf = readFileSync(filePath)
  const sourceHash = sha256(buf)
  const sourceName = filePath.replace(/^.*[\\/]/, '')
  const start = Date.now()

  let parsed: unknown
  try { parsed = JSON.parse(buf.toString('utf8')) }
  catch (err) { throw new Error(`JSON 解析失败: ${err instanceof Error ? err.message : String(err)}`) }

  if (Array.isArray(parsed)) {
    // Layout (a): array-of-objects
    const arr = parsed as Array<Record<string, unknown>>
    if (arr.length === 0) throw new Error('JSON 数组为空')
    const columns = Object.keys(arr[0]!)
    const rows = arr.slice(0, MAX_ROWS).map((obj) => {
      const row: Record<string, string> = {}
      for (const c of columns) row[c] = obj[c] == null ? '' : String(obj[c])
      return row
    })
    return { sourcePath: filePath, sourceHash, sourceName, sourceSize: stat.size, format: 'json' as ImportFormat, columns, rows, parseMs: Date.now() - start }
  }
  if (parsed && typeof parsed === 'object') {
    // Layout (b): columnar {col: [...values...]}
    const obj = parsed as Record<string, unknown>
    const columns = Object.keys(obj)
    if (columns.length === 0) throw new Error('JSON 对象为空')
    const lengths = columns.map((c) => Array.isArray(obj[c]) ? (obj[c] as unknown[]).length : 0)
    const maxLen = Math.max(...lengths)
    if (maxLen === 0) throw new Error('JSON 字段无数组数据')
    const rows: Array<Record<string, string>> = []
    const limit = Math.min(maxLen, MAX_ROWS)
    for (let i = 0; i < limit; i++) {
      const row: Record<string, string> = {}
      for (const c of columns) {
        const v = (obj[c] as unknown[])[i]
        row[c] = v == null ? '' : String(v)
      }
      rows.push(row)
    }
    return { sourcePath: filePath, sourceHash, sourceName, sourceSize: stat.size, format: 'json' as ImportFormat, columns, rows, parseMs: Date.now() - start }
  }
  throw new Error('JSON 必须是对象数组或列式对象')
}
