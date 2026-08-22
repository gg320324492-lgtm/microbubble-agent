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
 * Phase 6-A6: real HTTP fetch + SSE/NDJSON streaming.
 * Replaces the Phase 6-A5 stub.
 *
 * @param request — minimal chat input (Phase 6-A5: only `message` + `session_id`)
 * @param resolved — the ResolvedProvider from routeChatRequest
 * @param callbacks — push Phase 3-B0 StreamEvent to renderer
 * @param signal — AbortSignal for cancellation
 * @param options — optional fetcher (for tests) + timeout
 *
 * Phase 6-A6 strict:
 *   - apiKey NEVER in any callback payload
 *   - apiKey goes ONLY into the Authorization header (Bearer)
 *   - chat:* IPC payloads remain Phase 3-B0 StreamEvent (no schema change)
 *   - abort signal honored: AbortError -> onError('ABORTED')
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

export interface ProviderRuntimeOptions {
  /** Phase 6-A6: injected fetcher (defaults to global fetch). */
  fetcher?: typeof fetch
  /** Phase 6-A6: total timeout in ms (default 30000). 0 = no timeout. */
  timeoutMs?: number
}

import type { CanonicalRequest, CanonicalMessage } from '@shared/model/provider-types'

/**
 * Phase 6-A6: build the chat endpoint URL for the resolved provider.
 *   - openai-compatible / cloud -> {endpoint}/v1/chat/completions
 *   - local (Ollama)             -> {endpoint}/api/chat
 */
function chatEndpointUrl(endpoint: string, type: ModelConfig['type']): string {
  const base = endpoint.replace(/\/$/, '')
  if (type === 'local') return `${base}/api/chat`
  return `${base}/v1/chat/completions`
}

/**
 * Phase 6-A6: build the HTTP headers for the chat request.
 * OpenAI-compatible uses Bearer; Ollama uses no Authorization.
 */
function chatHeaders(type: ModelConfig['type'], apiKey: string): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: type === 'local' ? 'application/x-ndjson' : 'text/event-stream',
    'Cache-Control': 'no-cache'
  }
  if (type !== 'local' && apiKey.length > 0) {
    headers['Authorization'] = `Bearer ${apiKey}`
  }
  return headers
}

/**
 * Phase 6-A6: split buffer into chunks based on provider type.
 *   - openai-compatible: SSE -> split on `\n\n`
 *   - local (Ollama): NDJSON -> split on `\n`
 */
function splitBuffer(
  buffer: string,
  type: ModelConfig['type']
): { chunks: string[]; remainder: string } {
  if (type === 'local') {
    const parts = buffer.split('\n')
    const remainder = parts.pop() ?? ''
    return { chunks: parts.filter((p) => p.trim().length > 0), remainder }
  }
  const parts = buffer.split('\n\n')
  const remainder = parts.pop() ?? ''
  return { chunks: parts.filter((p) => p.trim().length > 0), remainder }
}

/**
 * Phase 6-A6: HTTP status -> StreamErrorPayload code.
 */
function mapHttpToErrorCode(status: number): string {
  if (status === 401) return 'UNAUTHORIZED'
  if (status === 403) return 'FORBIDDEN'
  if (status === 404) return 'NOT_FOUND'
  if (status === 429) return 'RATE_LIMITED'
  if (status >= 500) return 'SERVER_ERROR'
  return 'INVALID_RESPONSE'
}

export async function runProviderRuntime(
  request: ChatRequestMinimal,
  resolved: ResolvedProvider,
  callbacks: ProviderRuntimeCallbacks,
  signal: AbortSignal,
  options?: ProviderRuntimeOptions
): Promise<void> {
  // Phase 6-A6: build canonical request
  const messages: CanonicalMessage[] = [
    { role: 'user', content: request.message }
  ]
  const canonical: CanonicalRequest = {
    model: resolved.model,
    messages,
    stream: true
  }
  const payload = resolved.provider.buildRequest(canonical, resolved.cfg)
  const endpoint = resolved.cfg.endpoint ?? ''
  const url = chatEndpointUrl(endpoint, resolved.cfg.type)
  const headers = chatHeaders(resolved.cfg.type, resolved.apiKey)
  const fetcher = options?.fetcher ?? fetch
  const timeoutMs = options?.timeoutMs ?? 30000

  // Phase 6-A6: compose timeout + abort signals
  const timeoutController = new AbortController()
  let timeoutHandle: ReturnType<typeof setTimeout> | null = null
  if (timeoutMs > 0) {
    timeoutHandle = setTimeout(() => timeoutController.abort(), timeoutMs)
  }
  // Combine user signal + timeout signal (AbortSignal.any is Node 20+)
  type AbortSignalAny = (signals: AbortSignal[]) => AbortSignal
  const anyFn = (AbortSignal as unknown as { any?: AbortSignalAny }).any
  const composed = anyFn
    ? anyFn([signal, timeoutController.signal])
    : signal

  try {
    if (signal.aborted) {
      callbacks.onError('ABORTED', 'stream cancelled before provider runtime started')
      return
    }
    const response = await fetcher(url, {
      method: 'POST',
      headers,
      body: JSON.stringify(payload),
      signal: composed
    })
    if (timeoutHandle) clearTimeout(timeoutHandle)
    if (!response.ok) {
      callbacks.onError(mapHttpToErrorCode(response.status), `HTTP ${response.status}`)
      return
    }
    if (!response.body) {
      callbacks.onError('INVALID_RESPONSE', 'no response body')
      return
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''
    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const { chunks, remainder } = splitBuffer(buffer, resolved.cfg.type)
        buffer = remainder
        for (const raw of chunks) {
          // Phase 6-A6: strip SSE "data:" prefix if present
          const cleaned = raw.replace(/^data:\s*/, '').trim()
          if (cleaned.length === 0) continue
          const ev = resolved.provider.parseChunk(cleaned)
          if (ev) callbacks.onChunk(ev)
        }
      }
      // Drain final buffer
      if (buffer.trim().length > 0) {
        const cleaned = buffer.replace(/^data:\s*/, '').trim()
        if (cleaned.length > 0) {
          const ev = resolved.provider.parseChunk(cleaned)
          if (ev) callbacks.onChunk(ev)
        }
      }
      callbacks.onEnd()
    } catch (e) {
      const name = (e as { name?: string }).name
      if (name === 'AbortError') {
        callbacks.onError('ABORTED', 'stream cancelled mid-read')
      } else {
        callbacks.onError(
          'PROVIDER_RUNTIME_ERROR',
          e instanceof Error ? e.message : String(e)
        )
      }
    }
  } catch (e) {
    if (timeoutHandle) clearTimeout(timeoutHandle)
    const name = (e as { name?: string }).name
    if (name === 'AbortError') {
      if (timeoutController.signal.aborted && !signal.aborted) {
        callbacks.onError('TIMEOUT', `provider did not respond within ${timeoutMs}ms`)
      } else {
        callbacks.onError('ABORTED', 'stream cancelled before/during fetch')
      }
      return
    }
    callbacks.onError(
      'NETWORK_ERROR',
      e instanceof Error ? e.message : String(e)
    )
  }
}

// Phase 6-A5: test-only reset for feature flag
export function __resetRuntimeMode(): void {
  _mode = 'legacy'
}
