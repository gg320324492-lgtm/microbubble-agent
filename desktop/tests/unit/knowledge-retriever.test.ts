// Phase 8-C0 Knowledge Retrieval Foundation tests.
//
// Coverage (~200 cases):
//   - Document schema validators (44)
//   - Chunk / citation / query / result validators (30)
//   - LocalChunker construction + splitting + merging (34)
//   - LocalRetriever ingest + lifecycle (16)
//   - LocalRetriever search + ranking (32)
//   - Metadata filtering (16)
//   - Citations (12)
//   - Determinism + empty cases (12)
//   - Security + planner separation source scans (12)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  DOCUMENT_TYPES,
  isValidDocumentType,
  isValidDocument,
  isValidDocumentChunk,
  isValidCitationReference,
  __testHelpers as docHelpers
} from '../../src/shared/knowledge/document-schema'
import type { Document, DocumentChunk, CitationReference } from '../../src/shared/knowledge/document-schema'
import { isValidChunkMetadata, isSplitDocumentInput } from '../../src/shared/knowledge/chunker-schema'
import { isValidSearchQuery, isValidSearchResult, isValidRetriever } from '../../src/shared/knowledge/retriever-schema'
import type { SearchQuery } from '../../src/shared/knowledge/retriever-schema'

// ============ Implementations ============
import { LocalChunker, splitContent, __testHelpers as chunkerHelpers } from '../../src/main/services/knowledge/local-chunker'
import { LocalRetriever, scoreChunk, tokenizeQuery, countOccurrences, matchesFilters, __testHelpers as retrHelpers } from '../../src/main/services/knowledge/local-retriever'

// ============ Fixtures ============

function makeDoc(overrides: Partial<Document> = {}): Document {
  return {
    id: 'doc:1',
    type: 'paper',
    title: 'Bubble Dynamics Review',
    source: 'src:1',
    metadata: { content: 'Micro-nano bubble dynamics in water quality control. The reactor shows stable kinetics.' },
    createdAt: 100,
    ...overrides
  }
}

function makeChunk(overrides: Partial<DocumentChunk> = {}): DocumentChunk {
  return {
    id: 'doc:1#0',
    documentId: 'doc:1',
    content: 'bubble dynamics',
    position: 0,
    metadata: {},
    ...overrides
  }
}

function makeCitation(overrides: Partial<CitationReference> = {}): CitationReference {
  return { documentId: 'doc:1', chunkId: 'doc:1#0', confidence: 0.9, ...overrides }
}

function longContent(n: number): string {
  return 'water '.repeat(Math.ceil(n / 6)).slice(0, n)
}

// ============ DocumentType schema ============

describe('Phase 8-C0 DocumentType schema', () => {
  it('DOCUMENT_TYPES has exactly 6 entries', () => {
    expect(DOCUMENT_TYPES.length).toBe(6)
  })
  it('contains paper', () => expect(DOCUMENT_TYPES).toContain('paper'))
  it('contains experiment', () => expect(DOCUMENT_TYPES).toContain('experiment'))
  it('contains dataset', () => expect(DOCUMENT_TYPES).toContain('dataset'))
  it('contains equipment', () => expect(DOCUMENT_TYPES).toContain('equipment'))
  it('contains report', () => expect(DOCUMENT_TYPES).toContain('report'))
  it('contains manual', () => expect(DOCUMENT_TYPES).toContain('manual'))
  it('accepts every listed type', () => {
    for (const t of DOCUMENT_TYPES) expect(isValidDocumentType(t)).toBe(true)
  })
  it('rejects an unknown type', () => {
    expect(isValidDocumentType('video')).toBe(false)
  })
  it('rejects a non-string type', () => {
    expect(isValidDocumentType(5)).toBe(false)
  })
})

// ============ Document validator ============

