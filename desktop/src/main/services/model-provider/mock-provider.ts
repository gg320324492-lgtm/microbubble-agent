// Test Mock Provider (Phase 6-A1: Model Provider Foundation).
//
// Phase 6-A1: in-memory MockProvider that satisfies ModelProvider interface
// without contacting any vendor SDK. Used by tests to verify the foundation.

import type {
  CanonicalRequest,
  ModelProvider,
  ProviderCapabilities,
  StreamEvent
} from '@shared/model/provider-types'
import type { ModelConfig } from '@shared/model/model-types'

export const MOCK_PROVIDER_ID = 'mock-provider'

/**
 * Phase 6-A1: canned chunks emitted in order. Last entry must be the
 * terminal {type:'done'} (or stream end). Tests assert exact sequence.
 */
export interface MockChunkSpec {
  raw: string
}

export function createMockProvider(
  cfg: ModelConfig,
  _chunks?: MockChunkSpec[]
): ModelProvider {
  const caps: ProviderCapabilities = {
    streaming: true,
    tools: cfg.capabilities.includes('tools'),
    vision: cfg.capabilities.includes('vision'),
    functionCalling: cfg.capabilities.includes('function-calling'),
    jsonMode: cfg.capabilities.includes('json-mode')
  }
  return {
    id: cfg.providerId,
    type: cfg.type,
    capabilities: caps,
    buildRequest(req: CanonicalRequest, c: ModelConfig): unknown {
      // Phase 6-A1: openai-compatible passthrough shape
      return {
        model: c.defaultModel,
        messages: req.messages.map((m) => ({ role: m.role, content: m.content })),
        stream: req.stream,
        temperature: req.temperature,
        max_tokens: req.max_tokens
      }
    },
    parseChunk(raw: string): StreamEvent | null {
      // Phase 6-A1: minimal passthrough; real parseChunk uses stream-normalizer
      if (raw === '[DONE]') return { type: 'done' }
      try {
        return JSON.parse(raw) as StreamEvent
      } catch (_e) {
        return null
      }
    },
    async ping(_c: ModelConfig) {
      return { ok: true, latencyMs: 1 }
    }
  }
}

/**
 * Phase 6-A1: replay a chunk sequence against a mock provider.
 * Tests assert the sequence of normalized events.
 */
export async function replayChunks(provider: ModelProvider, chunks: MockChunkSpec[]): Promise<StreamEvent[]> {
  const events: StreamEvent[] = []
  if (chunks && chunks.length > 0) {
    for (const c of chunks) {
      const ev = provider.parseChunk(c.raw)
      if (ev !== null) events.push(ev)
    }
  }
  return events
}
