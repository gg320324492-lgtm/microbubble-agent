// Local Retriever (Phase 8-C0: Knowledge Retrieval Foundation).
//
// Phase 8-C0: in-memory document index + keyword retrieval.
//   - indexDocuments()  ingests Documents (atomic — all-or-nothing)
//   - chunking via an injected Chunker (default LocalChunker)
//   - search()          keyword matching + metadata filters + deterministic ranking
//   - retrieve() / list()
//
// Phase 8-C0 scope: NO vector database, NO embeddings, NO RAG generation,
// NO LLM. Retriever CONSUMES knowledge; it never modifies storage.
//
// Phase 8-C0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / backend / chat-stream / planner / runtime

import type { Document, DocumentChunk, CitationReference } from '../../../shared/knowledge/document-schema'
import { isValidDocument } from '../../../shared/knowledge/document-schema'
import type { Chunker } from '../../../shared/knowledge/chunker-schema'
import type { KnowledgeRetriever, SearchQuery, SearchResult } from '../../../shared/knowledge/retriever-schema'
import { isValidSearchQuery } from '../../../shared/knowledge/retriever-schema'
import { LocalChunker } from './local-chunker'

// ============ Deterministic scoring helpers (pure, exported for tests) ============

export function countOccurrences(haystack: string, term: string): number {
  if (term.length === 0) return 0
  let count = 0
  let idx = 0
  while ((idx = haystack.indexOf(term, idx)) !== -1) {
    count++
    idx += term.length
  }
  return count
}

/** Phase 8-C0: lowercase + split on non-letter/non-digit runs (CJK aware). */
export function tokenizeQuery(text: string): string[] {
  return text.toLowerCase().split(/[^\p{L}\p{N}]+/u).filter((t) => t.length > 0)
}

function round2(x: number): number {
  return Math.round(x * 100) / 100
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}

/**
 * Phase 8-C0: deterministic relevance score.
 *   coverage*100  +  min(20, freq)*0.5  +  2/(position+1)
 * Returns 0 when no query term is present (chunk excluded from results).
 */
export function scoreChunk(queryTerms: string[], content: string, position: number): number {
  if (queryTerms.length === 0) return 0
  const hay = content.toLowerCase()
  let hits = 0
  let freq = 0
  for (const t of queryTerms) {
    if (t.length === 0) continue
    const c = countOccurrences(hay, t)
    if (c > 0) {
      hits++
      freq += c
    }
  }
  if (hits === 0) return 0
  const coverage = hits / queryTerms.length
  return round2(coverage * 100 + Math.min(20, freq) * 0.5 + 2 / (position + 1))
}

function valueMatches(stored: unknown, expected: unknown): boolean {
  if (Array.isArray(stored)) return stored.some((x) => x === expected)
  return stored === expected
}

/**
 * Phase 8-C0: metadata equality filter. Supports `type` (document.type) plus
 * any key matched against document.metadata OR chunk.metadata.
 */
export function matchesFilters(
  document: Document,
  chunk: DocumentChunk,
  filters: Record<string, unknown>
): boolean {
  for (const [key, expected] of Object.entries(filters)) {
    if (key === 'type') {
      if (document.type !== expected) return false
      continue
    }
    const docValue = document.metadata?.[key]
    const chunkValue = chunk.metadata?.[key]
    if (valueMatches(docValue, expected) || valueMatches(chunkValue, expected)) continue
    return false
  }
  return true
}

// ============ LocalRetriever ============

export class LocalRetriever implements KnowledgeRetriever {
  private readonly chunker: Chunker
  private readonly documents = new Map<string, Document>()
  private readonly chunks = new Map<string, DocumentChunk>()
  private readonly docChunks = new Map<string, string[]>()

  constructor(options: { chunker?: Chunker } = {}) {
    this.chunker = options?.chunker ?? new LocalChunker()
  }

  /** Phase 8-C0: ingest documents. Atomic — throws before mutating on any invalid doc. */
  indexDocuments(documents: Document[]): number {
    if (!Array.isArray(documents)) {
      throw new Error('local retriever: documents must be an array (Phase 8-C0 strict)')
    }
    const prepared: Array<{ doc: Document; chunkList: DocumentChunk[] }> = []
    for (const doc of documents) {
      if (!isValidDocument(doc)) {
        throw new Error(`local retriever: invalid document '${String((doc as { id?: string })?.id)}' (Phase 8-C0 strict)`)
      }
      prepared.push({ doc, chunkList: this.chunker.splitDocument(doc) })
    }
    for (const { doc, chunkList } of prepared) {
      this.removeDocument(doc.id)
      this.documents.set(doc.id, doc)
      const ids: string[] = []
      for (const chunk of chunkList) {
        this.chunks.set(chunk.id, chunk)
        ids.push(chunk.id)
      }
      this.docChunks.set(doc.id, ids)
    }
    return prepared.length
  }

  /** Phase 8-C0: drop a document + its chunks. Returns true if it existed. */
  removeDocument(documentId: string): boolean {
    const existed = this.documents.delete(documentId)
    const chunkIds = this.docChunks.get(documentId) ?? []
    for (const id of chunkIds) this.chunks.delete(id)
    this.docChunks.delete(documentId)
    return existed
  }

  async retrieve(documentId: string): Promise<Document | null> {
    return this.documents.get(documentId) ?? null
  }

  async list(): Promise<Document[]> {
    return Array.from(this.documents.values())
      .sort((a, b) => a.id.localeCompare(b.id))
  }

  /** Phase 8-C0: chunks of one document, ordered by position (implementation helper). */
  listChunks(documentId: string): DocumentChunk[] {
    const ids = this.docChunks.get(documentId) ?? []
    return ids
      .map((id) => this.chunks.get(id))
      .filter((c): c is DocumentChunk => c !== undefined)
      .sort((a, b) => a.position - b.position)
  }

  async search(query: SearchQuery): Promise<SearchResult[]> {
    return this.searchSync(query)
  }

  /** Phase 8-C0: synchronous search (interface `search` awaits this). */
  searchSync(query: SearchQuery): SearchResult[] {
    if (!isValidSearchQuery(query)) {
      throw new Error('local retriever: invalid search query (Phase 8-C0 strict)')
    }
    const terms = tokenizeQuery(query.text)
    if (terms.length === 0) return []
    const filters = query.filters ?? {}
    const limit = query.limit ?? 0

    const results: SearchResult[] = []
    for (const chunk of this.chunks.values()) {
      const document = this.documents.get(chunk.documentId)
      if (!document) continue
      if (!matchesFilters(document, chunk, filters)) continue
      const score = scoreChunk(terms, chunk.content, chunk.position)
      if (score <= 0) continue
      const citation: CitationReference = {
        documentId: chunk.documentId,
        chunkId: chunk.id,
        confidence: round2(clamp01(score / 100))
      }
      results.push({ chunk, score, citation })
    }

    results.sort((a, b) =>
      b.score - a.score
      || a.chunk.documentId.localeCompare(b.chunk.documentId)
      || a.chunk.position - b.chunk.position
    )
    return limit > 0 ? results.slice(0, limit) : results
  }

  documentCount(): number {
    return this.documents.size
  }

  chunkCount(): number {
    return this.chunks.size
  }
}

export const __testHelpers = {
  scoreChunk,
  tokenizeQuery,
  countOccurrences,
  matchesFilters
}