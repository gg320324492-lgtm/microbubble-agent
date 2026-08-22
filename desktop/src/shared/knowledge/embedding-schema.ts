// Embedding Schema Contracts (Phase 8-C2: Embedding + Vector Retrieval Foundation).
//
// Phase 8-C2: the embedding seam — DocumentChunk content becomes dense vectors.
// Consumes DocumentChunk content ONLY; never storage, tools, or the runtime.
//
// Phase 8-C2 frozen contract:
//   - EmbeddingVector (id / dimension / values)
//   - EmbeddingProvider (embed / embedBatch)
//   - Validators + assertNoSecret guard
//
// Phase 8-C2 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No external embedding API / OpenAI SDK / model download
//   - Providers are pure-ish: same text => same vector (deterministic local provider)

// ============ EmbeddingVector ============

/**
 * Phase 8-C2: a dense vector representing one chunk of text.
 * `dimension` must equal `values.length`.
 */
export interface EmbeddingVector {
  id: string
  dimension: number
  values: number[]
}

// ============ EmbeddingProvider ============

export interface EmbeddingProvider {
  /**
   * Embed a single string. `id` defaults to a content-hash when not given.
   * Deterministic providers return identical vectors for identical text.
   */
  embed(text: string, id?: string): EmbeddingVector
  /** Embed many strings in one call. `ids`, when given, must match lengths. */
  embedBatch(texts: string[], ids?: string[]): EmbeddingVector[]
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`embedding leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-C2 strict)`)
    }
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidEmbeddingVector(v: unknown): v is EmbeddingVector {
  if (!isObject(v)) return false
  if (typeof v.id !== 'string' || v.id.length === 0) return false
  if (typeof v.dimension !== 'number' || !Number.isInteger(v.dimension) || v.dimension < 1) return false
  if (!Array.isArray(v.values)) return false
  if (v.values.length !== v.dimension) return false
  if (!v.values.every((x) => typeof x === 'number' && Number.isFinite(x))) return false
  assertNoSecret(v, 'EmbeddingVector')
  return true
}

export function isValidEmbeddingProvider(p: unknown): p is EmbeddingProvider {
  if (!isObject(p)) return false
  return typeof p.embed === 'function' && typeof p.embedBatch === 'function'
}

export const __testHelpers = {
  FORBIDDEN,
  isValidEmbeddingVector,
  isValidEmbeddingProvider
}