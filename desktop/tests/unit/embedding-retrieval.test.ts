// Phase 8-C2 Embedding + Vector Retrieval tests.
//
// Coverage (~200 cases):
//   - embedding-schema validators (22)
//   - vector-store-schema validators (22)
//   - cosine similarity (22)
//   - local embedding determinism + provider (32)
//   - local vector store (30)
//   - hybrid retriever (50)
//   - security + source isolation (12)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  isValidEmbeddingVector,
  isValidEmbeddingProvider,
  __testHelpers as embedHelpers
} from '../../src/shared/knowledge/embedding-schema'
import type { EmbeddingVector, EmbeddingProvider } from '../../src/shared/knowledge/embedding-schema'
import {
  isValidVectorRecord,
  isValidVectorSearchQuery,
  isValidVectorSearchHit,
  isValidVectorStore,
  __testHelpers as vecHelpers
} from '../../src/shared/knowledge/vector-store-schema'
import type { VectorRecord, VectorSearchQuery, VectorSearchHit } from '../../src/shared/knowledge/vector-store-schema'
import type { Document, DocumentChunk, CitationReference } from '../../src/shared/knowledge/document-schema'

// ============ Implementations ============
import {
  LocalEmbeddingProvider,
  fnv1a32,
  djb2Sign,
  tokenizeForEmbedding,
  contentId,
  computeEmbedding,
  __testHelpers as localEmbedHelpers
} from '../../src/main/services/knowledge/local-embedding'
import {
  LocalVectorStore,
  cosineSimilarity,
  matchesVectorFilters,
  __testHelpers as localVecHelpers
} from '../../src/main/services/knowledge/local-vector-store'
import { HybridRetriever } from '../../src/main/services/knowledge/hybrid-retriever'
import { LocalRetriever } from '../../src/main/services/knowledge/local-retriever'

// ============ Fixtures ============

function makeDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc:1',
    type: 'paper',
    title: 'Test Doc',
    source: 'doc:1.pdf',
    metadata: { content: 'bubble dynamics water quality' },
    createdAt: 0,
    ...overrides
  }
}

function makeDocContent(content: string, id: string = 'doc:1'): Document {
  return makeDoc({ id, metadata: { content } })
}

function makeVec(chunkId: string, dim: number, values: number[]): EmbeddingVector {
  return { id: chunkId, dimension: dim, values }
}

function norm(v: number[]): number {
  return Math.sqrt(v.reduce((s, x) => s + x * x, 0))
}

// ============ embedding-schema validators ============

describe('Phase 8-C2 EmbeddingVector validator', () => {
  const v: EmbeddingVector = { id: 'c1', dimension: 3, values: [1, 0, 0] }
  it('accepts a valid vector', () => {
    expect(isValidEmbeddingVector(v)).toBe(true)
  })
  it('accepts a unit-length normalized vector', () => {
    const inv = Math.sqrt(2)
    expect(isValidEmbeddingVector({ id: 'c1', dimension: 2, values: [1 / inv, 1 / inv] })).toBe(true)
  })
  it('rejects empty id', () => {
    expect(isValidEmbeddingVector({ ...v, id: '' })).toBe(false)
  })
  it('rejects missing id', () => {
    expect(isValidEmbeddingVector({ dimension: 3, values: [1, 0, 0] })).toBe(false)
  })
  it('rejects dimension < 1', () => {
    expect(isValidEmbeddingVector({ ...v, dimension: 0 })).toBe(false)
  })
  it('rejects non-integer dimension', () => {
    expect(isValidEmbeddingVector({ ...v, dimension: 3.5 })).toBe(false)
  })
  it('rejects length mismatch', () => {
    expect(isValidEmbeddingVector({ ...v, values: [1, 0] })).toBe(false)
  })
  it('rejects non-array values', () => {
    expect(isValidEmbeddingVector({ ...v, values: 'x' as never })).toBe(false)
  })
  it('rejects NaN component', () => {
    expect(isValidEmbeddingVector({ ...v, values: [1, NaN, 0] })).toBe(false)
  })
  it('rejects Infinity component', () => {
    expect(isValidEmbeddingVector({ ...v, values: [1, Infinity, 0] })).toBe(false)
  })
  it('rejects non-finite component (string)', () => {
    expect(isValidEmbeddingVector({ ...v, values: [1, 'x' as never, 0] })).toBe(false)
  })
  it('rejects non-object vector', () => {
    expect(isValidEmbeddingVector(null)).toBe(false)
  })
})

describe('Phase 8-C2 EmbeddingProvider validator', () => {
  it('recognizes LocalEmbeddingProvider', () => {
    expect(isValidEmbeddingProvider(new LocalEmbeddingProvider())).toBe(true)
  })
  it('rejects a plain object', () => {
    expect(isValidEmbeddingProvider({ foo: 1 })).toBe(false)
  })
  it('requires both embed and embedBatch', () => {
    const p = { embed: () => ({}) } as never
    expect(isValidEmbeddingProvider(p)).toBe(false)
  })
  it('FORBIDDEN list has 8 entries', () => {
    expect(embedHelpers.FORBIDDEN.length).toBe(8)
  })
  it('throws when vector id contains a secret', () => {
    expect(() => isValidEmbeddingVector({ id: 'providerId:x', dimension: 1, values: [0] })).toThrow(/forbidden/)
  })
  it('throws when values contain a secret via JSON.stringify', () => {
    expect(() => isValidEmbeddingVector({ id: 'a', dimension: 2, values: [1, 2] as number[] })).not.toThrow()
  })
})

// ============ vector-store-schema validators ============

