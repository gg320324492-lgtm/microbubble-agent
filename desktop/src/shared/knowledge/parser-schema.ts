// Scientific Parser Schema Contracts (Phase 8-C1: Scientific PDF Document Import Pipeline).
//
// Phase 8-C1: the parser seam — a PDF paper becomes a PDFDocument + sections.
//
// Phase 8-C1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Parsers produce ParsedPDF; they never modify the Retriever
//   - No LLM call — deterministic text-based parsing

import type { PDFDocument, ParsedSection } from './pdf-schema'
import { isValidPDFDocument, isValidParsedSection } from './pdf-schema'

// ============ ParsedPDF ============

export interface ParsedPDF {
  document: PDFDocument
  sections: ParsedSection[]
}

// ============ ScientificDocumentParser ============

/**
 * Phase 8-C1: consumes extracted PDF text and returns a parsed document.
 *
 * `text` is the PDF's text layer as a string (pages separated by a page
 * extractor). `options` lets the caller pin the document id / filename.
 */
export interface ScientificDocumentParser {
  parsePDF(text: string, options?: { id?: string; filename?: string }): ParsedPDF
  extractMetadata(text: string): ParsedPDF['document']['metadata']
  extractSections(text: string): ParsedSection[]
}

// ============ Validators ============

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidParsedPDF(p: unknown): p is ParsedPDF {
  if (!isObject(p)) return false
  if (!isValidPDFDocument(p.document as PDFDocument)) return false
  if (!Array.isArray(p.sections)) return false
  return p.sections.every((s) => isValidParsedSection(s))
}

export function isValidScientificDocumentParser(p: unknown): p is ScientificDocumentParser {
  if (!isObject(p)) return false
  return typeof p.parsePDF === 'function'
    && typeof p.extractMetadata === 'function'
    && typeof p.extractSections === 'function'
}

export const __testHelpers = {
  isValidParsedPDF,
  isValidScientificDocumentParser
}