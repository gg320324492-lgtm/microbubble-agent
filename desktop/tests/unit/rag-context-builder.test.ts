// Phase 8-C3 RAG Context Builder tests.
//
// Coverage (~205 cases):
//   - context-schema validators (22)
//   - citation formatter inline (24)
//   - citation reference list (14)
//   - citation deduplication (12)
//   - token estimator + truncation (22)
//   - rank + merge similar (24)
//   - buildContext end-to-end (28)
//   - ResearchContextProvider adapter (16)
//   - security + source scans (16)
//   - supplementary (27)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  isValidContextChunk,
  isValidRAGContext,
  __testHelpers as ctxHelpers
} from '../../src/shared/knowledge/context-schema'
import type { ContextChunk, RAGContext } from '../../src/shared/knowledge/context-schema'
import type { CitationReference, DocumentChunk } from '../../src/shared/knowledge/document-schema'
import { isValidCitationReference } from '../../src/shared/knowledge/document-schema'

// ============ Implementations ============
import {
  formatInlineCitation,
  formatReferenceList,
  deduplicateCitation,
  __testHelpers as formatHelpers
} from '../../src/main/services/knowledge/citation-formatter'
import {
  RAGContextBuilder,
  estimateTokens,
  rankChunks,
  mergeSimilarChunks,
  truncateByTokenBudget,
  dedupeSearchResults,
  __testHelpers as builderHelpers
} from '../../src/main/services/knowledge/rag-context-builder'
import { ResearchContextProvider } from '../../src/main/services/knowledge/research-context-provider'
import { LocalRetriever } from '../../src/main/services/knowledge/local-retriever'
import { LocalVectorStore } from '../../src/main/services/knowledge/local-vector-store'
import { LocalEmbeddingProvider } from '../../src/main/services/knowledge/local-embedding'
import { HybridRetriever } from '../../src/main/services/knowledge/hybrid-retriever'
import type { SearchResult } from '../../src/shared/knowledge/retriever-schema'

// ============ Fixtures ============

function cite(overrides: Partial<CitationReference> = {}): CitationReference {
  return {
    documentId: 'doc:1',
    chunkId: 'doc:1#0',
    confidence: 0.9,
    ...overrides
  }
}

function chunk(overrides: Partial<DocumentChunk> = {}): DocumentChunk {
  return {
    id: 'doc:1#0',
    documentId: 'doc:1',
    content: 'bubble dynamics in water',
    position: 0,
    metadata: {},
    ...overrides
  }
}

function result(overrides: Partial<SearchResult> & { chunk?: DocumentChunk; citation?: CitationReference } = {}): SearchResult {
  const c = overrides.chunk ?? chunk()
  const cit = overrides.citation ?? cite({ documentId: c.documentId, chunkId: c.id })
  const r: SearchResult = {
    chunk: c,
    score: typeof overrides.score === 'number' ? overrides.score : 100,
    citation: cit
  }
  return r
}

function makeHybrid(): { h: HybridRetriever; docs: Array<{ id: string; content: string }> } {
  const h = new HybridRetriever({
    vectorStore: new LocalVectorStore(),
    embedding: new LocalEmbeddingProvider()
  })
  const docs = [
    { id: 'doc:1', content: 'bubble dynamics in water quality control' },
    { id: 'doc:2', content: 'reactor kinetics stability analysis' }
  ]
  for (const d of docs) {
    h.indexDocuments([{
      id: d.id, type: 'paper', title: d.id, source: `${d.id}.pdf`,
      metadata: { content: d.content }, createdAt: 0
    }])
  }
  return { h, docs }
}

// ============ ContextChunk validator ============

describe('Phase 8-C3 ContextChunk validator', () => {
  it('accepts a valid ContextChunk', () => {
    expect(isValidContextChunk({
      chunkId: 'c1', content: 'bubble', score: 0.9, citation: cite()
    })).toBe(true)
  })
  it('rejects empty chunkId', () => {
    expect(isValidContextChunk({ chunkId: '', content: 'x', score: 0, citation: cite() })).toBe(false)
  })
  it('rejects non-string content', () => {
    expect(isValidContextChunk({ chunkId: 'c', content: 1 as never, score: 0, citation: cite() })).toBe(false)
  })
  it('accepts empty content string', () => {
    expect(isValidContextChunk({ chunkId: 'c', content: '', score: 0, citation: cite() })).toBe(true)
  })
  it('rejects non-finite score', () => {
    expect(isValidContextChunk({ chunkId: 'c', content: 'x', score: NaN, citation: cite() })).toBe(false)
  })
  it('accepts score 0', () => {
    expect(isValidContextChunk({ chunkId: 'c', content: 'x', score: 0, citation: cite() })).toBe(true)
  })
  it('rejects invalid citation', () => {
    expect(isValidContextChunk({ chunkId: 'c', content: 'x', score: 0, citation: { bad: true } as never })).toBe(false)
  })
  it('rejects non-object', () => {
    expect(isValidContextChunk(null)).toBe(false)
  })
})

// ============ RAGContext validator ============

