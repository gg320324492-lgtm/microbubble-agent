// Local Chunker (Phase 8-C0: Knowledge Retrieval Foundation).
//
// Deterministic, character-exact chunker used by the LocalRetriever.
// No NLP, no embeddings, no PDF parsing — pure slice-based splitting.
//
// Round-trip contract:
//   - overlapChars = 0                     =>  mergeChunks(split(content)) === content
//   - preserveWords = true (no overlap)    =>  mergeChunks(split(content)) === content
//                                             (whitespace stays as next chunk's head)
//   - overlapChars > 0                     =>  NOT round-trip safe (overlap duplicated)
//
// Phase 8-C0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / backend
//   - Never touches storage — consumes Documents only

import type { Document, DocumentChunk } from '../../../shared/knowledge/document-schema'
import type { Chunker } from '../../../shared/knowledge/chunker-schema'
import { isSplitDocumentInput } from '../../../shared/knowledge/chunker-schema'

export interface LocalChunkerOptions {
  /** Target max chars per chunk (default 400). */
  maxChars?: number
  /** Overlap chars between consecutive chunks (default 0 => exact round-trip). */
  overlapChars?: number
  /** Back up cuts to whitespace; drops the separator and disables overlap (default false). */
  preserveWords?: boolean
}

/**
 * Phase 8-C0: deterministic slice-based chunker.
 */
export class LocalChunker implements Chunker {
  private readonly maxChars: number
  private readonly overlapChars: number
  private readonly preserveWords: boolean

  constructor(options: LocalChunkerOptions = {}) {
    this.maxChars = normalizePositive(options.maxChars ?? 400, 'maxChars')
    this.overlapChars = normalizeNonNegative(options.overlapChars ?? 0, 'overlapChars')
    this.preserveWords = options.preserveWords === true
    if (this.overlapChars >= this.maxChars) {
      throw new Error('local chunker: overlapChars must be < maxChars (Phase 8-C0 strict)')
    }
  }

  splitDocument(document: Document): DocumentChunk[] {
    if (!isSplitDocumentInput(document)) {
      throw new Error(`local chunker: invalid document '${String((document as { id?: string })?.id)}' (Phase 8-C0 strict)`)
    }
    const content = typeof document.metadata.content === 'string' ? document.metadata.content : ''
    const parts = splitContent(content, this.maxChars, this.overlapChars, this.preserveWords)
    const section = document.metadata.section
    const page = document.metadata.page
    const chunkMetadata: Record<string, unknown> = {}
    if (typeof section === 'string') chunkMetadata.section = section
    if (typeof page === 'number' && Number.isInteger(page) && page >= 0) chunkMetadata.page = page

    return parts.map((contentPart, index) => ({
      id: `${document.id}#${index}`,
      documentId: document.id,
      content: contentPart,
      position: index,
      metadata: { ...chunkMetadata }
    }))
  }

  mergeChunks(chunks: readonly DocumentChunk[]): string {
    const ordered = [...chunks].sort((a, b) => a.position - b.position)
    return ordered.map((c) => c.content).join('')
  }
}

export function normalizePositive(value: number, label: string): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value <= 0) {
    throw new Error(`local chunker: ${label} must be a positive integer (Phase 8-C0 strict)`)
  }
  return value
}

export function normalizeNonNegative(value: number, label: string): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < 0) {
    throw new Error(`local chunker: ${label} must be a non-negative integer (Phase 8-C0 strict)`)
  }
  return value
}

/**
 * Phase 8-C0: exact slice splitting of `content`. No characters are created
 * or destroyed when overlapChars = 0 and preserveWords = false.
 */
export function splitContent(
  content: string,
  maxChars: number,
  overlapChars: number,
  preserveWords: boolean
): string[] {
  if (content.length === 0) return ['']
  if (content.length <= maxChars) return [content]
  const parts: string[] = []
  let pos = 0
  while (pos < content.length) {
    let end = pos + maxChars
    const lastChunk = end >= content.length
    if (lastChunk) {
      end = content.length
    } else if (preserveWords) {
      const window = content.slice(pos, end)
      const lastWs = Math.max(window.lastIndexOf(' '), window.lastIndexOf('\n'), window.lastIndexOf('\t'))
      if (lastWs > 0) end = pos + lastWs
    }
    parts.push(content.slice(pos, end))
    if (lastChunk) break
    pos = preserveWords ? end : end - overlapChars
    if (pos <= 0) break
  }
  return parts
}

export const __testHelpers = {
  splitContent,
  normalizePositive,
  normalizeNonNegative
}