// Import Engine — Phase 9-A
// 编排器: parse → map → validate → commit (写入 experiments + samples + measurements).

import type { DatabaseService } from '../database.service'
import { parseCsv } from './csv-importer'
import { parseJson } from './json-importer'
import { parseXlsx } from './xlsx-importer'
import { suggestMapping, validateMapping } from './column-mapper'
import { validate } from './validator'
import type {
  ColumnMapping,
  ColumnMappingSuggestion,
  ImportDataset,
  ImportEngine,
  ImportFormat,
  ImportResult,
  RawImportTable,
  ValidationResult
} from './types'

class ImportEngineImpl implements ImportEngine {
  constructor(private readonly getService: () => DatabaseService | null) {}

  async parseFile(filePath: string, format?: ImportFormat): Promise<RawImportTable> {
    const fmt: ImportFormat = format ?? detectFormat(filePath)
    if (fmt === 'csv') return parseCsv(filePath)
    if (fmt === 'json') return parseJson(filePath)
    return parseXlsx(filePath)
  }

  async suggestMapping(raw: RawImportTable): Promise<ColumnMappingSuggestion> {
    return suggestMapping(raw)
  }

  async validate(raw: RawImportTable, mapping: ColumnMapping): Promise<ValidationResult> {
    return validate(raw, mapping)
  }

