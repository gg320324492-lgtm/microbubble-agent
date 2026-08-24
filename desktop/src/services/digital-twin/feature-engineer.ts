// Feature Engineer — 特征工程层。
//
// 支持: numeric experiments / time series / parameter optimization
// 提供 extractFeatures / normalize / selectFeatures / validateInput 四函数。

export type FeatureSourceKind = 'numeric' | 'time-series' | 'parameter-optimization'
export const FEATURE_SOURCE_KINDS: readonly FeatureSourceKind[] = Object.freeze([
  'numeric', 'time-series', 'parameter-optimization'
])

export interface FeatureVector {
  name: string
  values: number[]
  kind: FeatureSourceKind
}

export interface NormalizedFeature {
  name: string
  values: number[]
  min: number
  max: number
}

export function extractFeatures(rows: Record<string, unknown>[], column: string, kind: FeatureSourceKind = 'numeric'): FeatureVector {
  const values: number[] = []
  for (const r of rows) {
    const v = r[column]
    if (typeof v === 'number' && Number.isFinite(v)) values.push(v)
  }
  return { name: column, values, kind }
}

export function normalize(feature: FeatureVector): NormalizedFeature {
  if (feature.values.length === 0) {
    return { name: feature.name, values: [], min: 0, max: 0 }
  }
  let min = feature.values[0]
  let max = feature.values[0]
  for (const v of feature.values) {
    if (v < min) min = v
    if (v > max) max = v
  }
  const range = max - min
  const values = range === 0 ? feature.values.map(() => 0) : feature.values.map((v) => (v - min) / range)
  return { name: feature.name, values, min, max }
}

export interface SelectionCriteria {
  minVariance?: number
  topK?: number
  requiredColumns?: string[]
}

export function selectFeatures(features: FeatureVector[], criteria: SelectionCriteria = {}): FeatureVector[] {
  const minVariance = criteria.minVariance ?? 0
  const required = new Set(criteria.requiredColumns ?? [])

  const scored = features.map((f) => {
    const mean = f.values.length === 0 ? 0 : f.values.reduce((s, v) => s + v, 0) / f.values.length
    const variance = f.values.length === 0 ? 0 : f.values.reduce((s, v) => s + (v - mean) ** 2, 0) / f.values.length
    return { feature: f, variance, required: required.has(f.name) }
  }).filter((s) => s.variance >= minVariance || s.required)

  const topK = criteria.topK
  if (topK !== undefined && topK > 0) {
    scored.sort((a, b) => {
      if (a.required !== b.required) return a.required ? -1 : 1
      return b.variance - a.variance
    })
    return scored.slice(0, topK).map((s) => s.feature)
  }
  return scored.map((s) => s.feature)
}

export function validateInput(input: Record<string, unknown>, schema: Record<string, 'number' | 'string' | 'boolean'>): { ok: true } | { ok: false; error: string } {
  for (const [key, expectedType] of Object.entries(schema)) {
    if (!(key in input)) return { ok: false, error: `missing field: ${key}` }
    const v = input[key]
    if (expectedType === 'number') {
      if (typeof v !== 'number' || !Number.isFinite(v)) return { ok: false, error: `${key} must be number` }
    } else if (expectedType === 'string') {
      if (typeof v !== 'string') return { ok: false, error: `${key} must be string` }
    } else {
      if (typeof v !== 'boolean') return { ok: false, error: `${key} must be boolean` }
    }
  }
  return { ok: true }
}

export const __testHelpers = { FEATURE_SOURCE_KINDS }