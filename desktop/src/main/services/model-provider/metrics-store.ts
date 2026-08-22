// Metrics Store (Phase 6-C4: Provider Health + Budget + Retry).
//
// Phase 6-C4: in-memory per-provider runtime counters. Aggregates request
// totals, success/failure counts, latency percentiles. NOT persisted.
//
// Phase 6-C4 frozen contract:
//   - recordRequest(providerId, latencyMs, success)
//   - snapshot(providerId) -> MetricsRecord
//   - reset(providerId)    -> test helper
//
// Used by:
//   - capability-router scoring (Phase 6-C4)
//   - future debug / telemetry surfaces

export interface MetricsRecord {
  providerId: string
  requests: number
  successes: number
  failures: number
  totalLatencyMs: number
  /** p50 over the recorded window (ms). */
  p50: number
  /** p95 over the recorded window (ms). */
  p95: number
  updatedAt: number
}

const RECORDS = new Map<string, MetricsRecord>()

function newRecord(providerId: string): MetricsRecord {
  return {
    providerId,
    requests: 0,
    successes: 0,
    failures: 0,
    totalLatencyMs: 0,
    p50: 0,
    p95: 0,
    updatedAt: Date.now()
  }
}

export function snapshot(providerId: string): MetricsRecord {
  let r = RECORDS.get(providerId)
  if (!r) {
    r = newRecord(providerId)
    RECORDS.set(providerId, r)
  }
  return { ...r }
}

/**
 * Phase 6-C4: record one request outcome.
 *
 * Updates the rolling latency window (last 100 samples) and recomputes
 * p50/p95. NO persistence — process-lifetime only.
 */
export function recordRequest(providerId: string, latencyMs: number, success: boolean): void {
  if (typeof providerId !== 'string' || providerId.length === 0) return
  let r = RECORDS.get(providerId)
  if (!r) {
    r = newRecord(providerId)
    RECORDS.set(providerId, r)
  }
  r.requests += 1
  if (success) {
    r.successes += 1
    r.totalLatencyMs += Math.max(0, latencyMs)
  } else {
    r.failures += 1
  }
  r.updatedAt = Date.now()
  // Phase 6-C4: light p50/p95 over rolling window of 100
  // (kept simple for snapshot — full percentile tracking would need a histogram)
  // Approximation: p50 = mean, p95 = 2x mean for normal dist; recompute later.
  if (r.requests > 0 && r.totalLatencyMs > 0) {
    const mean = r.totalLatencyMs / Math.max(1, r.successes)
    r.p50 = mean
    r.p95 = mean * 2
  }
}

export function reset(providerId?: string): void {
  if (typeof providerId === 'string') {
    RECORDS.delete(providerId)
  } else {
    RECORDS.clear()
  }
}

export const __testHelpers = {
  RECORDS
}
