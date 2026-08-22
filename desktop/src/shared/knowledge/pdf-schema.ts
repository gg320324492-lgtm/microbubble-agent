// PDF Parser Schema Contracts (Phase 8-C1: Scientific PDF Document Import Pipeline).
//
// Phase 8-C1: typed contracts for parsing a PDF paper into a scientific document.
// Distinct from:
//   - Phase 8-C0 document-schema (Document / DocumentChunk / CitationReference)
//   - Phase 7-A0 schemas.ts (Paper / Experiment / ... entity shapes)
//
// Phase 8-C1 frozen contract:
//   - PDFMetadata (title / authors / year / journal)
//   - PDFDocument (id / filename / pages / metadata)
//   - ParsedSection (title / level / content / pageStart / pageEnd)
//   - Validators + assertNoSecret guard
//
// Phase 8-C1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No LLM, no OCR, no embeddings — deterministic text-based parsing

// ============ PDFMetadata ============

/**
 * Phase 8-C1: bibliographic metadata extracted from a PDF's front matter.
 * All fields optional — extraction is best-effort deterministic.
 */
export interface PDFMetadata {
  title?: string
  authors?: string[]
  year?: number
  journal?: string
}

// ============ PDFDocument ============

/**
 * Phase 8-C1: a parsed PDF paper's identity + bookkeeping.
 */
export interface PDFDocument {
  id: string
  filename: string
  pages: number
  metadata: PDFMetadata
}

// ============ ParsedSection ============

/**
 * Phase 8-C1: one detected section of the paper.
 * `level` is the heading depth (1 = top-level, 2 = subsection, ...), 0 = fallback body.
 * `pageStart` / `pageEnd` are 1-based page numbers.
 */
export interface ParsedSection {
  title: string
  level: number
  content: string
  pageStart: number
  pageEnd: number
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`pdf parser leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-C1 strict)`)
    }
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidPDFMetadata(m: unknown): m is PDFMetadata {
  if (!isObject(m)) return false
  if (m.title !== undefined && typeof m.title !== 'string') return false
  if (m.year !== undefined && (typeof m.year !== 'number' || !Number.isInteger(m.year))) return false
  if (m.journal !== undefined && typeof m.journal !== 'string') return false
  if (m.authors !== undefined
      && (!Array.isArray(m.authors) || !m.authors.every((a) => typeof a === 'string'))) return false
  assertNoSecret(m, 'PDFMetadata')
  return true
}

export function isValidPDFDocument(d: unknown): d is PDFDocument {
  if (!isObject(d)) return false
  if (typeof d.id !== 'string' || d.id.length === 0) return false
  if (typeof d.filename !== 'string' || d.filename.length === 0) return false
  if (typeof d.pages !== 'number' || !Number.isInteger(d.pages) || d.pages < 1) return false
  if (!isValidPDFMetadata(d.metadata)) return false
  assertNoSecret(d, 'PDFDocument')
  return true
}

export function isValidParsedSection(s: unknown): s is ParsedSection {
  if (!isObject(s)) return false
  if (typeof s.title !== 'string' || s.title.length === 0) return false
  if (typeof s.level !== 'number' || !Number.isInteger(s.level) || s.level < 0) return false
  if (typeof s.content !== 'string') return false
  if (typeof s.pageStart !== 'number' || !Number.isInteger(s.pageStart) || s.pageStart < 1) return false
  if (typeof s.pageEnd !== 'number' || !Number.isInteger(s.pageEnd) || s.pageEnd < s.pageStart) return false
  assertNoSecret(s, 'ParsedSection')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  isValidPDFMetadata,
  isValidPDFDocument,
  isValidParsedSection
}