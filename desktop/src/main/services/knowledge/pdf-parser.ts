// Local PDF Pipeline (Phase 8-C1: Scientific PDF Document Import Pipeline).
//
// Deterministic text-based PDF parsing: metadata extraction + section detection.
// Consumes the PDF text layer provided by an injected PageExtractor (default
// LinePageExtractor handles form-feed (\\f) and "@@PAGE:N@@" page markers).
// NO LLM, NO OCR, NO embeddings.
//
// Phase 8-C1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / backend
//   - Produces ParsedPDF; never modifies the retriever

import type { PDFMetadata, PDFDocument, ParsedSection } from '../../../shared/knowledge/pdf-schema'
import { isValidPDFMetadata, isValidPDFDocument } from '../../../shared/knowledge/pdf-schema'
import type { ParsedPDF, ScientificDocumentParser } from '../../../shared/knowledge/parser-schema'
import type { TextExtractor } from './text-extractor'
import { LinePageExtractor } from './text-extractor'

// ============ Deterministic helpers ============

/** djb2 content hash (no randomness) — stable ids from text. */
export function contentHash(s: string): string {
  let h = 5381
  for (let i = 0; i < s.length; i++) {
    h = ((h * 33) ^ s.charCodeAt(i)) >>> 0
  }
  return h.toString(36).padStart(8, '0').slice(0, 8)
}

const PAGE_ONLY_RE = /^\s*['-]?\s*\d{1,3}\s*['-]?\s*$/

const HEADING_KEYWORDS: readonly string[] = Object.freeze([
  'abstract', 'introduction', 'methods', 'methodology', 'experimental',
  'experimental section', 'materials and methods', 'results and discussion',
  'results', 'discussion', 'conclusions', 'conclusion', 'references',
  'acknowledgements', 'acknowledgments', 'supporting information', 'appendix'
])

function isNoise(line: string): boolean {
  const t = line.trim()
  if (t.length === 0) return true
  if (PAGE_ONLY_RE.test(t)) return true
  if (/^(doi|https?:\/\/|www\.)/i.test(t)) return true
  return false
}

function headingLevel(line: string): number | null {
  const t = line.trim()
  if (t.length === 0 || t.length > 90) return null
  if (t.endsWith('.')) return null
  // numeric: "1 Introduction", "1. Introduction", "2.1 Methods", "1. 引言"
  const numeric = /^(\d+(\.\d+)*)\s*[.)]?\s+\S/.exec(t)
  if (numeric) {
    const segments = numeric[1]!.split('.').length
    return segments > 3 ? 3 : segments
  }
  // roman: "I. Introduction", "III Results"
  const roman = /^([IVXL]+)\s*[.)]?\s+[A-Z][a-z]/.exec(t)
  if (roman && roman[1]!.length <= 4) return 1
  // keyword headings (case-insensitive)
  const lower = t.toLowerCase().replace(/[.\s]+$/g, '')
  if (HEADING_KEYWORDS.includes(lower)) return 1
  // full-uppercase line: two words, or a single colon-terminated label
  const words = t.split(/\s+/).filter(Boolean)
  if (/^[A-Z][A-Z0-9\s&()\-–:,'"%]*$/.test(t) && (words.length >= 2 || t.endsWith(':'))) {
    return 1
  }
  return null
}

// ============ LocalPdfParser ============

export class LocalPdfParser implements ScientificDocumentParser {
  private readonly extractor: TextExtractor

  constructor(options: { extractor?: TextExtractor } = {}) {
    this.extractor = options?.extractor ?? new LinePageExtractor()
  }

  /** Phase 8-C1: full parse — pages + metadata + sections. */
  parsePDF(text: string, options?: { id?: string; filename?: string }): ParsedPDF {
    if (typeof text !== 'string') {
      throw new Error('local pdf parser: text must be a string (Phase 8-C1 strict)')
    }
    const pages = this.extractor.extractPages(text)
    const metadata = this.extractMetadata(text)
    const sections = this.extractSections(text)
    const id = options?.id ?? (text.length > 0 ? `pdf:${contentHash(text)}` : 'pdf:empty')
    const document: PDFDocument = {
      id,
      filename: options?.filename ?? 'untitled.pdf',
      pages: Math.max(1, pages.length),
      metadata
    }
    if (!isValidPDFDocument(document)) {
      throw new Error('local pdf parser: produced invalid PDFDocument (Phase 8-C1 strict)')
    }
    return { document, sections }
  }

