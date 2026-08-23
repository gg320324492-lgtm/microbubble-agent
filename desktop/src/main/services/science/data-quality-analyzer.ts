// Data Quality Analyzer (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: deterministic analysis of dataset quality — missing values,
// duplicate rows, outliers, invalid values, and unit consistency. No LLM.

import type {
  ScientificDataset,
  DataQualityReport
} from '../../../shared/science/scientific-data-schema'

// ============ Missing values ============

function countMissingValues(dataset: ScientificDataset): Record<string, number> {
  const missing: Record<string, number> = {}
  for (const v of dataset.variables) {
    let count = 0
    for (const row of dataset.rows) {
      const val = row[v.name]
      if (val === null || val === undefined || val === '') count++
    }
    if (count > 0) missing[v.name] = count
  }
  return missing
}

// ============ Duplicate rows ============

function countDuplicateRows(dataset: ScientificDataset): number {
  if (dataset.rows.length === 0) return 0
  const seen = new Set<string>()
  let duplicates = 0
  for (const row of dataset.rows) {
    const key = JSON.stringify(row)
    if (seen.has(key)) duplicates++
    else seen.add(key)
  }
  return duplicates
}

// ============ Outlier detection (IQR method) ============

function detectOutliers(dataset: ScientificDataset): Record<string, number> {
  const outliers: Record<string, number> = {}
  for (const v of dataset.variables) {
    if (v.type !== 'number') continue
    const values = dataset.rows
      .map(r => r[v.name])
      .filter((val): val is number => typeof val === 'number' && Number.isFinite(val))
    if (values.length < 4) continue

    const sorted = [...values].sort((a, b) => a - b)
    const q1 = sorted[Math.floor(sorted.length * 0.25)]
    const q3 = sorted[Math.floor(sorted.length * 0.75)]
    const iqr = q3 - q1
    const lower = q1 - 1.5 * iqr
    const upper = q3 + 1.5 * iqr
    const count = values.filter(v => v < lower || v > upper).length
    if (count > 0) outliers[v.name] = count
  }
  return outliers
}

// ============ Invalid values ============

function detectInvalidValues(dataset: ScientificDataset): string[] {
  const warnings: string[] = []
  for (const v of dataset.variables) {
    for (let i = 0; i < dataset.rows.length; i++) {
      const val = dataset.rows[i][v.name]
      if (val === null || val === undefined || val === '') continue
      if (v.type === 'number' && typeof val !== 'number') {
        warnings.push(`Row ${i}: ${v.name} expected number, got ${typeof val}`)
        break // one warning per variable
      }
      if (v.type === 'boolean' && typeof val !== 'boolean') {
        warnings.push(`Row ${i}: ${v.name} expected boolean, got ${typeof val}`)
        break
      }
    }
  }
  return warnings
}

// ============ Completeness ============

function calculateCompleteness(dataset: ScientificDataset): number {
  if (dataset.rows.length === 0 || dataset.variables.length === 0) return 0
  const totalCells = dataset.rows.length * dataset.variables.length
  let filledCells = 0
  for (const row of dataset.rows) {
    for (const v of dataset.variables) {
      const val = row[v.name]
      if (val !== null && val !== undefined && val !== '') filledCells++
    }
  }
  return Math.round((filledCells / totalCells) * 100) / 100
}

// ============ Public API ============

/**
 * Phase 8-H2: analyze dataset quality. Returns DataQualityReport with
 * completeness, missing values, outliers, and warnings. Deterministic.
 */
export function analyzeDataQuality(dataset: ScientificDataset): DataQualityReport {
  const missingValues = countMissingValues(dataset)
  const outliers = detectOutliers(dataset)
  const completeness = calculateCompleteness(dataset)

  const warnings: string[] = []
  const dupCount = countDuplicateRows(dataset)
  if (dupCount > 0) warnings.push(`${dupCount} duplicate row(s) detected`)

  const invalidWarnings = detectInvalidValues(dataset)
  warnings.push(...invalidWarnings)

  const totalMissing = Object.values(missingValues).reduce((s, n) => s + n, 0)
  if (totalMissing > 0) warnings.push(`${totalMissing} missing value(s) across variables`)

  const totalOutliers = Object.values(outliers).reduce((s, n) => s + n, 0)
  if (totalOutliers > 0) warnings.push(`${totalOutliers} outlier(s) detected`)

  return { completeness, missingValues, outliers, warnings }
}
