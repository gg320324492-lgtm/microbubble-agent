// Exporter — Phase 8-M1-G
// CSV / JSON 导出. Excel 留 Phase 8-M1-G+ (需 xlsx 包).

import { writeFileSync } from 'node:fs'
import type { DatabaseService } from '../database.service'

export type ExportFormat = 'csv' | 'json'

export interface ExportRequest {
  format: ExportFormat
  table: string
  where?: string
  limit?: number
  outputPath: string
}

export interface ExportResult {
  rowCount: number
  sizeBytes: number
  outputPath: string
}

export interface Exporter {
  export(req: ExportRequest): ExportResult
}

class ExporterImpl implements Exporter {
  constructor(private readonly getService: () => DatabaseService | null) {}

  export(req: ExportRequest): ExportResult {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const where = req.where ? `WHERE ${req.where}` : ''
    const limit = req.limit ?? 100_000
    const sql = `SELECT * FROM ${req.table} ${where} LIMIT ?`
    const rows = svc.db.query<Record<string, unknown>>(sql, [limit])
    if (req.format === 'csv') {
      const content = this.toCsv(rows)
      writeFileSync(req.outputPath, content, 'utf8')
      return { rowCount: rows.length, sizeBytes: Buffer.byteLength(content, 'utf8'), outputPath: req.outputPath }
    }
    if (req.format === 'json') {
      const content = JSON.stringify(rows, null, 2)
      writeFileSync(req.outputPath, content, 'utf8')
      return { rowCount: rows.length, sizeBytes: Buffer.byteLength(content, 'utf8'), outputPath: req.outputPath }
    }
    throw new Error(`不支持的导出格式 '${req.format}'`)
  }

  private toCsv(rows: Record<string, unknown>[]): string {
    if (rows.length === 0) return ''
    const first = rows[0]!
    const headers = Object.keys(first)
    const escape = (v: unknown): string => {
      if (v === null || v === undefined) return ''
      const s = String(v)
      if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`
      return s
    }
    const lines = [headers.join(',')]
    for (const r of rows) lines.push(headers.map((h) => escape(r[h])).join(','))
    return lines.join('\n')
  }
}

export function createExporter(getService: () => DatabaseService | null): Exporter {
  return new ExporterImpl(getService)
}