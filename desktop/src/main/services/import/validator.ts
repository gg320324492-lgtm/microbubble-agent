// Validator — Phase 9-A
// 5 条规则: missing / duplicate / invalid / unit_mismatch / outlier (>3σ)

import type { ColumnMapping, RawImportTable, ValidationError, ValidationResult } from './types'

interface ParsedRow {
  rowIndex: number
  timestamp: number | null
  metric: string | null
  value: number | null
  unit: string | null
  sampleBatch: string | null
  replicate: string | null
  operator: string | null
  notes: string | null
}

function parseTimestamp(s: string): number | null {
  if (!s) return null
  // 数字: 可能是 ms / s
  if (/^-?\d+(\.\d+)?$/.test(s)) {
    const n = Number(s)
    // 10 位以内当秒, 否则当 ms
    return n < 1e11 ? n * 1000 : n
  }
  const t = Date.parse(s)
  if (Number.isNaN(t)) return null
  return t
}

function parseNumber(s: string): number | null {
  if (!s) return null
  const n = Number(s)
  return Number.isFinite(n) ? n : null
}

function buildParsedRows(raw: RawImportTable, mapping: ColumnMapping): ParsedRow[] {
  return raw.rows.map((row, idx) => ({
    rowIndex: idx,
    timestamp: parseTimestamp(row[mappingKey(mapping, 'timestamp')] ?? ''),
    metric: row[mappingKey(mapping, 'metric')] ?? null,
    value: parseNumber(row[mappingKey(mapping, 'value')] ?? ''),
    unit: row[mappingKey(mapping, 'unit')] ?? null,
    sampleBatch: row[mappingKey(mapping, 'sample_batch')] ?? null,
    replicate: row[mappingKey(mapping, 'replicate')] ?? null,
    operator: row[mappingKey(mapping, 'operator')] ?? null,
    notes: row[mappingKey(mapping, 'notes')] ?? null
  }))
}

function mappingKey(mapping: ColumnMapping, target: string): string {
  for (const [src, dst] of Object.entries(mapping)) {
    if (dst === target) return src
  }
  return ''
}

export function validate(raw: RawImportTable, mapping: ColumnMapping): ValidationResult {
  const start = Date.now()
  const rows = buildParsedRows(raw, mapping)
  const errors: ValidationError[] = []
  const validRows: ParsedRow[] = []
  const seen = new Map<string, number>()

  for (const r of rows) {
    if (!r.metric) { errors.push({ rowIndex: r.rowIndex, column: 'metric', reason: 'missing', message: 'metric 缺失', value: '' }); continue }
    if (r.timestamp === null) { errors.push({ rowIndex: r.rowIndex, column: 'timestamp', reason: 'missing', message: '时间戳缺失或解析失败', value: '' }); continue }
    if (r.value === null) { errors.push({ rowIndex: r.rowIndex, column: 'value', reason: 'invalid', message: 'value 非有限数', value: '' }); continue }
    const key = `${r.timestamp}|${r.metric}|${r.unit ?? ''}`
    if (seen.has(key)) { errors.push({ rowIndex: r.rowIndex, column: 'timestamp', reason: 'duplicate', message: `与第 ${seen.get(key)} 行重复`, value: key }); continue }
    seen.set(key, r.rowIndex)
    validRows.push(r)
  }

  // 单位一致性: 同 metric 不同 unit
  const unitByMetric = new Map<string, Set<string>>()
  for (const r of validRows) {
    if (!r.metric || !r.unit) continue
    if (!unitByMetric.has(r.metric)) unitByMetric.set(r.metric, new Set())
    unitByMetric.get(r.metric)!.add(r.unit)
  }
  for (const [metric, units] of unitByMetric.entries()) {
    if (units.size > 1) {
      for (const r of validRows) {
        if (r.metric === metric) {
          errors.push({ rowIndex: r.rowIndex, column: 'unit', reason: 'unit_mismatch', message: `${metric} 单位不一致 (${Array.from(units).join(', ')})`, value: r.unit ?? '' })
        }
      }
    }
  }

  // 离群点: 同 metric, |x - mean| > 3σ
  const byMetric = new Map<string, ParsedRow[]>()
  for (const r of validRows) {
    if (!r.metric || r.value === null) continue
    if (!byMetric.has(r.metric)) byMetric.set(r.metric, [])
    byMetric.get(r.metric)!.push(r)
  }
  for (const [metric, group] of byMetric.entries()) {
    if (group.length < 4) continue
    const xs = group.map((g) => g.value as number)
    const mean = xs.reduce((a, b) => a + b, 0) / xs.length
    const variance = xs.reduce((a, b) => a + (b - mean) ** 2, 0) / (xs.length - 1)
    const std = Math.sqrt(variance)
    if (std === 0) continue
    for (const g of group) {
      const z = Math.abs(((g.value as number) - mean) / std)
      if (z > 3) {
        errors.push({ rowIndex: g.rowIndex, column: 'value', reason: 'outlier', message: `${metric} 离群 (z=${z.toFixed(2)})`, value: String(g.value) })
      }
    }
  }

  const detectedMetrics = Array.from(new Set(validRows.map((r) => r.metric).filter((m): m is string => !!m)))
  const detectedUnits = Array.from(new Set(validRows.map((r) => r.unit).filter((u): u is string => !!u)))
  return {
    validRowCount: validRows.length,
    invalidRowCount: errors.length,
    errors: errors.slice(0, 500),
    detectedMetrics,
    detectedUnits,
    validateMs: Date.now() - start
  }
}
