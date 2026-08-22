// Research Context Provider (Phase 8-C3: Citation-aware RAG Context Builder).
//
// Phase 8-C3: the only seam that the future Research Agent layer uses to
// obtain a citation-aware RAGContext. It owns no LLM call, no model call —
// it composes a HybridRetriever (Phase 8-C2) with a RAGContextBuilder
// (Phase 8-C3).
//
// Phase 8-C3 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT modify the agent runtime / planner / model layer

import type { HybridRetriever } from './hybrid-retriever'
import type { RAGContext } from '../../../shared/knowledge/context-schema'
import type { RAGContextBuilder } from './rag-context-builder'

export interface ResearchContextProviderOptions {
  retriever: HybridRetriever
  builder: RAGContextBuilder
  /** Optional default title resolver for citation rendering. */
  defaultTitle?: string
}

export interface ResearchContextQuery {
  text: string
  tokenBudget?: number
  maxChunks?: number
  filters?: Record<string, unknown>
  titleResolver?: (chunkId: string, documentId: string) => string | undefined
}

export interface ResearchContextResult {
  context: RAGContext
  /** Phase 8-C3: simple summary suitable for agent logging. */
  summary: {
    query: string
    chunkCount: number
    citationCount: number
    tokenBudget: number
    estimatedTokens: number
  }
}

/**
 * Phase 8-C3: adapter only. Future agent layers inject a ResearchContextProvider
 * to fetch citation-aware context; this module never executes the planner,
 * the runtime, or the model layer.
 */
export class ResearchContextProvider {
  private readonly retriever: HybridRetriever
  private readonly builder: RAGContextBuilder
  private readonly defaultTitle: string

  constructor(options: ResearchContextProviderOptions) {
    if (!options?.retriever) {
      throw new Error('research context provider: retriever required (Phase 8-C3 strict)')
    }
    if (!options?.builder) {
      throw new Error('research context provider: builder required (Phase 8-C3 strict)')
    }
    this.retriever = options.retriever
    this.builder = options.builder
    this.defaultTitle = options.defaultTitle ?? 'Untitled Source'
  }

  /**
   * Phase 8-C3: end-to-end — search the hybrid retriever and assemble an
   * RAGContext via the builder. Does NOT call an LLM.
   */
  async provide(query: ResearchContextQuery): Promise<ResearchContextResult> {
    if (!query || typeof query.text !== 'string' || query.text.length === 0) {
      throw new Error('research context provider: query.text must be a non-empty string (Phase 8-C3 strict)')
    }
    const results = await this.retriever.search({
      text: query.text,
      ...(query.filters !== undefined ? { filters: query.filters } : {})
    })
    const ctx = this.builder.buildContext(query.text, results, {
      ...(query.tokenBudget !== undefined ? { tokenBudget: query.tokenBudget } : {}),
      ...(query.maxChunks !== undefined ? { maxChunks: query.maxChunks } : {}),
      metadata: { provider: this.defaultTitle }
    })
    const estimatedTokens = ctx.metadata.totalTokens as number
    return {
      context: ctx,
      summary: {
        query: query.text,
        chunkCount: ctx.chunks.length,
        citationCount: ctx.citations.length,
        tokenBudget: ctx.tokenBudget,
        estimatedTokens
      }
    }
  }

  /** Phase 8-C3: expose a built-in title resolver that uses the default title. */
  defaultTitleResolver(): (chunkId: string, documentId: string) => string | undefined {
    return (_chunkId: string, _documentId: string) => this.defaultTitle
  }
}

export const __testHelpers = {}