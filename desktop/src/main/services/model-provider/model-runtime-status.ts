// Model Runtime Status (Phase 6-A6: E2E Verification).
//
// Phase 6-A6: lightweight status snapshot returned from provider runtime tests
// and exposed to the renderer for the chat header status display.
//
// Phase 6-A6 frozen contract:
//   - modelRuntimeStatus(snapshot) -> RenderableStatus (Phase 6-A6: type only;
//     renderer reads from chat-stream.service.ts push; Phase 6-B owns UI)
//
// Phase 6-A6 strict forbids:
//   - NEVER include apiKey in the status snapshot
//   - NEVER include Authorization header
//   - NEVER include ciphertext

/**
 * Phase 6-A6: connection status (mirrors Phase 6-A4 Pinia store type).
 * Duplicated here to keep main process independent of renderer imports.
 */
export type ProviderConnectionStatus = 'unknown' | 'checking' | 'connected' | 'failed'

/**
 * Phase 6-A6: non-secret status snapshot.
 *
 * Used by:
 *   - Phase 6-A6 e2e tests (assertions on chunks + status)
 *   - Phase 6-B chat header status indicator (read-only)
 *
 * Renderer-readable. NEVER contains API key.
 */
export interface ModelRuntimeStatus {
  providerId: string
  model: string
  status: ProviderConnectionStatus
  latencyMs?: number
  lastError?: string
  /** Phase 6-A6: when the status was last updated (epoch ms). */
  updatedAt: number
}

/**
 * Phase 6-A6: build a status snapshot from runtime signals.
 *
 * @param providerId non-secret providerId
 * @param model      non-secret model name
 * @param latencyMs  optional observed latency
 * @param error      optional error message
 * @param success    true if the runtime just emitted onEnd()
 */
export function buildModelRuntimeStatus(
  providerId: string,
  model: string,
  options?: { latencyMs?: number; error?: string; success?: boolean }
): ModelRuntimeStatus {
  let status: ProviderConnectionStatus = 'unknown'
  if (options?.error) status = 'failed'
  else if (options?.success) status = 'connected'
  const out: ModelRuntimeStatus = {
    providerId,
    model,
    status,
    updatedAt: Date.now()
  }
  if (typeof options?.latencyMs === 'number') out.latencyMs = options.latencyMs
  if (typeof options?.error === 'string') out.lastError = options.error
  return out
}

/**
 * Phase 6-A6: validate that a status snapshot does not contain secret material.
 * Used by tests + as a defensive runtime check.
 *
 * @throws if any field looks like a secret.
 */
export function assertStatusSafe(snapshot: ModelRuntimeStatus): void {
  const dump = JSON.stringify(snapshot)
  if (dump.includes('sk-')) throw new Error('status snapshot leaked "sk-" (Phase 6-A6 secret violation)')
  if (dump.includes('apiKey')) throw new Error('status snapshot leaked "apiKey" (Phase 6-A6 secret violation)')
  if (dump.includes('cipher')) throw new Error('status snapshot leaked "cipher" (Phase 6-A6 secret violation)')
  if (dump.toLowerCase().includes('bearer ')) {
    throw new Error('status snapshot leaked "Bearer " header (Phase 6-A6 secret violation)')
  }
}
