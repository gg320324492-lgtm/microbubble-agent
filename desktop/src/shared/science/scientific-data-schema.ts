// Scientific Data Schema Contracts (Phase 8-H2: Scientific Data Analyst Agent).
//
// Phase 8-H2: typed contracts for dataset representation, data quality,
// statistical analysis, model fitting, visualization, and interpretation.
// Consumes Phase 8-H1 ExperimentObservation but never modifies it.
//
// Phase 8-H2 frozen contract:
//   - DataType (4 types)
//   - ScientificDataset / VariableDefinition / DataQualityReport
//   - StatisticalResult / ModelFitResult / FigureRecommendation
//   - ScientificConclusion / AnalysisReport
//   - Validators + assertNoSecret guard
//
// Phase 8-H2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId

// ============ Enums ============

export type DataType = 'number' | 'string' | 'boolean' | 'date'

export const DATA_TYPES: readonly DataType[] = Object.freeze([
  'number', 'string', 'boolean', 'date'
])

// ============ Core types ============

export interface VariableDefinition {
  name: string
  type: DataType
  unit: string
}

export interface ScientificDataset {
  datasetId: string
  name: string
  variables: VariableDefinition[]
  rows: Record<string, unknown>[]
  metadata: Record<string, unknown>
}

export interface DataQualityReport {
  completeness: number // 0..1
  missingValues: Record<string, number>
  outliers: Record<string, number>
  warnings: string[]
}

export interface StatisticalResult {
  metric: string
  value: number
  interpretation: string
}

export interface ModelFitResult {
  model: string
  parameters: Record<string, number>
  rSquared: number
  residualError: number
}

export interface FigureRecommendation {
  type: string
  title: string
  xVariable: string
  yVariable: string
  reason: string
}

export interface ScientificConclusion {
  observation: string
  interpretation: string
  confidence: number // 0..1
}

export interface AnalysisReport {
  quality: DataQualityReport
  statistics: StatisticalResult[]
  models: ModelFitResult[]
  figures: FigureRecommendation[]
  conclusions: ScientificConclusion[]
}

// ============ Validators ============

const VALID_DATA_TYPES: ReadonlySet<DataType> = new Set(DATA_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

// Value-only secret guard
const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') {
    for (const bad of FORBIDDEN) if (value.includes(bad)) return bad
    return null
  }
  if (Array.isArray(value)) {
    for (const v of value) { const r = findForbidden(v); if (r) return r }
    return null
  }
  if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) {
      const r = findForbidden(v); if (r) return r
    }
  }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) {
    throw new Error(`scientific data leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-H2 strict)`)
  }
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidDataType(t: unknown): t is DataType {
  return typeof t === 'string' && VALID_DATA_TYPES.has(t as DataType)
}

export function isValidVariableDefinition(v: unknown): v is VariableDefinition {
  if (!isObject(v)) return false
  if (typeof v.name !== 'string' || v.name.length === 0) return false
  if (!isValidDataType(v.type)) return false
  if (typeof v.unit !== 'string') return false
  assertNoSecret(v, 'VariableDefinition')
  return true
}

export function isValidScientificDataset(d: unknown): d is ScientificDataset {
  if (!isObject(d)) return false
  if (typeof d.datasetId !== 'string' || d.datasetId.length === 0) return false
  if (typeof d.name !== 'string' || d.name.length === 0) return false
  if (!Array.isArray(d.variables)) return false
  if (!d.variables.every((v) => isValidVariableDefinition(v))) return false
  if (!Array.isArray(d.rows)) return false
  if (!isObject(d.metadata)) return false
  assertNoSecret(d, 'ScientificDataset')
  return true
}

export function isValidDataQualityReport(r: unknown): r is DataQualityReport {
  if (!isObject(r)) return false
  if (!isValidScore(r.completeness)) return false
  if (!isObject(r.missingValues)) return false
  if (!isObject(r.outliers)) return false
  if (!Array.isArray(r.warnings)) return false
  assertNoSecret(r, 'DataQualityReport')
  return true
}

export function isValidStatisticalResult(s: unknown): s is StatisticalResult {
  if (!isObject(s)) return false
  if (typeof s.metric !== 'string' || s.metric.length === 0) return false
  if (typeof s.value !== 'number' || !Number.isFinite(s.value)) return false
  if (typeof s.interpretation !== 'string') return false
  assertNoSecret(s, 'StatisticalResult')
  return true
}

export function isValidModelFitResult(m: unknown): m is ModelFitResult {
  if (!isObject(m)) return false
  if (typeof m.model !== 'string' || m.model.length === 0) return false
  if (!isObject(m.parameters)) return false
  if (typeof m.rSquared !== 'number' || !Number.isFinite(m.rSquared)) return false
  if (typeof m.residualError !== 'number' || !Number.isFinite(m.residualError)) return false
  assertNoSecret(m, 'ModelFitResult')
  return true
}

export function isValidFigureRecommendation(f: unknown): f is FigureRecommendation {
  if (!isObject(f)) return false
  if (typeof f.type !== 'string' || f.type.length === 0) return false
  if (typeof f.title !== 'string') return false
  if (typeof f.xVariable !== 'string') return false
  if (typeof f.yVariable !== 'string') return false
  if (typeof f.reason !== 'string') return false
  assertNoSecret(f, 'FigureRecommendation')
  return true
}

export function isValidScientificConclusion(c: unknown): c is ScientificConclusion {
  if (!isObject(c)) return false
  if (typeof c.observation !== 'string' || c.observation.length === 0) return false
  if (typeof c.interpretation !== 'string') return false
  if (!isValidScore(c.confidence)) return false
  assertNoSecret(c, 'ScientificConclusion')
  return true
}

export function isValidAnalysisReport(r: unknown): r is AnalysisReport {
  if (!isObject(r)) return false
  if (!isValidDataQualityReport(r.quality)) return false
  if (!Array.isArray(r.statistics)) return false
  if (!r.statistics.every((s) => isValidStatisticalResult(s))) return false
  if (!Array.isArray(r.models)) return false
  if (!r.models.every((m) => isValidModelFitResult(m))) return false
  if (!Array.isArray(r.figures)) return false
  if (!r.figures.every((f) => isValidFigureRecommendation(f))) return false
  if (!Array.isArray(r.conclusions)) return false
  if (!r.conclusions.every((c) => isValidScientificConclusion(c))) return false
  assertNoSecret(r, 'AnalysisReport')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  DATA_TYPES,
  VALID_DATA_TYPES,
  findForbidden,
  isValidScore
}
