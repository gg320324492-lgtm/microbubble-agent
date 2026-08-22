// Capability Resolver (Phase 6-C1: Model Capability Intelligence Foundation).
//
// Phase 6-C1: main-process resolver that maps (providerId, model) -> research
// capability profile. Three resolution paths:
//   1. ProviderConfigStore researchProfile (Phase 6-C1: user-configurable per-provider)
//   2. ProviderRegistryMeta researchProfile (Phase 6-C1: hardcoded by factory)
//   3. unknown fallback (returns { source: 'unknown', capabilities: ['chat'] })
//
// Phase 6-C1 frozen contract:
//   - resolveModelCapability(providerId, model?) -> CapabilityMatch
//   - matchTaskCapability(taskCaps)             -> CapabilityMatch[]
//   - CapabilityMatch NEVER contains apiKey / token / cipher
//
// Used by:
//   - Future Agent Router (Phase 6-C2): pick best provider+model for a task
//   - Chat header UI (Phase 6-C1 extension): display capability chips

import {
  isValidResearchCapability,
  type ResearchCapability,
  type ModelResearchProfile,
  assertProfileSafe
} from '@shared/model/research-capability'
import { getConfig } from './provider-config-store'
import { listProviders as registryListProviders } from './registry'

export type CapabilitySource = 'config' | 'registry' | 'unknown'

/**
 * Phase 6-C1: result of a capability lookup.
 */
export interface CapabilityMatch {
  providerId: string
  model: string
  source: CapabilitySource
  profile: ModelResearchProfile
}

/**
 * Phase 6-C1: minimum default profile used when no metadata is available.
 */
function defaultUnknownProfile(providerId: string, model: string): ModelResearchProfile {
  return {
    providerId,
    model,
    capabilities: ['chat']
  }
}

/**
 * Phase 6-C1: build a CapabilityMatch from a profile (with secret guard).
 */
function buildMatch(
  providerId: string,
  model: string,
  profile: ModelResearchProfile,
  source: CapabilitySource
): CapabilityMatch {
  assertProfileSafe(profile)
  return { providerId, model, source, profile }
}

/**
 * Phase 6-C1: resolve the capability profile for (providerId, model).
 *
 * @param providerId  registered provider id
 * @param model       model name (defaults to registry's defaultModel)
 *
 * Resolution order (first non-null wins):
 *   1. ProviderConfigStore researchProfile (user-configurable)
 *   2. ProviderRegistryMeta researchProfile (factory-supplied)
 *   3. unknown fallback with { capabilities: ['chat'] }
 */
export function resolveModelCapability(
  providerId: string,
  model?: string
): CapabilityMatch | null {
  if (typeof providerId !== 'string' || providerId.length < 2) return null
  const cfg = getConfig(providerId)
  // Phase 6-C1: registry meta lookup is direct (does not require factory build).
  // This lets us read researchProfile without instantiating the provider.
  const meta = registryListProviders().find((m) => m.providerId === providerId)
  const modelName = model
    ?? cfg?.defaultModel
    ?? meta?.defaultModel
    ?? providerId
  if (cfg?.researchProfile) {
    // Phase 6-C1: ConfigStore stores capabilities as string[] (Phase 6-A4);
    // narrow to ResearchCapability[] here. Invalid tags are dropped (defensive).
    const rp = cfg.researchProfile
    const filtered = rp.capabilities.filter(isValidResearchCapability)
    return buildMatch(
      providerId,
      modelName,
      {
        providerId: rp.providerId,
        model: rp.model,
        capabilities: filtered,
        ...(typeof rp.maxContext === 'number' ? { maxContext: rp.maxContext } : {}),
        ...(Array.isArray(rp.strengths) ? { strengths: [...rp.strengths] } : {}),
        ...(Array.isArray(rp.limitations) ? { limitations: [...rp.limitations] } : {})
      },
      'config'
    )
  }
  if (meta?.researchProfile) {
    return buildMatch(providerId, modelName, meta.researchProfile, 'registry')
  }
  return buildMatch(
    providerId,
    modelName,
    defaultUnknownProfile(providerId, modelName),
    'unknown'
  )
}

/**
 * Phase 6-C1: rank registered providers by how well they match a task's
 * required capabilities. Phase 6-C2 (Agent Router) consumes the result.
 *
 * @param taskCaps required ResearchCapability list for the task
 * @returns ranked list — best match first. Items with zero overlap are
 *          still returned (sorted last) so the caller can fall back.
 */
export function matchTaskCapability(
  taskCaps: ResearchCapability[]
): CapabilityMatch[] {
  const validCaps = taskCaps.filter(isValidResearchCapability)
  const all = registryListProviders()
  const scored: Array<{ match: CapabilityMatch; score: number }> = []
  for (const meta of all) {
    const match = resolveModelCapability(meta.providerId, meta.defaultModel)
    if (!match) continue
    const overlap = match.profile.capabilities.filter((c) => validCaps.includes(c)).length
    scored.push({ match, score: overlap })
  }
  scored.sort((a, b) => b.score - a.score)
  return scored.map((s) => s.match)
}

/**
 * Phase 6-C1: returns true if a model has ALL of the required capabilities.
 */
export function hasAllCapabilities(
  match: CapabilityMatch,
  required: ResearchCapability[]
): boolean {
  const validRequired = required.filter(isValidResearchCapability)
  return validRequired.every((c) => match.profile.capabilities.includes(c))
}

/**
 * Phase 6-C1: returns true if a model has ANY of the required capabilities.
 */
export function hasAnyCapability(
  match: CapabilityMatch,
  required: ResearchCapability[]
): boolean {
  const validRequired = required.filter(isValidResearchCapability)
  return validRequired.some((c) => match.profile.capabilities.includes(c))
}

export const __testHelpers = {
  defaultUnknownProfile
}