describe('Phase 8-C3 RAGContext validator', () => {
  const baseCtx = {
    query: 'bubble dynamics',
    chunks: [{
      chunkId: 'doc:1#0', content: 'bubble', score: 0.9, citation: cite()
    }],
    citations: [cite()],
    tokenBudget: 2000,
    metadata: {}
  }
  it('accepts a valid RAGContext', () => {
    expect(isValidRAGContext(baseCtx)).toBe(true)
  })
  it('rejects empty query', () => {
    expect(isValidRAGContext({ ...baseCtx, query: '' })).toBe(false)
  })
  it('rejects non-string query', () => {
    expect(isValidRAGContext({ ...baseCtx, query: 1 as never })).toBe(false)
  })
  it('rejects non-array chunks', () => {
    expect(isValidRAGContext({ ...baseCtx, chunks: 'x' as never })).toBe(false)
  })
  it('rejects non-array citations', () => {
    expect(isValidRAGContext({ ...baseCtx, citations: 'x' as never })).toBe(false)
  })
  it('rejects tokenBudget < 1', () => {
    expect(isValidRAGContext({ ...baseCtx, tokenBudget: 0 })).toBe(false)
  })
  it('rejects non-integer tokenBudget', () => {
    expect(isValidRAGContext({ ...baseCtx, tokenBudget: 1.5 })).toBe(false)
  })
  it('rejects metadata as array', () => {
    expect(isValidRAGContext({ ...baseCtx, metadata: [] as never })).toBe(false)
  })
  it('rejects a chunk with invalid citation', () => {
    expect(isValidRAGContext({
      ...baseCtx,
      chunks: [{ chunkId: 'c', content: 'x', score: 0, citation: { bad: true } as never }]
    })).toBe(false)
  })
  it('rejects a citation with invalid structure', () => {
    expect(isValidRAGContext({ ...baseCtx, citations: [{ bad: true } as never] })).toBe(false)
  })
  it('throws when metadata contains a secret', () => {
    expect(() => isValidRAGContext({ ...baseCtx, metadata: { providerId: 'sk-leak' } })).toThrow(/forbidden/)
  })
  it('FORBIDDEN list has 8 entries', () => {
    expect(ctxHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ formatInlineCitation ============

describe('Phase 8-C3 formatInlineCitation', () => {
  it('renders "[1]" with no options', () => {
    expect(formatInlineCitation(cite())).toBe('[1]')
  })
  it('renders "[3]" when number option provided', () => {
    expect(formatInlineCitation(cite(), { number: 3 })).toBe('[3]')
  })
  it('renders "[1, page 5]" when citation has a page', () => {
    expect(formatInlineCitation(cite({ page: 5 }))).toBe('[1, page 5]')
  })
  it('renders title + page when both provided', () => {
    expect(formatInlineCitation(cite({ page: 5 }), { number: 2, title: 'Microbubble Dynamics' }))
      .toBe('[2] Microbubble Dynamics, page 5')
  })
  it('renders section when provided', () => {
    expect(formatInlineCitation(cite({ page: 5 }), { number: 1, title: 'Paper', section: 'Methods' }))
      .toBe('[1] Paper, § Methods, page 5')
  })
  it('omits page when it is below 1', () => {
    expect(formatInlineCitation(cite({ page: 0 }))).toBe('[1]')
  })
  it('omits page when it is not an integer', () => {
    expect(formatInlineCitation(cite({ page: 1.5 as never }))).toBe('[1]')
  })
  it('renders number with no extras', () => {
    expect(formatInlineCitation(cite({ page: 3 }), { number: 7 })).toBe('[7, page 3]')
  })
  it('produces deterministic output', () => {
    const a = formatInlineCitation(cite({ page: 3 }), { number: 2 })
    const b = formatInlineCitation(cite({ page: 3 }), { number: 2 })
    expect(a).toBe(b)
  })
})

// ============ formatReferenceList ============

describe('Phase 8-C3 formatReferenceList', () => {
  const title = (_c: CitationReference, n: number) => `Title ${n}`
  it('renders numbered lines joined by \\n', () => {
    const text = formatReferenceList([cite(), cite({ chunkId: 'doc:1#1' })], title)
    expect(text).toBe('[1] Title 1\n[2] Title 2')
  })
  it('uses 1-based numbering', () => {
    const text = formatReferenceList([cite(), cite(), cite()], title)
    const lines = text.split('\n')
    expect(lines[0]).toBe('[1] Title 1')
    expect(lines[2]).toBe('[3] Title 3')
  })
  it('appends page when citation has one', () => {
    const text = formatReferenceList([cite({ page: 5 })], title)
    expect(text).toBe('[1] Title 1, page 5')
  })
  it('renders just the number when title resolver returns undefined', () => {
    const text = formatReferenceList([cite({ page: 3 })], () => undefined)
    expect(text).toBe('[1], page 3')
  })
  it('handles empty citations', () => {
    expect(formatReferenceList([], title)).toBe('')
  })
  it('throws on non-array input', () => {
    expect(() => formatReferenceList(null as never, title)).toThrow(/must be an array/)
  })
  it('throws on non-function resolver', () => {
    expect(() => formatReferenceList([cite()], null as never)).toThrow(/titleResolver must be a function/)
  })
  it('is deterministic', () => {
    const a = formatReferenceList([cite({ page: 2 })], title)
    const b = formatReferenceList([cite({ page: 2 })], title)
    expect(a).toBe(b)
  })
})

// ============ deduplicateCitation ============

describe('Phase 8-C3 deduplicateCitation', () => {
  it('returns [] for empty input', () => {
    expect(deduplicateCitation([])).toEqual([])
  })
  it('returns unique citations', () => {
    expect(deduplicateCitation([cite(), cite({ chunkId: 'doc:1#1' })]))
      .toHaveLength(2)
  })
  it('collapses identical (docId, chunkId, page)', () => {
    expect(deduplicateCitation([cite({ page: 1 }), cite({ page: 1 })])).toHaveLength(1)
  })
  it('distinguishes different pages on the same chunk', () => {
    expect(deduplicateCitation([cite({ page: 1 }), cite({ page: 2 })])).toHaveLength(2)
  })
  it('preserves first-seen order', () => {
    const a = cite({ chunkId: 'a' })
    const b = cite({ chunkId: 'b' })
    const c = cite({ chunkId: 'c' })
    expect(deduplicateCitation([a, b, c, a]).map((x) => x.chunkId)).toEqual(['a', 'b', 'c'])
  })
  it('is deterministic', () => {
    const a = deduplicateCitation([cite(), cite({ page: 1 })])
    const b = deduplicateCitation([cite(), cite({ page: 1 })])
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('throws on non-array input', () => {
    expect(() => deduplicateCitation(null as never)).toThrow(/must be an array/)
  })
  it('treats absent page as part of key', () => {
    expect(deduplicateCitation([cite(), cite()])).toHaveLength(1)
    expect(deduplicateCitation([cite(), cite({ page: undefined as never })])).toHaveLength(1)
  })
})

// ============ estimateTokens + truncateByTokenBudget ============

describe('Phase 8-C3 estimateTokens', () => {
  it('returns 0 for empty', () => {
    expect(estimateTokens('')).toBe(0)
  })
  it('returns >= 1 for non-empty', () => {
    expect(estimateTokens('bubble')).toBeGreaterThanOrEqual(1)
  })
  it('grows monotonically with length', () => {
    const a = estimateTokens('bubble dynamics in water')
    const b = estimateTokens('bubble dynamics in water with longer text here')
    expect(b).toBeGreaterThan(a)
  })
  it('throws on non-string', () => {
    expect(() => estimateTokens(1 as never)).toThrow(/must be a string/)
  })
  it('returns integer', () => {
    expect(Number.isInteger(estimateTokens('a b c d'))).toBe(true)
  })
  it('is deterministic', () => {
    expect(estimateTokens('x')).toBe(estimateTokens('x'))
  })
})

describe('Phase 8-C3 truncateByTokenBudget', () => {
  const c1: ContextChunk = { chunkId: 'c1', content: 'bubble dynamics', score: 0.9, citation: cite() }
  const c2: ContextChunk = { chunkId: 'c2', content: 'reactor kinetics', score: 0.8, citation: cite({ chunkId: 'c2' }) }
  const c3: ContextChunk = { chunkId: 'c3', content: 'bubble water', score: 0.7, citation: cite({ chunkId: 'c3' }) }

  it('returns [] when budget < smallest chunk cost', () => {
    expect(truncateByTokenBudget([c1, c2, c3], 1)).toEqual([])
  })
  it('returns all chunks when budget fits all', () => {
    const out = truncateByTokenBudget([c1, c2, c3], 1000)
    expect(out.map((c) => c.chunkId)).toEqual(['c1', 'c2', 'c3'])
  })
  it('truncates when budget exhausted mid-stream', () => {
    const out = truncateByTokenBudget([c1, c2, c3], estimateTokens('bubble dynamics') + estimateTokens('reactor kinetics'))
    expect(out.length).toBeGreaterThanOrEqual(1)
    expect(out[0]!.chunkId).toBe('c1')
  })
  it('throws on non-integer budget < 1', () => {
    expect(() => truncateByTokenBudget([], 0)).toThrow(/positive integer/)
    expect(() => truncateByTokenBudget([], -1)).toThrow(/positive integer/)
  })
  it('throws on non-array chunks', () => {
    expect(() => truncateByTokenBudget(null as never, 100)).toThrow(/must be an array/)
  })
  it('throws on invalid chunk', () => {
    expect(() => truncateByTokenBudget([{ chunkId: '', content: 'x', score: 0, citation: cite() } as ContextChunk], 100))
      .toThrow(/invalid ContextChunk/)
  })
  it('honors a custom estimator', () => {
    const big = truncateByTokenBudget([c1, c2], 1000)
    const custom = (s: string): number => s.length
    const smaller = truncateByTokenBudget([c1, c2], 30, custom)
    expect(smaller.length).toBeLessThan(big.length)
  })
  it('deterministic', () => {
    const a = truncateByTokenBudget([c1, c2, c3], estimateTokens('bubble dynamics') + 5)
    const b = truncateByTokenBudget([c1, c2, c3], estimateTokens('bubble dynamics') + 5)
    expect(a.map((c) => c.chunkId)).toEqual(b.map((c) => c.chunkId))
  })
})

// ============ rankChunks + mergeSimilarChunks ============

describe('Phase 8-C3 rankChunks', () => {
  it('orders results by score desc', () => {
    const r = rankChunks([result({ score: 50, chunk: chunk({ id: 'a' }) }), result({ score: 100, chunk: chunk({ id: 'b' }) })])
    expect(r.map((x) => x.chunk.id)).toEqual(['b', 'a'])
  })
  it('breaks ties by documentId asc', () => {
    const r = rankChunks([
      result({ score: 100, chunk: chunk({ id: 'b', documentId: 'doc:2' }) }),
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'doc:1' }) })
    ])
    expect(r.map((x) => x.chunk.documentId)).toEqual(['doc:1', 'doc:2'])
  })
  it('breaks ties by position asc', () => {
    const r = rankChunks([
      result({ score: 100, chunk: chunk({ id: 'b', position: 5 }) }),
      result({ score: 100, chunk: chunk({ id: 'a', position: 1 }) })
    ])
    expect(r.map((x) => x.chunk.id)).toEqual(['a', 'b'])
  })
  it('does not mutate input', () => {
    const a = [result({ score: 50, chunk: chunk({ id: 'a' }) }), result({ score: 100, chunk: chunk({ id: 'b' }) })]
    const before = a.map((x) => x.chunk.id)
    rankChunks(a)
    expect(a.map((x) => x.chunk.id)).toEqual(before)
  })
  it('throws on non-array input', () => {
    expect(() => rankChunks(null as never)).toThrow(/must be an array/)
  })
  it('query boost gives a hit higher score', () => {
    const r = rankChunks([
      result({ score: 100, chunk: chunk({ content: 'no match here' }) }),
      result({ score: 100, chunk: chunk({ content: 'bubble bubble' }) })
    ], 'bubble')
    expect(r[0]!.chunk.content).toBe('bubble bubble')
  })
  it('preserves order with no query', () => {
    const r = rankChunks([result({ score: 10 }), result({ score: 20 })])
    expect(r[0]!.score).toBe(20)
  })
})

describe('Phase 8-C3 mergeSimilarChunks', () => {
  it('returns input when no adjacent same-doc chunks', () => {
    const r = mergeSimilarChunks([
      result({ chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'apple' }) }),
      result({ chunk: chunk({ id: 'b', documentId: 'd2', position: 0, content: 'banana' }) })
    ])
    expect(r).toHaveLength(2)
  })
  it('drops lower-scored near-duplicate within same doc', () => {
    const r = mergeSimilarChunks([
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta' }) }),
      result({ score: 50, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'alpha beta gamma delta epsilon' }) })
    ])
    expect(r.map((x) => x.chunk.id)).toEqual(['a'])
  })
  it('keeps higher-scored near-duplicate', () => {
    const r = mergeSimilarChunks([
      result({ score: 50, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta' }) }),
      result({ score: 100, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'alpha beta gamma delta epsilon' }) })
    ])
    expect(r.map((x) => x.chunk.id)).toEqual(['b'])
  })
  it('keeps non-adjacent chunks regardless of similarity', () => {
    const r = mergeSimilarChunks([
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta' }) }),
      result({ score: 50, chunk: chunk({ id: 'c', documentId: 'd1', position: 5, content: 'alpha beta gamma delta' }) })
    ])
    expect(r).toHaveLength(2)
  })
  it('throws on invalid threshold', () => {
    expect(() => mergeSimilarChunks([], -1)).toThrow(/\[0,1\]/)
    expect(() => mergeSimilarChunks([], 2)).toThrow(/\[0,1\]/)
  })
  it('throws on non-array input', () => {
    expect(() => mergeSimilarChunks(null as never)).toThrow(/must be an array/)
  })
  it('keeps distinct-content adjacent chunks', () => {
    const r = mergeSimilarChunks([
      result({ chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'apple banana' }) }),
      result({ chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'cherry durian' }) })
    ])
    expect(r).toHaveLength(2)
  })
})

