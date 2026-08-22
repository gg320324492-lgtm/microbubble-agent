// Knowledge Document Schema Contracts (Phase 8-C0: Knowledge Retrieval Foundation).
//
// Phase 8-C0: typed contracts for documents, chunks, and citations that the
// Retrieval layer consumes. Distinct from:
//   - Phase 7-A0 knowledge/schemas.ts (entity shapes — Paper / Experiment / ...)
//   - Phase 7-B0 knowledge/storage.ts (storage provider contracts)
//   - Phase 8 planner contracts (planner consumes Context derived from these)
//
// Phase 8-C0 frozen contract:
//   - DocumentType (6 types)
//   - Document (id / type / title / source / metadata / createdAt)
//   - DocumentChunk (id / documentId / content / position / metadata)
//   - CitationReference (documentId / chunkId / confidence)
//   - Validators + assertNoSecret guard
//
// Phase 8-C0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - The Retrieval layer CONSUMES knowledge; it never modifies storage

// ============ Document types ============

export type DocumentType =
  | 'paper'
  | 'experiment'
  | 'dataset'
  | 'equipment'
  | 'report'
  | 'manual'

export const DOCUMENT_TYPES: readonly DocumentType[] = Object.freeze([
  'paper', 'experiment', 'dataset', 'equipment', 'report', 'manual'
])

// ============ Document ============

/**
 * Phase 8-C0: a unified knowledge asset.
 *
 * Naming the domain spans Phase 7-A0 entities: a `paper` maps to Paper,
 * `experiment` to Experiment, `dataset` to Dataset, `equipment` to Equipment,
 * `report` / `manual` to lab-authored artifacts. `metadata` carries the raw
 * entity fields (e.g. researchTopic, materials) and, for retrievable prose,
 * a `content` string the chunker splits. NEVER contains secrets.
 */
export interface Document {
  id: string
  type: DocumentType
  title: string
  source: string
  metadata: Record<string, unknown>
  createdAt: number
}

// ============ DocumentChunk ============

/**
 * Phase 8-C0: a unit of retrievable text produced by a Chunker.
 */
export interface DocumentChunk {
  id: string
  documentId: string
  content: string
  /** 0-based order inside the document. */
  position: number
  metadata: Record<string, unknown>
}

// ============ CitationReference ============

/**
 * Phase 8-C0: points back to the exact retrieved unit so the research agent
 * can cite its sources. `confidence` is 0..1 (normalized retrieval score).
 */
export interface CitationReference {
  documentId: string
  chunkId: string
  confidence: number
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`knowledge document leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-C0 strict)`)
    }
  }
}

const VALID_DOCUMENT_TYPES: ReadonlySet<DocumentType> = new Set(DOCUMENT_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidDocumentType(t: unknown): t is DocumentType {
  return typeof t === 'string' && VALID_DOCUMENT_TYPES.has(t as DocumentType)
}

export function isValidDocument(d: unknown): d is Document {
  if (!isObject(d)) return false
  if (typeof d.id !== 'string' || d.id.length === 0) return false
  if (!isValidDocumentType(d.type)) return false
  if (typeof d.title !== 'string' || d.title.length === 0) return false
  if (typeof d.source !== 'string' || d.source.length === 0) return false
  if (!isObject(d.metadata)) return false
  if (typeof d.createdAt !== 'number' || !Number.isFinite(d.createdAt) || d.createdAt < 0) return false
  assertNoSecret(d, 'Document')
  return true
}

export function isValidDocumentChunk(c: unknown): c is DocumentChunk {
  if (!isObject(c)) return false
  if (typeof c.id !== 'string' || c.id.length === 0) return false
  if (typeof c.documentId !== 'string' || c.documentId.length === 0) return false
  if (typeof c.content !== 'string') return false
  if (typeof c.position !== 'number' || !Number.isInteger(c.position) || c.position < 0) return false
  if (!isObject(c.metadata)) return false
  assertNoSecret(c, 'DocumentChunk')
  return true
}

export function isValidCitationReference(r: unknown): r is CitationReference {
  if (!isObject(r)) return false
  if (typeof r.documentId !== 'string' || r.documentId.length === 0) return false
  if (typeof r.chunkId !== 'string' || r.chunkId.length === 0) return false
  if (typeof r.confidence !== 'number' || !Number.isFinite(r.confidence) || r.confidence < 0 || r.confidence > 1) return false
  assertNoSecret(r, 'CitationReference')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  DOCUMENT_TYPES,
  VALID_DOCUMENT_TYPES
}