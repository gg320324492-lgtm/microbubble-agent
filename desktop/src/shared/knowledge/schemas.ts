// Scientific Knowledge Schemas (Phase 7-A0: Scientific Knowledge Architecture).
//
// Phase 7-A0: typed contract for the Knowledge Layer. Distinct from
//   - Phase 6 Model Runtime (Provider / Router / Chat)
//   - Phase 6-A5 legacy FastAPI /chat/stream
//   - Future RAG pipeline (Phase 7+)
//
// Phase 7-A0 frozen contract:
//   - 6 entity types (Paper / Experiment / Equipment / Dataset / Figure / ResearchProject)
//   - 3 metadata standards (Parameter / Measurement / Citation)
//   - Validators for each entity + metadata shape
//   - Extension-compatible shape (Phase 7+ adds new fields without breaking old data)
//
// Phase 7-A0 strict:
//   - NEVER contains apiKey / token / secret / authorization
//   - Knowledge Layer is INDEPENDENT from Model Provider / Capability Router /
//     Chat Runtime / legacy FastAPI backend

// ============ Entities ============

export interface Paper {
  id: string
  title: string
  authors: string[]
  journal: string
  year: number
  doi?: string
  keywords: string[]
  researchField: string
  abstract: string
  methods?: string
  parameters?: Parameter[]
  results?: string
  conclusions?: string
  relatedExperiments?: string[]
}

export interface Experiment {
  id: string
  name: string
  researchTopic: string
  objective: string
  system: string
  materials?: string[]
  equipment: string[]
  parameters: Parameter[]
  conditions?: string
  measurements?: Measurement[]
  results?: string
  conclusion?: string
}

export interface Equipment {
  id: string
  name: string
  type: string
  manufacturer?: string
  specifications?: Record<string, string>
  operatingRange?: string
  relatedExperiments?: string[]
}

export interface Dataset {
  id: string
  name: string
  source: string
  variables: string[]
  units?: Record<string, string>
  samples?: number
  processingMethod?: string
  results?: string
}

export type FigureType =
  | 'SEM'
  | 'CFD-contour'
  | 'particle-distribution'
  | 'kinetic-curve'
  | 'spectrum'
  | 'microscopy'
  | 'other'

export interface Figure {
  id: string
  type: FigureType
  source: string
  caption: string
  relatedDataset?: string
  relatedPaper?: string
}

export interface ResearchProject {
  id: string
  title: string
  members: string[]
  topic: string
  papers: string[]
  experiments: string[]
  datasets: string[]
}

// ============ Metadata Standards ============

export interface Parameter {
  name: string
  value: number | string | boolean
  unit?: string
  uncertainty?: number
  source?: 'experiment' | 'literature' | 'simulation' | 'derived' | 'unknown'
}

export interface Measurement {
  metric: string
  value: number | string
  method?: string
  instrument?: string
}

export interface Citation {
  paperId: string
  source: 'paper' | 'book' | 'web' | 'preprint' | 'other'
  confidence?: 'verified' | 'inferred' | 'unverified'
}

// ============ Validators ============

const ID_RE = /^[a-zA-Z][a-zA-Z0-9_\-:.]{1,63}$/
const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`schema leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-A0 strict)`)
    }
  }
}

function isNonEmptyString(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === 'string')
}

export function isValidPaper(p: unknown): p is Paper {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (!isNonEmptyString(o.title)) return false
  if (!isStringArray(o.authors) || (o.authors as string[]).length === 0) return false
  if (!isNonEmptyString(o.journal)) return false
  if (typeof o.year !== 'number' || o.year < 1800 || o.year > 2200) return false
  if (!isStringArray(o.keywords)) return false
  if (!isNonEmptyString(o.researchField)) return false
  if (!isNonEmptyString(o.abstract)) return false
  if (o.doi !== undefined && typeof o.doi !== 'string') return false
  if (o.methods !== undefined && typeof o.methods !== 'string') return false
  if (o.results !== undefined && typeof o.results !== 'string') return false
  if (o.conclusions !== undefined && typeof o.conclusions !== 'string') return false
  if (o.parameters !== undefined && !Array.isArray(o.parameters)) return false
  if (o.relatedExperiments !== undefined && !isStringArray(o.relatedExperiments)) return false
  assertNoSecret(p, 'Paper')
  return true
}

export function isValidExperiment(e: unknown): e is Experiment {
  if (!e || typeof e !== 'object') return false
  const o = e as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (!isNonEmptyString(o.name)) return false
  if (!isNonEmptyString(o.researchTopic)) return false
  if (!isNonEmptyString(o.objective)) return false
  if (!isNonEmptyString(o.system)) return false
  if (!isStringArray(o.equipment)) return false
  if (!Array.isArray(o.parameters) || (o.parameters as unknown[]).length === 0) return false
  for (const p of o.parameters) {
    if (!isValidParameter(p)) return false
  }
  if (o.materials !== undefined && !isStringArray(o.materials)) return false
  if (o.conditions !== undefined && typeof o.conditions !== 'string') return false
  if (o.measurements !== undefined) {
    if (!Array.isArray(o.measurements)) return false
    for (const m of o.measurements) {
      if (!isValidMeasurement(m)) return false
    }
  }
  if (o.results !== undefined && typeof o.results !== 'string') return false
  if (o.conclusion !== undefined && typeof o.conclusion !== 'string') return false
  assertNoSecret(e, 'Experiment')
  return true
}

