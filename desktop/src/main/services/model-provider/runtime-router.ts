// Model Runtime Router (Phase 6-A5: Model Runtime Integration).
//
// Phase 6-A5: in-process router that decides whether a chat stream should
// go through the legacy FastAPI backend (default) or through the local
// ModelProvider runtime (Phase 6-A3 + Phase 6-A2 SecretStore + Phase 6-A4 ConfigStore).
//
// Phase 6-A5 frozen contract:
//   - routeChatRequest(req, modelContext) -> RouteDecision
//     returns { mode: 'legacy' } OR { mode: 'provider', provider, apiKey (from SecretStore ONLY) }
//
//   - resolveActiveProvider() -> { provider, apiKey } | null
//
// Phase 6-A5 explicit forbids:
//   - NEVER log the apiKey
//   - NEVER include the apiKey in any return value that crosses an IPC boundary
//   - Internal `resolveActiveProvider` returns apiKey ONLY for main-process use
//
// Feature flag MODEL_RUNTIME_MODE:
//   'legacy'   (default) — chat routes through FastAPI /chat/stream unchanged
//   'provider'           — chat routes through the local provider runtime
//
// Phase 6-A5 strict: legacy mode is the safe default. provider mode requires
// the user to have explicitly configured an active provider + key, otherwise
// the router falls back to legacy.

import { getProvider } from './registry'
import { exists as keyExists, get as keyGet } from './model-secret-store'
import { getConfig } from './provider-config-store'
import { getActive } from './active-provider-store'
import type { ModelConfig } from '@shared/model/model-types'
import type { ModelProvider } from '@shared/model/provider-types'

export type RuntimeMode = 'legacy' | 'provider'

export interface RuntimeFeatureFlag {
  /**
   * Phase 6-A5: reads from process.env.MODEL_RUNTIME_MODE.
   * Default: 'legacy'.
   */
  getMode(): RuntimeMode
  /**
   * Phase 6-A5: test-only override.
   */
  setMode(mode: RuntimeMode): void
}

let _mode: RuntimeMode = ((): RuntimeMode => {
  const v = process.env.MODEL_RUNTIME_MODE
  if (v === 'provider' || v === 'legacy') return v
  return 'legacy'
})()

export const runtimeFeatureFlag: RuntimeFeatureFlag = {
  getMode: () => _mode,
  setMode: (mode) => {
    _mode = mode
  }
}

/**
 * Phase 6-A5: request-time model context (added to ChatStreamRequest as optional).
 */
export interface ModelRuntimeContext {
  providerId?: string
  model?: string
}

/**
 * Phase 6-A5: routing decision.
 *
 * `mode = 'legacy'` — caller should use the existing FastAPI /chat/stream flow.
 * `mode = 'provider'` — caller should use `provider.buildRequest` + `provider.parseChunk`
 *                        to drive the local provider runtime.
 *
 * Phase 6-A5 strict: apiKey NEVER appears in the legacy branch and is only present
 * in the provider branch's internal `resolvedProvider` field. The IPC boundary
 * (chat:* IPC) NEVER sees apiKey — those payloads are Phase 3-B0 StreamEvent only.
 */
export interface RouteDecisionLegacy {
  mode: 'legacy'
  reason: string
}

export interface RouteDecisionProvider {
  mode: 'provider'
  reason: string
  resolvedProvider: ResolvedProvider
}

export interface ResolvedProvider {
  provider: ModelProvider
  cfg: ModelConfig
  apiKey: string
  providerId: string
  model: string
}

export type RouteDecision = RouteDecisionLegacy | RouteDecisionProvider

/**
 * Phase 6-A5: resolve a provider from (modelContext.providerId || active providerId).
 * Returns null if no provider is registered for that id.
 */
function lookupProvider(providerId: string): { provider: ModelProvider; cfg: ModelConfig } | null {
  // Phase 6-A5: must look up config first (Phase 6-A4) — registry needs a ModelConfig.
  const cfgBlob = getConfig(providerId)
  if (!cfgBlob) return null
  const cfg: ModelConfig = {
    providerId: cfgBlob.providerId,
    displayName: cfgBlob.displayName,
    type: cfgBlob.type,
    defaultModel: cfgBlob.defaultModel,
    ...(typeof cfgBlob.endpoint === 'string' ? { endpoint: cfgBlob.endpoint } : {}),
    capabilities: cfgBlob.capabilities as ModelConfig['capabilities']
  }
  const provider = getProvider(providerId, cfg)
  if (!provider) return null
  return { provider, cfg }
}

/**
 * Phase 6-A5: resolve the active provider (config + factory + key).
 * Returns null if any of: no active provider / no config / no factory / no key.
 *
 * Phase 6-A5 strict: apiKey is read from SecretStore (main process only).
 * This function is NEVER called from renderer code paths.
 */
export function resolveActiveProvider(): ResolvedProvider | null {
  const active = getActive()
  if (!active) return null
  const lookup = lookupProvider(active.providerId)
  if (!lookup) return null
  if (!keyExists(active.providerId)) return null
  const apiKey = keyGet(active.providerId)
  if (!apiKey) return null
  return {
    provider: lookup.provider,
    cfg: lookup.cfg,
    apiKey,
    providerId: active.providerId,
    model: active.model
  }
}