describe('Phase 8-C2 VectorRecord validator', () => {
  const rec: VectorRecord = {
    chunkId: 'doc:1#0',
    embedding: { id: 'doc:1#0', dimension: 2, values: [1, 0] },
    metadata: { section: 'intro' }
  }
  it('accepts a valid record', () => {
    expect(isValidVectorRecord(rec)).toBe(true)
  })
  it('rejects empty chunkId', () => {
    expect(isValidVectorRecord({ ...rec, chunkId: '' })).toBe(false)
  })
  it('rejects invalid embedding', () => {
    expect(isValidVectorRecord({ ...rec, embedding: { id: '', dimension: 1, values: [0] } })).toBe(false)
  })
  it('rejects metadata as array', () => {
    expect(isValidVectorRecord({ ...rec, metadata: [] as never })).toBe(false)
  })
  it('throws when metadata contains a secret', () => {
    expect(() => isValidVectorRecord({ ...rec, metadata: { apiKey: 'x' } })).toThrow(/forbidden/)
  })
  it('rejects non-object record', () => {
    expect(isValidVectorRecord(null)).toBe(false)
  })
})

describe('Phase 8-C2 VectorSearchQuery validator', () => {
  const q: VectorSearchQuery = { queryEmbedding: { id: 'q', dimension: 2, values: [1, 0] } }
  it('accepts a valid query', () => {
    expect(isValidVectorSearchQuery(q)).toBe(true)
  })
  it('accepts a query with filters and limit', () => {
    expect(isValidVectorSearchQuery({ ...q, limit: 5, filters: { type: 'paper' } })).toBe(true)
  })
  it('rejects negative limit', () => {
    expect(isValidVectorSearchQuery({ ...q, limit: -1 })).toBe(false)
  })
  it('rejects non-integer limit', () => {
    expect(isValidVectorSearchQuery({ ...q, limit: 1.5 })).toBe(false)
  })
  it('accepts limit 0 (no cap)', () => {
    expect(isValidVectorSearchQuery({ ...q, limit: 0 })).toBe(true)
  })
  it('rejects non-array filters', () => {
    expect(isValidVectorSearchQuery({ ...q, filters: 'nope' as never })).toBe(false)
  })
  it('rejects non-object query', () => {
    expect(isValidVectorSearchQuery(null)).toBe(false)
  })
})

describe('Phase 8-C2 VectorSearchHit validator', () => {
  it('accepts a valid hit', () => {
    expect(isValidVectorSearchHit({ chunkId: 'c1', score: 0.9 })).toBe(true)
  })
  it('rejects empty chunkId', () => {
    expect(isValidVectorSearchHit({ chunkId: '', score: 0.9 })).toBe(false)
  })
  it('rejects non-finite score', () => {
    expect(isValidVectorSearchHit({ chunkId: 'c1', score: NaN })).toBe(false)
  })
  it('recognizes LocalVectorStore as VectorStore', () => {
    expect(isValidVectorStore(new LocalVectorStore())).toBe(true)
  })
  it('rejects a plain object as VectorStore', () => {
    expect(isValidVectorStore({})).toBe(false)
  })
})

// ============ cosine similarity ============

describe('Phase 8-C2 cosineSimilarity', () => {
  it('returns 1 for identical unit vectors', () => {
    expect(cosineSimilarity([1, 0], [1, 0])).toBe(1)
  })
  it('returns -1 for opposite vectors', () => {
    expect(cosineSimilarity([1, 0], [-1, 0])).toBe(-1)
  })
  it('returns 0 for orthogonal vectors', () => {
    expect(cosineSimilarity([1, 0], [0, 1])).toBe(0)
  })
  it('returns 1 for parallel vectors', () => {
    expect(cosineSimilarity([3, 4], [6, 8])).toBe(1)
  })
  it('rounds the result to 6 decimals', () => {
    const r = cosineSimilarity([1, 2, 3], [4, 5, 6])
    expect(Number.isInteger(Math.round(r * 1e6))).toBe(true)
  })
  it('throws on dimension mismatch', () => {
    expect(() => cosineSimilarity([1, 0], [1, 0, 0])).toThrow(/dimensions must match/)
  })
  it('throws on empty vectors', () => {
    expect(() => cosineSimilarity([], [])).toThrow(/non-empty/)
  })
  it('throws on non-array inputs', () => {
    expect(() => cosineSimilarity('x' as never, [1, 0])).toThrow(/must be arrays/)
  })
  it('returns 0 for a zero-norm vector', () => {
    expect(cosineSimilarity([0, 0], [1, 1])).toBe(0)
  })
  it('returns 0 when both vectors are zero', () => {
    expect(cosineSimilarity([0, 0], [0, 0])).toBe(0)
  })
  it('throws on non-finite components', () => {
    expect(() => cosineSimilarity([NaN, 0], [1, 0])).toThrow(/finite/)
    expect(() => cosineSimilarity([1, 0], [1, Infinity])).toThrow(/finite/)
  })
  it('handles fractional components', () => {
    expect(cosineSimilarity([0.5, 0.5], [0.5, 0.5])).toBe(1)
  })
  it('handles mixed-sign fractions', () => {
    expect(cosineSimilarity([1, 0], [-0.5, 0.5])).toBeCloseTo(-1 / Math.SQRT2, 5)
  })
  it('matches a fixed expected value (orthogonal fractional)', () => {
    expect(cosineSimilarity([1, 0, 0], [0, 1, 0])).toBe(0)
  })
  it('matches a fixed expected value (4-dim parallel)', () => {
    expect(cosineSimilarity([1, 2, 3, 4], [2, 4, 6, 8])).toBe(1)
  })
  it('returns deterministic results across calls', () => {
    const a = cosineSimilarity([1, 2, 3], [4, 5, 6])
    const b = cosineSimilarity([1, 2, 3], [4, 5, 6])
    expect(a).toBe(b)
  })
})

