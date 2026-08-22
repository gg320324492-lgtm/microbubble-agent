// Chunker Schema Contracts (Phase 8-C0: Knowledge Retrieval Foundation).
//
// Phase 8-C0: typed contracts for splitting a Document into retrievable chunks
// and merging chunks back. The interface is implementation-agnostic — Phase 8-C0
// ships a deterministic LocalChunker; a later phase may add a semantic chunker.
//
// Phase 8-C0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Chunkers are pure consumers of Documents; they never modify storage

import type { Document, DocumentChunk } from './document-schema'
import { isValidDocument } from './document-schema'

// ============ ChunkMetadata ============

/**
 * Phase 8-C0: provenance hints attached to a chunk.
 * Aligned with the local chunker's output keys (section / page / position).
 */
export interface ChunkMetadata {
  section?: string
  page?: number
  position: number
}

// ============ Chunker interface ============

/**
 * Phase 8-C0: a deterministic document splitter.
 *
 * `splitDocument` returns an ordered array of chunks (0-based `position`).
 * `mergeChunks` rebuilds a single string from chunk contents — a faithful
 * chunker (no overlap, no dropped characters) round-trips exactly.
 */
export interface Chunker {
  splitDocument(document: Document): DocumentChunk[]
  mergeChunks(chunks: readonly DocumentChunk[]): string
}

// ============ Validators ============

export function isValidChunkMetadata(m: unknown): m is ChunkMetadata {
  if (!m || typeof m !== 'object' || Array.isArray(m)) return false
  const o = m as Record<string, unknown>
  if (typeof o.position !== 'number' || !Number.isInteger(o.position) || o.position < 0) return false
  if (o.section !== undefined && typeof o.section !== 'string') return false
  if (o.page !== undefined && (typeof o.page !== 'number' || !Number.isInteger(o.page) || o.page < 0)) return false
  return true
}

/**
 * Phase 8-C0: validate the input contract for splitDocument (a valid Document
 * whose optional `content` string, when present, is a string).
 */
export function isSplitDocumentInput(d: unknown): d is Document {
  if (!isValidDocument(d)) return false
  if (d.metadata.content !== undefined && typeof d.metadata.content !== 'string') return false
  return true
}

export const __testHelpers = {
  isValidChunkMetadata,
  isSplitDocumentInput
}