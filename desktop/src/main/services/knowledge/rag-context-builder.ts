// RAG Context Builder (Phase 8-C3: Citation-aware RAG Context Builder).
//
// Phase 8-C3: deterministic assembly of SearchResult[] into RAGContext.
// Consumes SearchResult + CitationReference only; never touches the embedding /
// vector store / parser / runtime / tool layer.
//
// Pipeline:
//   SearchResult[]  ->  rank  ->  cap  ->  merge similar  ->  dedupe citations
//                  ->  truncate by token budget  ->  ContextChunk[]
//                  ->  deduped CitationReference[]  ->  RAGContext
//
// Phase 8-C3 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No LLM call, no prompt generation — pure assembly

import type { SearchResult } from '../../../shared/knowledge/retriever-schema'
import type { ContextChunk, RAGContext } from '../../../shared/knowledge/context-schema'
import { isValidContextChunk, isValidRAGContext } from '../../../shared/knowledge/context-schema'
import type { CitationReference } from '../../../shared/knowledge/document-schema'
import { deduplicateCitation } from './citation-formatter'

// ============ Defaults ============

const DEFAULT_TOKEN_BUDGET = 2000
const DEFAULT_MAX_CHUNKS = 8
const DEFAULT_MERGE_THRESHOLD = 0.5

// ============ Token estimator (pure, no LLM) ============

function wordCount(s: string): number {
  if (s.length === 0) return 0
  return s.trim().split(/\s+/).filter(Boolean).length
}

/** Phase 8-C3: rough heuristic — words + characters / 4. Round to integer. */
export function estimateTokens(text: string): number {
  if (typeof text !== 'string') {
    throw new Error('rag context builder: text must be a string (Phase 8-C3 strict)')
  }
  if (text.trim().length === 0) return 0
  const wc = wordCount(text)
  return Math.max(1, Math.floor(wc * 1.3 + text.length / 4))
}

export type TokenEstimator = (text: string) => number

// ============ Ranking ============

function compareResults(a: SearchResult, b: SearchResult): number {
  if (b.score !== a.score) return b.score - a.score
  const d = a.chunk.documentId.localeCompare(b.chunk.documentId)
  if (d !== 0) return d
  return a.chunk.position - b.chunk.position
}

/** Phase 8-C3: deterministic ranking (score desc, docId, position) with optional query-term boost. */
export function rankChunks(results: SearchResult[], query?: string): SearchResult[] {
  if (!Array.isArray(results)) {
    throw new Error('rag context builder: results must be an array (Phase 8-C3 strict)')
  }
  const ordered = [...results].sort(compareResults)
  if (!query) return ordered
  const terms = query.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((t) => t.length > 0)
  if (terms.length === 0) return ordered
  const boosted = ordered.map((r) => {
    const hay = r.chunk.content.toLowerCase()
    let hits = 0
    for (const t of terms) if (hay.includes(t)) hits++
    const boost = hits / terms.length
    const adjusted = Math.round((r.score + boost) * 1e4) / 1e4
    return { ...r, score: adjusted }
  })
  return boosted.sort(compareResults)
}

// ============ Merge similar ============

function tokensOf(s: string): Set<string> {
  return new Set(s.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((t) => t.length > 0))
}

function jaccard(a: Set<string>, b: Set<string>): number {
  if (a.size === 0 && b.size === 0) return 1
  let inter = 0
  for (const t of a) if (b.has(t)) inter++
  const union = a.size + b.size - inter
  return union === 0 ? 0 : inter / union
}

/**
 * Phase 8-C3: for each pair of same-doc adjacent chunks whose token-set
 * Jaccard exceeds `threshold`, keep only the higher-scored. The lower-scored
 * is dropped even if it appeared earlier in the input — deterministic and
 * order-preserving among non-merged chunks.
 */
export function mergeSimilarChunks(
  results: SearchResult[],
  threshold: number = DEFAULT_MERGE_THRESHOLD
): SearchResult[] {
  if (!Array.isArray(results)) {
    throw new Error('rag context builder: results must be an array (Phase 8-C3 strict)')
  }
  if (typeof threshold !== 'number' || threshold < 0 || threshold > 1) {
    throw new Error('rag context builder: merge threshold must be in [0,1] (Phase 8-C3 strict)')
  }
  const keep = results.map(() => true)
  for (let i = 0; i < results.length; i++) {
    for (let j = 0; j < i; j++) {
      if (!keep[j]) continue
      const a = results[j]!
      const b = results[i]!
      if (a.chunk.documentId !== b.chunk.documentId) continue
      if (Math.abs(a.chunk.position - b.chunk.position) !== 1) continue
      const sim = jaccard(tokensOf(a.chunk.content), tokensOf(b.chunk.content))
      if (sim >= threshold) {
        if (a.score >= b.score) keep[i] = false
        else keep[j] = false
      }
    }
  }
  return results.filter((_, idx) => keep[idx])
}

// ============ Token-budget truncation ============

/**
 * Phase 8-C3: greedy take while total tokens fit. Reserves one token for the
 * trailing separator; never overflows.
 */