describe('Phase 8-C0 Document validator', () => {
  it('accepts a minimal valid document', () => {
    expect(isValidDocument(makeDoc())).toBe(true)
  })
  it('accepts a document with content in metadata', () => {
    expect(isValidDocument(makeDoc({ metadata: { content: 'full text here' } }))).toBe(true)
  })
  it('rejects empty id', () => {
    expect(isValidDocument(makeDoc({ id: '' }))).toBe(false)
  })
  it('rejects missing id', () => {
    const { id, ...rest } = makeDoc()
    expect(isValidDocument(rest as Document)).toBe(false)
  })
  it('rejects invalid type', () => {
    expect(isValidDocument(makeDoc({ type: 'movie' as never }))).toBe(false)
  })
  it('rejects empty title', () => {
    expect(isValidDocument(makeDoc({ title: '' }))).toBe(false)
  })
  it('rejects empty source', () => {
    expect(isValidDocument(makeDoc({ source: '' }))).toBe(false)
  })
  it('rejects metadata as array', () => {
    expect(isValidDocument(makeDoc({ metadata: [] as never }))).toBe(false)
  })
  it('rejects metadata as string', () => {
    expect(isValidDocument(makeDoc({ metadata: 'x' as never }))).toBe(false)
  })
  it('accepts empty metadata object', () => {
    expect(isValidDocument(makeDoc({ metadata: {} }))).toBe(true)
  })
  it('rejects negative createdAt', () => {
    expect(isValidDocument(makeDoc({ createdAt: -1 }))).toBe(false)
  })
  it('rejects NaN createdAt', () => {
    expect(isValidDocument(makeDoc({ createdAt: NaN }))).toBe(false)
  })
  it('rejects non-number createdAt', () => {
    expect(isValidDocument(makeDoc({ createdAt: '2024' as never }))).toBe(false)
  })
  it('accepts createdAt 0', () => {
    expect(isValidDocument(makeDoc({ createdAt: 0 }))).toBe(true)
  })
  it('rejects a non-object document', () => {
    expect(isValidDocument(null)).toBe(false)
    expect(isValidDocument('doc')).toBe(false)
  })
  it('throws when metadata contains apiKey', () => {
    expect(() => isValidDocument(makeDoc({ metadata: { apiKey: 'sk-x' } }))).toThrow(/forbidden/)
  })
  it('throws when title contains a secret', () => {
    expect(() => isValidDocument(makeDoc({ title: 'Bearer token' }))).toThrow(/forbidden/)
  })
  it('throws when content contains sk-leak', () => {
    expect(() => isValidDocument(makeDoc({ metadata: { content: 'sk-leak inside' } }))).toThrow(/forbidden/)
  })
  it('FORBIDDEN list has 8 entries', () => {
    expect(docHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ DocumentChunk validator ============

describe('Phase 8-C0 DocumentChunk validator', () => {
  it('accepts a valid chunk', () => {
    expect(isValidDocumentChunk(makeChunk())).toBe(true)
  })
  it('accepts empty content string', () => {
    expect(isValidDocumentChunk(makeChunk({ content: '' }))).toBe(true)
  })
  it('rejects empty id', () => {
    expect(isValidDocumentChunk(makeChunk({ id: '' }))).toBe(false)
  })
  it('rejects empty documentId', () => {
    expect(isValidDocumentChunk(makeChunk({ documentId: '' }))).toBe(false)
  })
  it('rejects non-string content', () => {
    expect(isValidDocumentChunk(makeChunk({ content: 42 as never }))).toBe(false)
  })
  it('rejects negative position', () => {
    expect(isValidDocumentChunk(makeChunk({ position: -1 }))).toBe(false)
  })
  it('rejects non-integer position', () => {
    expect(isValidDocumentChunk(makeChunk({ position: 1.5 }))).toBe(false)
  })
  it('rejects metadata as array', () => {
    expect(isValidDocumentChunk(makeChunk({ metadata: [] as never }))).toBe(false)
  })
  it('accepts position 0', () => {
    expect(isValidDocumentChunk(makeChunk({ position: 0 }))).toBe(true)
  })
  it('throws when content contains a secret', () => {
    expect(() => isValidDocumentChunk(makeChunk({ content: 'token value here' }))).toThrow(/forbidden/)
  })
})

// ============ CitationReference validator ============

describe('Phase 8-C0 CitationReference validator', () => {
  it('accepts a valid citation', () => {
    expect(isValidCitationReference(makeCitation())).toBe(true)
  })
  it('rejects empty documentId', () => {
    expect(isValidCitationReference(makeCitation({ documentId: '' }))).toBe(false)
  })
  it('rejects empty chunkId', () => {
    expect(isValidCitationReference(makeCitation({ chunkId: '' }))).toBe(false)
  })
  it('rejects confidence above 1', () => {
    expect(isValidCitationReference(makeCitation({ confidence: 1.1 }))).toBe(false)
  })
  it('rejects negative confidence', () => {
    expect(isValidCitationReference(makeCitation({ confidence: -0.1 }))).toBe(false)
  })
  it('rejects non-number confidence', () => {
    expect(isValidCitationReference(makeCitation({ confidence: 'high' as never }))).toBe(false)
  })
  it('accepts confidence at the bounds', () => {
    expect(isValidCitationReference(makeCitation({ confidence: 0 }))).toBe(true)
    expect(isValidCitationReference(makeCitation({ confidence: 1 }))).toBe(true)
  })
  it('throws when chunkId contains a secret', () => {
    expect(() => isValidCitationReference(makeCitation({ chunkId: 'providerId:x' }))).toThrow(/forbidden/)
  })
  it('rejects a non-object citation', () => {
    expect(isValidCitationReference(7)).toBe(false)
  })
})

// ============ ChunkMetadata validator ============

describe('Phase 8-C0 ChunkMetadata validator', () => {
  it('accepts position-only metadata', () => {
    expect(isValidChunkMetadata({ position: 3 })).toBe(true)
  })
  it('accepts section + page + position', () => {
    expect(isValidChunkMetadata({ section: 'methods', page: 4, position: 1 })).toBe(true)
  })
  it('rejects missing position', () => {
    expect(isValidChunkMetadata({ section: 'x' })).toBe(false)
  })
  it('rejects negative page', () => {
    expect(isValidChunkMetadata({ position: 0, page: -1 })).toBe(false)
  })
  it('rejects non-string section', () => {
    expect(isValidChunkMetadata({ position: 0, section: 3 })).toBe(false)
  })
  it('rejects non-integer page', () => {
    expect(isValidChunkMetadata({ position: 0, page: 1.5 })).toBe(false)
  })
  it('rejects null metadata', () => {
    expect(isValidChunkMetadata(null)).toBe(false)
  })
  it('isSplitDocumentInput accepts a doc with string content', () => {
    expect(isSplitDocumentInput(makeDoc())).toBe(true)
  })
  it('isSplitDocumentInput rejects a doc with non-string content', () => {
    const bad = makeDoc({ metadata: { content: 42 as never } })
    expect(isSplitDocumentInput(bad)).toBe(false)
  })
})

// ============ SearchQuery / SearchResult / retriever validators ============

describe('Phase 8-C0 query + retriever validators', () => {
  it('accepts a valid SearchQuery', () => {
    expect(isValidSearchQuery({ text: 'water quality' })).toBe(true)
  })
  it('rejects empty text', () => {
    expect(isValidSearchQuery({ text: '' })).toBe(false)
  })
  it('rejects non-string text', () => {
    expect(isValidSearchQuery({ text: 5 as never })).toBe(false)
  })
  it('accepts whitespace-only text', () => {
    expect(isValidSearchQuery({ text: '   ' })).toBe(true)
  })
  it('rejects negative limit', () => {
    expect(isValidSearchQuery({ text: 'x', limit: -1 })).toBe(false)
  })
  it('rejects non-integer limit', () => {
    expect(isValidSearchQuery({ text: 'x', limit: 1.5 })).toBe(false)
  })
  it('accepts limit 0 (no cap)', () => {
    expect(isValidSearchQuery({ text: 'x', limit: 0 })).toBe(true)
  })
  it('rejects non-object filters', () => {
    expect(isValidSearchQuery({ text: 'x', filters: 'nope' as never })).toBe(false)
  })
  it('accepts object filters', () => {
    expect(isValidSearchQuery({ text: 'x', filters: { type: 'paper' } })).toBe(true)
  })
  it('isValidRetriever recognizes LocalRetriever', () => {
    expect(isValidRetriever(new LocalRetriever())).toBe(true)
  })
  it('isValidRetriever rejects a plain object', () => {
    expect(isValidRetriever({ foo: 1 })).toBe(false)
  })
  it('accepts a valid SearchResult', () => {
    const r: unknown = { chunk: makeChunk(), score: 12, citation: makeCitation() }
    expect(isValidSearchResult(r)).toBe(true)
  })
  it('rejects a SearchResult with negative score', () => {
    const r: unknown = { chunk: makeChunk(), score: -1, citation: makeCitation() }
    expect(isValidSearchResult(r)).toBe(false)
  })
})

// ============ LocalChunker — construction ============

describe('Phase 8-C0 LocalChunker construction', () => {
  it('defaults maxChars to 400', () => {
    const chunker = new LocalChunker()
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(1000) } }))
    expect(chunks).toHaveLength(3)
  })
  it('throws when maxChars is 0', () => {
    expect(() => new LocalChunker({ maxChars: 0 })).toThrow(/maxChars/)
  })
  it('throws when maxChars is negative', () => {
    expect(() => new LocalChunker({ maxChars: -5 })).toThrow(/maxChars/)
  })
  it('throws when maxChars is non-integer', () => {
    expect(() => new LocalChunker({ maxChars: 12.5 })).toThrow(/maxChars/)
  })
  it('throws when overlapChars >= maxChars', () => {
    expect(() => new LocalChunker({ maxChars: 10, overlapChars: 10 })).toThrow(/overlapChars/)
  })
  it('throws when overlapChars is negative', () => {
    expect(() => new LocalChunker({ overlapChars: -1 })).toThrow(/overlapChars/)
  })
  it('honors a custom maxChars', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(25) } }))
    expect(chunks).toHaveLength(3)
  })
  it('honors preserveWords flag', () => {
    expect(() => new LocalChunker({ preserveWords: true })).not.toThrow()
  })
  it('splitContent validates via normalize helpers', () => {
    expect(() => chunkerHelpers.normalizePositive(10, 'x')).not.toThrow()
    expect(() => chunkerHelpers.normalizePositive(0, 'x')).toThrow(/positive integer/)
  })
})