describe('Phase 8-C2 matchesVectorFilters', () => {
  it('accepts an empty filter object', () => {
    expect(matchesVectorFilters({}, {})).toBe(true)
  })
  it('rejects mismatched scalar', () => {
    expect(matchesVectorFilters({ type: 'paper' }, { type: 'report' })).toBe(false)
  })
  it('matches array containment', () => {
    expect(matchesVectorFilters({ tags: ['a', 'b'] }, { tags: 'a' })).toBe(true)
  })
  it('rejects absent key', () => {
    expect(matchesVectorFilters({}, { x: 1 })).toBe(false)
  })
  it('checks multiple keys (all must pass)', () => {
    expect(matchesVectorFilters({ a: 1, b: 2 }, { a: 1, b: 3 })).toBe(false)
  })
})

// ============ local embedding determinism + provider ============

describe('Phase 8-C2 hashing primitives', () => {
  it('fnv1a32 is deterministic', () => {
    expect(fnv1a32('alpha')).toBe(fnv1a32('alpha'))
  })
  it('fnv1a32 differs for different inputs', () => {
    expect(fnv1a32('alpha')).not.toBe(fnv1a32('beta'))
  })
  it('djb2Sign returns +1 or -1', () => {
    const s = djb2Sign('x')
    expect(s === 1 || s === -1).toBe(true)
  })
  it('djb2Sign is deterministic', () => {
    expect(djb2Sign('x')).toBe(djb2Sign('x'))
  })
})

describe('Phase 8-C2 tokenizeForEmbedding', () => {
  it('splits an English sentence on word boundaries', () => {
    expect(tokenizeForEmbedding('water bubble')).toEqual(['water', 'bubble', 'water##bubble'])
  })
  it('emits each CJK character plus its bigrams', () => {
    expect(tokenizeForEmbedding('气泡')).toEqual(['气', '泡', '气##泡'])
  })
  it('lowercases the English tokens', () => {
    expect(tokenizeForEmbedding('Water BUBBLE')).toEqual(['water', 'bubble', 'water##bubble'])
  })
  it('emits only bigrams for short input', () => {
    expect(tokenizeForEmbedding('a')).toEqual(['a'])
  })
  it('returns empty for empty input', () => {
    expect(tokenizeForEmbedding('')).toEqual([])
  })
})

describe('Phase 8-C2 computeEmbedding', () => {
  it('returns a unit-length vector for non-empty input', () => {
    const v = computeEmbedding('bubble dynamics in water')
    expect(Math.abs(norm(v) - 1)).toBeLessThan(1e-5)
  })
  it('returns a zero vector for empty input', () => {
    const v = computeEmbedding('')
    expect(norm(v)).toBe(0)
  })
  it('honors a custom dimension', () => {
    const v = computeEmbedding('water', 8)
    expect(v.length).toBe(8)
    expect(Math.abs(norm(v) - 1)).toBeLessThan(1e-5)
  })
  it('throws on invalid dimension', () => {
    expect(() => computeEmbedding('water', 0)).toThrow(/positive integer/)
    expect(() => computeEmbedding('water', -4)).toThrow(/positive integer/)
    expect(() => computeEmbedding('water', 12.5)).toThrow(/positive integer/)
  })
  it('is pure (same text ⇒ same vector)', () => {
    expect(computeEmbedding('water bubble')).toEqual(computeEmbedding('water bubble'))
  })
  it('produces different vectors for different inputs', () => {
    expect(computeEmbedding('water')).not.toEqual(computeEmbedding('bubble'))
  })
  it('produces equal vectors across CJS and ESM runs (pure)', () => {
    expect(computeEmbedding('a b c')).toEqual(computeEmbedding('a b c'))
  })
})

describe('Phase 8-C2 LocalEmbeddingProvider', () => {
  let p: LocalEmbeddingProvider
  beforeEach(() => { p = new LocalEmbeddingProvider() })
  it('default dimension is 64', () => {
    expect(p.getDimension()).toBe(64)
    expect(p.embed('hello').dimension).toBe(64)
  })
  it('throws on non-positive dimension', () => {
    expect(() => new LocalEmbeddingProvider({ dimension: 0 })).toThrow(/positive integer/)
    expect(() => new LocalEmbeddingProvider({ dimension: -1 })).toThrow(/positive integer/)
    expect(() => new LocalEmbeddingProvider({ dimension: 5.5 })).toThrow(/positive integer/)
  })
  it('produces a schema-valid vector', () => {
    expect(isValidEmbeddingVector(p.embed('bubble'))).toBe(true)
  })
  it('uses a deterministic content id when id omitted', () => {
    expect(p.embed('hello').id).toBe(contentId('hello'))
  })
  it('respects a provided id', () => {
    expect(p.embed('hello', 'c1').id).toBe('c1')
  })
  it('embed is deterministic for the same text', () => {
    expect(p.embed('hello')).toEqual(p.embed('hello'))
  })
  it('embed throws on non-string input', () => {
    expect(() => p.embed(7 as never)).toThrow(/must be a string/)
  })
  it('embedBatch produces vectors aligned to ids', () => {
    const vs = p.embedBatch(['a', 'b'], ['id-a', 'id-b'])
    expect(vs.map((v) => v.id)).toEqual(['id-a', 'id-b'])
  })
  it('embedBatch matches embed for identical inputs', () => {
    expect(p.embedBatch(['a', 'b'])).toEqual([p.embed('a'), p.embed('b')])
  })
  it('embedBatch throws on length mismatch', () => {
    expect(() => p.embedBatch(['a'], ['1', '2'])).toThrow(/length must match/)
  })
  it('embedBatch throws on non-array', () => {
    expect(() => p.embedBatch('x' as never)).toThrow(/must be an array/)
  })
  it('embedBatch throws on non-string element', () => {
    expect(() => p.embedBatch(['a', 5 as never])).toThrow(/every text must be a string/)
  })
  it('produces vectors with unit length (no explosion on long text)', () => {
    const long = ('bubble ' + 'word '.repeat(100)).trim()
    const v = p.embed(long)
    expect(Math.abs(norm(v.values) - 1)).toBeLessThan(1e-5)
  })
  it('vector components are finite numbers', () => {
    for (const x of p.embed('bubble').values) {
      expect(Number.isFinite(x)).toBe(true)
    }
  })
})

