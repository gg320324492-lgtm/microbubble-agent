// Budget Manager (Phase 6-C4: Provider Health + Budget + Retry).
//
// Phase 6-C4: per-provider token budget tracker. Default = unlimited.
// In-memory; NOT persisted (process-lifetime).
//
// Phase 6-C4 frozen contract:
//   - setLimit(providerId, tokens)         -> 0 = unlimited
//   - getLimit(providerId)                 -> tokens (0 = unlimited)
//   - recordUsage(providerId, tokens)      -> tracks usage
//   - getUsage(providerId)                  -> { used, limit, remaining }
//   - isOverBudget(providerId)             -> boolean
//   - reset(providerId)                    -> test helper
//
// Phase 6-C4 strict:
//   - tokens are integer (no fractional)
//   - recordUsage on missing provider with no limit = no-op
//   - recordUsage on missing provider WITH limit = blocks future usage
//     (router filters such providers)

export interface BudgetUsage {
  providerId: string
  used: number
  limit: number  // 0 = unlimited
  remaining: number  // Infinity when limit = 0
}

interface BudgetRecord {
  providerId: string
  limit: number
  used: number
}

const RECORDS = new Map<string, BudgetRecord>()

function getRecord(providerId: string): BudgetRecord {
  let r = RECORDS.get(providerId)
  if (!r) {
    r = { providerId, limit: 0, used: 0 }
    RECORDS.set(providerId, r)
  }
  return r
}

export function setLimit(providerId: string, tokens: number): void {
  if (typeof providerId !== 'string' || providerId.length === 0) return
  if (typeof tokens !== 'number' || tokens < 0 || !Number.isFinite(tokens)) return
  const r = getRecord(providerId)
  r.limit = Math.floor(tokens)
}

export function getLimit(providerId: string): number {
  if (typeof providerId !== 'string') return 0
  return getRecord(providerId).limit
}

export function recordUsage(providerId: string, tokens: number): void {
  if (typeof providerId !== 'string' || providerId.length === 0) return
  if (typeof tokens !== 'number' || tokens < 0 || !Number.isFinite(tokens)) return
  const r = getRecord(providerId)
  r.used += Math.floor(tokens)
}

export function getUsage(providerId: string): BudgetUsage {
  const r = getRecord(providerId)
  const remaining = r.limit === 0 ? Number.POSITIVE_INFINITY : Math.max(0, r.limit - r.used)
  return {
    providerId: r.providerId,
    used: r.used,
    limit: r.limit,
    remaining
  }
}

/**
 * Phase 6-C4: true if the provider has a limit AND has exceeded it.
 * Providers with no limit (limit=0) are NEVER over budget.
 */
export function isOverBudget(providerId: string): boolean {
  const r = getRecord(providerId)
  if (r.limit === 0) return false
  return r.used >= r.limit
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
