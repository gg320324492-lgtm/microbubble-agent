// Research Capability Model (Phase 6-C1: Model Capability Intelligence Foundation).
//
// Phase 6-C1: domain-specific capability taxonomy for the MicroBubble
// research workflow. Distinct from Phase 6-A1 ModelCapability (which
// describes the chat API surface: streaming / tools / vision / etc.) —
// ResearchCapability describes WHAT the model is good at in our
// research domain (literature review, paper writing, CFD simulation).
//
// Phase 6-C1 frozen contract:
//   - ResearchCapability = 10-tag enum (see below)
//   - ModelResearchProfile = non-secret metadata
//   - Profile carries: providerId, model, capabilities, maxContext,
//     strengths, limitations
//   - NEVER contains apiKey / token / cipher
//
// Used by:
//   - ModelProviderConfig (Phase 6-A4) — optional researchProfile field
//   - ProviderRegistryMeta (Phase 6-A3) — optional researchProfile field
//   - CapabilityResolver (Phase 6-C1 main) — match task to model
//   - ModelSelector UI (Phase 6-C1) — display capability badges

export type ResearchCapability =
  | 'chat'
  | 'coding'
  | 'math'
  | 'matlab'
  | 'python'
  | 'cfd'
  | 'literature'
  | 'paper-writing'
  | 'image-analysis'
  | 'data-analysis'

/**
 * Phase 6-C1: renderable label for the chat header / selector UI.
 * Kept stable (do NOT rename without a Phase bump — UI depends on these).
 */
export function researchCapabilityLabel(cap: ResearchCapability): string {
  switch (cap) {
    case 'chat': return 'Chat'
    case 'coding': return 'Code'
    case 'math': return 'Math'
    case 'matlab': return 'MATLAB'
    case 'python': return 'Python'
    case 'cfd': return 'CFD'
    case 'literature': return 'Literature'
    case 'paper-writing': return 'Paper'
    case 'image-analysis': return 'Vision'
    case 'data-analysis': return 'Data'
  }
}

/**
 * Phase 6-C1: short glyph for capability chips (UI).
 */
export function researchCapabilityGlyph(cap: ResearchCapability): string {
  switch (cap) {
    case 'chat': return '💬'
    case 'coding': return '⌨️'
    case 'math': return '∑'
    case 'matlab': return '𝓜'
    case 'python': return '🐍'
    case 'cfd': return '🌊'
    case 'literature': return '📚'
    case 'paper-writing': return '📝'
    case 'image-analysis': return '🖼️'
    case 'data-analysis': return '📊'
  }
}

/**
 * Phase 6-C1: validate that a value is a known ResearchCapability.
 */
export function isValidResearchCapability(cap: unknown): cap is ResearchCapability {
  return (
    cap === 'chat' ||
    cap === 'coding' ||
    cap === 'math' ||
    cap === 'matlab' ||
    cap === 'python' ||
    cap === 'cfd' ||
    cap === 'literature' ||
    cap === 'paper-writing' ||
    cap === 'image-analysis' ||
    cap === 'data-analysis'
  )
}

/**
 * Phase 6-C1: research profile attached to a provider+model pair.
 * Non-secret metadata; renderer-visible.
 */
export interface ModelResearchProfile {
  providerId: string
  model: string
  capabilities: ResearchCapability[]
  /** Maximum context window size in tokens (approximate). */
  maxContext?: number
  /** Brief strength tags — 1-line human-readable (e.g. 'strong math reasoning'). */
  strengths?: string[]
  /** Brief limitation tags (e.g. 'no vision', 'zh-only'). */
  limitations?: string[]
}

/**
 * Phase 6-C1: validate a research profile shape.
 *
 * Phase 6-C1 strict: rejects any secret-like field (defense-in-depth —
 * even if a caller accidentally passes an apiKey field, the validator
 * refuses it).
 */
export function isValidModelResearchProfile(p: unknown): p is ModelResearchProfile {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (typeof o.providerId !== 'string' || o.providerId.length < 2 || o.providerId.length > 32) return false
  if (typeof o.model !== 'string' || o.model.length === 0) return false
  if (!Array.isArray(o.capabilities)) return false
  for (const cap of o.capabilities) {
    if (!isValidResearchCapability(cap)) return false
  }
  if (o.maxContext !== undefined && (typeof o.maxContext !== 'number' || o.maxContext <= 0)) return false
  if (o.strengths !== undefined && !Array.isArray(o.strengths)) return false
  if (o.limitations !== undefined && !Array.isArray(o.limitations)) return false
  // Phase 6-C1 strict: refuse secret-like fields
  const dump = JSON.stringify(p)
  if (dump.includes('sk-') || dump.includes('apiKey') || dump.includes('cipher')) return false
  return true
}

/**
 * Phase 6-C1: defensive scan — throws if a payload contains secret-like substrings.
 * Used by capability-resolver at the boundary between IPC payloads and runtime state.
 */
export function assertProfileSafe(profile: ModelResearchProfile): void {
  const dump = JSON.stringify(profile)
  if (dump.includes('sk-')) throw new Error('research profile leaked "sk-" (Phase 6-C1 secret violation)')
  if (dump.includes('apiKey')) throw new Error('research profile leaked "apiKey" (Phase 6-C1 secret violation)')
  if (dump.includes('cipher')) throw new Error('research profile leaked "cipher" (Phase 6-C1 secret violation)')
}