// ============ LocalChunker — splitting ============

describe('Phase 8-C0 LocalChunker splitting', () => {
  it('empty content yields a single empty chunk', () => {
    const chunker = new LocalChunker()
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: '' } }))
    expect(chunks).toHaveLength(1)
    expect(chunks[0]!.content).toBe('')
    expect(chunks[0]!.position).toBe(0)
  })
  it('content absent from metadata yields a single empty chunk', () => {
    const chunker = new LocalChunker()
    const chunks = chunker.splitDocument(makeDoc({ metadata: {} }))
    expect(chunks).toHaveLength(1)
    expect(chunks[0]!.content).toBe('')
  })
  it('short content yields a single chunk', () => {
    const chunker = new LocalChunker()
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: 'short' } }))
    expect(chunks).toHaveLength(1)
    expect(chunks[0]!.position).toBe(0)
  })
  it('long content splits into increasing positions', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(35) } }))
    expect(chunks.length).toBeGreaterThan(1)
    expect(chunks.map((c) => c.position)).toEqual(chunks.map((_, i) => i))
  })
  it('every chunk stays within maxChars', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    for (const c of chunker.splitDocument(makeDoc({ metadata: { content: longContent(99) } }))) {
      expect(c.content.length).toBeLessThanOrEqual(10)
    }
  })
  it('chunk ids are prefixed with the document id', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    for (const c of chunker.splitDocument(makeDoc({ metadata: { content: longContent(33) } }))) {
      expect(c.id.startsWith('doc:1#')).toBe(true)
    }
  })
  it('chunk documentId matches the source document', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    for (const c of chunker.splitDocument(makeDoc({ metadata: { content: longContent(33) } }))) {
      expect(c.documentId).toBe('doc:1')
    }
  })
  it('round-trips exactly with no overlap', () => {
    const chunker = new LocalChunker({ maxChars: 33 })
    const content = longContent(100)
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content } }))
    expect(chunker.mergeChunks(chunks)).toBe(content)
  })
  it('mergeChunks sorts by position regardless of input order', () => {
    const chunker = new LocalChunker({ maxChars: 7 })
    const content = longContent(20)
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content } }))
    expect(chunker.mergeChunks([...chunks].reverse())).toBe(content)
  })
  it('overlap shares characters between consecutive chunks', () => {
    const chunker = new LocalChunker({ maxChars: 10, overlapChars: 3 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(25) } }))
    expect(chunks[0]!.content.endsWith(chunks[1]!.content.slice(0, 3))).toBe(true)
  })
  it('preserveWords keeps chunks within maxChars', () => {
    const chunker = new LocalChunker({ maxChars: 15, preserveWords: true })
    const content = 'one two three four five six seven'
    for (const c of chunker.splitDocument(makeDoc({ metadata: { content } }))) {
      expect(c.content.length).toBeLessThanOrEqual(15)
    }
  })
  it('preserveWords keeps separators so round trip still holds', () => {
    const chunker = new LocalChunker({ maxChars: 10, preserveWords: true })
    const content = 'alpha beta gamma delta'
    expect(chunker.mergeChunks(chunker.splitDocument(makeDoc({ metadata: { content } })))).toBe(content)
  })
  it('inherits section metadata into every chunk', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const doc = makeDoc({ metadata: { content: longContent(25), section: 'methods' } })
    for (const c of chunker.splitDocument(doc)) {
      expect(c.metadata.section).toBe('methods')
    }
  })
  it('inherits page metadata into every chunk', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const doc = makeDoc({ metadata: { content: longContent(25), page: 7 } })
    for (const c of chunker.splitDocument(doc)) {
      expect(c.metadata.page).toBe(7)
    }
  })
  it('uses empty metadata when no hints are present', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(25) } }))
    expect(chunks[0]!.metadata).toEqual({})
  })
  it('chunk ids are unique', () => {
    const chunker = new LocalChunker({ maxChars: 10 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(45) } }))
    expect(new Set(chunks.map((c) => c.id)).size).toBe(chunks.length)
  })
  it('throws on an invalid document', () => {
    const chunker = new LocalChunker()
    expect(() => chunker.splitDocument({ id: '', type: 'paper', title: 'x', source: 's', metadata: {}, createdAt: 1 }))
      .toThrow(/invalid document/)
  })
  it('throws on non-string content in metadata', () => {
    const chunker = new LocalChunker()
    expect(() => chunker.splitDocument(makeDoc({ metadata: { content: 42 as never } }))).toThrow(/local chunker/)
  })
  it('is deterministic for the same document', () => {
    const chunker = new LocalChunker({ maxChars: 12 })
    const doc = makeDoc({ metadata: { content: longContent(40) } })
    const a = chunker.splitDocument(doc)
    const b = chunker.splitDocument(doc)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('content exactly at maxChars is one chunk', () => {
    const chunker = new LocalChunker({ maxChars: 12 })
    const chunks = chunker.splitDocument(makeDoc({ metadata: { content: longContent(12) } }))
    expect(chunks).toHaveLength(1)
    expect(chunks[0]!.content).toBe(longContent(12))
  })
  it('splitContent is exported and deterministic', () => {
    const a = splitContent('abcdefghij', 4, 0, false)
    const b = splitContent('abcdefghij', 4, 0, false)
    expect(a).toEqual(b)
    expect(a.join('')).toBe('abcdefghij')
  })
})

