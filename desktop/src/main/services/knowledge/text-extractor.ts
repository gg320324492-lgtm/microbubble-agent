// Text Extractor (Phase 8-C1: Scientific PDF Document Import Pipeline).
//
// The page-boundary seam between raw PDF text and the parser. A real renderer
// (pdf.js / OCR) plugs in here; the default handles the two deterministic
// conventions used in this phase:
//   - form-feed separators  (\f)
//   - "@@PAGE:N@@" marker lines
//
// Phase 8-C1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - No OCR engine, no embeddings

export interface TextExtractor {
  /** Split raw extracted text into 1-based page strings. */
  extractPages(raw: string): string[]
}

const MARKER_RE = /^@@PAGE:(\d+)@@\s*$/m

/**
 * Phase 8-C1: default deterministic page splitter.
 */
export class LinePageExtractor implements TextExtractor {
  extractPages(raw: string): string[] {
    if (typeof raw !== 'string') {
      throw new Error('line page extractor: raw must be a string (Phase 8-C1 strict)')
    }
    if (raw.trim().length === 0) return ['']

    // Form feed: the canonical PDF text-layer separator.
    if (raw.includes('\f')) {
      return raw.split('\f').map((p) => p.replace(/^\s*\n/, '').trimEnd())
    }

    // "@@PAGE:N@@" markers.
    const markerMatch = MARKER_RE.exec(raw)
    if (markerMatch) {
      const pages = raw.split(/@@PAGE:\d+@@/).slice(1)
      return pages.map((p) => p.replace(/^\s*\n/, '').trimEnd())
    }

    // No structure: single page.
    return [raw.trimEnd()]
  }
}

export const __testHelpers = { MARKER_RE }