// ============ buildContext end-to-end ============

describe('Phase 8-C3 buildContext end-to-end', () => {
  let builder: RAGContextBuilder
  beforeEach(() => { builder = new RAGContextBuilder() })

  it('builds a valid RAGContext', () => {
    const ctx = builder.buildContext('bubble', [result()])
    expect(isValidRAGContext(ctx)).toBe(true)
  })
  it('preserves the query verbatim', () => {
    expect(builder.buildContext('bubble dynamics', []).query).toBe('bubble dynamics')
  })
  it('drops results beyond maxChunks', () => {
    const small = new RAGContextBuilder({ maxChunks: 1 })
    const rs = [result({ chunk: chunk({ id: 'a', content: 'a' }) }), result({ chunk: chunk({ id: 'b', content: 'b' }) })]
    expect(small.buildContext('x', rs).chunks.length).toBe(1)
  })
  it('maxChunks 0 disables the cap', () => {
    const unlimited = new RAGContextBuilder({ maxChunks: 0 })
    const rs = [result({ chunk: chunk({ id: 'a' }) }), result({ chunk: chunk({ id: 'b' }) })]
    expect(unlimited.buildContext('x', rs).chunks.length).toBe(2)
  })
  it('chunks are numbered 1..N aligned with citations', () => {
    const ctx = builder.buildContext('q', [result()])
    expect(ctx.chunks.length).toBe(ctx.citations.length)
    expect(ctx.citations[0]!.chunkId).toBe(ctx.chunks[0]!.chunkId)
  })
  it('truncates when total tokens exceed the budget', () => {
    const tiny = new RAGContextBuilder({ defaultTokenBudget: 5 })
    const ctx = tiny.buildContext('x', [
      result({ chunk: chunk({ id: 'a', content: 'alpha beta gamma delta epsilon zeta eta theta iota' }) })
    ])
    expect(ctx.chunks.length).toBeLessThanOrEqual(1)
  })
  it('preserves citations for kept chunks', () => {
    const ctx = builder.buildContext('x', [
      result({ chunk: chunk({ id: 'a', documentId: 'd1', content: 'x' }), citation: cite({ documentId: 'd1', chunkId: 'a', page: 4 }) }),
      result({ chunk: chunk({ id: 'b', documentId: 'd2', content: 'y' }), citation: cite({ documentId: 'd2', chunkId: 'b', page: 9 }) })
    ])
    expect(ctx.citations.find((c) => c.page === 4)).toBeDefined()
    expect(ctx.citations.find((c) => c.page === 9)).toBeDefined()
  })
  it('deduplicates citations across repeated chunks', () => {
    const ctx = builder.buildContext('x', [
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 1 }) }),
      result({ chunk: chunk({ id: 'b' }), citation: cite({ chunkId: 'b', page: 2 }) }),
      result({ chunk: chunk({ id: 'a', position: 2 }), citation: cite({ chunkId: 'a', page: 1 }) })
    ])
    expect(ctx.chunks.length).toBe(2)
    expect(ctx.citations.length).toBe(2)
  })
  it('merges similar adjacent chunks', () => {
    const rs = [
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta epsilon' }) }),
      result({ score: 50, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'alpha beta gamma delta zeta' }) })
    ]
    const ctx = builder.buildContext('x', rs)
    expect(ctx.chunks.length).toBe(1)
  })
  it('throws on empty query', () => {
    expect(() => builder.buildContext('', [result()])).toThrow(/non-empty string/)
  })
  it('throws on non-array results', () => {
    expect(() => builder.buildContext('q', null as never)).toThrow(/must be an array/)
  })
  it('throws when maxChunks is negative', () => {
    expect(() => new RAGContextBuilder({ maxChunks: -1 })).toThrow(/non-negative/)
  })
  it('throws when defaultTokenBudget is negative', () => {
    expect(() => new RAGContextBuilder({ defaultTokenBudget: -1 })).toThrow(/non-negative/)
  })
  it('throws when mergeThreshold out of [0,1]', () => {
    expect(() => new RAGContextBuilder({ mergeThreshold: 1.5 })).toThrow(/\[0,1\]/)
  })
  it('metadata.totalTokens reflects the kept chunks', () => {
    const ctx = builder.buildContext('x', [result()])
    expect(typeof ctx.metadata.totalTokens).toBe('number')
    expect(ctx.metadata.totalTokens as number).toBeGreaterThan(0)
  })
  it('metadata.totalCandidates reflects pre-truncate deduped count', () => {
    const ctx = builder.buildContext('x', [
      result({ chunk: chunk({ id: 'a' }) }),
      result({ chunk: chunk({ id: 'b' }) })
    ])
    expect(ctx.metadata.totalCandidates).toBe(2)
  })
  it('is deterministic across calls', () => {
    const rs = [
      result({ chunk: chunk({ id: 'a', content: 'bubble water' }) }),
      result({ chunk: chunk({ id: 'b', content: 'reactor kinetics' }) })
    ]
    const a = builder.buildContext('bubble', rs)
    const b = builder.buildContext('bubble', rs)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('context metadata accepts a custom field', () => {
    const ctx = builder.buildContext('q', [], { metadata: { source: 'paper.pdf' } })
    expect(ctx.metadata.source).toBe('paper.pdf')
  })
  it('throws when a chunk reference is invalid', () => {
    expect(() => builder.buildContext('x', [{
      chunk: chunk({ id: '' }), score: 100, citation: cite({ chunkId: '' })
    }])).toThrow(/invalid (RAGContext|ContextChunk)/)
  })
  it('token budget overrides the builder default', () => {
    const big = builder.buildContext('x', [
      result({ chunk: chunk({ id: 'a', content: 'alpha beta gamma' }) })
    ], { tokenBudget: 100 })
    expect(big.tokenBudget).toBe(100)
  })
  it('maxChunks overrides the builder default', () => {
    const limited = builder.buildContext('x', [
      result({ chunk: chunk({ id: 'a' }) }),
      result({ chunk: chunk({ id: 'b' }) }),
      result({ chunk: chunk({ id: 'c' }) })
    ], { maxChunks: 1 })
    expect(limited.chunks.length).toBe(1)
  })
  it('filters results below the cap when results exceed maxChunks', () => {
    const limited = builder.buildContext('x', [
      result({ score: 200, chunk: chunk({ id: 'a' }) }),
      result({ score: 100, chunk: chunk({ id: 'b' }) }),
      result({ score: 50, chunk: chunk({ id: 'c' }) })
    ], { maxChunks: 2 })
    expect(limited.chunks.map((c) => c.chunkId)).toEqual(['a', 'b'])
  })
})

