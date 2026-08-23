// Xiaomi MIMO Adapter (Phase 8-D0: Research Agent Model Gateway).
//
// Online OpenAI-compatible chat-completions adapter for Xiaomi MIMO.
// The credential is resolved via the injected `secretResolver` (wired to the
// Phase 6 secret store at gateway construction); it is never embedded in
// source, logs, or the wire payload.
//
// Phase 8-D0 strict:
//   - NEVER contains a literal key value
//   - No SDK imports; no local model dependency

import type {
  ModelRequest,
  ModelResponse,
  StreamChunk,
  TokenUsage
} from '../../../../shared/agent/model-gateway-schema'
import { isValidModelRequest } from '../../../../shared/agent/model-gateway-schema'
import type {
  OnlineModelAdapter,
  AdapterCapabilities,
  HealthCheck
} from '../model-adapter'
import { ZERO_USAGE } from '../model-adapter'
import { parseSseStream } from './sse-stream'

export const MIMO_PROVIDER_ID = 'mimo'
export const MIMO_DEFAULT_BASE_URL = 'https://api.xiaomi.com/mimo/v1/chat/completions'
export const MIMO_DEFAULT_MODEL = 'mimo'
const MIMO_DEFAULT_TIMEOUT_MS = 30_000
const MIMO_DEFAULT_MAX_TOKENS_CAP = 8_192

export type MimoSecretResolver = (providerId: string) => string | null

export interface MimoAdapterConfig {
  secretResolver: MimoSecretResolver
  model?: string
  baseUrl?: string
  timeoutMs?: number
  /** Injected fetch for tests; defaults to global fetch. */
  fetchFn?: typeof fetch
}

export class MimoAdapter implements OnlineModelAdapter {
  readonly id = MIMO_PROVIDER_ID
  private readonly secretResolver: MimoSecretResolver
  private readonly model: string
  private readonly baseUrl: string
  private readonly timeoutMs: number
  private readonly fetchFn: typeof fetch

  constructor(config: MimoAdapterConfig) {
    if (!config?.secretResolver) {
      throw new Error('mimo adapter: secretResolver required (Phase 8-D0 strict)')
    }
    this.secretResolver = config.secretResolver
    this.model = config.model ?? MIMO_DEFAULT_MODEL
    this.baseUrl = config.baseUrl ?? MIMO_DEFAULT_BASE_URL
    this.timeoutMs = normalizePositiveInt(config.timeoutMs ?? MIMO_DEFAULT_TIMEOUT_MS, 'timeoutMs')
    this.fetchFn = config.fetchFn ?? (fetch as typeof fetch)
    if (typeof this.fetchFn !== 'function') {
      throw new Error('mimo adapter: fetch is not available (Phase 8-D0 strict)')
    }
  }

  capabilities(): AdapterCapabilities {
    return {
      contextWindow: 32_000,
      costClass: 3,
      streaming: true,
      tasks: ['qa', 'summarization', 'extraction', 'code', 'general']
    }
  }

  async chat(req: ModelRequest): Promise<ModelResponse> {
    if (!isValidModelRequest(req)) {
      throw new Error('mimo adapter: invalid ModelRequest (Phase 8-D0 strict)')
    }
    const started = Date.now()
    const apiKey = this.resolveKey()
    const body = JSON.stringify(this.buildPayload(req, false))
    const response = await this.post(body, apiKey, false)
    const json = await readJson(response) as {
      choices?: Array<{ message?: { content?: string } }>
      usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }
    }
    const content = json.choices?.[0]?.message?.content ?? ''
    const usage: TokenUsage = json.usage
      ? { promptTokens: json.usage.prompt_tokens ?? 0, completionTokens: json.usage.completion_tokens ?? 0, totalTokens: json.usage.total_tokens ?? 0 }
      : { ...ZERO_USAGE }
    return { content, usage, provider: this.id, latencyMs: Date.now() - started }
  }

  async *stream(req: ModelRequest): AsyncIterable<StreamChunk> {
    if (!isValidModelRequest(req)) {
      throw new Error('mimo adapter: invalid ModelRequest (Phase 8-D0 strict)')
    }
    const apiKey = this.resolveKey()
    const body = JSON.stringify(this.buildPayload(req, true))
    const response = await this.post(body, apiKey, true)
    if (!response.body) {
      yield { delta: '', done: true }
      return
    }
    for await (const evt of parseSseStream(response.body)) {
      if (evt.data === '[DONE]') {
        yield { delta: '', done: true }
        return
      }
      if (!evt.data) continue
      try {
        const obj = JSON.parse(evt.data) as {
          choices?: Array<{ delta?: { content?: string } }>
          usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number }
        }
        const delta = obj.choices?.[0]?.delta?.content ?? ''
        if (delta) yield { delta, done: false }
        if (obj.usage) {
          yield {
            delta: '',
            done: true,
            usage: {
              promptTokens: obj.usage.prompt_tokens ?? 0,
              completionTokens: obj.usage.completion_tokens ?? 0,
              totalTokens: obj.usage.total_tokens ?? 0
            }
          }
        }
      } catch {
        // Ignore malformed chunks; SSE may include comment lines or empty payloads.
      }
    }
    yield { delta: '', done: true }
  }

  async healthCheck(): Promise<HealthCheck> {
    const started = Date.now()
    try {
      const apiKey = this.resolveKey()
      const response = await this.fetchFn(this.baseUrl, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${apiKey}` }
      })
      return { ok: response.ok, latencyMs: Date.now() - started }
    } catch (e) {
      return { ok: false, error: e instanceof Error ? e.message : String(e) }
    }
  }

  // ============ Internals ============

  private resolveKey(): string {
    const key = this.secretResolver(MIMO_PROVIDER_ID)
    if (!key) {
      throw new Error('mimo adapter: secret not found (Phase 8-D0 strict)')
    }
    return key
  }

  private buildPayload(req: ModelRequest, stream: boolean): Record<string, unknown> {
    const payload: Record<string, unknown> = {
      model: this.model,
      messages: req.messages,
      temperature: req.temperature,
      max_tokens: Math.min(req.tokenBudget, MIMO_DEFAULT_MAX_TOKENS_CAP),
      stream
    }
    if (req.context !== null) {
      payload['metadata'] = { context: req.context }
    }
    return payload
  }

  private async post(body: string, apiKey: string, stream: boolean): Promise<Response> {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), this.timeoutMs)
    try {
      return await this.fetchFn(this.baseUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${apiKey}`,
          ...(stream ? { 'Accept': 'text/event-stream' } : {})
        },
        body,
        signal: controller.signal
      })
    } finally {
      clearTimeout(timer)
    }
  }
}

function normalizePositiveInt(v: number, label: string): number {
  if (!Number.isInteger(v) || v < 1) {
    throw new Error(`mimo adapter: ${label} must be a positive integer (Phase 8-D0 strict)`)
  }
  return v
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text()
  if (!text) return {}
  try { return JSON.parse(text) } catch { return {} }
}

export const __testHelpers = {
  MIMO_PROVIDER_ID,
  MIMO_DEFAULT_BASE_URL,
  MIMO_DEFAULT_MODEL,
  readJson
}