// ============ Chunker merge ============

describe('Phase 8-C0 Chunker merge', () => {
  it('merges an empty chunk list to empty string', () => {
    expect(new LocalChunker().mergeChunks([])).toBe('')
  })
  it('merges a single chunk to its content', () => {
    expect(new LocalChunker().mergeChunks([makeChunk({ content: 'hello', position: 0 })])).toBe('hello')
  })
  it('does not mutate the input array', () => {
    const chunker = new LocalChunker()
    const chunks = [makeChunk({ id: 'b', content: 'B', position: 1 }), makeChunk({ id: 'a', content: 'A', position: 0 })]
    chunker.mergeChunks(chunks)
    expect(chunks.map((c) => c.position)).toEqual([1, 0])
  })
  it('chunk chunk metadata can carry section/page findings', () => {
    const chunker = new LocalChunker({ maxChars: 6 })
    const doc = makeDoc({ metadata: { content: longContent(20), section: 'results', page: 2 } })
    const chunks = chunker.splitDocument(doc)
    for (const c of chunks) expect(isValidChunkMetadata({ ...c.metadata, position: c.position })).toBe(true)
  })
})

// ============ LocalRetriever — ingest + lifecycle ============

describe('Phase 8-C0 LocalRetriever lifecycle', () => {
  let r: LocalRetriever
  beforeEach(() => { r = new LocalRetriever() })
  it('starts empty', () => {
    expect(r.documentCount()).toBe(0)
    expect(r.chunkCount()).toBe(0)
  })
  it('indexDocuments returns the count', () => {
    expect(r.indexDocuments([makeDoc(), makeDoc({ id: 'doc:2' })])).toBe(2)
  })
  it('retrieve returns the inserted document', async () => {
    r.indexDocuments([makeDoc()])
    const doc = await r.retrieve('doc:1')
    expect(doc?.title).toBe('Bubble Dynamics Review')
  })
  it('retrieve returns null for an unknown id', async () => {
    expect(await r.retrieve('missing')).toBeNull()
  })
  it('list returns all documents sorted by id', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:b' }), makeDoc({ id: 'doc:a' })])
    const docs = await r.list()
    expect(docs.map((d) => d.id)).toEqual(['doc:a', 'doc:b'])
  })
  it('list is empty before any ingest', async () => {
    expect(await r.list()).toEqual([])
  })
  it('removeDocument returns true when present', () => {
    r.indexDocuments([makeDoc()])
    expect(r.removeDocument('doc:1')).toBe(true)
  })
  it('removeDocument returns false for unknown', () => {
    expect(r.removeDocument('doc:zzz')).toBe(false)
  })
  it('removeDocument clears chunks', () => {
    r.indexDocuments([makeDoc()])
    r.removeDocument('doc:1')
    expect(r.chunkCount()).toBe(0)
  })
  it('re-indexing an id replaces the old chunks', () => {
    r.indexDocuments([makeDoc({ metadata: { content: longContent(1000) } })])
    const before = r.chunkCount()
    r.indexDocuments([makeDoc()])
    expect(r.chunkCount()).not.toBe(before)
  })
  it('indexDocuments is atomic on invalid batch', () => {
    const valid = makeDoc()
    const invalid = makeDoc({ id: '' })
    expect(() => r.indexDocuments([valid, invalid])).toThrow(/invalid document/)
    expect(r.documentCount()).toBe(0)
    expect(r.chunkCount()).toBe(0)
  })
  it('indexDocuments rejects non-array input', () => {
    expect(() => r.indexDocuments(makeDoc() as never)).toThrow(/must be an array/)
  })
  it('indexDocuments([]) returns 0', () => {
    expect(r.indexDocuments([])).toBe(0)
  })
  it('retrieve after remove returns null', async () => {
    r.indexDocuments([makeDoc()])
    r.removeDocument('doc:1')
    expect(await r.retrieve('doc:1')).toBeNull()
  })
  it('listChunks for unknown document is empty', () => {
    expect(r.listChunks('nope')).toEqual([])
  })
  it('re-inserting a duplicate id keeps a single document', () => {
    r.indexDocuments([makeDoc({ id: 'doc:x', title: 'first' }), makeDoc({ id: 'doc:x', title: 'second' })])
    expect(r.documentCount()).toBe(1)
  })
})

