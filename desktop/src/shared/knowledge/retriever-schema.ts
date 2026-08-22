// Retriever Schema Contracts (Phase 8-C0: Knowledge Retrieval Foundation).
//
// Phase 8-C0: typed contracts for the retrieval layer.
// Distinct from:
//   - Phase 7-B0 knowledge/storage.ts (storage provider — this layer consumes it)
//   - Phase 8 planner contracts (context feeds the planner, never modified)
//
// Phase 8-C0 frozen contract:
//   - SearchQuery (text / filters / limit)
//   - SearchResult (chunk / score / citation)
//   - KnowledgeRetriever interface (search / retrieve / list)
//   - Validators + assertNoSecret guard
//
// Phase 8-C0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - The Retriever CONSUMES knowledge; it does NOT modify storage
//   - NO vector database — Phase 8-C0 keyword matching only

import type { Document, DocumentChunk, CitationReference } from './document-schema'
import { isValidDocument } from './document-schema'

// ============ SearchQuery ============

/**
 * Phase 8-C0: a retrieval query.
 *
 *  - text:    required free-text (non-empty string)
 *  - filters: metadata equality filters (type / doc metadata / chunk metadata)
 *  - limit:   result cap; undefined or 0 = no cap
 */
export interface SearchQuery {
  text: string
  filters?: Record<string, unknown>
  limit?: number
}

// ============ SearchResult ============

/**
 * Phase 8-C0: a single retrieval hit, with its citation.
 * `score` is a deterministic relevance score (higher = better).
 */
export interface SearchResult {
  chunk: DocumentChunk
  score: number
  citation: CitationReference
}

// ============ KnowledgeRetriever ============

/**
 * Phase 8-C0: read-only retrieval surface.
 *
 * Implementers also expose their own ingest primitives (e.g. indexDocuments)
 * out-of-band; this interface pinpoints what the research agent consumes.
 */
export interface KnowledgeRetriever {
  search(query: SearchQuery): Promise<SearchResult[]>
  retrieve(documentId: string): Promise<Document | null>
  list(): Promise<Document[]>
}

// ============ Validators ============

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidSearchQuery(q: unknown): q is SearchQuery {
  if (!isObject(q)) return false
  if (typeof q.text !== 'string' || q.text.length === 0) return false
  if (q.limit !== undefined
      && (typeof q.limit !== 'number' || !Number.isInteger(q.limit) || q.limit < 0)) return false
  if (q.filters !== undefined && !isObject(q.filters)) return false
  return true
}

export function isValidSearchResult(r: unknown): r is SearchResult {
  if (!isObject(r)) return false
  if (typeof r.score !== 'number' || !Number.isFinite(r.score) || r.score < 0) return false
  if (!r.chunk || typeof r.chunk !== 'object') return false
  if (!isValidDocumentChunkRef(r.chunk as DocumentChunk)) return false
  if (!r.citation || typeof r.citation !== 'object') return false
  const citation = r.citation as Record<string, unknown>
  if (typeof citation.documentId !== 'string' || citation.documentId.length === 0) return false
  if (typeof citation.chunkId !== 'string' || citation.chunkId.length === 0) return false
  if (typeof citation.confidence !== 'number' || citation.confidence < 0 || citation.confidence > 1) return false
  return true
}

function isValidDocumentChunkRef(c: DocumentChunk): boolean {
  return typeof c.id === 'string' && c.id.length > 0
    && typeof c.documentId === 'string' && c.documentId.length > 0
    && typeof c.content === 'string'
}

export function isValidRetriever(r: unknown): r is KnowledgeRetriever {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  return typeof o.search === 'function'
    && typeof o.retrieve === 'function'
    && typeof o.list === 'function'
}

export const __testHelpers = {
  isValidSearchQuery,
  isValidSearchResult,
  isValidDocument,
  isValidRetriever
}