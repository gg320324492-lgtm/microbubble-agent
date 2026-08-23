// Research Model Provider (Phase 8-D0: Research Agent Model Gateway).
//
// Phase 8-D0: the ONLY agent-facing seam the agent runtime uses to obtain a
// final answer from a citation-aware RAGContext. Wraps the ModelGateway so
// the runtime never imports model-adapters, providers, or HTTP code.
//
// Phase 8-D0 strict:
//   - NEVER contains apiKey / secret / token value / cipher
//   - Does NOT touch the agent runtime module
//   - Does NOT import model-provider SDKs or local model code

import type {
  ModelResponse,
  StreamChunk
} from '../../../shared/agent/model-gateway-schema'
import type { RAGContext } from '../../../shared/knowledge/context-schema'
import { isValidRAGContext } from '../../../shared/knowledge/context-schema'
import type { TaskType } from '../../../shared/agent/model-gateway-schema'
import type { ModelGateway, StreamOutcome } from './model-gateway'

export interface ResearchModelProviderOptions {
  gateway: ModelGateway
}

export interface AnswerOptions {
  taskType?: TaskType
  tokenBudget?: number
  temperature?: number
}

export class ResearchModelProvider {
  private readonly gateway: ModelGateway

  constructor(options: ResearchModelProviderOptions) {
    if (!options?.gateway) {
      throw new Error('research model provider: gateway required (Phase 8-D0 strict)')
    }
    this.gateway = options.gateway
  }

  /**
   * Phase 8-D0: single-shot answer. The only seam the agent runtime needs.
   * Returns a ModelResponse (content + usage + provider + latencyMs).
   */
  async provideAnswer(ragContext: RAGContext, options: AnswerOptions = {}): Promise<ModelResponse> {
    if (!isValidRAGContext(ragContext)) {
      throw new Error('research model provider: invalid RAGContext (Phase 8-D0 strict)')
    }
    return this.gateway.generateAnswer(ragContext, options)
  }

  /**
   * Phase 8-D0: token-by-token streaming. Returns a single AsyncIterable of
   * StreamChunks with assistant deltas.
   */
  async *provideStream(
    ragContext: RAGContext,
    options: AnswerOptions = {}
  ): AsyncIterable<StreamChunk> {
    if (!isValidRAGContext(ragContext)) {
      throw new Error('research model provider: invalid RAGContext (Phase 8-D0 strict)')
    }
    for await (const c of this.gateway.streamAnswer(ragContext, options)) {
      yield c
    }
  }

  /** Phase 8-D0: collect a full stream into a single outcome. */
  async provideCollected(
    ragContext: RAGContext,
    options: AnswerOptions = {}
  ): Promise<StreamOutcome> {
    if (!isValidRAGContext(ragContext)) {
      throw new Error('research model provider: invalid RAGContext (Phase 8-D0 strict)')
    }
    return this.gateway.collectStream(ragContext, options)
  }

  /** Phase 8-D0: list available provider ids (debug / status). */
  listProviderIds(): string[] {
    return this.gateway.listProviderIds()
  }

  /** Phase 8-D0: capabilities for a given provider. */
  capabilities(providerId: string): unknown {
    return this.gateway.capabilities(providerId)
  }
}

export const __testHelpers = {}