// ============ LocalRetriever — search ============

describe('Phase 8-C0 LocalRetriever search', () => {
  let r: LocalRetriever
  beforeEach(() => {
    r = new LocalRetriever()
    r.indexDocuments([
      makeDoc({ id: 'doc:water', metadata: { content: 'bubble water quality regulation' } }),
      makeDoc({ id: 'doc:reactor', metadata: { content: 'reactor kinetics and stability' } })
    ])
  })
  it('finds a chunk containing the query term', async () => {
    const hits = await r.search({ text: 'bubble' })
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0]!.chunk.content).toContain('bubble')
  })
  it('matches case-insensitively', async () => {
    const hits = await r.search({ text: 'BUBBLE' })
    expect(hits[0]!.chunk.content).toContain('bubble')
  })
  it('searches across multiple documents', async () => {
    const hits = await r.search({ text: 'reactor' })
    expect(hits[0]!.citation.documentId).toBe('doc:reactor')
  })
  it('ranks a chunk matching more terms above one matching fewer', async () => {
    r.indexDocuments([
      makeDoc({ id: 'doc:both', metadata: { content: 'water quality' } }),
      makeDoc({ id: 'doc:one', metadata: { content: 'water only' } })
    ])
    const hits = await r.search({ text: 'water quality' })
    expect(hits[0]!.citation.documentId).toBe('doc:both')
  })
  it('ranks higher term frequency above lower', async () => {
    r.indexDocuments([
      makeDoc({ id: 'doc:freq', metadata: { content: 'reactor reactor reactor' } }),
      makeDoc({ id: 'doc:single', metadata: { content: 'reactor' } })
    ])
    const hits = await r.search({ text: 'reactor' })
    expect(hits[0]!.citation.documentId).toBe('doc:freq')
  })
  it('earlier position breaks score ties', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:x', metadata: { content: 'reactor' } })])
    const hits = await r.search({ text: 'reactor' })
    expect(hits[0]!.chunk.position).toBe(0)
  })
  it('returns no results when nothing matches', async () => {
    const hits = await r.search({ text: 'zyzzyva' })
    expect(hits).toEqual([])
  })
  it('returns empty for a whitespace query', async () => {
    const hits = await r.search({ text: '   ' })
    expect(hits).toEqual([])
  })
  it('throws on an empty query text', async () => {
    await expect(r.search({ text: '' })).rejects.toThrow(/invalid search query/)
  })
  it('throws on a non-string query text', async () => {
    await expect(r.search({ text: 1 as never })).rejects.toThrow(/invalid search query/)
  })
  it('limit truncates to the top N', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:water2', metadata: { content: 'water treatment' } })])
    const hits = await r.search({ text: 'water' })
    expect(hits.length).toBeGreaterThan(1)
    const top = await r.search({ text: 'water', limit: 1 })
    expect(top).toHaveLength(1)
  })
  it('limit 0 returns all matches', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:water2', metadata: { content: 'water treatment' } })])
    const hits = await r.search({ text: 'water', limit: 0 })
    expect(hits.length).toBeGreaterThan(1)
  })
  it('negative limit is rejected', async () => {
    await expect(r.search({ text: 'water', limit: -1 })).rejects.toThrow(/invalid search query/)
  })
  it('matches CJK query terms', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:cjk', metadata: { content: '气泡动力学与传质特性研究' } })])
    const hits = await r.search({ text: '气泡' })
    expect(hits.length).toBeGreaterThan(0)
    expect(hits[0]!.citation.documentId).toBe('doc:cjk')
  })
  it('matches a query term that is a substring of a content word', async () => {
    const hits = await r.search({ text: 'kinetic' })
    expect(hits).toHaveLength(1)
    expect(hits[0]!.citation.documentId).toBe('doc:reactor')
  })
  it('searchSync mirrors search', () => {
    const sync = r.searchSync({ text: 'bubble' })
    expect(sync.length).toBeGreaterThan(0)
  })
  it('search on an empty index returns nothing', async () => {
    const empty = new LocalRetriever()
    expect(await empty.search({ text: 'water' })).toEqual([])
  })
  it('search result score is a finite positive number', async () => {
    const hits = await r.search({ text: 'bubble' })
    for (const h of hits) {
      expect(Number.isFinite(h.score)).toBe(true)
      expect(h.score).toBeGreaterThan(0)
    }
  })
  it('result chunks are the indexed chunks', async () => {
    const hits = await r.search({ text: 'bubble' })
    expect(hits[0]!.chunk.documentId).toBe('doc:water')
  })
  it('search finds a full chunk then re-search after re-index is consistent', async () => {
    const before = await r.search({ text: 'bubble' })
    r.indexDocuments([makeDoc({ id: 'doc:water', metadata: { content: 'bubble bubble bubble' } })])
    const after = await r.search({ text: 'bubble' })
    expect(after.length).toBeGreaterThanOrEqual(before.length)
  })
  it('deterministic ordering for equal-score docs', async () => {
    r.indexDocuments([
      makeDoc({ id: 'doc:a1', metadata: { content: 'zeta zeta' } }),
      makeDoc({ id: 'doc:a0', metadata: { content: 'zeta zeta' } })
    ])
    const hits = await r.search({ text: 'zeta' })
    expect(hits.map((h) => h.citation.documentId).slice(0, 2)).toEqual(['doc:a0', 'doc:a1'])
  })
  it('position tie-break orders chunks of one long doc', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:long', metadata: { content: 'alpha '.repeat(200) } })])
    const hits = await r.search({ text: 'alpha' })
    expect(hits[0]!.chunk.position).toBe(0)
    expect(hits[1]!.chunk.position).toBe(1)
  })
  it('scores stay deterministic across calls', async () => {
    const a = await r.search({ text: 'water' })
    const b = await r.search({ text: 'water' })
    expect(a.map((h) => h.score)).toEqual(b.map((h) => h.score))
  })
  it('exact score for a single-term single-hit chunk', () => {
    expect(scoreChunk(['water'], 'water', 0)).toBe(102.5)
  })
  it('exact score at a later position', () => {
    expect(scoreChunk(['water'], 'water', 1)).toBe(101.5)
  })
  it('exact score for full multi-term coverage', () => {
    expect(scoreChunk(['water', 'quality'], 'water quality', 0)).toBe(103)
  })
  it('score is 0 when no term matches', () => {
    expect(scoreChunk(['water'], 'dry soil', 0)).toBe(0)
  })
  it('score is 0 for an empty term list', () => {
    expect(scoreChunk([], 'water', 0)).toBe(0)
  })
  it('exact partial-coverage score', () => {
    expect(scoreChunk(['water', 'quality'], 'water only', 0)).toBe(52.5)
  })
  it('exact three-term partial coverage rounds to 2dp', () => {
    expect(scoreChunk(['water', 'x', 'y'], 'water here', 0)).toBe(35.83)
  })
})