export function isValidEquipment(eq: unknown): eq is Equipment {
  if (!eq || typeof eq !== 'object') return false
  const o = eq as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (!isNonEmptyString(o.name)) return false
  if (!isNonEmptyString(o.type)) return false
  if (o.manufacturer !== undefined && typeof o.manufacturer !== 'string') return false
  if (o.specifications !== undefined && (typeof o.specifications !== 'object' || o.specifications === null)) return false
  if (o.operatingRange !== undefined && typeof o.operatingRange !== 'string') return false
  if (o.relatedExperiments !== undefined && !isStringArray(o.relatedExperiments)) return false
  assertNoSecret(eq, 'Equipment')
  return true
}

export function isValidDataset(d: unknown): d is Dataset {
  if (!d || typeof d !== 'object') return false
  const o = d as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (!isNonEmptyString(o.name)) return false
  if (!isNonEmptyString(o.source)) return false
  if (!isStringArray(o.variables) || (o.variables as string[]).length === 0) return false
  if (o.units !== undefined && (typeof o.units !== 'object' || o.units === null)) return false
  if (o.samples !== undefined && (typeof o.samples !== 'number' || o.samples < 0)) return false
  if (o.processingMethod !== undefined && typeof o.processingMethod !== 'string') return false
  if (o.results !== undefined && typeof o.results !== 'string') return false
  assertNoSecret(d, 'Dataset')
  return true
}

const VALID_FIGURE_TYPES: ReadonlySet<FigureType> = new Set([
  'SEM', 'CFD-contour', 'particle-distribution', 'kinetic-curve', 'spectrum', 'microscopy', 'other'
])

export function isValidFigure(f: unknown): f is Figure {
  if (!f || typeof f !== 'object') return false
  const o = f as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (typeof o.type !== 'string' || !VALID_FIGURE_TYPES.has(o.type as FigureType)) return false
  if (!isNonEmptyString(o.source)) return false
  if (!isNonEmptyString(o.caption)) return false
  if (o.relatedDataset !== undefined && typeof o.relatedDataset !== 'string') return false
  if (o.relatedPaper !== undefined && typeof o.relatedPaper !== 'string') return false
  assertNoSecret(f, 'Figure')
  return true
}

export function isValidResearchProject(p: unknown): p is ResearchProject {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (!isNonEmptyString(o.id) || !ID_RE.test(o.id as string)) return false
  if (!isNonEmptyString(o.title)) return false
  if (!isStringArray(o.members)) return false
  if (!isNonEmptyString(o.topic)) return false
  if (!isStringArray(o.papers)) return false
  if (!isStringArray(o.experiments)) return false
  if (!isStringArray(o.datasets)) return false
  assertNoSecret(p, 'ResearchProject')
  return true
}

export function isValidParameter(p: unknown): p is Parameter {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (!isNonEmptyString(o.name)) return false
  if (o.value === undefined) return false
  const v = o.value
  const validType = typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean'
  if (!validType) return false
  if (o.unit !== undefined && typeof o.unit !== 'string') return false
  if (o.uncertainty !== undefined && typeof o.uncertainty !== 'number') return false
  if (o.source !== undefined) {
    const validSource = o.source === 'experiment' || o.source === 'literature'
      || o.source === 'simulation' || o.source === 'derived' || o.source === 'unknown'
    if (!validSource) return false
  }
  assertNoSecret(p, 'Parameter')
  return true
}

export function isValidMeasurement(m: unknown): m is Measurement {
  if (!m || typeof m !== 'object') return false
  const o = m as Record<string, unknown>
  if (!isNonEmptyString(o.metric)) return false
  if (o.value === undefined) return false
  const v = o.value
  if (typeof v !== 'number' && typeof v !== 'string') return false
  if (o.method !== undefined && typeof o.method !== 'string') return false
  if (o.instrument !== undefined && typeof o.instrument !== 'string') return false
  assertNoSecret(m, 'Measurement')
  return true
}

export function isValidCitation(c: unknown): c is Citation {
  if (!c || typeof c !== 'object') return false
  const o = c as Record<string, unknown>
  if (!isNonEmptyString(o.paperId)) return false
  if (typeof o.source !== 'string') return false
  const validSource = o.source === 'paper' || o.source === 'book'
    || o.source === 'web' || o.source === 'preprint' || o.source === 'other'
  if (!validSource) return false
  if (o.confidence !== undefined) {
    const validConf = o.confidence === 'verified' || o.confidence === 'inferred'
      || o.confidence === 'unverified'
    if (!validConf) return false
  }
  assertNoSecret(c, 'Citation')
  return true
}

// ============ Relationship validator ============

/**
 * Phase 7-A0: validate a relationship tuple (parentId, childId, kind).
 * Used by tests to ensure that entity IDs reference real entities.
 *
 * NOTE: this is a structural check, NOT a database lookup.
 */
export function isValidRelationship(
  parent: { id: string } | null | undefined,
  childId: string,
  kind: 'paper' | 'experiment' | 'equipment' | 'dataset' | 'figure' | 'project'
): boolean {
  if (!parent || typeof parent.id !== 'string') return false
  if (typeof childId !== 'string' || childId.length === 0) return false
  const validKinds = ['paper', 'experiment', 'equipment', 'dataset', 'figure', 'project']
  if (!validKinds.includes(kind)) return false
  // Phase 7-A0 strict: parent.id != childId (no self-reference)
  if (parent.id === childId) return false
  return true
}

/**
 * Phase 7-A0: minimal extension-point — generic extra fields container
 * that future schema versions can use without breaking older data.
 */
export interface ExtensionFields {
  [key: string]: unknown
}

export function isExtensionFieldsSafe(ext: unknown): boolean {
  if (!ext || typeof ext !== 'object') return false
  assertNoSecret(ext, 'ExtensionFields')
  return true
}

export const __testHelpers = {
  ID_RE,
  FORBIDDEN,
  VALID_FIGURE_TYPES
}
