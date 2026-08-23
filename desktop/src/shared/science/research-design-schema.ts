// Research Design Schema Contracts (Phase 8-H0: Research Design Agent).
//
// Phase 8-H0: typed contracts for research problem analysis, hypothesis
// generation, experiment design, and model selection. Consumes Phase 8-G0
// MethodRecommendation but never modifies the reasoning layer.
//
// Phase 8-H0 frozen contract:
//   - ResearchDomain (7 types)
//   - VariableType (3 types)
//   - ResearchProblem / ResearchHypothesis / DesignVariable / ExperimentPlan
//   - ExperimentGroup / EvaluationMetric / ModelSelection / ProblemAnalysis
//   - ResearchDesignResult
//   - Validators + assertNoSecret guard
//
// Phase 8-H0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId

// ============ Enums ============

export type ResearchDomain =
  | 'environment'
  | 'material'
  | 'chemical'
  | 'biomedical'
  | 'engineering'
  | 'physics'
  | 'computer-science'

export const RESEARCH_DOMAINS: readonly ResearchDomain[] = Object.freeze([
  'environment', 'material', 'chemical', 'biomedical',
  'engineering', 'physics', 'computer-science'
])

export type VariableType =
  | 'independent'
  | 'dependent'
  | 'control'

export const VARIABLE_TYPES: readonly VariableType[] = Object.freeze([
  'independent', 'dependent', 'control'
])

// ============ Core types ============

export interface ResearchProblem {
  problemId: string
  title: string
  objective: string
  domain: ResearchDomain
  constraints: string[]
}

export interface ResearchHypothesis {
  hypothesisId: string
  statement: string
  mechanism: string
  confidence: number // 0..1
}

export interface DesignVariable {
  name: string
  type: VariableType
  range: string
  unit: string
  importance: number // 0..1
}

export interface ExperimentGroup {
  groupId: string
  condition: string
  purpose: string
}

export interface EvaluationMetric {
  name: string
  method: string
  reason: string
}

export interface ExperimentPlan {
  planId: string
  hypothesis: string
  variables: DesignVariable[]
  groups: ExperimentGroup[]
  measurements: EvaluationMetric[]
  expectedOutcome: string
}

export interface ModelSelection {
  model: string
  purpose: string
  justification: string
  confidence: number // 0..1
}

// ============ Analysis result types ============

export interface ProblemAnalysis {
  problemId: string
  keyScientificQuestion: string
  possibleMechanisms: string[]
  requiredEvidence: string[]
  recommendedApproach: string
}

export interface ResearchDesignResult {
  problemAnalysis: ProblemAnalysis
  hypotheses: ResearchHypothesis[]
  experimentPlan: ExperimentPlan
  modelSelection: ModelSelection
}

// ============ Validators ============

const VALID_RESEARCH_DOMAINS: ReadonlySet<ResearchDomain> = new Set(RESEARCH_DOMAINS)
const VALID_VARIABLE_TYPES: ReadonlySet<VariableType> = new Set(VARIABLE_TYPES)

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
    throw new Error(`research design leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-H0 strict)`)
  }
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidResearchDomain(d: unknown): d is ResearchDomain {
  return typeof d === 'string' && VALID_RESEARCH_DOMAINS.has(d as ResearchDomain)
}

export function isValidVariableType(t: unknown): t is VariableType {
  return typeof t === 'string' && VALID_VARIABLE_TYPES.has(t as VariableType)
}

export function isValidResearchProblem(p: unknown): p is ResearchProblem {
  if (!isObject(p)) return false
  if (typeof p.problemId !== 'string' || p.problemId.length === 0) return false
  if (typeof p.title !== 'string' || p.title.length === 0) return false
  if (typeof p.objective !== 'string' || p.objective.length === 0) return false
  if (!isValidResearchDomain(p.domain)) return false
  if (!Array.isArray(p.constraints)) return false
  assertNoSecret(p, 'ResearchProblem')
  return true
}

