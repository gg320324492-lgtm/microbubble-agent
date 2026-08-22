// Local Vector Store (Phase 8-C2: Embedding + Vector Retrieval Foundation).
//
// In-memory vector store with deterministic cosine-similarity search, metadata
// filters, and delete. NO FAISS, NO external DB.
//
// Phase 8-C2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Stores embeddings only — never chunk content / secrets

import type { VectorRecord, VectorSearchQuery, VectorSearchHit } from '../../../shared/knowledge/vector-store-schema'
import { isValidVectorRecord, isValidVectorSearchQuery } from '../../../shared/knowledge/vector-store-schema'

// ============ Similarity primitives ============

function round6(x: number): number {
  return Math.round(x * 1e6) / 1e6
}

/**
 * Phase 8-C2: cosine similarity in [-1, 1]. Throws on dim mismatch.
 * Returns 0 when either vector is zero-norm.
 */
export function cosineSimilarity(a: number[], b: number[]): number {
  if (!Array.isArray(a) || !Array.isArray(b)) {
    throw new Error('cosine: inputs must be arrays (Phase 8-C2 strict)')
  }
  if (a.length !== b.length) {
    throw new Error('cosine: vector dimensions must match (Phase 8-C2 strict)')
  }
  if (a.length === 0) {
    throw new Error('cosine: vectors must be non-empty (Phase 8-C2 strict)')
  }
  let dot = 0
  let na = 0
  let nb = 0
  for (let i = 0; i < a.length; i++) {
    const x = a[i]!
    const y = b[i]!
    if (!Number.isFinite(x) || !Number.isFinite(y)) {
      throw new Error('cosine: components must be finite (Phase 8-C2 strict)')
    }
    dot += x * y
    na += x * x
    nb += y * y
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb)
  if (denom === 0) return 0
  return round6(dot / denom)
}

// ============ Metadata filtering ============

function valueMatches(stored: unknown, expected: unknown): boolean {
  if (Array.isArray(stored)) return stored.some((x) => x === expected)
  return stored === expected
}

export function matchesVectorFilters(metadata: Record<string, unknown>, filters: Record<string, unknown>): boolean {
  for (const [key, expected] of Object.entries(filters)) {
    if (!valueMatches(metadata[key], expected)) return false
  }
  return true
}

// ============ LocalVectorStore ============

export class LocalVectorStore {
  private readonly records = new Map<string, VectorRecord>()

  /** Phase 8-C2: returns true on insert, false on duplicate chunkId (no overwrite). */
  insert(record: VectorRecord): boolean {
    if (!isValidVectorRecord(record)) {
      throw new Error('local vector store: invalid VectorRecord (Phase 8-C2 strict)')
    }
    if (this.records.has(record.chunkId)) return false
    this.records.set(record.chunkId, record)
    return true
  }

  /** Phase 8-C2: cosine search with deterministic ranking + optional filters. */
  search(query: VectorSearchQuery): VectorSearchHit[] {
    if (!isValidVectorSearchQuery(query)) {
      throw new Error('local vector store: invalid VectorSearchQuery (Phase 8-C2 strict)')
    }
    const filters = query.filters ?? {}
    const limit = query.limit ?? 0
    const hits: VectorSearchHit[] = []
    for (const record of this.records.values()) {
      if (Object.keys(filters).length > 0 && !matchesVectorFilters(record.metadata, filters)) continue
      let score: number
      try {
        score = cosineSimilarity(record.embedding.values, query.queryEmbedding.values)
      } catch {
        score = 0
      }
      // store only positive similarity — preserves "no false positives" semantics.
      if (score <= 0) continue
      hits.push({ chunkId: record.chunkId, score })
    }
    hits.sort((a, b) => b.score - a.score || (a.chunkId < b.chunkId ? -1 : a.chunkId > b.chunkId ? 1 : 0))
    return limit > 0 ? hits.slice(0, limit) : hits
  }

  delete(chunkId: string): boolean {
    if (typeof chunkId !== 'string') {
      throw new Error('local vector store: chunkId must be a string (Phase 8-C2 strict)')
    }
    return this.records.delete(chunkId)
  }

  list(): VectorRecord[] {
    return Array.from(this.records.values()).sort((a, b) => a.chunkId < b.chunkId ? -1 : a.chunkId > b.chunkId ? 1 : 0)
  }

  size(): number {
    return this.records.size
  }

  clear(): void {
    this.records.clear()
  }
}

export const __testHelpers = {
  cosineSimilarity,
  matchesVectorFilters,
  round6
}