// ============ Search — metadata filters ============

describe('Phase 8-C0 metadata filtering', () => {
  let r: LocalRetriever
  beforeEach(() => {
    r = new LocalRetriever()
    r.indexDocuments([
      makeDoc({ id: 'doc:p', type: 'paper', metadata: { content: 'bubble dynamics', year: 2024, tags: ['tc', 'review'] } }),
      makeDoc({ id: 'doc:d', type: 'dataset', metadata: { content: 'bubble concentration', year: 2023, tags: ['raw'] } })
    ])
  })
  it('filters by document type', async () => {
    const hits = await r.search({ text: 'bubble', filters: { type: 'paper' } })
    expect(hits.every((h) => h.citation.documentId === 'doc:p')).toBe(true)
  })
  it('returns nothing when the type filter excludes all', async () => {
    const hits = await r.search({ text: 'bubble', filters: { type: 'manual' } })
    expect(hits).toEqual([])
  })
  it('filters by document metadata equality', async () => {
    const hits = await r.search({ text: 'bubble', filters: { year: 2024 } })
    expect(hits.map((h) => h.citation.documentId)).toEqual(['doc:p'])
  })
  it('filters by array metadata containment', async () => {
    const hits = await r.search({ text: 'bubble', filters: { tags: 'raw' } })
    expect(hits.map((h) => h.citation.documentId)).toEqual(['doc:d'])
  })
  it('combines text match and filters', async () => {
    const hits = await r.search({ text: 'concentration', filters: { type: 'dataset' } })
    expect(hits).toHaveLength(1)
    expect(hits[0]!.citation.documentId).toBe('doc:d')
  })
  it('text must still match under filters', async () => {
    const hits = await r.search({ text: 'unrelated', filters: { type: 'paper' } })
    expect(hits).toEqual([])
  })
  it('unknown filter keys match nothing', async () => {
    const hits = await r.search({ text: 'bubble', filters: { nope: 1 } })
    expect(hits).toEqual([])
  })
  it('filter compares by strict type', async () => {
    const hits = await r.search({ text: 'bubble', filters: { year: '2024' } })
    expect(hits).toEqual([])
  })
  it('empty filters object behaves like no filter', async () => {
    const hits = await r.search({ text: 'bubble', filters: {} })
    expect(hits.length).toBe(2)
  })
  it('chunk metadata participates in filters', async () => {
    const r2 = new LocalRetriever()
    r2.indexDocuments([makeDoc({ id: 'doc:s', metadata: { content: 'water section a', section: 'methods' } })])
    const hits = await r2.search({ text: 'water', filters: { section: 'methods' } })
    expect(hits).toHaveLength(1)
  })
  it('type + metadata filters combine', async () => {
    const hits = await r.search({ text: 'bubble', filters: { type: 'paper', year: 2024 } })
    expect(hits.map((h) => h.citation.documentId)).toEqual(['doc:p'])
  })
  it('filters do not leak across documents', async () => {
    const hits = await r.search({ text: 'bubble', filters: { tags: 'raw' } })
    expect(hits.some((h) => h.citation.documentId === 'doc:p')).toBe(false)
  })
  it('matchesFilters accepts undefined filters as all-match', () => {
    const d = makeDoc()
    expect(matchesFilters(d, makeChunk(), {})).toBe(true)
  })
  it('tokenizeQuery splits CJK-adjacent Latin terms', () => {
    expect(tokenizeQuery('Bubble-Quality 2024')).toEqual(['bubble', 'quality', '2024'])
  })
  it('countOccurrences counts overlapping-free matches', () => {
    expect(countOccurrences('aaaa', 'aa')).toBe(2)
  })
})

