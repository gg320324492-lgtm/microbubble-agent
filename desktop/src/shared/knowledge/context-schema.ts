// RAG Context Schema Contracts (Phase 8-C3: Citation-aware RAG Context Builder).
//
// Phase 8-C3: typed contracts for assembling SearchResult[] into a
// citation-aware RAGContext the agent consumes. Consumes SearchResult only;
// never touches the embedding / vector / parser / runtime layers.
//
// Phase 8-C3 frozen contract:
//   - ContextChunk (chunkId / content / score / citation)
//   - RAGContext (query / chunks / citations / tokenBudget / metadata)
//   - Validators + assertNoSecret guard
//
// Phase 8-C3 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No LLM call, no prompt generation — pure assembly

import type { CitationReference } from './document-schema'
import { isValidCitationReference } from './document-schema'

// ============ ContextChunk ============

/**
 * Phase 8-C3: a SearchResult rewritten as a self-contained chunk for the
 * generator. Keeps the original CitationReference intact.
 */
export interface ContextChunk {
  chunkId: string
  content: string
  score: number
  citation: CitationReference
}

// ============ RAGContext ============

/**
 * Phase 8-C3: the assembled context handed to the agent.
 * `chunks` is in citation order (1-based numbering when rendered); `citations`
 * is the deduplicated, citation-order list to display at the bottom.
 */
export interface RAGContext {
  query: string
  chunks: ContextChunk[]
  citations: CitationReference[]
  tokenBudget: number
  metadata: Record<string, unknown>
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

/**
 * Phase 8-C3: walk only string values (keys are identifiers — never secrets).
 * JSON.stringify dumps both keys and values, which would reject legitimate
 * field names like `tokenBudget` that contain the substring "token".
 */
function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') {
    for (const bad of FORBIDDEN) if (value.includes(bad)) return bad
    return null
  }
  if (Array.isArray(value)) {
    for (const v of value) { const r = findForbidden(v); if (r) return r }
    return null
  }
  if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) {
      const r = findForbidden(v); if (r) return r
    }
  }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) {
    throw new Error(`rag context leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-C3 strict)`)
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidContextChunk(c: unknown): c is ContextChunk {
  if (!isObject(c)) return false
  if (typeof c.chunkId !== 'string' || c.chunkId.length === 0) return false
  if (typeof c.content !== 'string') return false
  if (typeof c.score !== 'number' || !Number.isFinite(c.score)) return false
  if (!isValidCitationReference(c.citation)) return false
  return true
}

export function isValidRAGContext(c: unknown): c is RAGContext {
  if (!isObject(c)) return false
  if (typeof c.query !== 'string' || c.query.length === 0) return false
  if (!Array.isArray(c.chunks)) return false
  if (!c.chunks.every((x) => isValidContextChunk(x))) return false
  if (!Array.isArray(c.citations)) return false
  if (!c.citations.every((x) => isValidCitationReference(x))) return false
  if (typeof c.tokenBudget !== 'number' || !Number.isInteger(c.tokenBudget) || c.tokenBudget < 1) return false
  if (!isObject(c.metadata)) return false
  assertNoSecret(c, 'RAGContext')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  isValidContextChunk,
  isValidRAGContext
}