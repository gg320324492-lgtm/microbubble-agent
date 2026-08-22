// Runtime Diagnostics (Phase 6-D: Live E2E Validation).
//
// Phase 6-D: per-provider debug snapshot for runtime observability.
// Combines data from:
//   - Phase 6-A3 registry (providerId, displayName, defaultModel)
//   - Phase 6-A4 ConfigStore (endpoint, capabilities, hasKey)
//   - Phase 6-C4 health-tracker (status, latency, failures)
//   - Phase 6-C4 metrics-store (requests, successes, failures, p50/p95)
//   - Phase 6-C4 budget-manager (limit, used, remaining)
//   - Phase 6-A2 SecretStore existence (hasApiKey boolean ONLY — never the key itself)
//
// Phase 6-D strict forbids:
//   - NEVER include apiKey / token / cipher / Authorization
//   - NEVER include the actual key value in any return shape
//   - Defensive: throws if the snapshot JSON would leak a key

import type { ProviderConnectionStatus } from './model-runtime-status'
import { listProviders } from './registry'
import { getConfig } from './provider-config-store'
import { exists as keyExists } from './model-secret-store'
import { getHealth } from './health-tracker'
import { snapshot as metricsSnapshot } from './metrics-store'
import { getUsage } from './budget-manager'
import { resolveModelCapability } from './capability-resolver'

export interface ProviderDiagnostics {
  providerId: string
  displayName: string
  defaultModel: string
  type: 'cloud' | 'local' | 'openai-compatible' | 'unknown'
  status: ProviderConnectionStatus
  latencyMs: number | null
  successRate: number  // 0..1; null => no requests yet
  totalRequests: number
  lastUsed: number | null  // epoch ms
  capabilities: string[]
  hasApiKey: boolean  // Phase 6-D strict: BOOLEAN ONLY — never the key value
  budget: {
    limit: number  // 0 = unlimited
    used: number
    remaining: number  // Infinity when limit = 0
  }
  researchCapabilities: string[]  // Phase 6-C1
}

const FORBIDDEN_SUBSTRINGS = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'Authorization']

/**
 * Phase 6-D: build a diagnostic snapshot for one provider.
 * Returns null if the provider is not in the registry.
 *
 * @throws if the snapshot would leak a secret (defense in depth).
 */
export function getProviderDiagnostics(providerId: string): ProviderDiagnostics | null {
  if (typeof providerId !== 'string' || providerId.length === 0) return null
  const meta = listProviders().find((m) => m.providerId === providerId)
  if (!meta) return null
  const cfg = getConfig(providerId)
  const health = getHealth(providerId)
  const metrics = metricsSnapshot(providerId)
  const budget = getUsage(providerId)
  const capability = resolveModelCapability(providerId, cfg?.defaultModel ?? providerId)
  const researchCaps = capability?.profile.capabilities ?? []

  // Phase 6-D: success rate over total successful+failed requests
  const successRate = metrics.requests === 0 ? 1 : metrics.successes / metrics.requests
  const latencyMs = metrics.successes === 0 ? null : metrics.p50
  const lastUsed = metrics.updatedAt && metrics.requests > 0 ? metrics.updatedAt : null

  const status: ProviderConnectionStatus =
    health.state === 'cooldown' ? 'failed' :
    health.state === 'degraded' ? 'checking' :
    health.state === 'healthy' ? 'connected' :
    'unknown'

  const out: ProviderDiagnostics = {
    providerId,
    displayName: meta.displayName,
    defaultModel: meta.defaultModel,
    type: cfg?.type ?? 'unknown',
    status,
    latencyMs,
    successRate: Math.round(successRate * 100) / 100,
    totalRequests: metrics.requests,
    lastUsed,
    capabilities: cfg?.capabilities ?? [],
    hasApiKey: keyExists(providerId),
    budget: {
      limit: budget.limit,
      used: budget.used,
      remaining: budget.limit === 0 ? Number.POSITIVE_INFINITY : Math.max(0, budget.limit - budget.used)
    },
    researchCapabilities: researchCaps
  }
  assertSnapshotSafe(out)
  return out
}

/**
 * Phase 6-D: snapshot every registered provider.
 * Skips providers that aren't in the registry.
 */
export function getAllProviderDiagnostics(): ProviderDiagnostics[] {
  const out: ProviderDiagnostics[] = []
  for (const m of listProviders()) {
    const snap = getProviderDiagnostics(m.providerId)
    if (snap) out.push(snap)
  }
  return out
}

/**
 * Phase 6-D: defensive — throws if the snapshot JSON contains any
 * secret-like substring. Used by getProviderDiagnostics before returning.
 */
export function assertSnapshotSafe(snap: ProviderDiagnostics): void {
  const dump = JSON.stringify(snap)
  for (const bad of FORBIDDEN_SUBSTRINGS) {
    if (dump.includes(bad)) {
      throw new Error(`runtime-diagnostics: snapshot leaks forbidden substring '${bad}' (Phase 6-D strict)`)
    }
  }
}

export const __testHelpers = {
  FORBIDDEN_SUBSTRINGS
}
