// Digital Twin Schema — 数字孪生契约。

// ============ Enums ============

export type ModelStatus = 'draft' | 'training' | 'validated' | 'deployed' | 'deprecated'
export const MODEL_STATUSES: readonly ModelStatus[] = Object.freeze([
  'draft', 'training', 'validated', 'deployed', 'deprecated'
])

export type PredictionKind = 'linear' | 'polynomial' | 'kinetic'
export const PREDICTION_KINDS: readonly PredictionKind[] = Object.freeze([
  'linear', 'polynomial', 'kinetic'
])

// ============ Core types ============

export interface TwinParameter {
  name: string
  value: number
  range: string
  unit: string
}

export interface DigitalTwinModel {
  id: string
  name: string
  domain: string
  inputs: string[]
  outputs: string[]
  parameters: TwinParameter[]
  accuracy: number
  status: ModelStatus
  createdAt: number
  updatedAt: number
}

export interface TwinPrediction {
  modelId: string
  input: Record<string, number>
  output: Record<string, number>
  confidence: number
  timestamp: number
}

// ============ Validators ============

const VALID_MODEL_STATUSES: ReadonlySet<ModelStatus> = new Set(MODEL_STATUSES)
const VALID_PREDICTION_KINDS: ReadonlySet<PredictionKind> = new Set(PREDICTION_KINDS)

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
  if (hit) throw new Error(`digital twin schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-K1 strict)`)
}

function isValidTimestamp(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidModelStatus(s: unknown): s is ModelStatus {
  return typeof s === 'string' && VALID_MODEL_STATUSES.has(s as ModelStatus)
}

export function isValidPredictionKind(k: unknown): k is PredictionKind {
  return typeof k === 'string' && VALID_PREDICTION_KINDS.has(k as PredictionKind)
}

export function isValidTwinParameter(p: unknown): p is TwinParameter {
  if (!isObject(p)) return false
  if (typeof p.name !== 'string' || p.name.length === 0) return false
  if (typeof p.value !== 'number' || !Number.isFinite(p.value)) return false
  if (typeof p.range !== 'string') return false
  if (typeof p.unit !== 'string') return false
  assertNoSecret(p, 'TwinParameter')
  return true
}

export function isValidDigitalTwinModel(m: unknown): m is DigitalTwinModel {
  if (!isObject(m)) return false
  if (typeof m.id !== 'string' || m.id.length === 0) return false
  if (typeof m.name !== 'string' || m.name.length === 0) return false
  if (typeof m.domain !== 'string') return false
  if (!Array.isArray(m.inputs)) return false
  if (!m.inputs.every((x) => typeof x === 'string' && x.length > 0)) return false
  if (!Array.isArray(m.outputs)) return false
  if (!m.outputs.every((x) => typeof x === 'string' && x.length > 0)) return false
  if (!Array.isArray(m.parameters)) return false
  if (!m.parameters.every((p) => isValidTwinParameter(p))) return false
  if (!isValidScore(m.accuracy)) return false
  if (!isValidModelStatus(m.status)) return false
  if (!isValidTimestamp(m.createdAt)) return false
  if (!isValidTimestamp(m.updatedAt)) return false
  assertNoSecret(m, 'DigitalTwinModel')
  return true
}

export function isValidTwinPrediction(p: unknown): p is TwinPrediction {
  if (!isObject(p)) return false
  if (typeof p.modelId !== 'string' || p.modelId.length === 0) return false
  if (!isObject(p.input)) return false
  for (const [, v] of Object.entries(p.input)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return false
  }
  if (!isObject(p.output)) return false
  for (const [, v] of Object.entries(p.output)) {
    if (typeof v !== 'number' || !Number.isFinite(v)) return false
  }
  if (!isValidScore(p.confidence)) return false
  if (!isValidTimestamp(p.timestamp)) return false
  assertNoSecret(p, 'TwinPrediction')
  return true
}

export const __testHelpers = {
  MODEL_STATUSES, PREDICTION_KINDS,
  VALID_MODEL_STATUSES, VALID_PREDICTION_KINDS,
  FORBIDDEN, findForbidden
}