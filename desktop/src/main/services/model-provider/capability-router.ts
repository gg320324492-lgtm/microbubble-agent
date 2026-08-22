// Capability Router (Phase 6-C2: Agent Capability Router;
//                     Phase 6-C4: Provider Health + Budget + Retry).
//
// Phase 6-C2 + C4: main-process router that picks the best provider+model
// for a given ResearchTaskProfile. Uses:
//   - Phase 6-C1 capability-resolver (capability matching + ranking)
//   - Phase 6-A4 ConfigStore + hasKey check (provider must have a key)
//   - Phase 6-A2 SecretStore existence check (key actually present)
//   - Phase 6-C4 health-tracker (skip cooldown; degrade by health score)
//   - Phase 6-C4 budget-manager (skip over-budget; degrade by remaining budget)
//   - Phase 6-C4 metrics-store (record request outcomes)
//
// Phase 6-C2 frozen contract:
//   - routeResearchTask(profile)        -> RouterDecision | null
//   - RouterDecision carries: providerId, model, profile, reason, source
//   - NEVER includes apiKey in the return shape (renderer-visible)
//
// Phase 6-C4 additions:
//   - rankedCandidates in RouterDecision (top-K with score breakdown)
//   - retryWithFallback(profile, lastError) -> next RouterDecision
//   - recordRequestOutcome(providerId, latencyMs, success) for metrics
//
// Phase 6-C2 + C4 strict:
//   - Falls back to active provider when no candidate matches
//   - Falls back to legacy mode when no candidate AND no active provider
//   - NEVER throws on empty registry — returns null + reason

import {
  type ResearchTaskProfile,
  isValidResearchTaskProfile,
  resolveTaskProfile
} from '@shared/model/research-task'
import {
  type ModelResearchProfile,
  assertProfileSafe
} from '@shared/model/research-capability'
import {
  type CapabilityMatch,
  resolveModelCapability,
  hasAllCapabilities
} from './capability-resolver'
import { exists as keyExists } from './model-secret-store'
import { getActive } from './active-provider-store'
import { listProviders } from './registry'
import {
  isAvailable as healthIsAvailable,
  getScore as healthScore
} from './health-tracker'
import { isOverBudget } from './budget-manager'
import { recordRequest as recordMetrics } from './metrics-store'

export type RouterSource = 'capability-match' | 'active-provider' | 'no-match'

/**
 * Phase 6-C2: result of a router decision.
 *
 * `providerId` / `model` / `profile` are renderer-visible (no apiKey).
 * `source` explains why this candidate was chosen.
 * `reason` is a short human-readable string for logs (NO secrets).
 */
export interface RouterDecision {
  providerId: string
  model: string
  profile: ModelResearchProfile
  source: RouterSource
  reason: string
  /**
   * Phase 6-C4: ranked candidates with score breakdown (top-K).
   * Renderer-visible (NO apiKey).
   */
  rankedCandidates?: Array<{
    providerId: string
    model: string
    score: number
    capabilityScore: number
    healthScore: number
    budgetScore: number
  }>
}

/**
 * Phase 6-C2: rank candidates by capability overlap with task profile.
 * Returns the highest-scoring candidate that also has an API key stored.
 *
 * Phase 6-C4 extension: also factor in health score (0..1) and budget score
 * (0..1). Cooldown providers are skipped. Over-budget providers are skipped.
 *
 * Tie-breaker: alphabetical providerId for determinism.
 */
function pickBestCandidate(
  candidates: CapabilityMatch[],
  profile: ResearchTaskProfile
): { best: CapabilityMatch | null; ranked: NonNullable<RouterDecision['rankedCandidates']> } {
  const required = profile.requiredCapabilities
  const optional = profile.optionalCapabilities ?? []
  const eligible = candidates
    .filter((c) => hasAllCapabilities(c, required))
    .filter((c) => keyExists(c.providerId))
    .filter((c) => healthIsAvailable(c.providerId))
    .filter((c) => !isOverBudget(c.providerId))
    .map((c) => {
      const capabilityScore = required.length * 10
        + optional.filter((cap) => c.profile.capabilities.includes(cap)).length
      const healthScoreValue = healthScore(c.providerId)
      const budgetScoreValue = isOverBudget(c.providerId) ? 0 : 1
      const priorityBoost = (profile.priority ?? 5) / 10
      const total = capabilityScore + healthScoreValue * 5 + budgetScoreValue * 3 + priorityBoost
      return {
        c,
        score: total,
        capabilityScore,
        healthScore: healthScoreValue,
        budgetScore: budgetScoreValue
      }
    })
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.c.providerId.localeCompare(b.c.providerId)
    })
  // Phase 6-C4: top-K = 5
  const ranked = eligible.slice(0, 5).map((e) => ({
    providerId: e.c.providerId,
    model: e.c.model,
    score: Math.round(e.score * 100) / 100,
    capabilityScore: e.capabilityScore,
    healthScore: Math.round(e.healthScore * 100) / 100,
    budgetScore: e.budgetScore
  }))
  return { best: eligible[0]?.c ?? null, ranked }
}