  async commit(input: {
    projectId: string
    experimentName: string
    mapping: ColumnMapping
    raw: RawImportTable
    fileHash: string
    importedBy?: string
  }): Promise<ImportResult> {
    const svc = this.getService()
    if (!svc) throw new Error('数据库未就绪')
    const check = validateMapping(input.mapping)
    if (!check.ok) throw new Error(`映射缺失必需字段: ${check.missing.join(', ')}`)
    const validation = validate(input.raw, input.mapping)
    const start = Date.now()
    const experimentId = `exp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
    const batchKey = input.mapping.sample_batch ? findSourceColumn(input.mapping, 'sample_batch') : null
    const now = Date.now()
    const validRows = filterValidRows(input.raw, input.mapping, validation)

    let sampleCount = 0
    let measurementCount = 0
    svc.db.transaction(() => {
      svc.db.execute(
        `INSERT INTO experiments (id, project_id, name, parameters, status, created_at) VALUES (?, ?, ?, ?, ?, ?)`,
        [experimentId, input.projectId, input.experimentName, JSON.stringify({ sourceFile: input.raw.sourceName, fileHash: input.fileHash }), 'imported', now]
      )
      // 按 batch 分组创建 sample
      const batchMap = new Map<string, string>()
      for (const r of validRows) {
        const batchVal = batchKey ? r[batchKey] ?? '' : ''
        const batchId = batchVal !== '' ? batchVal : 'default'
        if (!batchMap.has(batchId)) {
          const sampleId = `sample-${Date.now()}-${Math.random().toString(36).slice(2, 6)}-${sampleCount}`
          batchMap.set(batchId, sampleId)
          svc.db.execute(
            `INSERT INTO samples (id, experiment_id, batch, sampled_at, metadata) VALUES (?, ?, ?, ?, ?)`,
            [sampleId, experimentId, batchId, now, JSON.stringify({ fileHash: input.fileHash, importedBy: input.importedBy ?? null })]
          )
          sampleCount += 1
        }
      }
      const tsCol = findSourceColumn(input.mapping, 'timestamp')
      const metricCol = findSourceColumn(input.mapping, 'metric')
      const valueCol = findSourceColumn(input.mapping, 'value')
      const unitCol = findSourceColumn(input.mapping, 'unit')
      const sampleCol = findSourceColumn(input.mapping, 'sample_batch')
      const replCol = findSourceColumn(input.mapping, 'replicate')
      const stmt = svc.db.prepare('INSERT INTO measurements (experiment_id, timestamp, metric, value, unit, sample_id, replicate, batch) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
      for (const r of validRows) {
        const ts = parseTs(r[tsCol!] ?? '')
        const metric = r[metricCol!] ?? ''
        const value = Number(r[valueCol!])
        if (!Number.isFinite(value)) continue
        const unit = unitCol ? r[unitCol] ?? null : null
        const batchVal = sampleCol ? r[sampleCol] ?? 'default' : 'default'
        const sampleId = batchMap.get(batchVal)!
        const replicate = replCol ? Number(r[replCol]) || null : null
        stmt.run([experimentId, ts, metric, value, unit, sampleId, replicate, batchVal])
        measurementCount += 1
      }
    })
    svc.audit.record({ action: 'import.commit', module: 'import', metadata: { experimentId, fileHash: input.fileHash, sampleCount, measurementCount } })
    return { experimentId, sampleCount, measurementCount, durationMs: Date.now() - start }
  }

  async listDatasets(projectId?: string): Promise<ImportDataset[]> {
    const svc = this.getService()
    if (!svc) return []
    const where = projectId ? 'WHERE e.project_id = ?' : ''
    const params = projectId ? [projectId] : []
    const rows = svc.db.query<Record<string, unknown>>(
      `SELECT e.id AS experiment_id, e.name AS experiment_name, e.project_id, e.parameters, e.created_at,
              (SELECT COUNT(*) FROM measurements m WHERE m.experiment_id = e.id) AS measurement_count,
              (SELECT COUNT(*) FROM samples s WHERE s.experiment_id = e.id) AS sample_count
       FROM experiments e ${where} AND e.status = 'imported' ORDER BY e.created_at DESC`,
      params
    )
    return rows.map((r) => {
      let fileName = ''
      let fileHash = ''
      try {
        const p = JSON.parse(String(r['parameters'] ?? '{}')) as { sourceFile?: string; fileHash?: string }
        fileName = p.sourceFile ?? ''
        fileHash = p.fileHash ?? ''
      } catch { /* noop */ }
      return {
        experimentId: String(r['experiment_id']),
        experimentName: String(r['experiment_name']),
        fileName,
        fileHash,
        format: fileName.endsWith('.xlsx') ? 'xlsx' : fileName.endsWith('.json') ? 'json' : 'csv',
        rowCount: Number(r['measurement_count']),
        importedAt: Number(r['created_at']),
        sampleCount: Number(r['sample_count'])
      }
    })
  }
}

function detectFormat(filePath: string): ImportFormat {
  const lower = filePath.toLowerCase()
  if (lower.endsWith('.xlsx') || lower.endsWith('.xlsm')) return 'xlsx'
  if (lower.endsWith('.json')) return 'json'
  return 'csv'
}

function findSourceColumn(mapping: ColumnMapping, target: string): string | null {
  for (const [src, dst] of Object.entries(mapping)) {
    if (dst === target) return src
  }
  return null
}

function parseTs(s: string): number {
  if (/^-?\d+(\.\d+)?$/.test(s)) {
    const n = Number(s); return n < 1e11 ? n * 1000 : n
  }
  const t = Date.parse(s)
  return Number.isNaN(t) ? Date.now() : t
}

function filterValidRows(raw: RawImportTable, mapping: ColumnMapping, _validation: ValidationResult): Array<Record<string, string>> {
  const tsCol = findSourceColumn(mapping, 'timestamp')
  const metricCol = findSourceColumn(mapping, 'metric')
  const valueCol = findSourceColumn(mapping, 'value')
  if (!tsCol || !metricCol || !valueCol) return []
  const seen = new Set<string>()
  const out: Array<Record<string, string>> = []
  for (const row of raw.rows) {
    const ts = row[tsCol] ?? ''
    const metric = row[metricCol] ?? ''
    const value = row[valueCol] ?? ''
    if (!ts || !metric || !value) continue
    if (!Number.isFinite(Number(value))) continue
    const key = `${ts}|${metric}`
    if (seen.has(key)) continue
    seen.add(key)
    out.push(row)
  }
  return out
}

export function createImportEngine(getService: () => DatabaseService | null): ImportEngine {
  return new ImportEngineImpl(getService)
}

export type { ImportEngine } from './types'