  /** Phase 8-C1: deterministic best-effort bibliographic metadata. */
  extractMetadata(text: string): PDFMetadata {
    const entries = this.pageEntries(text)
    const lines = entries.map((e) => e.line)

    // Title: first non-noise line.
    let title: string | undefined
    let titleIdx = -1
    for (let i = 0; i < lines.length; i++) {
      if (isNoise(lines[i]!)) continue
      title = cleanTitle(lines[i]!)
      titleIdx = i
      break
    }

    // Authors: name-like lines after the title, until abstract/keywords/numbered heading.
    const authors: string[] = []
    if (titleIdx >= 0) {
      let seenNonName = 0
      for (let i = titleIdx + 1; i < Math.min(lines.length, titleIdx + 14); i++) {
        const line = lines[i]!.trim()
        if (/^(abstract|keywords|introduction)\b/i.test(line)) break
        if (/^\d+\.\s/.test(line)) break
        if (isNoise(line)) continue
        // Journal/stopword lines look like name lines ("X and Y") — skip them.
        if (/(journal|letters|nature|science|applied|proceedings|acta|physics|review)/i.test(line)) continue
        if (line.includes(',') || line.includes(' and ')) {
          const parts = line.split(/\s*,\s*|\s+and\s+/i)
            .map((p) => p.replace(/\([^)]*\)/g, '').trim())
            .filter((p) => p.length > 0 && p.length <= 80 && isNamePart(p))
          for (const part of parts) {
            if (!authors.includes(part)) authors.push(part)
          }
          seenNonName = 0
        } else {
          seenNonName++
          if (seenNonName >= 2 && authors.length > 0) break
        }
      }
    }

    // Year: 4-digit year in 1900..2099, preferring a line that is not a standalone page number.
    let year: number | undefined
    let standaloneFallback: number | undefined
    for (const e of entries) {
      const t = e.line
      if (/^\s*\d{4}\s*$/.test(t)) {
        const v = Number(t.trim())
        if (v >= 1900 && v <= 2099 && standaloneFallback === undefined) standaloneFallback = v
        continue
      }
      const m = /(19|20)\d{2}/.exec(t)
      if (m) {
        year = Number(m[0])
        break
      }
    }
    if (year === undefined) year = standaloneFallback

    // Journal: first header-region line mentioning a known journal word.
    let journal: string | undefined
    for (let i = 0; i < Math.min(lines.length, 10); i++) {
      const t = lines[i]!.trim()
      if (isNoise(t)) continue
      if (/(journal|letters|review|nature|science|applied|proceedings|acta|physics)/i.test(t)) {
        journal = t.replace(/\s*\(\d{4}\)\s*$/, '').replace(/[.;]$/, '').trim()
        break
      }
    }

    const metadata: PDFMetadata = { title, authors: authors.slice(0, 12), year, journal }
    if (!isValidPDFMetadata(metadata)) {
      throw new Error('local pdf parser: produced invalid PDFMetadata (Phase 8-C1 strict)')
    }
    return metadata
  }

  /** Phase 8-C1: deterministic section detection over page-tagged lines. */
  extractSections(text: string): ParsedSection[] {
    const entries = this.pageEntries(text)
    const sections: ParsedSection[] = []
    let current: { title: string; level: number; contentLines: string[]; pageStart: number; lastBodyPage: number | null } | null = null
    let lastPage = entries.length > 0 ? entries[entries.length - 1]!.page : 1

    const flush = (): void => {
      if (!current) return
      const body = current.contentLines.join('\n').trim()
      const pageEnd = current.lastBodyPage ?? current.pageStart
      sections.push({
        title: current.title,
        level: current.level,
        content: body,
        pageStart: current.pageStart,
        pageEnd
      })
      current = null
    }

    for (const entry of entries) {
      const t = entry.line.trim()
      if (isNoise(t)) continue
      const level = headingLevel(t)
      if (level !== null) {
        flush()
        current = { title: t, level, contentLines: [], pageStart: entry.page, lastBodyPage: null }
        continue
      }
      if (current) {
        current.contentLines.push(t)
        current.lastBodyPage = entry.page
      }
    }
    flush()

    if (sections.length === 0) {
      const body = entries.map((e) => e.line.trim()).filter((l) => !isNoise(l)).join('\n').trim()
      return [{ title: 'body', level: 0, content: body, pageStart: 1, pageEnd: lastPage }]
    }
    return sections
  }

  /** Phase 8-C1: page-tagged line list for one text pass. */
  pageEntries(text: string): Array<{ line: string; page: number }> {
    const pages = this.extractor.extractPages(text)
    const entries: Array<{ line: string; page: number }> = []
    for (let i = 0; i < pages.length; i++) {
      const pageLines = (pages[i] ?? '').split('\n')
      for (const line of pageLines) {
        entries.push({ line: line.trimEnd(), page: i + 1 })
      }
    }
    return entries
  }
}

function cleanTitle(line: string): string {
  return line.trim().replace(/[.]+$/g, '').slice(0, 240)
}

/** Phase 8-C1: true if a split author part looks like a capitalized name. */
function isNamePart(part: string): boolean {
  const words = part.split(/\s+/).filter(Boolean)
  if (words.length < 1 || words.length > 4) return false
  return words.every((w) => /^[A-ZÀ-Ÿ][\p{L}\p{N}.'-]*$/u.test(w))
}

export const __testHelpers = {
  contentHash,
  headingLevel,
  isNoise,
  isNamePart
}