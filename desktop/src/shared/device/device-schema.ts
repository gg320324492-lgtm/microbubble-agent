// Device Schema — 科研设备契约。

// ============ Enums ============

export type DeviceType = 'pump' | 'ozone-generator' | 'sensor' | 'reactor' | 'controller'
export const DEVICE_TYPES: readonly DeviceType[] = Object.freeze([
  'pump', 'ozone-generator', 'sensor', 'reactor', 'controller'
])

export type DeviceStatus = 'offline' | 'connecting' | 'online' | 'error'
export const DEVICE_STATUSES: readonly DeviceStatus[] = Object.freeze([
  'offline', 'connecting', 'online', 'error'
])

// ============ Core types ============

export interface DeviceParameter {
  name: string
  value: string | number | boolean
  unit: string
}

export interface ScientificDevice {
  id: string
  name: string
  type: DeviceType
  protocol: string
  status: DeviceStatus
  parameters: DeviceParameter[]
  lastSeen: number
  createdAt: number
}

export interface SensorReading {
  deviceId: string
  timestamp: number
  metric: string
  value: number
  unit: string
}

// ============ Validators ============

const VALID_DEVICE_TYPES: ReadonlySet<DeviceType> = new Set(DEVICE_TYPES)
const VALID_DEVICE_STATUSES: ReadonlySet<DeviceStatus> = new Set(DEVICE_STATUSES)

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
  if (hit) throw new Error(`device schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-K2 strict)`)
}

function isValidTimestamp(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v)
}

export function isValidDeviceType(t: unknown): t is DeviceType {
  return typeof t === 'string' && VALID_DEVICE_TYPES.has(t as DeviceType)
}

export function isValidDeviceStatus(s: unknown): s is DeviceStatus {
  return typeof s === 'string' && VALID_DEVICE_STATUSES.has(s as DeviceStatus)
}

export function isValidDeviceParameter(p: unknown): p is DeviceParameter {
  if (!isObject(p)) return false
  if (typeof p.name !== 'string' || p.name.length === 0) return false
  if (typeof p.unit !== 'string') return false
  if (typeof p.value !== 'string' && typeof p.value !== 'number' && typeof p.value !== 'boolean') return false
  assertNoSecret(p, 'DeviceParameter')
  return true
}

export function isValidScientificDevice(d: unknown): d is ScientificDevice {
  if (!isObject(d)) return false
  if (typeof d.id !== 'string' || d.id.length === 0) return false
  if (typeof d.name !== 'string' || d.name.length === 0) return false
  if (!isValidDeviceType(d.type)) return false
  if (typeof d.protocol !== 'string') return false
  if (!isValidDeviceStatus(d.status)) return false
  if (!Array.isArray(d.parameters)) return false
  if (!d.parameters.every((p) => isValidDeviceParameter(p))) return false
  if (!isValidTimestamp(d.lastSeen)) return false
  if (!isValidTimestamp(d.createdAt)) return false
  assertNoSecret(d, 'ScientificDevice')
  return true
}

export function isValidSensorReading(r: unknown): r is SensorReading {
  if (!isObject(r)) return false
  if (typeof r.deviceId !== 'string' || r.deviceId.length === 0) return false
  if (!isValidTimestamp(r.timestamp)) return false
  if (typeof r.metric !== 'string' || r.metric.length === 0) return false
  if (typeof r.value !== 'number' || !Number.isFinite(r.value)) return false
  if (typeof r.unit !== 'string') return false
  assertNoSecret(r, 'SensorReading')
  return true
}

export const __testHelpers = {
  DEVICE_TYPES, DEVICE_STATUSES,
  VALID_DEVICE_TYPES, VALID_DEVICE_STATUSES,
  FORBIDDEN, findForbidden
}