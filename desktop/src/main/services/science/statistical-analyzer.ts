// Statistical Analyzer (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: deterministic computation of descriptive statistics and
// correlation from scientific datasets. No LLM.

import type {
  ScientificDataset,
  StatisticalResult
} from '../../../shared/science/scientific-data-schema'

// ============ Helpers ============

function getNumericValues(dataset: ScientificDataset, varName: string): number[] {
  return dataset.rows
    .map((r: Record<string, unknown>) => r[varName])
    .filter((v: unknown): v is number => typeof v === 'number' && Number.isFinite(v))
}

function mean(values: number[]): number {
  if (values.length === 0) return 0
  return values.reduce((s, v) => s + v, 0) / values.length
}

function median(values: number[]): number {
  if (values.length === 0) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid]
}

function std(values: number[]): number {
  if (values.length < 2) return 0
  const m = mean(values)
  const variance = values.reduce((s, v) => s + (v - m) ** 2, 0) / (values.length - 1)
  return Math.sqrt(variance)
}

function variance(values: number[]): number {
  if (values.length < 2) return 0
  const m = mean(values)
  return values.reduce((s, v) => s + (v - m) ** 2, 0) / (values.length - 1)
}

function cv(values: number[]): number {
  const m = mean(values)
  if (m === 0) return 0
  return std(values) / Math.abs(m)
}

function correlation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length)
  if (n < 2) return 0
  const meanX = mean(x.slice(0, n))
  const meanY = mean(y.slice(0, n))
  let num = 0, denX = 0, denY = 0
  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX
    const dy = y[i] - meanY
    num += dx * dy
    denX += dx * dx
    denY += dy * dy
  }
  const den = Math.sqrt(denX * denY)
  return den === 0 ? 0 : num / den
}

// ============ Public API ============

/**
 * Phase 8-H2: compute descriptive statistics for all numeric variables.
 * Returns StatisticalResult[] sorted by metric name. Deterministic.
 */
export function computeStatistics(dataset: ScientificDataset): StatisticalResult[] {
  const results: StatisticalResult[] = []
  const numericVars = dataset.variables.filter((v: { type: string }) => v.type === 'number')

  for (const v of numericVars) {
    const values = getNumericValues(dataset, v.name)
    if (values.length === 0) continue

    const m = mean(values)
    const med = median(values)
    const s = std(values)
    const vrn = variance(values)
    const c = cv(values)

    results.push({ metric: `${v.name}_mean`, value: Math.round(m * 10000) / 10000, interpretation: `Average ${v.name} is ${m.toFixed(4)} ${v.unit}` })
    results.push({ metric: `${v.name}_median`, value: Math.round(med * 10000) / 10000, interpretation: `Median ${v.name} is ${med.toFixed(4)} ${v.unit}` })
    results.push({ metric: `${v.name}_std`, value: Math.round(s * 10000) / 10000, interpretation: `Standard deviation of ${v.name} is ${s.toFixed(4)} ${v.unit}` })
    results.push({ metric: `${v.name}_variance`, value: Math.round(vrn * 10000) / 10000, interpretation: `Variance of ${v.name} is ${vrn.toFixed(4)}` })
    results.push({ metric: `${v.name}_cv`, value: Math.round(c * 10000) / 10000, interpretation: `Coefficient of variation of ${v.name} is ${(c * 100).toFixed(2)}%` })
  }

  // Pairwise correlation for numeric variable pairs
  for (let i = 0; i < numericVars.length; i++) {
    for (let j = i + 1; j < numericVars.length; j++) {
      const x = getNumericValues(dataset, numericVars[i].name)
      const y = getNumericValues(dataset, numericVars[j].name)
      if (x.length < 2 || y.length < 2) continue
      const r = correlation(x, y)
      const rRound = Math.round(r * 10000) / 10000
      const strength = Math.abs(r) > 0.7 ? 'strong' : Math.abs(r) > 0.3 ? 'moderate' : 'weak'
      const direction = r > 0 ? 'positive' : 'negative'
      results.push({
        metric: `correlation_${numericVars[i].name}_${numericVars[j].name}`,
        value: rRound,
        interpretation: `${strength} ${direction} correlation (r=${rRound}) between ${numericVars[i].name} and ${numericVars[j].name}`
      })
    }
  }

  return results
}