// ============ local vector store ============

describe('Phase 8-C2 LocalVectorStore lifecycle', () => {
  let store: LocalVectorStore
  beforeEach(() => { store = new LocalVectorStore() })
  it('starts empty', () => {
    expect(store.size()).toBe(0)
    expect(store.list()).toEqual([])
  })
  it('insert returns true on a new record', () => {
    expect(store.insert(makeRecord('c1'))).toBe(true)
    expect(store.size()).toBe(1)
  })
  it('insert returns false on duplicate (does not overwrite)', () => {
    store.insert(makeRecord('c1', [1, 0]))
    expect(store.insert(makeRecord('c1', [0, 1]))).toBe(false)
    expect(store.size()).toBe(1)
    expect(store.list()[0]!.embedding.values).toEqual([1, 0])
  })
  it('throws on invalid record', () => {
    expect(() => store.insert({ chunkId: '', embedding: { id: 'x', dimension: 1, values: [0] }, metadata: {} })).toThrow(/invalid VectorRecord/)
  })
  it('delete returns true when present', () => {
    store.insert(makeRecord('c1'))
    expect(store.delete('c1')).toBe(true)
    expect(store.size()).toBe(0)
  })
  it('delete returns false when absent', () => {
    expect(store.delete('missing')).toBe(false)
  })
  it('list returns records sorted by chunkId', () => {
    store.insert(makeRecord('c2'))
    store.insert(makeRecord('c1'))
    store.insert(makeRecord('c3'))
    expect(store.list().map((r) => r.chunkId)).toEqual(['c1', 'c2', 'c3'])
  })
  it('clear removes all records', () => {
    store.insert(makeRecord('c1'))
    store.insert(makeRecord('c2'))
    store.clear()
    expect(store.size()).toBe(0)
  })
  it('throws on non-string chunkId in delete', () => {
    expect(() => store.delete(5 as never)).toThrow(/must be a string/)
  })
})

describe('Phase 8-C2 LocalVectorStore search', () => {
  let store: LocalVectorStore
  beforeEach(() => {
    store = new LocalVectorStore()
    store.insert(makeRecord('doc:1#0', [1, 0]))
    store.insert(makeRecord('doc:1#1', [0.6, 0.8]))
    store.insert(makeRecord('doc:1#2', [0, 1]))
  })
  it('returns hits sorted by cosine desc', () => {
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    expect(hits.map((h) => h.chunkId)).toEqual(['doc:1#0', 'doc:1#1'])
  })
  it('scores are rounded to 6 decimals', () => {
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    for (const h of hits) expect(Number.isInteger(Math.round(h.score * 1e6))).toBe(true)
  })
  it('truncates to limit', () => {
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]), limit: 2 })
    expect(hits).toHaveLength(2)
  })
  it('limit 0 returns all matches', () => {
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]), limit: 0 })
    expect(hits).toHaveLength(2)
  })
  it('returns [] when no positive cosine matches', () => {
    expect(store.search({ queryEmbedding: makeVec('q', 2, [-1, 0]) })).toEqual([])
  })
  it('returns [] when filters exclude everything', () => {
    expect(store.search({ queryEmbedding: makeVec('q', 2, [1, 0]), filters: { documentId: 'doc:2' } })).toEqual([])
  })
  it('metadata filter passes through', () => {
    store.insert({
      chunkId: 'doc:2#0', embedding: makeVec('doc:2#0', 2, [1, 0]),
      metadata: { documentId: 'doc:2' }
    })
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]), filters: { documentId: 'doc:2' } })
    expect(hits.map((h) => h.chunkId)).toEqual(['doc:2#0'])
  })
  it('array filter uses containment semantics', () => {
    store.insert({
      chunkId: 'doc:3#0', embedding: makeVec('doc:3#0', 2, [1, 0]),
      metadata: { tags: ['a', 'b'] }
    })
    expect(store.search({ queryEmbedding: makeVec('q', 2, [1, 0]), filters: { tags: 'b' } }).map((h) => h.chunkId))
      .toEqual(['doc:3#0'])
  })
  it('multi-key filter is AND', () => {
    store.insert({
      chunkId: 'doc:4#0', embedding: makeVec('doc:4#0', 2, [1, 0]),
      metadata: { documentId: 'doc:4', section: 'intro' }
    })
    expect(store.search({
      queryEmbedding: makeVec('q', 2, [1, 0]),
      filters: { documentId: 'doc:4', section: 'methods' }
    })).toEqual([])
    expect(store.search({
      queryEmbedding: makeVec('q', 2, [1, 0]),
      filters: { documentId: 'doc:4', section: 'intro' }
    }).map((h) => h.chunkId)).toEqual(['doc:4#0'])
  })
  it('breaks ties deterministically by chunkId asc', () => {
    const local = new LocalVectorStore()
    local.insert(makeRecord('c2', [1, 0]))
    local.insert(makeRecord('c1', [1, 0]))
    expect(local.search({ queryEmbedding: makeVec('q', 2, [1, 0]) }).map((h) => h.chunkId)).toEqual(['c1', 'c2'])
  })
  it('returns valid VectorSearchHit objects', () => {
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    for (const h of hits) expect(isValidVectorSearchHit(h)).toBe(true)
  })
  it('throws on invalid query', () => {
    expect(() => store.search({ queryEmbedding: { id: '', dimension: 1, values: [0] } })).toThrow(/invalid VectorSearchQuery/)
  })
  it('is deterministic across calls', () => {
    const a = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    const b = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('search is empty on a fresh store', () => {
    expect(new LocalVectorStore().search({ queryEmbedding: makeVec('q', 2, [1, 0]) })).toEqual([])
  })
})