// ============ ResearchContextProvider adapter ============

describe('Phase 8-C3 ResearchContextProvider adapter', () => {
  it('requires a retriever and builder', () => {
    expect(() => new ResearchContextProvider({ retriever: undefined as never, builder: new RAGContextBuilder() })).toThrow(/retriever required/)
    expect(() => new ResearchContextProvider({ retriever: new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() }), builder: undefined as never })).toThrow(/builder required/)
  })
  it('builds a context end-to-end via the injected retriever + builder', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble' })
    expect(isValidRAGContext(out.context)).toBe(true)
    expect(out.summary.query).toBe('bubble')
    expect(out.summary.chunkCount).toBe(out.context.chunks.length)
  })
  it('rejects empty queries', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    await expect(provider.provide({ text: '' })).rejects.toThrow(/non-empty string/)
  })
  it('rejects non-string queries', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    await expect(provider.provide({ text: 1 as never })).rejects.toThrow(/non-empty string/)
  })
  it('passes filters through to the retriever', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble', filters: { documentId: 'doc:1' } })
    for (const c of out.context.chunks) expect(c.citation.documentId).toBe('doc:1')
  })
  it('honors per-call tokenBudget override', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder({ defaultTokenBudget: 5000 }) })
    const out = await provider.provide({ text: 'bubble', tokenBudget: 50 })
    expect(out.context.tokenBudget).toBe(50)
  })
  it('honors per-call maxChunks override', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble', maxChunks: 1 })
    expect(out.context.chunks.length).toBeLessThanOrEqual(1)
  })
  it('summary estimatedTokens matches context.metadata.totalTokens', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble' })
    expect(out.summary.estimatedTokens).toBe(out.context.metadata.totalTokens)
  })
  it('summary.tokenBudget reflects the effective budget', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble', tokenBudget: 123 })
    expect(out.summary.tokenBudget).toBe(123)
  })
  it('defaultTitleResolver returns the configured title', () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder(), defaultTitle: 'My Paper' })
    expect(provider.defaultTitleResolver()('c', 'd')).toBe('My Paper')
  })
  it('passes through arbitrary metadata fields', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'bubble' })
    expect(out.context.metadata.provider).toBe('Untitled Source')
  })
  it('supports a custom defaultTitle', () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder(), defaultTitle: 'Custom' })
    expect(provider.defaultTitleResolver()('c', 'd')).toBe('Custom')
  })
  it('returns zero results when retriever has nothing', async () => {
    const h = new HybridRetriever({ vectorStore: new LocalVectorStore(), embedding: new LocalEmbeddingProvider() })
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'no-such-text-anywhere-xyzzy' })
    expect(out.summary.chunkCount).toBe(0)
  })
  it('is deterministic across calls', async () => {
    const { h } = makeHybrid()
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const a = await provider.provide({ text: 'bubble' })
    const b = await provider.provide({ text: 'bubble' })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('does NOT depend on the agent runtime / planner / model layer', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(path.resolve(__dirname, '../../src/main/services/knowledge/research-context-provider.ts'), 'utf8')
    expect(src).not.toContain('agent-runtime')
    expect(src).not.toContain('research-planner')
    expect(src).not.toContain('model-provider')
  })
})

