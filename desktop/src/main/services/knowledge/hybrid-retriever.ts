// Hybrid Retriever (Phase 8-C2: Embedding + Vector Retrieval Foundation).
//
// Phase 8-C2: fuses the Phase 8-C0 keyword retriever (LocalRetriever) with a
// VectorStore + EmbeddingProvider. Same text, same vector (deterministic local
// embedding); hybrid ranking combines the two score streams.
//
// total = keywordWeight * normKeyword + semanticWeight * cosine
//         keyword norm: clamp01(score / 110)        (score scale 0..~110)
//         semantic:    cosine in [-1,1], stored positive ⇒ clamp01(cosine)
//
// Phase 8-C2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Consumes DocumentChunk content only for embedding
//   - Does NOT modify LocalRetriever / Document / runtime

import type { Document, DocumentChunk, CitationReference } from '../../../shared/knowledge/document-schema'
import type { SearchQuery, SearchResult } from '../../../shared/knowledge/retriever-schema'
import { isValidSearchQuery } from '../../../shared/knowledge/retriever-schema'
import type { VectorStore, VectorSearchHit } from '../../../shared/knowledge/vector-store-schema'
import type { EmbeddingProvider } from '../../../shared/knowledge/embedding-schema'
import { LocalRetriever } from './local-retriever'

const DEFAULT_WEIGHT = 0.5
const KEYWORD_SCALE = 110

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}
function round2(x: number): number {
  return Math.round(x * 100) / 100
}

export interface HybridRetrieverOptions {
  keyword?: LocalRetriever
  vectorStore: VectorStore
  embedding: EmbeddingProvider
  keywordWeight?: number
  semanticWeight?: number
}

/**
 * Phase 8-C2: keyword + vector hybrid over a single chunk id space.
 *
 * `indexDocuments` delegates to the keyword retriever's atomic index, then
 * embeds every chunk into the vector store. Re-indexing a document id
 * replaces its previous vector records.
 */
export class HybridRetriever {
  private readonly keyword: LocalRetriever
  private readonly vectorStore: VectorStore
  private readonly embedding: EmbeddingProvider
  private readonly keywordWeight: number
  private readonly semanticWeight: number
  private readonly chunks = new Map<string, DocumentChunk>()
  private readonly docChunkIds = new Map<string, string[]>()

  constructor(options: HybridRetrieverOptions) {
    if (!options?.vectorStore) {
      throw new Error('hybrid retriever: vectorStore required (Phase 8-C2 strict)')
    }
    if (!options?.embedding) {
      throw new Error('hybrid retriever: embedding provider required (Phase 8-C2 strict)')
    }
    this.keyword = options.keyword ?? new LocalRetriever()
    this.vectorStore = options.vectorStore
    this.embedding = options.embedding
    this.keywordWeight = options.keywordWeight ?? DEFAULT_WEIGHT
    this.semanticWeight = options.semanticWeight ?? DEFAULT_WEIGHT
    if (this.keywordWeight < 0 || this.semanticWeight < 0) {
      throw new Error('hybrid retriever: weights must be non-negative (Phase 8-C2 strict)')
    }
  }

  getKeyword(): LocalRetriever { return this.keyword }
  getVectorStore(): VectorStore { return this.vectorStore }
  getEmbedding(): EmbeddingProvider { return this.embedding }

  // ============ Index ============

  indexDocuments(documents: Document[]): number {
    if (!Array.isArray(documents)) {
      throw new Error('hybrid retriever: documents must be an array (Phase 8-C2 strict)')
    }
    const count = this.keyword.indexDocuments(documents)
    for (const doc of documents) {
      this.reindexVectorRecords(doc)
    }
    return count
  }

