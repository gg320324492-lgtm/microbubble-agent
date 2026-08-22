// Citation Formatter (Phase 8-C3: Citation-aware RAG Context Builder).
//
// Phase 8-C3: deterministic citation rendering + deduplication. No LLM, no
// prompt generation — pure strings out of CitationReference objects.
//
// Phase 8-C3 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No LLM call, no prompt generation

import type { CitationReference } from '../../../shared/knowledge/document-schema'

// ============ Inline citation ============

export interface InlineCitationOptions {
  /** 1-based citation number; defaults to 1 if omitted. */
  number?: number
  /** Display title (resolved upstream from the document). */
  title?: string
  /** Optional section name; rendered as " § {section}" before the page. */
  section?: string
}

function fmtPageSuffix(page: number | undefined): string {
  if (typeof page !== 'number' || !Number.isInteger(page) || page < 1) return ''
  return `, page ${page}`
}

function fmtTitleSuffix(title: string | undefined, section: string | undefined, page: number | undefined): string {
  const parts: string[] = []
  if (title) parts.push(title)
  if (section) parts.push(`§ ${section}`)
  if (typeof page === 'number' && Number.isInteger(page) && page >= 1) parts.push(`page ${page}`)
  return parts.length === 0 ? '' : ' ' + parts.join(', ')
}

/**
 * Phase 8-C3: render an inline citation marker.
 *  - Default: "[1]"
 *  - Page-only: "[1, page 5]"
 *  - With title: "[1] Microbubble Dynamics, page 5"
 */
export function formatInlineCitation(citation: CitationReference, options: InlineCitationOptions = {}): string {
  const n = options.number ?? 1
  const title = options.title
  const section = options.section
  const page = typeof citation.page === 'number' && Number.isInteger(citation.page) && citation.page >= 1
    ? citation.page
    : undefined
  if (title || section) {
    const parts: string[] = []
    if (title) parts.push(title)
    if (section) parts.push(`§ ${section}`)
    if (page !== undefined) parts.push(`page ${page}`)
    return `[${n}] ${parts.join(', ')}`
  }
  if (page !== undefined) return `[${n}, page ${page}]`
  return `[${n}]`
}

// ============ Reference list ============

export type TitleResolver = (citation: CitationReference, number: number) => string | undefined

/**
 * Phase 8-C3: render the deduplicated reference list shown beneath a context.
 * Lines: "[1] Microbubble Dynamics, page 5\n[2] Other Paper, page 3".
 *
 * `titleResolver` lets the caller plug in document metadata without coupling
 * the formatter to the retriever. Return undefined to skip the title.
 *
 * Rendering matches `formatInlineCitation` semantics:
 *   - title (+ page)  -> `[n] Title, page P`
 *   - title only      -> `[n] Title`
 *   - page only       -> `[n], page P`
 *   - nothing         -> `[n]`
 */
export function formatReferenceList(
  citations: CitationReference[],
  titleResolver: TitleResolver
): string {
  if (!Array.isArray(citations)) {
    throw new Error('citation formatter: citations must be an array (Phase 8-C3 strict)')
  }
  if (typeof titleResolver !== 'function') {
    throw new Error('citation formatter: titleResolver must be a function (Phase 8-C3 strict)')
  }
  const lines: string[] = []
  citations.forEach((cite, i) => {
    const n = i + 1
    const page = typeof cite.page === 'number' && Number.isInteger(cite.page) && cite.page >= 1 ? cite.page : undefined
    const title = titleResolver(cite, n)
    if (title) {
      const parts = [title]
      if (page !== undefined) parts.push(`page ${page}`)
      lines.push(`[${n}] ${parts.join(', ')}`)
    } else if (page !== undefined) {
      lines.push(`[${n}], page ${page}`)
    } else {
      lines.push(`[${n}]`)
    }
  })
  return lines.join('\n')
}

// ============ Deduplication ============

function citeKey(c: CitationReference): string {
  return `${c.documentId}::${c.chunkId}::${c.page ?? ''}`
}

/**
 * Phase 8-C3: deduplicate by (documentId, chunkId, page), preserving first-seen
 * order. Stable + deterministic.
 */
export function deduplicateCitation(citations: CitationReference[]): CitationReference[] {
  if (!Array.isArray(citations)) {
    throw new Error('citation formatter: citations must be an array (Phase 8-C3 strict)')
  }
  const seen = new Set<string>()
  const out: CitationReference[] = []
  for (const c of citations) {
    const k = citeKey(c)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(c)
  }
  return out
}

export const __testHelpers = {
  citeKey,
  fmtTitleSuffix,
  fmtPageSuffix
}