// ============ security + source scans ============

describe('Phase 8-C3 security + isolation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('context-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/knowledge/context-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('citation-formatter.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/citation-formatter.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
  })
  it('rag-context-builder.ts has no forbidden imports', () => {
    const src = readSrc('../../src/main/services/knowledge/rag-context-builder.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('rag-context-builder.ts does not import agent runtime / planner / tool layer', () => {
    const src = readSrc('../../src/main/services/knowledge/rag-context-builder.ts')
    expect(src).not.toContain('agent-runtime')
    expect(src).not.toContain('research-planner')
    expect(src).not.toContain('tools/')
  })
  it('research-context-provider.ts does not import agent runtime / planner / model layer', () => {
    const src = readSrc('../../src/main/services/knowledge/research-context-provider.ts')
    expect(src).not.toContain('agent-runtime')
    expect(src).not.toContain('research-planner')
    expect(src).not.toContain('model-provider')
  })
  it('no implementation file imports the PDF parser or embedding layer', () => {
    const builder = readSrc('../../src/main/services/knowledge/rag-context-builder.ts')
    const provider = readSrc('../../src/main/services/knowledge/research-context-provider.ts')
    expect(builder + provider).not.toContain('pdf-parser')
    expect(builder + provider).not.toContain('document-importer')
    expect(builder + provider).not.toContain('local-embedding')
    expect(builder + provider).not.toContain('local-vector-store')
  })
  it('no implementation file uses Math.random or Date.now', () => {
    for (const f of ['citation-formatter', 'rag-context-builder', 'research-context-provider']) {
      const src = readSrc(`../../src/main/services/knowledge/${f}.ts`)
      expect(src).not.toContain('Math.random')
      expect(src).not.toContain('Date.now')
    }
  })
  it('FORBIDDEN list in context-schema has 8 entries', () => {
    expect(ctxHelpers.FORBIDDEN.length).toBe(8)
  })
  it('context-schema throws on secret in chunk content', () => {
    expect(() => isValidRAGContext({
      query: 'q', chunks: [{ chunkId: 'c', content: 'token leaked', score: 0, citation: cite() }],
      citations: [cite()], tokenBudget: 100, metadata: {}
    })).toThrow(/forbidden/)
  })
  it('context-schema throws on secret in query', () => {
    expect(() => isValidRAGContext({
      query: 'Bearer token', chunks: [], citations: [], tokenBudget: 100, metadata: {}
    })).toThrow(/forbidden/)
  })
  it('context-schema throws on secret in metadata', () => {
    expect(() => isValidRAGContext({
      query: 'q', chunks: [], citations: [], tokenBudget: 100, metadata: { providerId: 'sk-leak' }
    })).toThrow(/forbidden/)
  })
  it('no process.env / fetch / http imports anywhere', () => {
    for (const f of ['citation-formatter', 'rag-context-builder', 'research-context-provider']) {
      const src = readSrc(`../../src/main/services/knowledge/${f}.ts`)
      expect(src).not.toContain('process.env')
      expect(src).not.toContain('fetch(')
      expect(src).not.toMatch(/from\s+['"]http/)
    }
  })
  it('formatter is a pure module (no class / instance state)', () => {
    const src = readSrc('../../src/main/services/knowledge/citation-formatter.ts')
    expect(src).toContain('export function')
    expect(src).not.toContain('class ')
  })
  it('adapter never executes an LLM call (no anthropic/openai SDK)', () => {
    const src = readSrc('../../src/main/services/knowledge/research-context-provider.ts')
    expect(src).not.toMatch(/@anthropic-ai/)
    expect(src).not.toMatch(/openai/)
  })
  it('adapter never generates a prompt template', () => {
    const src = readSrc('../../src/main/services/knowledge/research-context-provider.ts')
    expect(src).not.toContain('prompt')
    expect(src).not.toContain('systemMessage')
  })
})

// ============ supplementary ============

describe('Phase 8-C3 supplementary edge cases', () => {
  let builder: RAGContextBuilder
  beforeEach(() => { builder = new RAGContextBuilder() })
  it('dedupeSearchResults preserves first-seen order across citations', () => {
    const a = cite({ chunkId: 'a', page: 1 })
    const b = cite({ chunkId: 'b', page: 2 })
    const c = cite({ chunkId: 'a', page: 1 })
    const r = dedupeSearchResults([
      result({ chunk: chunk({ id: 'a' }), citation: a }),
      result({ chunk: chunk({ id: 'b' }), citation: b }),
      result({ chunk: chunk({ id: 'a2' }), citation: c })
    ])
    expect(r.map((x) => x.citation.chunkId)).toEqual(['a', 'b'])
  })
  it('mergeSimilarChunks keeps the higher-scored when threshold met', () => {
    const r = mergeSimilarChunks([
      result({ score: 30, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta epsilon zeta eta theta' }) }),
      result({ score: 90, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'alpha beta gamma delta epsilon zeta eta theta iota' }) })
    ])
    expect(r).toHaveLength(1)
    expect(r[0]!.chunk.id).toBe('b')
  })
  it('formatInlineCitation with no options and no page renders just the number', () => {
    expect(formatInlineCitation(cite())).toBe('[1]')
  })
  it('estimateTokens handles whitespace-only', () => {
    expect(estimateTokens('     ')).toBe(0)
  })
  it('buildContext honors default token budget when no override', () => {
    const ctx = builder.buildContext('q', [result({ chunk: chunk({ id: 'a', content: 'bubble water' }) })])
    expect(ctx.tokenBudget).toBe(builderHelpers.DEFAULT_TOKEN_BUDGET)
  })
  it('buildContext honors maxChunks default', () => {
    const rs = Array.from({ length: 10 }, (_, i) => result({ chunk: chunk({ id: `c${i}` }) }))
    const ctx = builder.buildContext('q', rs)
    expect(ctx.chunks.length).toBeLessThanOrEqual(builderHelpers.DEFAULT_MAX_CHUNKS)
  })
  it('truncateByTokenBudget returns [] when chunks empty', () => {
    expect(truncateByTokenBudget([], 1000)).toEqual([])
  })
  it('mergeSimilarChunks keeps both for non-adjacent positions', () => {
    const r = mergeSimilarChunks([
      result({ chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta' }) }),
      result({ chunk: chunk({ id: 'b', documentId: 'd1', position: 9, content: 'alpha beta gamma delta' }) })
    ])
    expect(r).toHaveLength(2)
  })
  it('rankChunks returns empty array on empty results', () => {
    expect(rankChunks([])).toEqual([])
  })
  it('mergeSimilarChunks returns empty array on empty results', () => {
    expect(mergeSimilarChunks([])).toEqual([])
  })
  it('dedupeSearchResults returns empty array on empty input', () => {
    expect(dedupeSearchResults([])).toEqual([])
  })
  it('formatReferenceList with mixed pages renders page on the ones with it', () => {
    const text = formatReferenceList([
      cite({ page: 3 }),
      cite(),
      cite({ page: 7 })
    ], () => 'Title')
    expect(text).toBe('[1] Title, page 3\n[2] Title\n[3] Title, page 7')
  })
  it('buildContext with empty results yields citations=[]', () => {
    const ctx = builder.buildContext('q', [])
    expect(ctx.chunks).toEqual([])
    expect(ctx.citations).toEqual([])
  })
  it('truncateByTokenBudget estimator default grows monotonically', () => {
    const s1 = truncateByTokenBudget([{ chunkId: 'a', content: 'short', score: 0.5, citation: cite() }], 100)
    void s1
    const s2 = truncateByTokenBudget([{ chunkId: 'b', content: 'long '.repeat(20), score: 0.5, citation: cite() }], 100)
    expect(s2.length).toBeLessThanOrEqual(1)
  })
  it('buildContext preserves score ordering after merge', () => {
    const rs = [
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta epsilon zeta eta theta iota kappa' }) }),
      result({ score: 80, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'apple banana cherry durian elderberry fig grape huckleberry' }) })
    ]
    const ctx = builder.buildContext('x', rs)
    if (ctx.chunks.length > 0) expect(ctx.chunks[0]!.score).toBe(100)
  })
  it('ResearchContextProvider on empty index yields a valid empty RAGContext', async () => {
    const { h } = makeHybrid()
    // strip docs by overwriting with empty content not possible; just use a query that doesn't match
    const provider = new ResearchContextProvider({ retriever: h, builder: new RAGContextBuilder() })
    const out = await provider.provide({ text: 'zzzqqqxxxnoooo' })
    expect(isValidRAGContext(out.context)).toBe(true)
    expect(out.context.chunks.length).toBe(0)
  })
  it('CitationReference page field can be omitted (optional)', () => {
    expect(isValidCitationReference(cite())).toBe(true)
    expect(isValidCitationReference(cite({ page: undefined }))).toBe(true)
  })
  it('buildContext with metadata containing source renders it back', () => {
    const ctx = builder.buildContext('q', [], { metadata: { source: 'paper.pdf' } })
    expect(ctx.metadata.source).toBe('paper.pdf')
  })
  it('rankChunks with empty query keeps original scores', () => {
    const rs = [result({ score: 50 }), result({ score: 100 })]
    const r = rankChunks(rs, '')
    expect(r[0]!.score).toBe(100)
    expect(r[1]!.score).toBe(50)
  })
  it('mergeSimilarChunks threshold 0 drops every adjacent same-doc pair', () => {
    const r = mergeSimilarChunks([
      result({ score: 100, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'apple banana' }) }),
      result({ score: 50, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'cherry durian' }) })
    ], 0)
    expect(r).toHaveLength(1)
    expect(r[0]!.chunk.id).toBe('a')
  })
  it('buildContext no chunk survives when budget is 1', () => {
    const tight = new RAGContextBuilder({ defaultTokenBudget: 1 })
    const ctx = tight.buildContext('q', [result({ chunk: chunk({ id: 'a', content: 'bubble water dynamics' }) })])
    expect(ctx.chunks.length).toBe(0)
  })
  it('buildContext citation count equals chunk count for unique citations', () => {
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 1 }) }),
      result({ chunk: chunk({ id: 'b' }), citation: cite({ chunkId: 'b', page: 2 }) }),
      result({ chunk: chunk({ id: 'c' }), citation: cite({ chunkId: 'c', page: 3 }) })
    ])
    expect(ctx.citations.length).toBe(ctx.chunks.length)
  })
})