  private reindexVectorRecords(doc: Document): void {
    // Remove any prior vector records for this document.
    const old = this.docChunkIds.get(doc.id) ?? []
    for (const id of old) {
      this.vectorStore.delete(id)
      this.chunks.delete(id)
    }
    const chunkList = this.keyword.listChunks(doc.id)
    const ids = chunkList.map((c) => c.id)
    this.docChunkIds.set(doc.id, ids)
    for (const c of chunkList) this.chunks.set(c.id, c)
    if (chunkList.length === 0) return
    const vectors = this.embedding.embedBatch(chunkList.map((c) => c.content), ids)
    for (let i = 0; i < vectors.length; i++) {
      const chunk = chunkList[i]!
      const vec = vectors[i]!
      this.vectorStore.insert({
        chunkId: chunk.id,
        embedding: vec,
        metadata: { ...chunk.metadata, documentId: doc.id }
      })
    }
  }

  // ============ Search ============

  async search(query: SearchQuery): Promise<SearchResult[]> {
    if (!isValidSearchQuery(query)) {
      throw new Error('hybrid retriever: invalid SearchQuery (Phase 8-C2 strict)')
    }
    const [kw, vec] = await Promise.all([
      this.keyword.search({ ...query, limit: 0 }),
      Promise.resolve(this.searchVector(query))
    ])
    return this.merge(query, kw, vec)
  }

  /** Phase 8-C2: expose keyword-only result stream (transparent). */
  async searchKeyword(query: SearchQuery): Promise<SearchResult[]> {
    if (!isValidSearchQuery(query)) {
      throw new Error('hybrid retriever: invalid SearchQuery (Phase 8-C2 strict)')
    }
    return this.keyword.search({ ...query, limit: 0 })
  }

  /** Phase 8-C2: expose vector-only result stream (transparent). */
  searchVector(query: SearchQuery): VectorSearchHit[] {
    if (!isValidSearchQuery(query)) {
      throw new Error('hybrid retriever: invalid SearchQuery (Phase 8-C2 strict)')
    }
    const qVec = this.embedding.embed(query.text, '__hybrid_query__')
    return this.vectorStore.search({
      queryEmbedding: qVec,
      limit: 0,
      filters: query.filters
    })
  }

  // ============ Merge / rank ============

  private merge(query: SearchQuery, kw: SearchResult[], vec: VectorSearchHit[]): SearchResult[] {
    type Entry = { chunk: DocumentChunk; kw: number; sem: number }
    const byId = new Map<string, Entry>()
    for (const hit of kw) {
      byId.set(hit.chunk.id, { chunk: hit.chunk, kw: hit.score, sem: 0 })
    }
    for (const hit of vec) {
      const chunk = this.chunks.get(hit.chunkId)
      if (!chunk) continue
      const existing = byId.get(hit.chunkId)
      if (existing) {
        existing.sem = hit.score
      } else {
        byId.set(hit.chunkId, { chunk, kw: 0, sem: hit.score })
      }
    }
    const out: SearchResult[] = []
    for (const entry of byId.values()) {
      const kwNorm = clamp01(entry.kw / KEYWORD_SCALE)
      const sem = clamp01(entry.sem)
      const total = round2(this.keywordWeight * kwNorm + this.semanticWeight * sem)
      const confidence = round2(clamp01(total / Math.max(this.keywordWeight + this.semanticWeight, 1)))
      const citation: CitationReference = {
        documentId: entry.chunk.documentId,
        chunkId: entry.chunk.id,
        confidence
      }
      out.push({ chunk: entry.chunk, score: total, citation })
    }
    out.sort((a, b) =>
      b.score - a.score
      || a.chunk.documentId.localeCompare(b.chunk.documentId)
      || a.chunk.position - b.chunk.position
    )
    const limit = query.limit ?? 0
    return limit > 0 ? out.slice(0, limit) : out
  }

  // ============ Accessors ============

  getChunk(chunkId: string): DocumentChunk | undefined {
    return this.chunks.get(chunkId)
  }

  documentCount(): number {
    return this.keyword.documentCount()
  }

  chunkCount(): number {
    return this.chunks.size
  }

  vectorCount(): number {
    return this.vectorStore.size()
  }
}

export const __testHelpers = {
  KEYWORD_SCALE,
  DEFAULT_WEIGHT,
  clamp01,
  round2
}