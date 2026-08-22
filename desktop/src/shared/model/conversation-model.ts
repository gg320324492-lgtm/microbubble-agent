// Conversation Model Context (Phase 6-B: Active Model Integration).
//
// Phase 6-B: shared type carried alongside chat sessions and chat streams.
// Describes WHICH model a conversation (or single stream) is bound to —
// non-secret metadata only.
//
// Phase 6-B frozen contract:
//   - ConversationModelContext = { providerId, model, displayName? }
//   - ALWAYS non-secret; NEVER contains apiKey / token / cipher
//   - Backward-compatible: conversations / streams without modelContext
//     continue to work (legacy FastAPI path)
//
// Used by:
//   - ChatSessionOut.modelContext (Phase 6-B: optional session binding)
//   - ChatStreamRequest.modelContext (Phase 6-A5: optional per-request override)
//   - Pinia model-selector store (renderer-side active selection)

export type ModelCapability =
  | 'streaming'
  | 'tools'
  | 'vision'
  | 'function-calling'
  | 'json-mode'

/**
 * Phase 6-B: a single capability tag for UI display.
 * CapabilityGate accepts a list of these.
 */
export interface ConversationModelContext {
  providerId: string
  model: string
  /** Optional human label for chat header display. */
  displayName?: string
  /**
   * Optional capability snapshot (Phase 6-A4 ConfigStore.caps).
   * UI may show capability tags (streaming / tools / vision).
   * Phase 6-B: read from provider registry, not persisted with session.
   */
  capabilities?: ModelCapability[]
}

/**
 * Phase 6-B: validate ConversationModelContext shape.
 * Renderer-side: never call with apiKey field; this validator rejects any
 * field that smells like a secret.
 */
export function isValidConversationModelContext(
  ctx: unknown
): ctx is ConversationModelContext {
  if (!ctx || typeof ctx !== 'object') return false
  const c = ctx as Record<string, unknown>
  if (typeof c.providerId !== 'string' || c.providerId.length < 2 || c.providerId.length > 32) return false
  if (typeof c.model !== 'string' || c.model.length === 0) return false
  if (typeof c.displayName !== 'string' && c.displayName !== undefined) return false
  if (c.capabilities !== undefined && !Array.isArray(c.capabilities)) return false
  // Phase 6-B strict: reject any secret-like field
  const dump = JSON.stringify(ctx)
  if (dump.includes('sk-') || dump.includes('apiKey') || dump.includes('cipher')) return false
  return true
}

/**
 * Phase 6-B: renderable capability display label (Phase 6-B UI contract).
 */
export function capabilityLabel(cap: ModelCapability): string {
  switch (cap) {
    case 'streaming': return 'streaming'
    case 'tools': return 'tools'
    case 'vision': return 'vision'
    case 'function-calling': return 'function-calling'
    case 'json-mode': return 'json-mode'
  }
}