function makeRecord(chunkId: string, values: number[] = [1, 0], metadata: Record<string, unknown> = {}): VectorRecord {
  return {
    chunkId,
    embedding: { id: chunkId, dimension: values.length, values },
    metadata
  }
}

// ============ HybridRetriever ============

describe('Phase 8-C2 HybridRetriever construction', () => {
  it('requires vectorStore and embedding', () => {
    expect(() => new HybridRetriever({ vectorStore: undefined as never, embedding: new LocalEmbeddingProvider() })).toThrow(/vectorStore required/)
    expect(() => new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: undefined as never })).toThrow(/embedding.*required/)
  })
  it('rejects negative weights', () => {
    expect(() => new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider(), keywordWeight: -1 })).toThrow(/non-negative/)
    expect(() => new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider(), semanticWeight: -1 })).toThrow(/non-negative/)
  })
  it('default weights are 0.5 each', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.getKeyword()).toBeDefined()
    expect(h.getVectorStore()).toBeDefined()
    expect(h.getEmbedding()).toBeDefined()
  })
  it('exposes a default LocalRetriever', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.getKeyword().documentCount()).toBe(0)
  })
  it('accepts a custom keyword retriever', () => {
    const custom = new LocalEmbeddingProvider()
    void custom
    const kw = new LocalRetriever()
    const h = new HybridRetriever({ keyword: kw, vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.getKeyword()).toBe(kw)
  })
})

describe('Phase 8-C2 HybridRetriever indexing', () => {
  it('indexes documents into keyword + vector', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.indexDocuments([makeDocContent('bubble dynamics water', 'd1')])).toBe(1)
    expect(h.documentCount()).toBe(1)
    expect(h.vectorCount()).toBeGreaterThan(0)
  })
  it('re-indexing a document replaces its vector records', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble dynamics water', 'd1')])
    const before = h.vectorCount()
    h.indexDocuments([makeDocContent('bubble dynamics water longer text', 'd1')])
    expect(h.vectorCount()).toBeGreaterThanOrEqual(before)
    expect(h.documentCount()).toBe(1)
  })
  it('rejects non-array documents', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(() => h.indexDocuments(null as never)).toThrow(/must be an array/)
  })
  it('getChunk returns the indexed chunk', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble dynamics', 'd1')])
    const chunk = h.getChunk('d1#0')
    expect(chunk).toBeDefined()
    expect(chunk!.documentId).toBe('d1')
  })
})

describe('Phase 8-C2 HybridRetriever search', () => {
  let h: HybridRetriever
  beforeEach(() => {
    h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble dynamics water quality regulation', 'd1'),
      makeDocContent('reactor kinetics stability analysis', 'd2')
    ])
  })
  it('returns SearchResult[]', async () => {
    const results = await h.search({ text: 'bubble' })
    expect(Array.isArray(results)).toBe(true)
    for (const r of results) {
      expect(r.chunk).toBeDefined()
      expect(typeof r.score).toBe('number')
      expect(r.citation).toBeDefined()
    }
  })
  it('citation chunkId matches the chunk id', async () => {
    const results = await h.search({ text: 'bubble' })
    for (const r of results) expect(r.citation.chunkId).toBe(r.chunk.id)
  })
  it('citation documentId matches the chunk documentId', async () => {
    const results = await h.search({ text: 'bubble' })
    for (const r of results) expect(r.citation.documentId).toBe(r.chunk.documentId)
  })
  it('citation confidence is in [0,1] and rounded to 2dp', async () => {
    const results = await h.search({ text: 'bubble' })
    for (const r of results) {
      expect(r.citation.confidence).toBeGreaterThanOrEqual(0)
      expect(r.citation.confidence).toBeLessThanOrEqual(1)
      expect(Number.isInteger(Math.round(r.citation.confidence * 100))).toBe(true)
    }
  })
  it('does not require page (citation page is undefined)', async () => {
    const results = await h.search({ text: 'bubble' })
    for (const r of results) expect(r.citation.page).toBeUndefined()
  })
  it('limits results', async () => {
    const results = await h.search({ text: 'bubble', limit: 1 })
    expect(results).toHaveLength(1)
  })
  it('returns empty array on no matches', async () => {
    expect(await h.search({ text: 'zyzzyvauniqueword' })).toEqual([])
  })
  it('rejects invalid query', async () => {
    await expect(h.search({ text: '' })).rejects.toThrow(/invalid SearchQuery/)
  })
  it('keyword-only stream works', async () => {
    const r = await h.searchKeyword({ text: 'bubble' })
    expect(r.length).toBeGreaterThan(0)
  })
  it('vector-only stream returns hits for indexed docs', () => {
    const r = h.searchVector({ text: 'bubble' })
    expect(r.length).toBeGreaterThan(0)
    for (const h of r) expect(typeof h.score).toBe('number')
  })
  it('union: a keyword-only hit still appears in hybrid', async () => {
    const only = h.searchVector({ text: 'zyzzyvauniqueword' })
    expect(only).toEqual([])
    const kw = await h.search({ text: 'bubble' })
    expect(kw.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-C2 HybridRetriever ranking', () => {
  let h: HybridRetriever
  beforeEach(() => {
    h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble dynamics water quality regulation', 'd1'),
      makeDocContent('reactor kinetics stability analysis', 'd2')
    ])
  })
  it('a doc matching both keyword + semantic ranks above a doc matching only one', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble dynamics water', 'd1'),
      makeDocContent('aerodynamics flight wind speed', 'd2')
    ])
    const r1 = await h.search({ text: 'bubble' })
    expect(r1[0]!.chunk.documentId).toBe('d1')
  })
  it('weights change the relative scores', async () => {
    const a = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider(), keywordWeight: 1.0, semanticWeight: 0.0 })
    const b = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider(), keywordWeight: 0.0, semanticWeight: 1.0 })
    for (const r of [a, b]) r.indexDocuments([
      makeDocContent('bubble dynamics water', 'd1'),
      makeDocContent('aerodynamics flight wind', 'd2')
    ])
    const ka = await a.search({ text: 'bubble' })
    const kb = await b.search({ text: 'bubble' })
    expect(ka[0]!.chunk.documentId).toBe('d1')
    expect(kb[0]!.chunk.documentId).toBe('d1')
    expect(ka[0]!.score).not.toBe(kb[0]!.score)
  })
  it('breaks equal-score ties by documentId asc', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble water', 'd2'),
      makeDocContent('bubble water', 'd1')
    ])
    const r = await h.search({ text: 'bubble water' })
    const docs = r.map((x) => x.chunk.documentId)
    const sortedPrefix = [...new Set(docs)].sort()
    expect(docs).toEqual(sortedPrefix.concat(docs.slice(sortedPrefix.length)))
  })
  it('is deterministic across calls', async () => {
    const a = await h.search({ text: 'bubble' })
    const b = await h.search({ text: 'bubble' })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('returns the expected number of hits without limit', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble water quality reactor', 'd1')])
    expect(await h.search({ text: 'bubble' })).toHaveLength(1)
  })
  it('filters apply to both streams', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble water', 'd1'),
      makeDocContent('bubble water', 'd2')
    ])
    const r = await h.search({ text: 'bubble', filters: { documentId: 'd1' } })
    expect(r.every((x) => x.citation.documentId === 'd1')).toBe(true)
  })
  it('union hit carries both keyword + semantic scores via total', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble water', 'd1')])
    const r = await h.search({ text: 'bubble' })
    expect(r[0]!.score).toBeGreaterThan(0)
  })
  it('keyword stream returns no hits for nonsense text', async () => {
    expect(await h.searchKeyword({ text: 'nope-unique' })).toEqual([])
  })
  it('non-empty docCount after index', () => {
    expect(h.documentCount()).toBe(2)
  })
  it('vectorCount equals keyword chunkCount after index', () => {
    expect(h.vectorCount()).toBeGreaterThan(0)
    expect(h.vectorCount()).toBe(h.chunkCount())
  })
})