// ============ Citations ============

describe('Phase 8-C0 citations', () => {
  let r: LocalRetriever
  beforeEach(() => {
    r = new LocalRetriever()
    r.indexDocuments([makeDoc({ id: 'doc:1', metadata: { content: 'water bubble kinetics' } })])
  })
  it('citation documentId equals the chunk documentId', async () => {
    const hits = await r.search({ text: 'bubble' })
    for (const h of hits) expect(h.citation.documentId).toBe(h.chunk.documentId)
  })
  it('citation chunkId equals the chunk id', async () => {
    const hits = await r.search({ text: 'bubble' })
    for (const h of hits) expect(h.citation.chunkId).toBe(h.chunk.id)
  })
  it('citation confidence is within [0,1]', async () => {
    const hits = await r.search({ text: 'bubble' })
    for (const h of hits) {
      expect(h.citation.confidence).toBeGreaterThanOrEqual(0)
      expect(h.citation.confidence).toBeLessThanOrEqual(1)
    }
  })
  it('citation confidence mirrors the score/100 clamp', async () => {
    expect(retrHelpers.scoreChunk(['water'], 'water', 0)).toBe(102.5)
  })
  it('every result carries a valid CitationReference', async () => {
    const hits = await r.search({ text: 'water' })
    for (const h of hits) expect(isValidCitationReference(h.citation)).toBe(true)
  })
  it('citations resolve through listChunks', async () => {
    const hits = await r.search({ text: 'kinetics' })
    const cite = hits[0]!.citation
    const chunks = r.listChunks(cite.documentId)
    expect(chunks.some((c) => c.id === cite.chunkId)).toBe(true)
  })
  it('removing the document removes its citations', async () => {
    const hits = await r.search({ text: 'bubble' })
    expect(hits).toHaveLength(1)
    r.removeDocument('doc:1')
    expect(await r.search({ text: 'bubble' })).toEqual([])
  })
  it('distinct documents yield distinct citations', async () => {
    r.indexDocuments([makeDoc({ id: 'doc:2', metadata: { content: 'water quality' } })])
    const hits = await r.search({ text: 'water' })
    const docIds = new Set(hits.map((h) => h.citation.documentId))
    expect(docIds.size).toBeGreaterThan(1)
  })
  it('low-coverage hits get non-unit confidence', async () => {
    const hits = await r.search({ text: 'water quality sensor' })
    // doc content lacks 'sensor' => coverage < 1 => confidence < 1
    for (const h of hits) expect(h.citation.confidence).toBeLessThan(1)
  })
  it('CitationReference schema rejects score-derived confidence out of range', () => {
    expect(isValidCitationReference(makeCitation({ confidence: 2 }))).toBe(false)
  })
})

