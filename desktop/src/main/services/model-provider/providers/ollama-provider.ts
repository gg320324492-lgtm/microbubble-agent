// Ollama Provider (Phase 6-A3: Provider Factory + Registry).
//
// Phase 6-A3: vendor factory for self-hosted Ollama (HTTP /api/tags + /api/chat).
//
// Contract (Phase 6-A3 frozen):
//   - buildRequest(CanonicalRequest, ModelConfig) -> Ollama /api/chat payload (stream:true)
//   - parseChunk(raw)                              -> StreamEvent (NDJSON one-line-per-event)
//   - ping(ModelConfig)                            -> GET /api/tags
//
// Ollama streaming shape (NDJSON, NOT SSE):
//   { "model": "...", "message": { "role": "assistant", "content": "..." }, "done": false }
//   { "model": "...", "done": true, "done_reason": "stop", "total_duration": ..., "eval_count": ... }
//
// Phase 6-A3 explicit forbids:
//   - NO Ollama SDK imports (pure fetch + NDJSON parse)
//   - NO auto-detect model list (caller passes cfg.defaultModel)

import type {
  CanonicalRequest,
  ModelProvider,
  ProviderCapabilities,
  StreamEvent
} from '@shared/model/provider-types'
import type { ModelConfig } from '@shared/model/model-types'

export const OLLAMA_ID = 'ollama'

/**
 * Phase 6-A3: derive capabilities from ModelConfig.capabilities.
 */
function capabilitiesFromConfig(cfg: ModelConfig): ProviderCapabilities {
  const set = new Set(cfg.capabilities)
  return {
    streaming: set.has('streaming'),
    tools: set.has('tools'),
    vision: set.has('vision'),
    functionCalling: set.has('function-calling'),
    jsonMode: set.has('json-mode')
  }
}

/**
 * Phase 6-A3: build the Ollama /api/chat payload.
 *
 * Notes:
 *   - Ollama uses `messages` array with {role, content, images?, tool_calls?}
 *   - `stream: true` required for NDJSON streaming
 *   - `options` field carries model params (temperature, num_ctx, etc.)
 *   - No Authorization header (Phase 6-A3: assume local network)
 */
export function buildOllamaRequest(
  req: CanonicalRequest,
  cfg: ModelConfig
): {
  model: string
  messages: Array<Record<string, unknown>>
  stream: boolean
  options?: Record<string, unknown>
} {
  const messages: Array<Record<string, unknown>> = []
  for (const m of req.messages) {
    if (m.role === 'system') messages.push({ role: 'system', content: m.content })
    else if (m.role === 'user') messages.push({ role: 'user', content: m.content })
    else if (m.role === 'assistant') messages.push({ role: 'assistant', content: m.content })
    else if (m.role === 'tool') messages.push({ role: 'tool', content: m.content })
  }
  const out: ReturnType<typeof buildOllamaRequest> = {
    model: cfg.defaultModel,
    messages,
    stream: req.stream !== false
  }
  // Phase 6-A3: pass through select options
  const options: Record<string, unknown> = {}
  if (typeof req.temperature === 'number') options.temperature = req.temperature
  if (typeof req.max_tokens === 'number') options.num_predict = req.max_tokens
  if (Object.keys(options).length > 0) out.options = options
  return out
}

/**
 * Phase 6-A3: parse one NDJSON line into a normalized StreamEvent.
 *
 * Ollama shape (per-line JSON):
 *   - { message: { role, content }, done: false }  -> text_delta
 *   - { done: true, done_reason?: string, ...stats } -> done
 *   - { error: string }                              -> error
 *
 * Phase 6-A3 explicit forbids:
 *   - SSE framing ('data:' prefix) is NOT Ollama — reject gracefully (return null).
 */
export function parseOllamaChunk(raw: string): StreamEvent | null {
  if (raw == null) return null
  const text = String(raw).trim()
  if (text.length === 0) return null

  // Phase 6-A3: Ollama uses NDJSON, not SSE. Skip lines starting with "data:".
  if (text.startsWith('data:')) return null

  // Skip SSE comments / keepalive
  if (text.startsWith(':')) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(text)
  } catch (_e) {
    return null
  }
  if (!parsed || typeof parsed !== 'object') return null
  const obj = parsed as Record<string, unknown>

  // Error envelope: { error: "..." }
  if (typeof obj.error === 'string') {
    return { type: 'error', message: obj.error }
  }

  // Done event: { done: true, ...stats }
  if (obj.done === true) {
    const reason = (typeof obj.done_reason === 'string' ? obj.done_reason : 'stop') as
      | 'stop'
      | 'length'
      | string
    const usage: Record<string, number> | undefined = {}
    if (typeof obj.eval_count === 'number') usage.completion_tokens = obj.eval_count
    if (typeof obj.prompt_eval_count === 'number') usage.prompt_tokens = obj.prompt_eval_count
    return {
      type: 'done',
      finish_reason: reason,
      usage: Object.keys(usage).length > 0 ? usage : undefined
    }
  }

  // Streaming chunk: { message: { role, content }, done: false }
  const msg = obj.message
  if (msg && typeof msg === 'object') {
    const m = msg as Record<string, unknown>
    if (typeof m.content === 'string' && m.content.length > 0) {
      return { type: 'text_delta', delta: m.content }
    }
  }

  // Phase 6-A3: unknown shape (Phase 6-A3 might add tool_calls later)
  return null
}

/**
 * Phase 6-A3: health-check via GET /api/tags (returns list of installed models).
 * Ollama does NOT require auth.
 */
export async function pingOllama(
  cfg: ModelConfig,
  fetcher: typeof fetch = fetch
): Promise<{ ok: boolean; latencyMs?: number; error?: string }> {
  if (typeof cfg.endpoint !== 'string' || cfg.endpoint.length === 0) {
    return { ok: false, error: 'ModelConfig.endpoint missing (Phase 6-A3 strict).' }
  }
  const url = `${cfg.endpoint.replace(/\/$/, '')}/api/tags`
  const start = Date.now()
  try {
    const res = await fetcher(url, { method: 'GET' })
    const latencyMs = Date.now() - start
    if (!res.ok) {
      return { ok: false, latencyMs, error: `HTTP ${res.status} ${res.statusText || ''}`.trim() }
    }
    // Phase 6-A3: confirm body has a "models" array (Ollama's signature).
    try {
      const body = (await res.json()) as { models?: unknown }
      if (!body || !Array.isArray(body.models)) {
        return { ok: false, latencyMs, error: 'response missing models array (not Ollama?)' }
      }
    } catch (_e) {
      return { ok: false, latencyMs, error: 'invalid JSON in /api/tags response' }
    }
    return { ok: true, latencyMs }
  } catch (e) {
    const latencyMs = Date.now() - start
    const msg = e instanceof Error ? e.message : String(e)
    return { ok: false, latencyMs, error: msg }
  }
}

/**
 * Phase 6-A3: factory function. Takes a ModelConfig and returns a ModelProvider.
 */
export function createOllamaProvider(
  fetcher: typeof fetch = fetch
): (cfg: ModelConfig) => ModelProvider {
  return (cfg: ModelConfig): ModelProvider => {
    return {
      id: cfg.providerId,
      type: cfg.type,
      capabilities: capabilitiesFromConfig(cfg),
      buildRequest: (req: CanonicalRequest) => buildOllamaRequest(req, cfg),
      parseChunk: (raw: string) => parseOllamaChunk(raw),
      ping: (_c: ModelConfig) => pingOllama(_c, fetcher)
    }
  }
}