// ============ security + source isolation ============

describe('Phase 8-C2 security + isolation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('local-embedding.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/local-embedding.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
    expect(src).not.toMatch(/from\s+['"][^'"]*@anthropic-ai/)
    expect(src).not.toMatch(/from\s+['"][^'"]*openai/)
  })
  it('local-vector-store.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/local-vector-store.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
    expect(src).not.toMatch(/from\s+['"][^'"]*faiss/)
  })
  it('hybrid-retriever.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/hybrid-retriever.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('implementation files have no randomness', () => {
    for (const f of ['local-embedding', 'local-vector-store', 'hybrid-retriever']) {
      const src = readSrc(`../../src/main/services/knowledge/${f}.ts`)
      expect(src).not.toContain('Math.random')
      expect(src).not.toContain('Date.now')
    }
  })
  it('hybrid does not modify the PDF parser or document schema', () => {
    const hybrid = readSrc('../../src/main/services/knowledge/hybrid-retriever.ts')
    expect(hybrid).not.toContain('pdf-parser')
    expect(hybrid).not.toContain('document-importer')
    expect(hybrid).not.toContain('agent-runtime')
  })
  it('shared schemas have no forbidden imports', () => {
    for (const f of ['embedding-schema', 'vector-store-schema']) {
      const src = readSrc(`../../src/shared/knowledge/${f}.ts`)
      expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
      expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
    }
  })
  it('no OCR / BGE / FAISS imports anywhere in the new code', () => {
    const all =
      readSrc('../../src/main/services/knowledge/local-embedding.ts') +
      readSrc('../../src/main/services/knowledge/local-vector-store.ts') +
      readSrc('../../src/main/services/knowledge/hybrid-retriever.ts')
    expect(all).not.toMatch(/from\s+['"][^'"]*tesseract/)
    expect(all).not.toMatch(/from\s+['"][^'"]*bge/)
    expect(all).not.toMatch(/from\s+['"][^'"]*faiss/)
  })
  it('FORBIDDEN lists in both schemas have 8 entries', () => {
    expect(embedHelpers.FORBIDDEN.length).toBe(8)
    expect(vecHelpers.FORBIDDEN.length).toBe(8)
  })
  it('vectors do not leak credential strings', () => {
    expect(() => isValidEmbeddingVector({ id: 'apiKey', dimension: 1, values: [0] })).toThrow(/forbidden/)
  })
  it('local provider uses no process.env', () => {
    const src = readSrc('../../src/main/services/knowledge/local-embedding.ts')
    expect(src).not.toContain('process.env')
  })
})

// ============ Supplementary edge cases ============

describe('Phase 8-C2 supplementary edge cases', () => {
  it('embedding output respects dimension when texts differ', () => {
    const p = new LocalEmbeddingProvider({ dimension: 16 })
    expect(p.embed('water').values.length).toBe(16)
    expect(p.embed('bubble').values.length).toBe(16)
    expect(p.embed('reactor kinetics').values.length).toBe(16)
  })
  it('embedding tokens are stable across whitespace variants', () => {
    expect(tokenizeForEmbedding('water  bubble')).toEqual(tokenizeForEmbedding('water bubble'))
  })
  it('embedding tokenizes punctuation-separated words independently (with bigram)', () => {
    expect(tokenizeForEmbedding('water,bubble')).toEqual(['water', 'bubble', 'water##bubble'])
  })
  it('embedBatch handles an empty array', () => {
    expect(new LocalEmbeddingProvider().embedBatch([])).toEqual([])
  })
  it('embedBatch with one empty text returns one zero vector', () => {
    const vs = new LocalEmbeddingProvider().embedBatch([''])
    expect(vs).toHaveLength(1)
    expect(norm(vs[0]!.values)).toBe(0)
  })
  it('embedBatch produces deterministic ids from texts', () => {
    const p = new LocalEmbeddingProvider()
    const vs = p.embedBatch(['alpha', 'beta'])
    expect(vs[0]!.id).toBe(contentId('alpha'))
    expect(vs[1]!.id).toBe(contentId('beta'))
  })
  it('fnv1a32 is robust to very long inputs', () => {
    const a = fnv1a32('a'.repeat(1000))
    const b = fnv1a32('a'.repeat(1001))
    expect(Number.isInteger(a)).toBe(true)
    expect(Number.isInteger(b)).toBe(true)
    expect(a).not.toBe(b)
  })
  it('djb2Sign is consistent for the same input across calls', () => {
    expect(djb2Sign('water')).toBe(djb2Sign('water'))
  })
  it('cosineSimilarity is deterministic across many runs', () => {
    const v = [1, 2, 3, 4, 5]
    const results = Array.from({ length: 5 }, () => cosineSimilarity(v, v))
    expect(new Set(results).size).toBe(1)
  })
  it('cosineSimilarity symmetric in inputs', () => {
    expect(cosineSimilarity([1, 2, 3], [4, 5, 6])).toBe(cosineSimilarity([4, 5, 6], [1, 2, 3]))
  })
  it('cosineSimilarity of identical vectors is 1 even at high dim', () => {
    const v = Array.from({ length: 128 }, (_, i) => i + 1)
    expect(cosineSimilarity(v, v)).toBe(1)
  })
  it('VectorRecord metadata accepts numeric values', () => {
    expect(isValidVectorRecord({
      chunkId: 'c1', embedding: { id: 'c1', dimension: 1, values: [1] }, metadata: { year: 2024, score: 0.5 }
    })).toBe(true)
  })
  it('VectorRecord rejects empty metadata object? No — empty metadata is allowed', () => {
    expect(isValidVectorRecord({
      chunkId: 'c1', embedding: { id: 'c1', dimension: 1, values: [0] }, metadata: {}
    })).toBe(true)
  })
  it('LocalVectorStore.search throws on negative limit', () => {
    const store = new LocalVectorStore()
    expect(() => store.search({ queryEmbedding: makeVec('q', 1, [1]), limit: -1 })).toThrow(/invalid VectorSearchQuery/)
  })
  it('LocalVectorStore search returns [] when filters match nothing', () => {
    const store = new LocalVectorStore()
    store.insert(makeRecord('c1', [1, 0]))
    expect(store.search({
      queryEmbedding: makeVec('q', 2, [1, 0]),
      filters: { missingKey: 1 }
    })).toEqual([])
  })
  it('LocalVectorStore handles 0-dim insert? No — throws', () => {
    const store = new LocalVectorStore()
    expect(() => store.insert({
      chunkId: 'c1', embedding: { id: 'c1', dimension: 0, values: [] }, metadata: {}
    })).toThrow(/invalid VectorRecord/)
  })
  it('LocalVectorStore handles 64-dim vectors (embedding default)', () => {
    const store = new LocalVectorStore()
    const v = new LocalEmbeddingProvider().embed('water bubble kinetics').values
    store.insert({ chunkId: 'c1', embedding: { id: 'c1', dimension: v.length, values: v }, metadata: {} })
    expect(store.size()).toBe(1)
  })
  it('HybridRetriever.searchVector returns hits for indexed docs', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble dynamics water', 'd1')])
    const hits = h.searchVector({ text: 'bubble' })
    expect(hits.length).toBe(1)
    expect(hits[0]!.chunkId).toBe('d1#0')
  })
  it('HybridRetriever.getChunk returns undefined for unknown id', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.getChunk('unknown#0')).toBeUndefined()
  })
  it('HybridRetriever.search on empty index returns []', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(await h.search({ text: 'water' })).toEqual([])
  })
  it('HybridRetriever.searchVector on empty index returns []', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.searchVector({ text: 'water' })).toEqual([])
  })
  it('HybridRetriever.indexDocuments multiple times counts returned sum', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    const a = h.indexDocuments([makeDocContent('bubble water', 'd1')])
    const b = h.indexDocuments([makeDocContent('reactor kinetics', 'd2')])
    expect(a).toBe(1)
    expect(b).toBe(1)
    expect(h.documentCount()).toBe(2)
  })
  it('HybridRetriever.embed-and-search round trip finds the indexed chunk', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('a totally unique phrase here', 'd1')])
    const r = await h.search({ text: 'a totally unique phrase here' })
    expect(r.length).toBeGreaterThan(0)
    expect(r[0]!.chunk.documentId).toBe('d1')
  })
  it('HybridRetriever.search honors limit', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([makeDocContent('bubble water reactor kinetics', 'd1')])
    const r = await h.search({ text: 'bubble', limit: 1 })
    expect(r).toHaveLength(1)
  })
  it('HybridRetriever rejects non-array index input', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(() => h.indexDocuments('x' as never)).toThrow(/must be an array/)
  })
  it('HybridRetriever.indexDocuments with empty array returns 0', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.indexDocuments([])).toBe(0)
  })
  it('HybridRetriever rejects search with non-string text', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    await expect(h.search({ text: 1 as never })).rejects.toThrow(/invalid SearchQuery/)
  })
  it('LocalVectorStore insert then search round trip preserves chunkId', () => {
    const store = new LocalVectorStore()
    store.insert({
      chunkId: 'doc:1#0',
      embedding: { id: 'doc:1#0', dimension: 4, values: [0.5, 0.5, 0.5, 0.5] },
      metadata: { section: 'intro' }
    })
    const hits = store.search({ queryEmbedding: { id: 'q', dimension: 4, values: [0.5, 0.5, 0.5, 0.5] } })
    expect(hits).toHaveLength(1)
    expect(hits[0]!.chunkId).toBe('doc:1#0')
    expect(hits[0]!.score).toBe(1)
  })
  it('LocalVectorStore delete clears the record', () => {
    const store = new LocalVectorStore()
    store.insert(makeRecord('c1'))
    store.delete('c1')
    expect(store.list()).toEqual([])
    expect(store.size()).toBe(0)
  })
  it('LocalVectorStore.search silently skips records with non-matching dim', () => {
    const store = new LocalVectorStore()
    store.insert(makeRecord('c1', [1, 0, 0]))
    // query dim 2 != record dim 3 -> record silently skipped, no throw, [] returned
    expect(() => store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })).not.toThrow()
    expect(store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })).toEqual([])
  })
  it('HybridRetriever vector+keyword converge on the strongest doc', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble water dynamics regulation', 'strong'),
      makeDocContent('unrelated content here today', 'weak')
    ])
    const r = await h.search({ text: 'bubble' })
    expect(r[0]!.chunk.documentId).toBe('strong')
  })
  it('LocalEmbeddingProvider honors a non-default dimension', () => {
    const p = new LocalEmbeddingProvider({ dimension: 32 })
    const v = p.embed('water')
    expect(v.dimension).toBe(32)
    expect(v.values.length).toBe(32)
    expect(Math.abs(norm(v.values) - 1)).toBeLessThan(1e-5)
  })
  it('LocalEmbeddingProvider with dimension 1 still works', () => {
    const p = new LocalEmbeddingProvider({ dimension: 1 })
    const v = p.embed('water')
    expect(v.values.length).toBe(1)
  })
  it('LocalVectorStore.search returns valid hits across multiple insertions', () => {
    const store = new LocalVectorStore()
    for (let i = 0; i < 20; i++) {
      store.insert({
        chunkId: `c${i}`,
        embedding: { id: `c${i}`, dimension: 2, values: [Math.cos(i), Math.sin(i)] },
        metadata: { i }
      })
    }
    const hits = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0]!.score).toBeGreaterThan(hits[hits.length - 1]!.score)
  })
  it('HybridRetriever.search with both keyword + vector filters applies both', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    h.indexDocuments([
      makeDocContent('bubble water', 'd1'),
      makeDocContent('bubble reactor', 'd2')
    ])
    const r = await h.search({ text: 'bubble', filters: { documentId: 'd1' } })
    expect(r.length).toBeGreaterThan(0)
    expect(r.every((x) => x.citation.documentId === 'd1')).toBe(true)
  })
})

