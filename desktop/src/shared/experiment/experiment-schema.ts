// Experiment Schema — 科研实验契约（生命周期 + 记录 + 参数 + 结果）。

// ============ Enums ============

export type ExperimentStatus =
  | 'draft' | 'planned' | 'running' | 'paused' | 'completed' | 'failed'

export const EXPERIMENT_STATUSES: readonly ExperimentStatus[] = Object.freeze([
  'draft', 'planned', 'running', 'paused', 'completed', 'failed'
])

export type ParameterType = 'numeric' | 'categorical' | 'boolean' | 'text'
export const PARAMETER_TYPES: readonly ParameterType[] = Object.freeze([
  'numeric', 'categorical', 'boolean', 'text'
])

// ============ Core types ============

export interface ExperimentParameter {
  name: string
  value: string | number | boolean
  unit: string
  type: ParameterType
}

export interface ExperimentRecord {
  id: string
  experimentId: string
  timestamp: number
  operator: string
  parameters: ExperimentParameter[]
  observations: string
  notes: string
}

export interface ExperimentResult {
  metrics: Record<string, number>
  conclusion: string
  confidence: number
}

export interface Experiment {
  id: string
  projectId: string
  title: string
  objective: string
  hypothesis: string
  status: ExperimentStatus
  design: string
  records: ExperimentRecord[]
  datasets: string[]
  results: ExperimentResult[]
  createdAt: number
  updatedAt: number
}

// ============ Validators ============

const VALID_EXPERIMENT_STATUSES: ReadonlySet<ExperimentStatus> = new Set(EXPERIMENT_STATUSES)
const VALID_PARAMETER_TYPES: ReadonlySet<ParameterType> = new Set(PARAMETER_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']

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
  if (hit) throw new Error(`experiment schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-K0 strict)`)
}

function isValidTimestamp(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidExperimentStatus(s: unknown): s is ExperimentStatus {
  return typeof s === 'string' && VALID_EXPERIMENT_STATUSES.has(s as ExperimentStatus)
}

export function isValidParameterType(t: unknown): t is ParameterType {
  return typeof t === 'string' && VALID_PARAMETER_TYPES.has(t as ParameterType)
}

export function isValidExperimentParameter(p: unknown): p is ExperimentParameter {
  if (!isObject(p)) return false
  if (typeof p.name !== 'string' || p.name.length === 0) return false
  if (typeof p.unit !== 'string') return false
  if (!isValidParameterType(p.type)) return false
  if (p.type === 'numeric') {
    if (typeof p.value !== 'number' || !Number.isFinite(p.value)) return false
  } else if (p.type === 'boolean') {
    if (typeof p.value !== 'boolean') return false
  } else {
    if (typeof p.value !== 'string') return false
  }
  assertNoSecret(p, 'ExperimentParameter')
  return true
}

export function isValidExperimentRecord(r: unknown): r is ExperimentRecord {
  if (!isObject(r)) return false
  if (typeof r.id !== 'string' || r.id.length === 0) return false
  if (typeof r.experimentId !== 'string') return false
  if (!isValidTimestamp(r.timestamp)) return false
  if (typeof r.operator !== 'string') return false
  if (!Array.isArray(r.parameters)) return false
  if (!r.parameters.every((p) => isValidExperimentParameter(p))) return false
  if (typeof r.observations !== 'string') return false
  if (typeof r.notes !== 'string') return false
  assertNoSecret(r, 'ExperimentRecord')
  return true
}

export function isValidExperimentResult(r: unknown): r is ExperimentResult {
  if (!isObject(r)) return false
  if (!isObject(r.metrics)) return false
  for (const [, v] of Object.entries(r.metrics)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return false
  }
  if (typeof r.conclusion !== 'string') return false
  if (!isValidScore(r.confidence)) return false
  assertNoSecret(r, 'ExperimentResult')
  return true
}

export function isValidExperiment(e: unknown): e is Experiment {
  if (!isObject(e)) return false
  if (typeof e.id !== 'string' || e.id.length === 0) return false
  if (typeof e.projectId !== 'string') return false
  if (typeof e.title !== 'string') return false
  if (typeof e.objective !== 'string') return false
  if (typeof e.hypothesis !== 'string') return false
  if (!isValidExperimentStatus(e.status)) return false
  if (typeof e.design !== 'string') return false
  if (!Array.isArray(e.records)) return false
  if (!e.records.every((r) => isValidExperimentRecord(r))) return false
  if (!Array.isArray(e.datasets)) return false
  if (!e.datasets.every((d) => typeof d === 'string')) return false
  if (!Array.isArray(e.results)) return false
  if (!e.results.every((r) => isValidExperimentResult(r))) return false
  if (!isValidTimestamp(e.createdAt)) return false
  if (!isValidTimestamp(e.updatedAt)) return false
  assertNoSecret(e, 'Experiment')
  return true
}

export const __testHelpers = {
  EXPERIMENT_STATUSES,
  PARAMETER_TYPES,
  VALID_EXPERIMENT_STATUSES,
  VALID_PARAMETER_TYPES,
  FORBIDDEN,
  findForbidden
}