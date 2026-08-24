// Experiment Control Schema — 统一实验控制中心契约。

// ============ Enums ============

export type ControlActionKind = 'start' | 'pause' | 'stop' | 'adjust' | 'switch' | 'record'
export const CONTROL_ACTION_KINDS: readonly ControlActionKind[] = Object.freeze([
  'start', 'pause', 'stop', 'adjust', 'switch', 'record'
])

export type AlertSeverity = 'info' | 'warning' | 'critical'
export const ALERT_SEVERITIES: readonly AlertSeverity[] = Object.freeze([
  'info', 'warning', 'critical'
])

// ============ Core types ============

export interface ControlDashboard {
  id: string
  experimentId: string
  title: string
  deviceIds: string[]
  metrics: string[]
  createdAt: number
  updatedAt: number
}

export interface DeviceStatusPanel {
  deviceId: string
  name: string
  type: string
  status: string
  lastSeen: number
  recentReadings: number
}

export interface RealtimeMetric {
  metric: string
  value: number
  unit: string
  timestamp: number
  deviceId: string
}

export interface ExperimentTimelineEntry {
  id: string
  experimentId: string
  timestamp: number
  event: string
  description: string
}

export interface AIRecommendation {
  id: string
  experimentId: string
  kind: string
  title: string
  rationale: string
  confidence: number
  createdAt: number
}

export interface ControlAction {
  id: string
  dashboardId: string
  kind: ControlActionKind
  target: string
  parameters: Record<string, string | number | boolean>
  issuedAt: number
}

// ============ Validators ============

const VALID_CONTROL_ACTION_KINDS: ReadonlySet<ControlActionKind> = new Set(CONTROL_ACTION_KINDS)
const VALID_ALERT_SEVERITIES: ReadonlySet<AlertSeverity> = new Set(ALERT_SEVERITIES)

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
  if (hit) throw new Error(`control center schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-K3 strict)`)
}

function isValidTimestamp(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

export function isValidControlActionKind(k: unknown): k is ControlActionKind {
  return typeof k === 'string' && VALID_CONTROL_ACTION_KINDS.has(k as ControlActionKind)
}

export function isValidAlertSeverity(s: unknown): s is AlertSeverity {
  return typeof s === 'string' && VALID_ALERT_SEVERITIES.has(s as AlertSeverity)
}

export function isValidControlDashboard(d: unknown): d is ControlDashboard {
  if (!isObject(d)) return false
  if (typeof d.id !== 'string' || d.id.length === 0) return false
  if (typeof d.experimentId !== 'string') return false
  if (typeof d.title !== 'string') return false
  if (!Array.isArray(d.deviceIds)) return false
  if (!d.deviceIds.every((x) => typeof x === 'string')) return false
  if (!Array.isArray(d.metrics)) return false
  if (!d.metrics.every((x) => typeof x === 'string')) return false
  if (!isValidTimestamp(d.createdAt)) return false
  if (!isValidTimestamp(d.updatedAt)) return false
  assertNoSecret(d, 'ControlDashboard')
  return true
}

export function isValidDeviceStatusPanel(p: unknown): p is DeviceStatusPanel {
  if (!isObject(p)) return false
  if (typeof p.deviceId !== 'string' || p.deviceId.length === 0) return false
  if (typeof p.name !== 'string') return false
  if (typeof p.type !== 'string') return false
  if (typeof p.status !== 'string') return false
  if (!isValidTimestamp(p.lastSeen)) return false
  if (typeof p.recentReadings !== 'number' || !Number.isFinite(p.recentReadings)) return false
  assertNoSecret(p, 'DeviceStatusPanel')
  return true
}

export function isValidRealtimeMetric(m: unknown): m is RealtimeMetric {
  if (!isObject(m)) return false
  if (typeof m.metric !== 'string' || m.metric.length === 0) return false
  if (typeof m.value !== 'number' || !Number.isFinite(m.value)) return false
  if (typeof m.unit !== 'string') return false
  if (!isValidTimestamp(m.timestamp)) return false
  if (typeof m.deviceId !== 'string') return false
  assertNoSecret(m, 'RealtimeMetric')
  return true
}

export function isValidExperimentTimelineEntry(e: unknown): e is ExperimentTimelineEntry {
  if (!isObject(e)) return false
  if (typeof e.id !== 'string' || e.id.length === 0) return false
  if (typeof e.experimentId !== 'string') return false
  if (!isValidTimestamp(e.timestamp)) return false
  if (typeof e.event !== 'string') return false
  if (typeof e.description !== 'string') return false
  assertNoSecret(e, 'ExperimentTimelineEntry')
  return true
}

export function isValidAIRecommendation(r: unknown): r is AIRecommendation {
  if (!isObject(r)) return false
  if (typeof r.id !== 'string' || r.id.length === 0) return false
  if (typeof r.experimentId !== 'string') return false
  if (typeof r.kind !== 'string') return false
  if (typeof r.title !== 'string' || r.title.length === 0) return false
  if (typeof r.rationale !== 'string') return false
  if (typeof r.confidence !== 'number' || !Number.isFinite(r.confidence) || r.confidence < 0 || r.confidence > 1) return false
  if (!isValidTimestamp(r.createdAt)) return false
  assertNoSecret(r, 'AIRecommendation')
  return true
}

export function isValidControlAction(a: unknown): a is ControlAction {
  if (!isObject(a)) return false
  if (typeof a.id !== 'string' || a.id.length === 0) return false
  if (typeof a.dashboardId !== 'string') return false
  if (!isValidControlActionKind(a.kind)) return false
  if (typeof a.target !== 'string') return false
  if (!isObject(a.parameters)) return false
  for (const [, v] of Object.entries(a.parameters)) {
    if (typeof v !== 'string' && typeof v !== 'number' && typeof v !== 'boolean') return false
  }
  if (!isValidTimestamp(a.issuedAt)) return false
  assertNoSecret(a, 'ControlAction')
  return true
}

export const __testHelpers = {
  CONTROL_ACTION_KINDS, ALERT_SEVERITIES,
  VALID_CONTROL_ACTION_KINDS, VALID_ALERT_SEVERITIES,
  FORBIDDEN, findForbidden
}