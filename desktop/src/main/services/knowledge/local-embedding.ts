// Local Embedding Provider (Phase 8-C2: Embedding + Vector Retrieval Foundation).
//
// Deterministic feature-hash embedding. No network, no LLM, no model download.
// Same text => same vector (pure function). Output is L2-normalized so cosine
// reduces to a dot product on a unit sphere.
//
// Phase 8-C2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Consumes only string inputs; never touches storage / tools / runtime

import type { EmbeddingVector, EmbeddingProvider } from '../../../shared/knowledge/embedding-schema'
import { isValidEmbeddingVector } from '../../../shared/knowledge/embedding-schema'

const DEFAULT_DIMENSION = 64

// ============ Hashing primitives (FNV-1a / djb2 — deterministic, no RNG) ============

/** FNV-1a 32-bit — deterministic string hash. */
export function fnv1a32(s: string): number {
  let h = 0x811c9dc5 >>> 0
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h >>> 0
}

/** djb2 — deterministic, used for the sign bit. */
export function djb2Sign(s: string): 1 | -1 {
  let h = 5381 >>> 0
  for (let i = 0; i < s.length; i++) {
    h = ((h * 33) ^ s.charCodeAt(i)) >>> 0
  }
  return (h & 1) ? 1 : -1
}

/**
 * Phase 8-C2: tokenize for embedding.
 * - Word tokens: runs of letters/digits/marks (Unicode).
 * - CJK characters are also produced as single-char tokens so Chinese text still embeds.
 * - Adjacent tokens are joined with "##" to produce bigram features.
 */
export function tokenizeForEmbedding(text: string): string[] {
  const out: string[] = []
  const lower = text.toLowerCase()
  let cur = ''
  const flush = (): void => {
    if (cur.length > 0) { out.push(cur); cur = '' }
  }
  for (const ch of lower) {
    const code = ch.codePointAt(0)!
    const isCjk = (code >= 0x3040 && code <= 0x30ff)
      || (code >= 0x3400 && code <= 0x9fff)
      || (code >= 0xac00 && code <= 0xd7af)
      || (code >= 0xf900 && code <= 0xfaff)
    const isWord = /[\p{L}\p{M}\p{N}]/u.test(ch)
    if (isCjk) {
      flush()
      out.push(ch)
      continue
    }
    if (isWord) { cur += ch } else flush()
  }
  flush()
  // bigrams
  const bigrams: string[] = []
  for (let i = 0; i < out.length - 1; i++) bigrams.push(out[i] + '##' + out[i + 1])
  return [...out, ...bigrams]
}

/** Phase 8-C2: deterministic content hash used as default vector id. */
export function contentId(text: string): string {
  return 'emb:' + fnv1a32(text).toString(36).padStart(8, '0').slice(0, 8)
}

function round6(x: number): number {
  return Math.round(x * 1e6) / 1e6
}

function l2Normalize(values: number[]): number[] {
  let s = 0
  for (const v of values) s += v * v
  const n = Math.sqrt(s)
  if (n === 0) return values.slice()
  return values.map((v) => round6(v / n))
}

/**
 * Phase 8-C2: deterministic embedding.
 * Feature hashing (sign-hashed) into `dimension` dims, L2-normalized.
 */
export function computeEmbedding(text: string, dimension: number = DEFAULT_DIMENSION): number[] {
  if (!Number.isInteger(dimension) || dimension < 1) {
    throw new Error('local embedding: dimension must be a positive integer (Phase 8-C2 strict)')
  }
  const vec = new Array<number>(dimension).fill(0)
  const tokens = tokenizeForEmbedding(text)
  if (tokens.length === 0) return l2Normalize(vec)
  // weight: 1/sqrt(tokens) keeps contribution comparable across lengths.
  const w = 1 / Math.sqrt(tokens.length)
  for (const tok of tokens) {
    const dim = fnv1a32(tok) % dimension
    const sign = djb2Sign(tok)
    vec[dim] = vec[dim]! + sign * w
  }
  return l2Normalize(vec)
}

// ============ LocalEmbeddingProvider ============

export interface LocalEmbeddingProviderOptions {
  dimension?: number
}

export class LocalEmbeddingProvider implements EmbeddingProvider {
  private readonly dimension: number

  constructor(options: LocalEmbeddingProviderOptions = {}) {
    const d = options?.dimension ?? DEFAULT_DIMENSION
    if (!Number.isInteger(d) || d < 1) {
      throw new Error('local embedding provider: dimension must be a positive integer (Phase 8-C2 strict)')
    }
    this.dimension = d
  }

  getDimension(): number { return this.dimension }

  embed(text: string, id?: string): EmbeddingVector {
    if (typeof text !== 'string') {
      throw new Error('local embedding provider: text must be a string (Phase 8-C2 strict)')
    }
    const values = computeEmbedding(text, this.dimension)
    const vector: EmbeddingVector = { id: id ?? contentId(text), dimension: this.dimension, values }
    if (!isValidEmbeddingVector(vector)) {
      throw new Error('local embedding provider: produced invalid EmbeddingVector (Phase 8-C2 strict)')
    }
    return vector
  }

  embedBatch(texts: string[], ids?: string[]): EmbeddingVector[] {
    if (!Array.isArray(texts)) {
      throw new Error('local embedding provider: texts must be an array (Phase 8-C2 strict)')
    }
    if (ids !== undefined && ids.length !== texts.length) {
      throw new Error('local embedding provider: ids length must match texts length (Phase 8-C2 strict)')
    }
    for (const t of texts) {
      if (typeof t !== 'string') {
        throw new Error('local embedding provider: every text must be a string (Phase 8-C2 strict)')
      }
    }
    return texts.map((t, i) => this.embed(t, ids?.[i]))
  }
}

export const __testHelpers = {
  DEFAULT_DIMENSION,
  fnv1a32,
  djb2Sign,
  tokenizeForEmbedding,
  contentId,
  computeEmbedding
}