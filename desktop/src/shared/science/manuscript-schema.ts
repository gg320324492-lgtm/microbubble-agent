// Manuscript Schema Contracts (Phase 8-H3: Scientific Paper Generation Agent).
//
// Phase 8-H3: typed contracts for manuscript structure, sections, figures,
// references, and highlights. Consumes Phase 8-H2 AnalysisReport and
// Phase 8-H0 ResearchDesignResult but never modifies them.
//
// Phase 8-H3 frozen contract:
//   - SectionType (5 types)
//   - Manuscript / Section / FigureCaption / Reference / Highlight
//   - ManuscriptOutline / SectionDraft / WritingIssue
//   - Validators + assertNoSecret guard
//
// Phase 8-H3 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId

// ============ Enums ============

export type SectionType =
  | 'introduction'
  | 'methods'
  | 'results'
  | 'discussion'
  | 'conclusion'

export const SECTION_TYPES: readonly SectionType[] = Object.freeze([
  'introduction', 'methods', 'results', 'discussion', 'conclusion'
])

// ============ Core types ============

export interface Reference {
  refId: string
  authors: string
  title: string
  journal: string
  year: number
  doi?: string
}

export interface Section {
  sectionType: SectionType
  title: string
  content: string
  citations: string[]
}

export interface FigureCaption {
  figureId: string
  caption: string
  description: string
}

export interface Highlight {
  text: string
  length: number
}

export interface Manuscript {
  manuscriptId: string
  title: string
  abstract: string
  sections: Section[]
  figures: FigureCaption[]
  references: Reference[]
  highlights: Highlight[]
}

// ============ Generation types ============

export interface ManuscriptOutline {
  title: string
  sections: Array<{ sectionType: SectionType; title: string; keyPoints: string[] }>
  figureCount: number
  referenceCount: number
}

export interface SectionDraft {
  sectionType: SectionType
  title: string
  paragraphs: string[]
  citations: string[]
}

export interface WritingIssue {
  type: string
  location: string
  description: string
  severity: 'low' | 'medium' | 'high'
  suggestion: string
}

// ============ Validators ============

const VALID_SECTION_TYPES: ReadonlySet<SectionType> = new Set(SECTION_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

// Value-only secret guard
const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') {
    for (const bad of FORBIDDEN) if (value.includes(bad)) return bad
    return null
  }
  if (Array.isArray(value)) {
    for (const v of value) { const r = findForbidden(v); if (r) return r }
    return null
  }
  if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) {
      const r = findForbidden(v); if (r) return r
    }
  }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) {
    throw new Error(`manuscript leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-H3 strict)`)
  }
}

export function isValidSectionType(t: unknown): t is SectionType {
  return typeof t === 'string' && VALID_SECTION_TYPES.has(t as SectionType)
}

export function isValidReference(r: unknown): r is Reference {
  if (!isObject(r)) return false
  if (typeof r.refId !== 'string' || r.refId.length === 0) return false
  if (typeof r.authors !== 'string' || r.authors.length === 0) return false
  if (typeof r.title !== 'string' || r.title.length === 0) return false
  if (typeof r.journal !== 'string' || r.journal.length === 0) return false
  if (typeof r.year !== 'number' || !Number.isInteger(r.year)) return false
  if (r.doi !== undefined && typeof r.doi !== 'string') return false
  assertNoSecret(r, 'Reference')
  return true
}

export function isValidSection(s: unknown): s is Section {
  if (!isObject(s)) return false
  if (!isValidSectionType(s.sectionType)) return false
  if (typeof s.title !== 'string' || s.title.length === 0) return false
  if (typeof s.content !== 'string') return false
  if (!Array.isArray(s.citations)) return false
  assertNoSecret(s, 'Section')
  return true
}

export function isValidFigureCaption(f: unknown): f is FigureCaption {
  if (!isObject(f)) return false
  if (typeof f.figureId !== 'string' || f.figureId.length === 0) return false
  if (typeof f.caption !== 'string' || f.caption.length === 0) return false
  if (typeof f.description !== 'string') return false
  assertNoSecret(f, 'FigureCaption')
  return true
}

export function isValidHighlight(h: unknown): h is Highlight {
  if (!isObject(h)) return false
  if (typeof h.text !== 'string' || h.text.length === 0) return false
  if (typeof h.length !== 'number' || !Number.isInteger(h.length) || h.length < 0) return false
  assertNoSecret(h, 'Highlight')
  return true
}

export function isValidManuscript(m: unknown): m is Manuscript {
  if (!isObject(m)) return false
  if (typeof m.manuscriptId !== 'string' || m.manuscriptId.length === 0) return false
  if (typeof m.title !== 'string' || m.title.length === 0) return false
  if (typeof m.abstract !== 'string') return false
  if (!Array.isArray(m.sections)) return false
  if (!m.sections.every((s) => isValidSection(s))) return false
  if (!Array.isArray(m.figures)) return false
  if (!m.figures.every((f) => isValidFigureCaption(f))) return false
  if (!Array.isArray(m.references)) return false
  if (!m.references.every((r) => isValidReference(r))) return false
  if (!Array.isArray(m.highlights)) return false
  if (!m.highlights.every((h) => isValidHighlight(h))) return false
  assertNoSecret(m, 'Manuscript')
  return true
}

export function isValidManuscriptOutline(o: unknown): o is ManuscriptOutline {
  if (!isObject(o)) return false
  if (typeof o.title !== 'string' || o.title.length === 0) return false
  if (!Array.isArray(o.sections)) return false
  if (typeof o.figureCount !== 'number' || !Number.isInteger(o.figureCount) || o.figureCount < 0) return false
  if (typeof o.referenceCount !== 'number' || !Number.isInteger(o.referenceCount) || o.referenceCount < 0) return false
  assertNoSecret(o, 'ManuscriptOutline')
  return true
}

export function isValidSectionDraft(d: unknown): d is SectionDraft {
  if (!isObject(d)) return false
  if (!isValidSectionType(d.sectionType)) return false
  if (typeof d.title !== 'string' || d.title.length === 0) return false
  if (!Array.isArray(d.paragraphs)) return false
  if (!Array.isArray(d.citations)) return false
  assertNoSecret(d, 'SectionDraft')
  return true
}

export function isValidWritingIssue(w: unknown): w is WritingIssue {
  if (!isObject(w)) return false
  if (typeof w.type !== 'string' || w.type.length === 0) return false
  if (typeof w.location !== 'string') return false
  if (typeof w.description !== 'string') return false
  if (w.severity !== 'low' && w.severity !== 'medium' && w.severity !== 'high') return false
  if (typeof w.suggestion !== 'string') return false
  assertNoSecret(w, 'WritingIssue')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  SECTION_TYPES,
  VALID_SECTION_TYPES,
  findForbidden
}
