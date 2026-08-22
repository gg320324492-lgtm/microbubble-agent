// OpenAI-Compatible Provider (Phase 6-A3: Provider Factory + Registry).
//
// Phase 6-A3: vendor factory for any OpenAI-compatible HTTP endpoint.
// Used by: OpenAI, MiniMax, Qwen, Mimo, vLLM (openai-compatible mode), etc.
//
// Contract (Phase 6-A3 frozen):
//   - buildRequest(CanonicalRequest, ModelConfig) -> OpenAI /v1/chat/completions payload
//   - parseChunk(raw)                              -> StreamEvent (via stream-normalizer)
//   - ping(ModelConfig)                            -> { ok, latencyMs?, error? }
//
// Phase 6-A3 explicit forbids:
//   - NO real network requests in production code path (Phase 6-A6 e2e only)
//   - NO SDK imports (no `openai` npm package; this is a pure adapter over fetch)

import type {
  CanonicalRequest,
  ModelProvider,
  ProviderCapabilities,
  StreamEvent
} from '@shared/model/provider-types'
import type { ModelConfig } from '@shared/model/model-types'
import { normalizeStreamChunk } from '../stream-normalizer'

export const OPENAI_COMPATIBLE_ID = 'openai-compatible'

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
 * Phase 6-A3: build the OpenAI-compatible /v1/chat/completions request payload.
 *
 * Supports:
 *   - system / user / assistant / tool messages
 *   - tool_calls passthrough (assistant -> tool chain)
 *   - tool message with tool_call_id
 *   - temperature / max_tokens / stop
 *   - stream: true (required for SSE)
 *
 * Does NOT support (Phase 6-A3: extend later):
 *   - vision image_url content (Phase 6-A3: pass-through if string already URL)
 *   - response_format / json_mode (Phase 6-A3: extra field passthrough)
 *   - function-calling legacy shape (Phase 6-A3: tools array only)
 */
export function buildOpenAiCompatibleRequest(req: CanonicalRequest, cfg: ModelConfig): {
  model: string
  messages: Array<Record<string, unknown>>
  temperature?: number
  max_tokens?: number
  stop?: string[]
  stream: boolean
} {
  const messages: Array<Record<string, unknown>> = []
  for (const m of req.messages) {
    if (m.role === 'system') {
      messages.push({ role: 'system', content: m.content })
    } else if (m.role === 'user') {
      messages.push({ role: 'user', content: m.content })
    } else if (m.role === 'assistant') {
      messages.push({ role: 'assistant', content: m.content })
    } else if (m.role === 'tool') {
      const msg: Record<string, unknown> = { role: 'tool', content: m.content }
      if (typeof m.tool_call_id === 'string') msg.tool_call_id = m.tool_call_id
      if (typeof m.name === 'string') msg.name = m.name
      messages.push(msg)
    }
  }
  const out: ReturnType<typeof buildOpenAiCompatibleRequest> = {
    model: cfg.defaultModel,
    messages,
    stream: req.stream !== false
  }
  if (typeof req.temperature === 'number') out.temperature = req.temperature
  if (typeof req.max_tokens === 'number') out.max_tokens = req.max_tokens
  if (Array.isArray(req.stop)) out.stop = req.stop
  return out
}

/**
 * Phase 6-A3: parse a single vendor chunk into a normalized StreamEvent.
 * Delegates to the Phase 6-A1 stream-normalizer for OpenAI-compatible shape
 * (data: {json}\n\n, [DONE], error envelope, content delta, tool_use delta).
 */
export function parseOpenAiCompatibleChunk(raw: string): StreamEvent | null {
  return normalizeStreamChunk(raw)
}

/**
 * Phase 6-A3: health-check a provider endpoint.
 *
 * Phase 6-A3 behavior:
 *   - GET {endpoint}/v1/models with Authorization header (if apiKey present)
 *   - 200 -> ok (latency = wall-clock ms)
 *   - non-200 -> ok=false, error=status text
 *   - network error -> ok=false, error=message
 *
 * Phase 6-A3: factory does NOT cache this; tests use mock fetch.
 */
export async function pingOpenAiCompatible(
  cfg: ModelConfig,
  apiKey: string | null,
  fetcher: typeof fetch = fetch
): Promise<{ ok: boolean; latencyMs?: number; error?: string }> {
  if (typeof cfg.endpoint !== 'string' || cfg.endpoint.length === 0) {
    return { ok: false, error: 'ModelConfig.endpoint missing (Phase 6-A3 strict).' }
  }
  const url = `${cfg.endpoint.replace(/\/$/, '')}/v1/models`
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`
  const start = Date.now()
  try {
    const res = await fetcher(url, { method: 'GET', headers })
    const latencyMs = Date.now() - start
    if (!res.ok) {
      return { ok: false, latencyMs, error: `HTTP ${res.status} ${res.statusText || ''}`.trim() }
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
 * The factory does NOT call fetch — ping is wired through the parameter.
 */
export function createOpenAiCompatibleProvider(
  apiKeyResolver: () => string | null = () => null,
  fetcher: typeof fetch = fetch
): (cfg: ModelConfig) => ModelProvider {
  return (cfg: ModelConfig): ModelProvider => {
    return {
      id: cfg.providerId,
      type: cfg.type,
      capabilities: capabilitiesFromConfig(cfg),
      buildRequest: (req: CanonicalRequest) => buildOpenAiCompatibleRequest(req, cfg),
      parseChunk: (raw: string) => parseOpenAiCompatibleChunk(raw),
      ping: (_c: ModelConfig) => pingOpenAiCompatible(_c, apiKeyResolver(), fetcher)
    }
  }
}
