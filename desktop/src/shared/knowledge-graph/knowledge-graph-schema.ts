// Knowledge Graph Schema — 科研知识图谱契约。

// ============ Enums ============

export type EntityType =
  | 'Paper' | 'Author' | 'Method' | 'Material'
  | 'Parameter' | 'Mechanism' | 'Experiment' | 'Result'
  | 'Claim' | 'Equation' | 'Dataset' | 'Model'

export const ENTITY_TYPES: readonly EntityType[] = Object.freeze([
  'Paper', 'Author', 'Method', 'Material',
  'Parameter', 'Mechanism', 'Experiment', 'Result',
  'Claim', 'Equation', 'Dataset', 'Model'
])

export type RelationType =
  | 'supports' | 'contradicts' | 'improves' | 'causes'
  | 'depends_on' | 'measured_by' | 'uses' | 'compared_with' | 'derived_from'

export const RELATION_TYPES: readonly RelationType[] = Object.freeze([
  'supports', 'contradicts', 'improves', 'causes',
  'depends_on', 'measured_by', 'uses', 'compared_with', 'derived_from'
])

// ============ Core Types ============

export interface ScientificEntity {
  id: string
  name: string
  type: EntityType
  description: string
  sourceDocuments: string[]
  confidence: number
  metadata: Record<string, unknown>
}

export interface KnowledgeRelation {
  id: string
  sourceEntityId: string
  targetEntityId: string
  relationType: RelationType
  confidence: number
  evidence: string
}

export interface KnowledgeGraph {
  nodes: ScientificEntity[]
  edges: KnowledgeRelation[]
}

// ============ Validators ============

const VALID_ENTITY_TYPES: ReadonlySet<EntityType> = new Set(ENTITY_TYPES)
const VALID_RELATION_TYPES: ReadonlySet<RelationType> = new Set(RELATION_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

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
    throw new Error(`knowledge graph leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-J0 strict)`)
  }
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidEntityType(t: unknown): t is EntityType {
  return typeof t === 'string' && VALID_ENTITY_TYPES.has(t as EntityType)
}

export function isValidRelationType(t: unknown): t is RelationType {
  return typeof t === 'string' && VALID_RELATION_TYPES.has(t as RelationType)
}

export function isValidScientificEntity(e: unknown): e is ScientificEntity {
  if (!isObject(e)) return false
  if (typeof e.id !== 'string' || e.id.length === 0) return false
  if (typeof e.name !== 'string' || e.name.length === 0) return false
  if (!isValidEntityType(e.type)) return false
  if (typeof e.description !== 'string') return false
  if (!Array.isArray(e.sourceDocuments)) return false
  if (!isValidScore(e.confidence)) return false
  if (!isObject(e.metadata)) return false
  assertNoSecret(e, 'ScientificEntity')
  return true
}

export function isValidKnowledgeRelation(r: unknown): r is KnowledgeRelation {
  if (!isObject(r)) return false
  if (typeof r.id !== 'string' || r.id.length === 0) return false
  if (typeof r.sourceEntityId !== 'string' || r.sourceEntityId.length === 0) return false
  if (typeof r.targetEntityId !== 'string' || r.targetEntityId.length === 0) return false
  if (!isValidRelationType(r.relationType)) return false
  if (!isValidScore(r.confidence)) return false
  if (typeof r.evidence !== 'string') return false
  assertNoSecret(r, 'KnowledgeRelation')
  return true
}

export function isValidKnowledgeGraph(g: unknown): g is KnowledgeGraph {
  if (!isObject(g)) return false
  if (!Array.isArray(g.nodes)) return false
  if (!Array.isArray(g.edges)) return false
  if (!g.nodes.every(n => isValidScientificEntity(n))) return false
  if (!g.edges.every(e => isValidKnowledgeRelation(e))) return false
  assertNoSecret(g, 'KnowledgeGraph')
  return true
}

export const __testHelpers = {
  ENTITY_TYPES, RELATION_TYPES, VALID_ENTITY_TYPES, VALID_RELATION_TYPES, findForbidden, isValidScore, FORBIDDEN
}
