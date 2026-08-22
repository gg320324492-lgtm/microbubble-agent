// Capability Router (Phase 6-C2: Agent Capability Router).
//
// Phase 6-C2: main-process router that picks the best provider+model for
// a given ResearchTaskProfile. Uses:
//   - Phase 6-C1 capability-resolver (capability matching + ranking)
//   - Phase 6-A4 ConfigStore + hasKey check (provider must have a key)
//   - Phase 6-A2 SecretStore existence check (key actually present)
//
// Phase 6-C2 frozen contract:
//   - routeResearchTask(profile)        -> RouterDecision | null
//   - RouterDecision carries: providerId, model, profile, reason, source
//   - NEVER includes apiKey in the return shape (renderer-visible)
//
// Phase 6-C2 strict:
//   - Falls back to active provider (Phase 6-A5) when no candidate matches
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
}

/**
 * Phase 6-C2: rank candidates by capability overlap with task profile.
 * Returns the highest-scoring candidate that also has an API key stored.
 *
 * Tie-breaker: alphabetical providerId for determinism.
 */
function pickBestCandidate(
  candidates: CapabilityMatch[],
  profile: ResearchTaskProfile
): CapabilityMatch | null {
  const required = profile.requiredCapabilities
  const optional = profile.optionalCapabilities ?? []
  const eligible = candidates
    .filter((c) => hasAllCapabilities(c, required))
    .filter((c) => keyExists(c.providerId))
    .map((c) => {
      const requiredScore = required.length
      const optionalScore = optional.filter((cap) => c.profile.capabilities.includes(cap)).length
      const priorityBoost = (profile.priority ?? 5) / 10
      return { c, score: requiredScore * 10 + optionalScore + priorityBoost }
    })
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.c.providerId.localeCompare(b.c.providerId)
    })
  return eligible[0]?.c ?? null
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

  // Step 3: pick best candidate with required caps + key
  const best = pickBestCandidate(candidates, effective)
  if (best) {
    assertProfileSafe(best.profile)
    return {
      providerId: best.providerId,
      model: best.model,
      profile: best.profile,
      source: 'capability-match',
      reason: `matched task='${effective.taskType}' required=[${effective.requiredCapabilities.join(',')}]`
    }
  }

  // Step 4: fall back to active provider
  const active = getActive()
  if (active && keyExists(active.providerId)) {
    const match = resolveModelCapability(active.providerId, active.model)
    if (match) {
      assertProfileSafe(match.profile)
      return {
        providerId: match.providerId,
        model: match.model,
        profile: match.profile,
        source: 'active-provider',
        reason: `no capability match for task='${effective.taskType}' — fell back to active provider`
      }
    }
  }

  // Step 5: no candidate, no active provider
  return null
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