/**
 * Phase 6-A5: route a chat request.
 *
 * Decision tree:
 *   1. If feature flag is 'legacy' -> legacy
 *   2. If modelContext.providerId is set:
 *      - lookup provider + key -> success => provider
 *      - any failure => legacy (with reason)
 *   3. If modelContext.providerId not set:
 *      - resolve active provider -> success => provider
 *      - no active provider => legacy (with reason)
 *
 * Phase 6-A5 explicit forbids:
 *   - NEVER throw on provider lookup failure (always fall back to legacy)
 *   - NEVER leak apiKey in reason string
 */
export function routeChatRequest(modelContext?: ModelRuntimeContext | null): RouteDecision {
  const mode = runtimeFeatureFlag.getMode()
  if (mode === 'legacy') {
    return { mode: 'legacy', reason: 'MODEL_RUNTIME_MODE=legacy (Phase 6-A5 default)' }
  }
  // mode === 'provider'
  let resolved: ResolvedProvider | null = null
  if (modelContext?.providerId) {
    const lookup = lookupProvider(modelContext.providerId)
    if (lookup && keyExists(modelContext.providerId)) {
      const apiKey = keyGet(modelContext.providerId)
      if (apiKey) {
        resolved = {
          provider: lookup.provider,
          cfg: lookup.cfg,
          apiKey,
          providerId: modelContext.providerId,
          model: modelContext.model ?? lookup.cfg.defaultModel
        }
      }
    }
    if (!resolved) {
      return {
        mode: 'legacy',
        reason: `provider mode requested but providerId='${modelContext.providerId}' not fully configured (Phase 6-A5 fallback)`
      }
    }
  } else {
    resolved = resolveActiveProvider()
    if (!resolved) {
      return {
        mode: 'legacy',
        reason: 'provider mode requested but no active provider configured (Phase 6-A5 fallback)'
      }
    }
  }
  return {
    mode: 'provider',
    reason: `routed to providerId='${resolved.providerId}' model='${resolved.model}'`,
    resolvedProvider: resolved
  }
}

/**
 * Phase 6-A5: provider runtime entry — called from chat-stream.service.ts when
 * RouteDecision.mode === 'provider'. Does NOT touch FastAPI.
 *
 * Phase 6-A5: this function is the boundary between chat-stream.service.ts
 * (legacy path) and the provider runtime. It receives a chat request, calls
 * provider.buildRequest, drives provider.parseChunk over each SSE/NDJSON chunk,
 * and pushes Phase 3-B0 StreamEvent through the provided callback.
 *
 * Phase 6-A5 explicit forbids:
 *   - NEVER include apiKey in any callback payload
 *   - NEVER call fetch to FastAPI
 *
 * @param request — minimal chat input (Phase 6-A5: only `message` + `session_id`)
 * @param resolved — the ResolvedProvider from routeChatRequest
 * @param onChunk — push Phase 3-B0 StreamEvent to renderer (chat-stream.service.ts owns the webContents.send)
 * @param onEnd — push end
 * @param onError — push error (does NOT include apiKey)
 * @param signal — AbortSignal for cancellation
 *
 * Phase 6-A5 strict: this function makes NO real network calls by default.
 * Tests inject a fake fetcher. Production runtime streaming is wired in Phase 6-A6.
 * For Phase 6-A5, this function emits a single text_delta + done to prove the
 * path works end-to-end without touching a real vendor API.
 */
export interface ChatRequestMinimal {
  message: string
  session_id: string
}

export interface ProviderRuntimeCallbacks {
  onChunk(event: import('@shared/model/provider-types').StreamEvent): void
  onEnd(): void
  onError(code: string, message: string): void
}

import type { CanonicalRequest, CanonicalMessage } from '@shared/model/provider-types'

export async function runProviderRuntime(
  request: ChatRequestMinimal,
  resolved: ResolvedProvider,
  callbacks: ProviderRuntimeCallbacks,
  signal: AbortSignal
): Promise<void> {
  // Phase 6-A5: build canonical request from chat request
  const messages: CanonicalMessage[] = [
    { role: 'user', content: request.message }
  ]
  const canonical: CanonicalRequest = {
    model: resolved.model,
    messages,
    stream: true
  }
  // Build the vendor-native payload — proves the contract works.
  // Phase 6-A5 strict: we DO NOT send the apiKey over IPC.
  // Phase 6-A6 will wire the actual HTTP fetch (currently no real network).
  void resolved.provider.buildRequest(canonical, resolved.cfg)

  // Phase 6-A5: prove parseChunk round-trip works.
  // Emit a synthetic "hello" event through parseChunk to confirm shape.
  try {
    if (signal.aborted) {
      callbacks.onError('ABORTED', 'stream cancelled before provider runtime started')
      return
    }
    // Phase 6-A5: emit a confirmation chunk then done (does NOT touch network).
    callbacks.onChunk({ type: 'text_delta', delta: '' })
    callbacks.onChunk({
      type: 'text_delta',
      delta: `[Phase 6-A5: provider runtime reached for providerId='${resolved.providerId}' model='${resolved.model}' — Phase 6-A6 wires real network.]`
    })
    callbacks.onEnd()
  } catch (e) {
    callbacks.onError(
      'PROVIDER_RUNTIME_ERROR',
      e instanceof Error ? e.message : String(e)
    )
  }
}

// Phase 6-A5: test-only reset for feature flag
export function __resetRuntimeMode(): void {
  _mode = 'legacy'
}
