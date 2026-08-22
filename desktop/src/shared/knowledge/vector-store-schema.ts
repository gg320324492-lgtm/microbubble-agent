// Vector Store Schema Contracts (Phase 8-C2: Embedding + Vector Retrieval Foundation).
//
// Phase 8-C2: the vector storage seam — EmbeddingVector records searchable by
// similarity. Stores chunkId → embedding + metadata (never chunk content).
//
// Phase 8-C2 frozen contract:
//   - VectorRecord (chunkId / embedding / metadata)
//   - VectorSearchQuery (queryEmbedding / limit / filters)
//   - VectorSearchHit (chunkId / score)
//   - VectorStore interface (insert / search / delete / list)
//   - Validators + assertNoSecret guard
//
// Phase 8-C2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No FAISS / external database — deterministic in-memory local store

import type { EmbeddingVector } from './embedding-schema'
import { isValidEmbeddingVector } from './embedding-schema'

// ============ VectorRecord ============

/**
 * Phase 8-C2: one indexed chunk embedding.
 * `metadata` mirrors the chunk metadata (section / page / documentId) so the
 * vector store can filter without touching chunk content.
 */
export interface VectorRecord {
  chunkId: string
  embedding: EmbeddingVector
  metadata: Record<string, unknown>
}

// ============ Search ============

export interface VectorSearchQuery {
  queryEmbedding: EmbeddingVector
  /** Result cap; undefined or 0 = no cap. */
  limit?: number
  filters?: Record<string, unknown>
}

export interface VectorSearchHit {
  chunkId: string
  /** Deterministic similarity score (cosine) in [-1, 1]. */
  score: number
}

// ============ VectorStore ============

export interface VectorStore {
  /** Insert a record. Returns true if newly added; false if chunkId already present (no overwrite). */
  insert(record: VectorRecord): boolean
  search(query: VectorSearchQuery): VectorSearchHit[]
  /** Delete by chunkId. Returns true if it existed. */
  delete(chunkId: string): boolean
  list(): VectorRecord[]
  /** Phase 8-C2: number of records currently stored (used by the hybrid retriever). */
  size(): number
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`vector store leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-C2 strict)`)
    }
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidVectorRecord(r: unknown): r is VectorRecord {
  if (!isObject(r)) return false
  if (typeof r.chunkId !== 'string' || r.chunkId.length === 0) return false
  if (!isValidEmbeddingVector(r.embedding)) return false
  if (!isObject(r.metadata)) return false
  assertNoSecret(r, 'VectorRecord')
  return true
}

export function isValidVectorSearchQuery(q: unknown): q is VectorSearchQuery {
  if (!isObject(q)) return false
  if (!isValidEmbeddingVector(q.queryEmbedding)) return false
  if (q.limit !== undefined
      && (typeof q.limit !== 'number' || !Number.isInteger(q.limit) || q.limit < 0)) return false
  if (q.filters !== undefined && !isObject(q.filters)) return false
  assertNoSecret(q, 'VectorSearchQuery')
  return true
}

export function isValidVectorSearchHit(h: unknown): h is VectorSearchHit {
  if (!isObject(h)) return false
  if (typeof h.chunkId !== 'string' || h.chunkId.length === 0) return false
  if (typeof h.score !== 'number' || !Number.isFinite(h.score)) return false
  return true
}

export function isValidVectorStore(s: unknown): s is VectorStore {
  if (!isObject(s)) return false
  return typeof s.insert === 'function'
    && typeof s.search === 'function'
    && typeof s.delete === 'function'
    && typeof s.list === 'function'
}

export const __testHelpers = {
  FORBIDDEN,
  isValidVectorRecord,
  isValidVectorSearchQuery,
  isValidVectorSearchHit,
  isValidVectorStore
}