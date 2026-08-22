// Provider Health Tracker (Phase 6-C4: Provider Health + Budget + Retry).
//
// Phase 6-C4: in-memory per-provider health record. Tracks latency + failures
// over a rolling window; transitions providers to 'cooldown' after consecutive
// failures so the router can skip them.
//
// Phase 6-C4 frozen contract:
//   - recordSuccess(providerId, latencyMs)
//   - recordFailure(providerId, error?)
//   - isAvailable(providerId) -> boolean (false during cooldown)
//   - getScore(providerId)    -> 0..1 (lower = worse)
//   - getHealth(providerId)   -> HealthRecord
//   - clear(providerId)       -> reset (test helper)
//
// Phase 6-C4 strict:
//   - NEVER persists (process-lifetime)
//   - NEVER logs latencyMs in plaintext (kept in-memory only)
//   - Tests inject a clock for deterministic time-based logic

export type HealthState = 'healthy' | 'degraded' | 'cooldown' | 'unknown'

export interface HealthRecord {
  providerId: string
  state: HealthState
  /** Most recent N latency samples (rolling window). */
  recentLatencyMs: number[]
  failures: number
  successes: number
  lastSuccessAt: number | null
  lastFailureAt: number | null
  /** epoch ms when cooldown ends; null if not in cooldown. */
  cooldownUntil: number | null
  /** Last error message (no key material; safe for log). */
  lastError: string | null
}

const WINDOW_SIZE = 10
const FAILURE_THRESHOLD = 3
const COOLDOWN_MS = 60_000
const DEGRADED_P95_MS = 5_000

const RECORDS = new Map<string, HealthRecord>()

/**
 * Phase 6-C4: clock injection for tests.
 */
let _clock: () => number = () => Date.now()

export function setHealthClock(clock: () => number): void {
  _clock = clock
}

export function resetHealthClock(): void {
  _clock = () => Date.now()
}

function newRecord(providerId: string): HealthRecord {
  return {
    providerId,
    state: 'unknown',
    recentLatencyMs: [],
    failures: 0,
    successes: 0,
    lastSuccessAt: null,
    lastFailureAt: null,
    cooldownUntil: null,
    lastError: null
  }
}

export function getHealth(providerId: string): HealthRecord {
  let r = RECORDS.get(providerId)
  if (!r) {
    r = newRecord(providerId)
    RECORDS.set(providerId, r)
  }
  // Phase 6-C4: auto-recover from cooldown when time has passed
  if (r.cooldownUntil !== null && _clock() >= r.cooldownUntil) {
    r.cooldownUntil = null
    // Phase 6-C4: a successful recovery resets the failure count
    // (the cooldown itself signals "cool down"; next success will further clear).
    r.failures = 0
    r.state = 'healthy'
  }
  return r
}

export function recordSuccess(providerId: string, latencyMs: number): void {
  if (typeof providerId !== 'string' || providerId.length === 0) return
  const r = getHealth(providerId)
  r.successes += 1
  r.lastSuccessAt = _clock()
  r.recentLatencyMs.push(latencyMs)
  if (r.recentLatencyMs.length > WINDOW_SIZE) r.recentLatencyMs.shift()
  // Phase 6-C4: a success clears the consecutive failure count + cooldown
  if (r.failures > 0) r.failures = 0
  if (r.cooldownUntil !== null && _clock() >= r.cooldownUntil) {
    r.cooldownUntil = null
  }
  r.state = computeState(r)
  r.lastError = null
}

export function recordFailure(providerId: string, error?: string): void {
  if (typeof providerId !== 'string' || providerId.length === 0) return
  const r = getHealth(providerId)
  r.failures += 1
  r.lastFailureAt = _clock()
  if (error) r.lastError = error
  if (r.failures >= FAILURE_THRESHOLD) {
    r.cooldownUntil = _clock() + COOLDOWN_MS
    r.state = 'cooldown'
  } else {
    r.state = computeState(r)
  }
}

function computeState(r: HealthRecord): HealthState {
  if (r.cooldownUntil !== null && _clock() < r.cooldownUntil) return 'cooldown'
  if (r.recentLatencyMs.length === 0) return r.failures > 0 ? 'degraded' : 'healthy'
  const sorted = [...r.recentLatencyMs].sort((a, b) => a - b)
  const p95idx = Math.min(sorted.length - 1, Math.floor(sorted.length * 0.95))
  const p95 = sorted[p95idx]
  if (p95 > DEGRADED_P95_MS) return 'degraded'
  return 'healthy'
}

export function isAvailable(providerId: string): boolean {
  const r = getHealth(providerId)
  return r.state !== 'cooldown'
}

/**
 * Phase 6-C4: health score in [0..1]. Used by capability-router scoring.
 *   - state='healthy'   -> 1.0
 *   - state='degraded'  -> 0.5
 *   - state='cooldown'  -> 0.0 (router should skip anyway)
 *   - state='unknown'   -> 0.7 (neutral — no signal yet)
 */
export function getScore(providerId: string): number {
  const r = getHealth(providerId)
  switch (r.state) {
    case 'healthy': return 1.0
    case 'degraded': return 0.5
    case 'cooldown': return 0.0
    case 'unknown':
    default: return 0.7
  }
}

export function clear(providerId?: string): void {
  if (typeof providerId === 'string') {
    RECORDS.delete(providerId)
  } else {
    RECORDS.clear()
  }
}

export const __testHelpers = {
  WINDOW_SIZE,
  FAILURE_THRESHOLD,
  COOLDOWN_MS,
  DEGRADED_P95_MS,
  RECORDS
}