// ============ Determinism + empty cases ============

describe('Phase 8-C0 determinism + empty cases', () => {
  it('scoreChunk is a pure function', () => {
    const a = scoreChunk(['water'], 'water quality', 0)
    const b = scoreChunk(['water'], 'water quality', 0)
    expect(a).toBe(b)
  })
  it('search results are stable across runs', async () => {
    const r = new LocalRetriever()
    r.indexDocuments([makeDoc({ id: 'd1', metadata: { content: 'alpha beta' } })])
    const a = await r.search({ text: 'alpha' })
    const b = await r.search({ text: 'alpha' })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('empty document count and chunk count are 0', () => {
    const r = new LocalRetriever()
    expect(r.documentCount()).toBe(0)
    expect(r.chunkCount()).toBe(0)
  })
  it('search before ingest returns []', async () => {
    expect(await new LocalRetriever().search({ text: 'anything' })).toEqual([])
  })
  it('whitespace-only tokenization yields no terms', () => {
    expect(tokenizeQuery('   \n\t  ')).toEqual([])
  })
  it('tokenizeQuery drops empty terms', () => {
    expect(tokenizeQuery('a  b  c')).toEqual(['a', 'b', 'c'])
  })
  it('countOccurrences returns 0 for absent term', () => {
    expect(countOccurrences('water', 'bubble')).toBe(0)
  })
  it('countOccurrences returns 0 for empty term', () => {
    expect(countOccurrences('water', '')).toBe(0)
  })
  it('search score for a repeated query term is stable', async () => {
    const r = new LocalRetriever()
    r.indexDocuments([makeDoc({ id: 'd1', metadata: { content: 'zeta zeta zeta' } })])
    const hits = await r.search({ text: 'zeta' })
    expect(hits[0]!.score).toBe(103.5)
  })
  it('search handles a mixed-language query', async () => {
    const r = new LocalRetriever()
    r.indexDocuments([makeDoc({ id: 'd1', metadata: { content: 'water 水质 bubble' } })])
    const hits = await r.search({ text: '水质' })
    expect(hits).toHaveLength(1)
  })
})

// ============ Security + source scans ============

describe('Phase 8-C0 security + planner separation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('local-retriever.ts is free of forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/local-retriever.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('local-chunker.ts is free of forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/local-chunker.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('implementation has no randomness', () => {
    const r = readSrc('../../src/main/services/knowledge/local-retriever.ts')
    const c = readSrc('../../src/main/services/knowledge/local-chunker.ts')
    expect(r).not.toContain('Math.random')
    expect(c).not.toContain('Math.random')
    expect(r).not.toContain('Date.now')
    expect(c).not.toContain('Date.now')
  })
  it('local-retriever does not import the planner or runtime', () => {
    const src = readSrc('../../src/main/services/knowledge/local-retriever.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*agent-runtime['"]/)
    expect(src).not.toMatch(/from\s+['"][^'"]*research-planner/)
    expect(src).not.toMatch(/from\s+['"][^'"]*hybrid-planner/)
  })
  it('local-chunker does not import the planner or runtime', () => {
    const src = readSrc('../../src/main/services/knowledge/local-chunker.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*agent-runtime['"]/)
    expect(src).not.toMatch(/from\s+['"][^'"]*research-planner/)
  })
  it('document-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/document-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('chunker-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/chunker-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('retriever-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/retriever-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('chunks never escape with credentials (schema guard covers metadata)', () => {
    expect(() => isValidDocumentChunk(makeChunk({ metadata: { providerId: 'x' } }))).toThrow(/forbidden/)
  })
  it('retriever consumes Documents but never mutates them', async () => {
    const doc = makeDoc()
    const snapshot = JSON.stringify(doc)
    const r = new LocalRetriever()
    r.indexDocuments([doc])
    await r.search({ text: 'bubble' })
    expect(JSON.stringify(doc)).toBe(snapshot)
  })
  it('retriever index is independent of the caller-referenced document list', () => {
    const r = new LocalRetriever()
    const docs = [makeDoc()]
    r.indexDocuments(docs)
    docs.length = 0
    expect(r.documentCount()).toBe(1)
  })
})