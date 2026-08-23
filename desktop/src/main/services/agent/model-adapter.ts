// Online Model Adapter (Phase 8-D0: Research Agent Model Gateway).
//
// Phase 8-D0: the seam between the agent-facing ModelGateway and online model
// providers (Xiaomi MIMO, MiniMax). No direct SDK imports — adapters go
// through fetch() with credentials fetched from the Phase 6 secret store.
//
// Phase 8-D0 strict:
//   - NEVER contains apiKey / secret / token value / cipher
//   - No SDK imports; no local model dependency

import type {
  ModelRequest,
  ModelResponse,
  StreamChunk,
  TokenUsage
} from '../../../shared/agent/model-gateway-schema'

export interface AdapterCapabilities {
  /** Free-form descriptor of model behavior (max context, supported tasks). */
  readonly contextWindow: number
  /** Cost class (1 = cheapest, 5 = premium); gateway uses this for routing. */
  readonly costClass: 1 | 2 | 3 | 4 | 5
  /** Whether streaming is supported. */
  readonly streaming: boolean
  /** What tasks this model handles well. */
  readonly tasks: readonly ('qa' | 'summarization' | 'extraction' | 'code' | 'general')[]
}

export interface HealthCheck {
  ok: boolean
  latencyMs?: number
  error?: string
}

/**
 * Phase 8-D0: the ONLY contract providers implement. Adapters load API keys
 * from the Phase 6 secret store; the gateway never sees a credential.
 */
export interface OnlineModelAdapter {
  readonly id: string

  /** Single-shot completion. Returns a parsed ModelResponse or throws. */
  chat(req: ModelRequest): Promise<ModelResponse>

  /** Token-by-token streaming. Each chunk carries the text delta. */
  stream(req: ModelRequest): AsyncIterable<StreamChunk>

  /** Cheap health probe. */
  healthCheck(): Promise<HealthCheck>

  /** Static capability descriptor. */
  capabilities(): AdapterCapabilities
}

/** Phase 8-D0: token usage accumulator. */
export function sumUsage(a: TokenUsage, b: TokenUsage): TokenUsage {
  return {
    promptTokens: a.promptTokens + b.promptTokens,
    completionTokens: a.completionTokens + b.completionTokens,
    totalTokens: a.totalTokens + b.totalTokens
  }
}

/** Phase 8-D0: zero usage. */
export const ZERO_USAGE: TokenUsage = Object.freeze({
  promptTokens: 0,
  completionTokens: 0,
  totalTokens: 0
})

export const __testHelpers = {
  sumUsage,
  ZERO_USAGE
}