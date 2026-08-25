// Column Mapper — Phase 9-A
// 启发式列映射: 时间 / 指标名 / 数值 / 单位 / 样本批次 / 重复

import type { ColumnMapping, ColumnMappingSuggestion, ColumnTarget, RawImportTable } from './types'

const TIMESTAMP_PATTERNS = [/time/i, /date/i, /timestamp/i, /time_?stamp/i, /\bts\b/i, /\bday\b/i]
const METRIC_PATTERNS = [/metric/i, /^name$/i, /^channel$/i, /^variable$/i, /^param/i, /\bseries\b/i]
const VALUE_PATTERNS = [/value/i, /reading/i, /measurement/i, /data$/i, /result/i, /concentration/i, /level/i, /rate/i]
const UNIT_PATTERNS = [/^unit/i, /units$/i, /^uom$/i]
const BATCH_PATTERNS = [/batch/i, /run/i, /^set$/i, /group/i]
const REPLICATE_PATTERNS = [/replicate/i, /^rep$/i, /replicate_no/i, /^n$/i]
const OPERATOR_PATTERNS = [/operator/i, /analyst/i, /user/i, /owner/i, /author/i]
const NOTES_PATTERNS = [/note/i, /comment/i, /remark/i, /description/i]

function patternMatches(name: string, patterns: RegExp[]): boolean {
  for (const p of patterns) if (p.test(name)) return true
  return false
}

function detectColumnKind(values: string[]): 'timestamp' | 'numeric' | 'text' | 'low-cardinality' {
  const finiteCount = values.filter((v) => v !== '' && Number.isFinite(Number(v))).length
  const isoCount = values.filter((v) => v !== '' && !Number.isNaN(Date.parse(v)) && /[-T:]/.test(v)).length
  const uniqueCount = new Set(values.filter((v) => v !== '')).size
  if (isoCount / values.filter((v) => v !== '').length > 0.7) return 'timestamp'
  if (finiteCount / values.filter((v) => v !== '').length > 0.7) return 'numeric'
  if (uniqueCount <= Math.max(20, values.length * 0.2)) return 'low-cardinality'
  return 'text'
}

export function suggestMapping(raw: RawImportTable): ColumnMappingSuggestion {
  const totalCols = raw.columns.length
  const mapping: ColumnMapping = {}
  let hits = 0
  const rationaleParts: string[] = []
  for (const col of raw.columns) {
    const values = raw.rows.slice(0, 100).map((r) => r[col] ?? '')
    const kind = detectColumnKind(values)
    if (patternMatches(col, TIMESTAMP_PATTERNS) || kind === 'timestamp') {
      mapping[col] = 'timestamp'
      hits += 1
      rationaleParts.push(`${col} → 时间戳 (列名 / 值模式)`)
    } else if (patternMatches(col, UNIT_PATTERNS)) {
      mapping[col] = 'unit'
      hits += 1
      rationaleParts.push(`${col} → 单位 (列名匹配)`)
    } else if (patternMatches(col, METRIC_PATTERNS)) {
      if (kind === 'low-cardinality') {
        mapping[col] = 'metric'
        hits += 1
        rationaleParts.push(`${col} → 指标名 (列名 + 低基数)`)
      } else {
        mapping[col] = 'ignore'
      }
    } else if (patternMatches(col, VALUE_PATTERNS) || (kind === 'numeric' && !mapping[col])) {
      mapping[col] = 'value'
      hits += 1
      rationaleParts.push(`${col} → 数值 (列名 / 类型)`)
    } else if (patternMatches(col, BATCH_PATTERNS)) {
      mapping[col] = 'sample_batch'
      hits += 1
      rationaleParts.push(`${col} → 样本批次 (列名匹配)`)
    } else if (patternMatches(col, REPLICATE_PATTERNS)) {
      mapping[col] = 'replicate'
      hits += 1
      rationaleParts.push(`${col} → 重复号 (列名匹配)`)
    } else if (patternMatches(col, OPERATOR_PATTERNS)) {
      mapping[col] = 'operator'
      hits += 1
    } else if (patternMatches(col, NOTES_PATTERNS)) {
      mapping[col] = 'notes'
      hits += 1
    } else {
      mapping[col] = 'ignore'
    }
  }
  const confidence = totalCols === 0 ? 0 : hits / Math.max(totalCols, 3)
  let rationale = rationaleParts.slice(0, 5).join('; ')
  if (rationaleParts.length > 5) rationale += ` ... 等 ${rationaleParts.length} 项`
  if (!rationale) rationale = '未识别出明确字段, 请手动映射'
  return { mapping, confidence, rationale }
}

/** 用户在 UI 调整后验证 (确保 5 必需字段中至少 4 个已映射). */
export function validateMapping(mapping: ColumnMapping): { ok: boolean; missing: ColumnTarget[] } {
  const required: ColumnTarget[] = ['timestamp', 'metric', 'value']
  const mapped = new Set(Object.values(mapping))
  const missing = required.filter((r) => !mapped.has(r))
  return { ok: missing.length === 0, missing }
}