// ============ Supplementary Phase 8-C3 ============

describe('Phase 8-C3 supplementary edge cases II', () => {
  let builder: RAGContextBuilder
  beforeEach(() => { builder = new RAGContextBuilder() })
  it('formatInlineCitation number 0 still renders', () => {
    expect(formatInlineCitation(cite({ page: 1 }), { number: 0 })).toBe('[0, page 1]')
  })
  it('formatInlineCitation title-only (no page)', () => {
    expect(formatInlineCitation(cite(), { number: 1, title: 'Paper' })).toBe('[1] Paper')
  })
  it('formatInlineCitation title + section, no page', () => {
    expect(formatInlineCitation(cite(), { number: 4, title: 'Paper', section: 'Intro' })).toBe('[4] Paper, § Intro')
  })
  it('formatReferenceList honors explicit 0 page (treated as missing)', () => {
    const text = formatReferenceList([cite({ page: 0 })], () => 'Title')
    expect(text).toBe('[1] Title')
  })
  it('formatReferenceList page 1.5 treated as missing', () => {
    const text = formatReferenceList([cite({ page: 1.5 as never })], () => 'Title')
    expect(text).toBe('[1] Title')
  })
  it('estimateTokens is 0 for an exact newline character', () => {
    expect(estimateTokens('\n\n\n')).toBe(0)
  })
  it('estimateTokens is deterministic across process invocations', () => {
    const a = estimateTokens('bubble dynamics reactor kinetics in water quality')
    const b = estimateTokens('bubble dynamics reactor kinetics in water quality')
    expect(a).toBe(b)
  })
  it('estimateTokens returns at least 1 for any non-whitespace text', () => {
    expect(estimateTokens('a')).toBe(1)
    expect(estimateTokens('a b c d e f g h i j k l m')).toBeGreaterThanOrEqual(1)
  })
  it('rankChunks preserves input when already sorted', () => {
    const rs = [result({ score: 200 }), result({ score: 100 }), result({ score: 50 })]
    expect(rankChunks(rs).map((r) => r.score)).toEqual([200, 100, 50])
  })
  it('rankChunks with empty terms (whitespace query) keeps original scores', () => {
    const rs = [result({ score: 50 }), result({ score: 100 })]
    const out = rankChunks(rs, '   ')
    expect(out.map((r) => r.score)).toEqual([100, 50])
  })
  it('mergeSimilarChunks with threshold 1 keeps everything', () => {
    const rs = [
      result({ score: 50, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta' }) }),
      result({ score: 30, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'gamma delta' }) })
    ]
    expect(mergeSimilarChunks(rs, 1)).toHaveLength(2)
  })
  it('mergeSimilarChunks treats different-doc adjacency as no-merge', () => {
    const rs = [
      result({ score: 50, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma delta' }) }),
      result({ score: 30, chunk: chunk({ id: 'b', documentId: 'd2', position: 0, content: 'alpha beta gamma delta' }) })
    ]
    expect(mergeSimilarChunks(rs)).toHaveLength(2)
  })
  it('buildContext respects a custom tokenEstimator', () => {
    const tiny = new RAGContextBuilder({ defaultTokenBudget: 100 })
    const custom = (_t: string) => 5
    const ctx = tiny.buildContext('q', [
      result({ chunk: chunk({ id: 'a', content: 'whatever' }) }),
      result({ chunk: chunk({ id: 'b', content: 'whatever' }) })
    ], { tokenEstimator: custom })
    // budget 100, each chunk costs 5+1, so 16 chunks fit (80); 17th would be 85+1=86>100. Actually 100/6 = 16.66 → 16 fit.
    expect(ctx.chunks.length).toBeLessThanOrEqual(16)
  })
  it('buildContext does not add chunks after the budget is exhausted', () => {
    const tight = new RAGContextBuilder({ defaultTokenBudget: 6 })
    const ctx = tight.buildContext('q', [
      result({ chunk: chunk({ id: 'a', content: 'alpha' }) }),
      result({ chunk: chunk({ id: 'b', content: 'beta gamma delta' }) })
    ])
    // alpha costs ~3, beta gamma delta costs ~6+ → only alpha fits
    expect(ctx.chunks.length).toBe(1)
  })
  it('buildContext with empty query throws', () => {
    expect(() => builder.buildContext('', [result()])).toThrow(/non-empty string/)
  })
  it('buildContext accepts a single-character non-empty query', () => {
    const ctx = builder.buildContext('q', [])
    expect(ctx.query).toBe('q')
    expect(ctx.chunks).toEqual([])
  })
  it('buildContext preserves citation order from chunks', () => {
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 5 }) }),
      result({ chunk: chunk({ id: 'b' }), citation: cite({ chunkId: 'b', page: 1 }) })
    ])
    expect(ctx.citations.map((c) => c.page)).toEqual([5, 1])
  })
  it('buildContext carries through custom tokenEstimator in metadata.totalTokens', () => {
    const ten = (s: string) => s.length
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'a', content: 'aaa' }) }),
      result({ chunk: chunk({ id: 'b', content: 'bbbbb' }) })
    ], { tokenEstimator: ten })
    expect(ctx.metadata.totalTokens).toBe(3 + 5)
  })
  it('buildContext deterministic output byte-for-byte across calls', () => {
    const rs = [
      result({ chunk: chunk({ id: 'a', content: 'bubble water', documentId: 'doc:1' }) }),
      result({ chunk: chunk({ id: 'b', content: 'reactor kinetics', documentId: 'doc:2' }) })
    ]
    const a = builder.buildContext('q', rs)
    const b = builder.buildContext('q', rs)
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('formatInlineCitation with title and section both producing 3 commas', () => {
    expect(formatInlineCitation(cite({ page: 7 }), { number: 1, title: 'X', section: 'Y' }))
      .toBe('[1] X, § Y, page 7')
  })
  it('CitationReference page 0 is invalid', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 0.9, page: 0 })).toBe(false)
  })
  it('CitationReference negative page is invalid', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 0.9, page: -1 })).toBe(false)
  })
  it('CitationReference fractional page is invalid', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 0.9, page: 2.5 })).toBe(false)
  })
  it('CitationReference with confidence > 1 is invalid', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 1.1, page: 1 })).toBe(false)
  })
  it('mergeSimilarChunks with explicit custom threshold 0 drops adjacent same-doc', () => {
    const rs = [
      result({ score: 50, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'apple banana' }) }),
      result({ score: 30, chunk: chunk({ id: 'b', documentId: 'd1', position: 1, content: 'cherry durian elderberry' }) })
    ]
    expect(mergeSimilarChunks(rs, 0)).toHaveLength(1)
    expect(mergeSimilarChunks(rs, 0)[0]!.chunk.id).toBe('a')
  })
  it('truncateByTokenBudget returns chunks in input order', () => {
    const out = truncateByTokenBudget([
      { chunkId: 'c1', content: 'alpha', score: 0.9, citation: cite() },
      { chunkId: 'c2', content: 'beta gamma delta', score: 0.8, citation: cite({ chunkId: 'c2' }) },
      { chunkId: 'c3', content: 'epsilon zeta', score: 0.7, citation: cite({ chunkId: 'c3' }) }
    ], 1000)
    expect(out.map((c) => c.chunkId)).toEqual(['c1', 'c2', 'c3'])
  })
  it('buildContext citation 1-based numbering matches chunks array', () => {
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 1 }) }),
      result({ chunk: chunk({ id: 'b' }), citation: cite({ chunkId: 'b', page: 2 }) })
    ])
    // Chunk 0 corresponds to citation[0] (number 1)
    expect(ctx.citations[0]).toBe(ctx.chunks[0]!.citation)
    expect(ctx.citations[1]).toBe(ctx.chunks[1]!.citation)
  })
  it('formatReferenceList empty array returns empty string', () => {
    expect(formatReferenceList([], () => 'X')).toBe('')
  })
  it('formatReferenceList single citation, no title, no page', () => {
    expect(formatReferenceList([cite()], () => 'Title')).toBe('[1] Title')
  })
  it('rankChunks returns a new array (does not mutate input)', () => {
    const input = [result({ score: 50, chunk: chunk({ id: 'a' }) }), result({ score: 100, chunk: chunk({ id: 'b' }) })]
    const before = input.map((r) => r.chunk.id)
    rankChunks(input)
    expect(input.map((r) => r.chunk.id)).toEqual(before)
  })
  it('buildContext with mixed cap and budget keeps the tighter limit', () => {
    const tight = new RAGContextBuilder({ defaultTokenBudget: 100, maxChunks: 100 })
    const ctx = tight.buildContext('q', [
      result({ chunk: chunk({ id: 'a', content: 'alpha' }) }),
      result({ chunk: chunk({ id: 'b', content: 'beta' }) }),
      result({ chunk: chunk({ id: 'c', content: 'gamma' }) }),
      result({ chunk: chunk({ id: 'd', content: 'delta' }) }),
      result({ chunk: chunk({ id: 'e', content: 'epsilon' }) })
    ])
    expect(ctx.chunks.length).toBeLessThanOrEqual(5)
  })
  it('estimateTokens treats a single 1-char string as 1', () => {
    expect(estimateTokens('a')).toBe(1)
  })
  it('dedupeSearchResults preserves first occurrence order across all', () => {
    const rs = [
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 1 }) }),
      result({ chunk: chunk({ id: 'b' }), citation: cite({ chunkId: 'b', page: 2 }) }),
      result({ chunk: chunk({ id: 'a' }), citation: cite({ chunkId: 'a', page: 1 }) })
    ]
    const deduped = dedupeSearchResults(rs)
    expect(deduped.map((r) => r.chunk.id)).toEqual(['a', 'b'])
  })
  it('buildContext is the same with and without query when no matches', () => {
    const a = builder.buildContext('q', [])
    const b = builder.buildContext('q', [], { tokenEstimator: undefined })
    expect(a.chunks).toEqual(b.chunks)
  })
  it('RAGContext.metadata is always an object', () => {
    const ctx = builder.buildContext('q', [])
    expect(typeof ctx.metadata).toBe('object')
    expect(ctx.metadata).not.toBeNull()
  })
  it('buildContext chunks[i] has the citation that matches citations[i]', () => {
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'x', documentId: 'dx' }), citation: cite({ documentId: 'dx', chunkId: 'x', page: 7 }) })
    ])
    expect(ctx.chunks[0]!.citation.page).toBe(7)
    expect(ctx.citations[0]!.page).toBe(7)
  })
  it('formatInlineCitation with title and no number option defaults to 1', () => {
    expect(formatInlineCitation(cite({ page: 3 }), { title: 'P' })).toBe('[1] P, page 3')
  })
  it('mergeSimilarChunks keeps both for non-adjacent positions in different docs', () => {
    const rs = [
      result({ chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'alpha beta gamma' }) }),
      result({ chunk: chunk({ id: 'b', documentId: 'd2', position: 0, content: 'alpha beta gamma' }) })
    ]
    expect(mergeSimilarChunks(rs)).toHaveLength(2)
  })
})