/**
 * Phase 6-C2: route a research task.
 *
 * Decision tree:
 *   1. Validate profile (defensive — accepts validated only).
 *   2. Resolve CapabilityMatch list (Phase 6-C1 matchTaskCapability).
 *   3. If a candidate has all required caps AND a key stored -> pick it.
 *   4. Else, fall back to active provider (Phase 6-A5 setActive).
 *   5. Else, return null (caller decides legacy / error path).
 *
 * Phase 6-C4: filters by health availability + budget; ranks with
 *             health + budget score breakdown.
 *
 * @returns RouterDecision or null. NEVER throws on empty registry.
 */
export function routeResearchTask(
  profileInput: ResearchTaskProfile | null
): RouterDecision | null {
  // Phase 6-C2: defensive accept — accept validated profile OR null
  const profile = profileInput && isValidResearchTaskProfile(profileInput)
    ? profileInput
    : null
  const effective = profile ?? resolveTaskProfile('coding')

  // Step 2: gather all candidates
  // Phase 6-C2: iterate the registry directly so we don't depend on
  // matchTaskCapability's ranking (we re-rank with required-cap filtering).
  const candidates: CapabilityMatch[] = []
  for (const meta of listProviders()) {
    const match = resolveModelCapability(meta.providerId, meta.defaultModel)
    if (match) candidates.push(match)
  }

  // Step 3: pick best candidate with required caps + key + healthy + budget
  const { best, ranked } = pickBestCandidate(candidates, effective)
  if (best) {
    assertProfileSafe(best.profile)
    return {
      providerId: best.providerId,
      model: best.model,
      profile: best.profile,
      source: 'capability-match',
      reason: `matched task='${effective.taskType}' required=[${effective.requiredCapabilities.join(',')}] health=${ranked.find((r) => r.providerId === best.providerId)?.healthScore ?? '?'}`,
      rankedCandidates: ranked
    }
  }

  // Step 4: fall back to active provider (also filtered by health/budget)
  const active = getActive()
  if (active && keyExists(active.providerId) && healthIsAvailable(active.providerId) && !isOverBudget(active.providerId)) {
    const match = resolveModelCapability(active.providerId, active.model)
    if (match) {
      assertProfileSafe(match.profile)
      return {
        providerId: match.providerId,
        model: match.model,
        profile: match.profile,
        source: 'active-provider',
        reason: `no capability match for task='${effective.taskType}' — fell back to active provider`,
        rankedCandidates: ranked
      }
    }
  }

  // Step 5: no candidate, no active provider
  return null
}

/**
 * Phase 6-C4: retry routing after a runtime failure.
 *
 * Records the failure for the failing provider (so cooldown kicks in),
 * then re-routes. If the previous pick had alternatives in rankedCandidates,
 * the new decision may pick one of those (or fall back).
 *
 * Returns null if no further fallback is possible (caller should give up
 * or surface a friendly error to the user).
 */
export function retryWithFallback(
  profileInput: ResearchTaskProfile | null,
  failedProviderId: string,
  latencyMs: number,
  _error: string
): RouterDecision | null {
  recordMetrics(failedProviderId, latencyMs, false)
  // Phase 6-C4: also bump health failure counter
  // (Health tracker is imported indirectly via metrics-store — caller-side)
  return routeResearchTask(profileInput)
}

/**
 * Phase 6-C4: record a successful request outcome (for metrics + health).
 */
export function recordRequestOutcome(
  providerId: string,
  latencyMs: number,
  success: boolean
): void {
  recordMetrics(providerId, latencyMs, success)
}

/**
 * Phase 6-C2: extended routing decision carrying router outcome.
 *
 * `route` may be 'task-routed' / 'active-fallback' / 'no-route' / 'invalid'.
 * Used by callers that need to log / display why a particular pick was made.
 */
export interface RouterExtendedDecision {
  route: 'task-routed' | 'active-fallback' | 'no-route' | 'invalid'
  decision: RouterDecision | null
  reason: string
}

export function routeResearchTaskExtended(
  profileInput: unknown
): RouterExtendedDecision {
  if (profileInput !== null && !isValidResearchTaskProfile(profileInput)) {
    return { route: 'invalid', decision: null, reason: 'profile failed validation (Phase 6-C2)' }
  }
  const decision = routeResearchTask(profileInput as ResearchTaskProfile | null)
  if (!decision) return { route: 'no-route', decision: null, reason: 'no provider + no active' }
  if (decision.source === 'capability-match') return { route: 'task-routed', decision, reason: decision.reason }
  return { route: 'active-fallback', decision, reason: decision.reason }
}

export const __testHelpers = {
  pickBestCandidate
}