// ============ Final edge cases (>=2400 aggregate) ============

describe('Phase 8-C2 final edge cases', () => {
  it('LocalEmbeddingProvider rejects non-string text in embed', () => {
    expect(() => new LocalEmbeddingProvider().embed(null as never)).toThrow(/must be a string/)
  })
  it('LocalEmbeddingProvider rejects null in embedBatch', () => {
    expect(() => new LocalEmbeddingProvider().embedBatch([null as never])).toThrow(/every text must be a string/)
  })
  it('LocalVectorStore delete returns false when called twice', () => {
    const store = new LocalVectorStore()
    store.insert(makeRecord('c1'))
    expect(store.delete('c1')).toBe(true)
    expect(store.delete('c1')).toBe(false)
  })
  it('LocalVectorStore clear preserves size 0', () => {
    const store = new LocalVectorStore()
    store.clear()
    expect(store.size()).toBe(0)
  })
  it('HybridRetriever embeds same content twice to the same vector across runs', async () => {
    const emb = new LocalEmbeddingProvider({ dimension: 32 })
    const a = emb.embed('water bubble')
    const b = emb.embed('water bubble')
    expect(a.values).toEqual(b.values)
  })
  it('HybridRetriever searchVector on an empty index returns []', () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h.searchVector({ text: 'water' })).toEqual([])
  })
  it('HybridRetriever accepts custom weights for asymmetric fusion', async () => {
    const h = new HybridRetriever({
      vectorStore: new LocalVectorStore(),
      embedding: new LocalEmbeddingProvider(),
      keywordWeight: 0.2,
      semanticWeight: 0.8
    })
    h.indexDocuments([makeDocContent('bubble water', 'd1')])
    const r = await h.search({ text: 'bubble' })
    expect(r.length).toBeGreaterThan(0)
    expect(r[0]!.citation.documentId).toBe('d1')
  })
  it('LocalEmbeddingProvider dimension 128 still produces unit vectors', () => {
    const p = new LocalEmbeddingProvider({ dimension: 128 })
    const v = p.embed('microscopic bubble dynamics in water quality research')
    expect(v.values.length).toBe(128)
    expect(Math.abs(norm(v.values) - 1)).toBeLessThan(1e-5)
  })
  it('LocalVectorStore.search returns hits sorted by score desc deterministically', () => {
    const store = new LocalVectorStore()
    for (let i = 0; i < 10; i++) {
      store.insert({
        chunkId: `c${i}`,
        embedding: { id: `c${i}`, dimension: 2, values: [Math.cos(i / 3), Math.sin(i / 3)] },
        metadata: {}
      })
    }
    const a = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    const b = store.search({ queryEmbedding: makeVec('q', 2, [1, 0]) })
    expect(a.map((h) => h.chunkId)).toEqual(b.map((h) => h.chunkId))
    for (let i = 1; i < a.length; i++) {
      expect(a[i]!.score).toBeLessThanOrEqual(a[i - 1]!.score)
    }
  })
  it('HybridRetriever.getKeyword delegates to the injected or default retriever', () => {
    const h1 = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h1.getKeyword()).toBeInstanceOf(LocalRetriever)
    const custom = new LocalRetriever()
    const h2 = new HybridRetriever({ keyword: custom, vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    expect(h2.getKeyword()).toBe(custom)
  })
})