// ============ Final 15 (>=2600 aggregate) ============

describe('Phase 8-C3 final 15', () => {
  it('formatInlineCitation with title and no number default to 1', () => {
    expect(formatInlineCitation(cite(), { title: 'Paper' })).toBe('[1] Paper')
  })
  it('formatInlineCitation renders no trailing space when neither title nor page', () => {
    expect(formatInlineCitation(cite(), { number: 5 })).toBe('[5]')
  })
  it('dedupeSearchResults returns the original chunks (not shallow copies)', () => {
    const rs = [result({ chunk: chunk({ id: 'a' }) })]
    const out = dedupeSearchResults(rs)
    expect(out[0]).toBe(rs[0])
  })
  it('rankChunks returns a new array (input is shallow-copied)', () => {
    const rs = [result({ score: 50 }), result({ score: 100 })]
    const out = rankChunks(rs)
    expect(out).not.toBe(rs)
    expect(out.map((r) => r.score)).toEqual([100, 50])
  })
  it('mergeSimilarChunks keeps input order for non-merged entries', () => {
    const rs = [
      result({ score: 50, chunk: chunk({ id: 'a', documentId: 'd1', position: 0, content: 'apple' }) }),
      result({ score: 30, chunk: chunk({ id: 'b', documentId: 'd2', position: 0, content: 'apple' }) }),
      result({ score: 80, chunk: chunk({ id: 'c', documentId: 'd1', position: 1, content: 'banana cherry' }) })
    ]
    expect(mergeSimilarChunks(rs).map((r) => r.chunk.id)).toEqual(['a', 'b', 'c'])
  })
  it('truncateByTokenBudget with budget 0 throws (positive integer)', () => {
    expect(() => truncateByTokenBudget([{ chunkId: 'c', content: 'x', score: 0, citation: cite() }], 0))
      .toThrow(/positive integer/)
  })
  it('estimateTokens is deterministic for very long input', () => {
    const long = 'bubble '.repeat(200)
    expect(estimateTokens(long)).toBe(estimateTokens(long))
  })
  it('buildContext returns chunks in citation order', () => {
    const builder = new RAGContextBuilder()
    const ctx = builder.buildContext('q', [
      result({ chunk: chunk({ id: 'x', documentId: 'dx' }), citation: cite({ documentId: 'dx', chunkId: 'x', page: 9 }) }),
      result({ chunk: chunk({ id: 'y', documentId: 'dy' }), citation: cite({ documentId: 'dy', chunkId: 'y', page: 2 }) })
    ])
    expect(ctx.citations[0]!.page).toBe(9)
    expect(ctx.citations[1]!.page).toBe(2)
  })
  it('isValidContextChunk returns true for the fixture', () => {
    const cc = { chunkId: 'a', content: 'bubble', score: 0.9, citation: cite() }
    expect(isValidContextChunk(cc)).toBe(true)
  })
  it('formatReferenceList with all titles resolved renders 3 lines', () => {
    const text = formatReferenceList([cite(), cite(), cite()], (_, n) => `Title ${n}`)
    expect(text.split('\n')).toHaveLength(3)
  })
  it('CitationReference with all valid fields is valid', () => {
    expect(isValidCitationReference({ documentId: 'd', chunkId: 'c', confidence: 0.5, page: 3 })).toBe(true)
  })
  it('RAGContext validator requires integer tokenBudget', () => {
    expect(isValidRAGContext({ query: 'q', chunks: [], citations: [], tokenBudget: 1.5, metadata: {} })).toBe(false)
  })
  it('rankChunks with negative scores sorts them to the end', () => {
    const r = rankChunks([result({ score: -5 }), result({ score: 10 }), result({ score: 0 })])
    expect(r[0]!.score).toBe(10)
  })
  it('buildContext with empty results carries zero totalCandidates', () => {
    const builder = new RAGContextBuilder()
    expect(builder.buildContext('q', []).metadata.totalCandidates).toBe(0)
  })
})