export function truncateByTokenBudget(
  chunks: ContextChunk[],
  budget: number,
  estimator: TokenEstimator = estimateTokens
): ContextChunk[] {
  if (!Array.isArray(chunks)) {
    throw new Error('rag context builder: chunks must be an array (Phase 8-C3 strict)')
  }
  if (typeof budget !== 'number' || !Number.isInteger(budget) || budget < 1) {
    throw new Error('rag context builder: token budget must be a positive integer (Phase 8-C3 strict)')
  }
  const used: string[] = []
  const out: ContextChunk[] = []
  let remaining = budget
  for (const c of chunks) {
    if (!isValidContextChunk(c)) {
      throw new Error('rag context builder: invalid ContextChunk (Phase 8-C3 strict)')
    }
    const cost = estimator(c.content) + 1
    if (cost > remaining) break
    used.push(c.content)
    out.push(c)
    remaining -= cost
  }
  void used
  return out
}

// ============ Dedupe (caller-facing) ============

function citationKey(c: CitationReference): string {
  return `${c.documentId}::${c.chunkId}::${c.page ?? ''}`
}

/** Phase 8-C3: dedupe by (documentId, chunkId, page), preserving first-seen order. */
export function dedupeSearchResults(results: SearchResult[]): SearchResult[] {
  const seen = new Set<string>()
  const out: SearchResult[] = []
  for (const r of results) {
    const k = citationKey(r.citation)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(r)
  }
  return out
}

// ============ ContextChunk construction ============

function toContextChunk(result: SearchResult): ContextChunk {
  return {
    chunkId: result.chunk.id,
    content: result.chunk.content,
    score: result.score,
    citation: result.citation
  }
}

// ============ RAGContextBuilder ============

export interface RAGContextBuilderOptions {
  maxChunks?: number
  defaultTokenBudget?: number
  tokenEstimator?: TokenEstimator
  mergeThreshold?: number
}

export interface BuildContextOptions {
  maxChunks?: number
  tokenBudget?: number
  tokenEstimator?: TokenEstimator
  metadata?: Record<string, unknown>
}

export class RAGContextBuilder {
  private readonly maxChunks: number
  private readonly defaultTokenBudget: number
  private readonly tokenEstimator: TokenEstimator
  private readonly mergeThreshold: number

  constructor(options: RAGContextBuilderOptions = {}) {
    this.maxChunks = normalizePositiveInt(options.maxChunks ?? DEFAULT_MAX_CHUNKS, 'maxChunks')
    this.defaultTokenBudget = normalizePositiveInt(options.defaultTokenBudget ?? DEFAULT_TOKEN_BUDGET, 'defaultTokenBudget')
    this.tokenEstimator = options.tokenEstimator ?? estimateTokens
    this.mergeThreshold = normalizeThreshold(options.mergeThreshold ?? DEFAULT_MERGE_THRESHOLD, 'mergeThreshold')
  }

  /**
   * Phase 8-C3: deterministic context builder.
   *  rank -> cap -> merge similar -> dedupe citations -> truncate -> assemble
   */
  buildContext(query: string, results: SearchResult[], options: BuildContextOptions = {}): RAGContext {
    if (typeof query !== 'string' || query.length === 0) {
      throw new Error('rag context builder: query must be a non-empty string (Phase 8-C3 strict)')
    }
    if (!Array.isArray(results)) {
      throw new Error('rag context builder: results must be an array (Phase 8-C3 strict)')
    }
    const maxChunks = options.maxChunks ?? this.maxChunks
    const budget = options.tokenBudget ?? this.defaultTokenBudget
    const estimator = options.tokenEstimator ?? this.tokenEstimator
    const metadata = options.metadata ?? {}

    const ranked = rankChunks(results, query)
    const capped = maxChunks > 0 ? ranked.slice(0, maxChunks) : ranked
    const merged = mergeSimilarChunks(capped, this.mergeThreshold)
    const deduped = dedupeSearchResults(merged)

    const chunkList: ContextChunk[] = deduped.map(toContextChunk)
    const truncated = truncateByTokenBudget(chunkList, budget, estimator)

    const citations = deduplicateCitation(truncated.map((c) => c.citation))
    const totalTokens = truncated.reduce((s, c) => s + estimator(c.content), 0)
    const contextMetadata = {
      ...metadata,
      totalTokens,
      totalCandidates: deduped.length,
      truncatedCount: truncated.length
    }

    const ctx: RAGContext = {
      query,
      chunks: truncated,
      citations,
      tokenBudget: budget,
      metadata: contextMetadata
    }
    if (!isValidRAGContext(ctx)) {
      throw new Error('rag context builder: produced invalid RAGContext (Phase 8-C3 strict)')
    }
    return ctx
  }
}

function normalizePositiveInt(v: number, label: string): number {
  if (!Number.isInteger(v) || v < 0) {
    throw new Error(`rag context builder: ${label} must be a non-negative integer (Phase 8-C3 strict)`)
  }
  return v
}
function normalizeThreshold(v: number, label: string): number {
  if (typeof v !== 'number' || v < 0 || v > 1) {
    throw new Error(`rag context builder: ${label} must be in [0,1] (Phase 8-C3 strict)`)
  }
  return v
}

export const __testHelpers = {
  estimateTokens,
  rankChunks,
  mergeSimilarChunks,
  truncateByTokenBudget,
  dedupeSearchResults,
  toContextChunk,
  jaccard,
  tokensOf,
  DEFAULT_TOKEN_BUDGET,
  DEFAULT_MAX_CHUNKS
}