export function isValidResearchHypothesis(h: unknown): h is ResearchHypothesis {
  if (!isObject(h)) return false
  if (typeof h.hypothesisId !== 'string' || h.hypothesisId.length === 0) return false
  if (typeof h.statement !== 'string' || h.statement.length === 0) return false
  if (typeof h.mechanism !== 'string' || h.mechanism.length === 0) return false
  if (!isValidScore(h.confidence)) return false
  assertNoSecret(h, 'ResearchHypothesis')
  return true
}

export function isValidDesignVariable(v: unknown): v is DesignVariable {
  if (!isObject(v)) return false
  if (typeof v.name !== 'string' || v.name.length === 0) return false
  if (!isValidVariableType(v.type)) return false
  if (typeof v.range !== 'string') return false
  if (typeof v.unit !== 'string') return false
  if (!isValidScore(v.importance)) return false
  assertNoSecret(v, 'DesignVariable')
  return true
}

export function isValidExperimentGroup(g: unknown): g is ExperimentGroup {
  if (!isObject(g)) return false
  if (typeof g.groupId !== 'string' || g.groupId.length === 0) return false
  if (typeof g.condition !== 'string') return false
  if (typeof g.purpose !== 'string') return false
  assertNoSecret(g, 'ExperimentGroup')
  return true
}

export function isValidEvaluationMetric(m: unknown): m is EvaluationMetric {
  if (!isObject(m)) return false
  if (typeof m.name !== 'string' || m.name.length === 0) return false
  if (typeof m.method !== 'string') return false
  if (typeof m.reason !== 'string') return false
  assertNoSecret(m, 'EvaluationMetric')
  return true
}

export function isValidExperimentPlan(p: unknown): p is ExperimentPlan {
  if (!isObject(p)) return false
  if (typeof p.planId !== 'string' || p.planId.length === 0) return false
  if (typeof p.hypothesis !== 'string') return false
  if (!Array.isArray(p.variables)) return false
  if (!p.variables.every((v) => isValidDesignVariable(v))) return false
  if (!Array.isArray(p.groups)) return false
  if (!p.groups.every((g) => isValidExperimentGroup(g))) return false
  if (!Array.isArray(p.measurements)) return false
  if (!p.measurements.every((m) => isValidEvaluationMetric(m))) return false
  if (typeof p.expectedOutcome !== 'string') return false
  assertNoSecret(p, 'ExperimentPlan')
  return true
}

export function isValidModelSelection(m: unknown): m is ModelSelection {
  if (!isObject(m)) return false
  if (typeof m.model !== 'string' || m.model.length === 0) return false
  if (typeof m.purpose !== 'string') return false
  if (typeof m.justification !== 'string') return false
  if (!isValidScore(m.confidence)) return false
  assertNoSecret(m, 'ModelSelection')
  return true
}

export function isValidProblemAnalysis(a: unknown): a is ProblemAnalysis {
  if (!isObject(a)) return false
  if (typeof a.problemId !== 'string' || a.problemId.length === 0) return false
  if (typeof a.keyScientificQuestion !== 'string') return false
  if (!Array.isArray(a.possibleMechanisms)) return false
  if (!Array.isArray(a.requiredEvidence)) return false
  if (typeof a.recommendedApproach !== 'string') return false
  assertNoSecret(a, 'ProblemAnalysis')
  return true
}

export function isValidResearchDesignResult(r: unknown): r is ResearchDesignResult {
  if (!isObject(r)) return false
  if (!isValidProblemAnalysis(r.problemAnalysis)) return false
  if (!Array.isArray(r.hypotheses)) return false
  if (!r.hypotheses.every((h) => isValidResearchHypothesis(h))) return false
  if (!isValidExperimentPlan(r.experimentPlan)) return false
  if (!isValidModelSelection(r.modelSelection)) return false
  assertNoSecret(r, 'ResearchDesignResult')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  RESEARCH_DOMAINS,
  VARIABLE_TYPES,
  VALID_RESEARCH_DOMAINS,
  VALID_VARIABLE_TYPES,
  findForbidden,
  isValidScore
}
