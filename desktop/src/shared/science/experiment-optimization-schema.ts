// Experiment Optimization Schema Contracts (Phase 8-H1: Experiment Optimization Agent).
//
// Phase 8-H1: typed contracts for experiment analysis, variable importance,
// mechanism interpretation, optimization suggestions, and next experiment
// recommendations. Consumes Phase 8-H0 ExperimentPlan but never modifies it.
//
// Phase 8-H1 frozen contract:
//   - IssueType (5 types)
//   - ExperimentObservation / MetricObservation / OptimizationIssue
//   - VariableImportance / OptimizationSuggestion / NextExperimentRecommendation
//   - ExperimentOptimizationResult
//   - Validators + assertNoSecret guard
//
// Phase 8-H1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId

// ============ Enums ============

export type IssueType =
  | 'outlier'
  | 'contradiction'
  | 'weak-signal'
  | 'missing-data'
  | 'unexpected-trend'

export const ISSUE_TYPES: readonly IssueType[] = Object.freeze([
  'outlier', 'contradiction', 'weak-signal', 'missing-data', 'unexpected-trend'
])

// ============ Core types ============

export interface MetricObservation {
  name: string
  value: number
  unit: string
  direction: 'higher-is-better' | 'lower-is-better'
}

export interface ExperimentObservation {
  observationId: string
  variableValues: Record<string, number>
  metrics: MetricObservation[]
  timestamp?: number
  notes?: string
}

export interface OptimizationIssue {
  type: IssueType
  description: string
  severity: number // 0..1
  evidence: string
}

export interface VariableImportance {
  variable: string
  importance: number // 0..1
  contribution: string
  confidence: number // 0..1
}

export interface OptimizationSuggestion {
  suggestion: string
  reason: string
  expectedEffect: string
  confidence: number // 0..1
}

export interface NextExperimentRecommendation {
  changeVariable: string
  currentValue: number
  suggestedRange: string
  purpose: string
}

export interface ExperimentOptimizationResult {
  issues: OptimizationIssue[]
  importantVariables: VariableImportance[]
  explanations: string[]
  suggestions: OptimizationSuggestion[]
  nextExperiments: NextExperimentRecommendation[]
}

// ============ Validators ============

const VALID_ISSUE_TYPES: ReadonlySet<IssueType> = new Set(ISSUE_TYPES)

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
    throw new Error(`experiment optimization leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-H1 strict)`)
  }
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidIssueType(t: unknown): t is IssueType {
  return typeof t === 'string' && VALID_ISSUE_TYPES.has(t as IssueType)
}

export function isValidMetricObservation(m: unknown): m is MetricObservation {
  if (!isObject(m)) return false
  if (typeof m.name !== 'string' || m.name.length === 0) return false
  if (typeof m.value !== 'number' || !Number.isFinite(m.value)) return false
  if (typeof m.unit !== 'string') return false
  if (m.direction !== 'higher-is-better' && m.direction !== 'lower-is-better') return false
  assertNoSecret(m, 'MetricObservation')
  return true
}

export function isValidExperimentObservation(o: unknown): o is ExperimentObservation {
  if (!isObject(o)) return false
  if (typeof o.observationId !== 'string' || o.observationId.length === 0) return false
  if (!isObject(o.variableValues)) return false
  if (!Array.isArray(o.metrics)) return false
  if (!o.metrics.every((m) => isValidMetricObservation(m))) return false
  if (o.timestamp !== undefined && (typeof o.timestamp !== 'number' || !Number.isFinite(o.timestamp))) return false
  if (o.notes !== undefined && typeof o.notes !== 'string') return false
  assertNoSecret(o, 'ExperimentObservation')
  return true
}

export function isValidOptimizationIssue(i: unknown): i is OptimizationIssue {
  if (!isObject(i)) return false
  if (!isValidIssueType(i.type)) return false
  if (typeof i.description !== 'string') return false
  if (!isValidScore(i.severity)) return false
  if (typeof i.evidence !== 'string') return false
  assertNoSecret(i, 'OptimizationIssue')
  return true
}

export function isValidVariableImportance(v: unknown): v is VariableImportance {
  if (!isObject(v)) return false
  if (typeof v.variable !== 'string' || v.variable.length === 0) return false
  if (!isValidScore(v.importance)) return false
  if (typeof v.contribution !== 'string') return false
  if (!isValidScore(v.confidence)) return false
  assertNoSecret(v, 'VariableImportance')
  return true
}

export function isValidOptimizationSuggestion(s: unknown): s is OptimizationSuggestion {
  if (!isObject(s)) return false
  if (typeof s.suggestion !== 'string' || s.suggestion.length === 0) return false
  if (typeof s.reason !== 'string') return false
  if (typeof s.expectedEffect !== 'string') return false
  if (!isValidScore(s.confidence)) return false
  assertNoSecret(s, 'OptimizationSuggestion')
  return true
}

export function isValidNextExperimentRecommendation(r: unknown): r is NextExperimentRecommendation {
  if (!isObject(r)) return false
  if (typeof r.changeVariable !== 'string' || r.changeVariable.length === 0) return false
  if (typeof r.currentValue !== 'number' || !Number.isFinite(r.currentValue)) return false
  if (typeof r.suggestedRange !== 'string') return false
  if (typeof r.purpose !== 'string') return false
  assertNoSecret(r, 'NextExperimentRecommendation')
  return true
}

export function isValidExperimentOptimizationResult(r: unknown): r is ExperimentOptimizationResult {
  if (!isObject(r)) return false
  if (!Array.isArray(r.issues)) return false
  if (!r.issues.every((i) => isValidOptimizationIssue(i))) return false
  if (!Array.isArray(r.importantVariables)) return false
  if (!r.importantVariables.every((v) => isValidVariableImportance(v))) return false
  if (!Array.isArray(r.explanations)) return false
  if (!Array.isArray(r.suggestions)) return false
  if (!r.suggestions.every((s) => isValidOptimizationSuggestion(s))) return false
  if (!Array.isArray(r.nextExperiments)) return false
  if (!r.nextExperiments.every((n) => isValidNextExperimentRecommendation(n))) return false
  assertNoSecret(r, 'ExperimentOptimizationResult')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  ISSUE_TYPES,
  VALID_ISSUE_TYPES,
  findForbidden,
  isValidScore
}
