// Scientific Reasoning Schema Contracts (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: typed contracts for scientific claims, evidence, conflicts, and
// method recommendations that the reasoning layer consumes. Consumes knowledge
// from Phase 8-C (Document/RAGContext) but never modifies storage.
//
// Phase 8-G0 frozen contract:
//   - ClaimCategory (5 types)
//   - EvidenceType (5 types)
//   - ConflictReason (5 types)
//   - ScientificClaim / EvidenceItem / ResearchConflict / MethodRecommendation / ResearchProblem
//   - PaperAssessment
//   - Validators + assertNoSecret guard
//
// Phase 8-G0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId

// ============ Enums ============

export type ClaimCategory =
  | 'mechanism'
  | 'observation'
  | 'correlation'
  | 'causation'
  | 'prediction'

export const CLAIM_CATEGORIES: readonly ClaimCategory[] = Object.freeze([
  'mechanism', 'observation', 'correlation', 'causation', 'prediction'
])

export type EvidenceType =
  | 'experiment'
  | 'simulation'
  | 'theory'
  | 'statistical'
  | 'review'

export const EVIDENCE_TYPES: readonly EvidenceType[] = Object.freeze([
  'experiment', 'simulation', 'theory', 'statistical', 'review'
])

export type ConflictReason =
  | 'scale_difference'
  | 'method_difference'
  | 'parameter_difference'
  | 'measurement_error'
  | 'insufficient_data'

export const CONFLICT_REASONS: readonly ConflictReason[] = Object.freeze([
  'scale_difference', 'method_difference', 'parameter_difference',
  'measurement_error', 'insufficient_data'
])

// ============ Core types ============

export interface EvidenceItem {
  evidenceId: string
  type: EvidenceType
  description: string
  strength: number // 0..1
}

export interface ScientificClaim {
  claimId: string
  statement: string
  sourceId: string
  evidence: EvidenceItem[]
  confidence: number // 0..1
  category: ClaimCategory
}

export interface ResearchConflict {
  conflictId: string
  claimA: ScientificClaim
  claimB: ScientificClaim
  possibleReasons: ConflictReason[]
  resolution?: string
}

export interface ResearchProblem {
  domain: string
  problemType: string
  description: string
  constraints: string[]
}

export interface MethodRecommendation {
  problem: string
  recommendedMethod: string
  reason: string
  confidence: number // 0..1
}

// ============ Paper Assessment ============

export interface PaperAssessment {
  documentId: string
  reliabilityScore: number // 0..1
  evidenceScore: number    // 0..1
  methodologyScore: number // 0..1
  limitations: string[]
  concerns: string[]
}

// ============ Validators ============

const VALID_CLAIM_CATEGORIES: ReadonlySet<ClaimCategory> = new Set(CLAIM_CATEGORIES)
const VALID_EVIDENCE_TYPES: ReadonlySet<EvidenceType> = new Set(EVIDENCE_TYPES)
const VALID_CONFLICT_REASONS: ReadonlySet<ConflictReason> = new Set(CONFLICT_REASONS)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

// Value-only secret guard (walks string values, not keys — avoids tokenBudget false positive)
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
    throw new Error(`scientific reasoning leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-G0 strict)`)
  }
}

export function isValidClaimCategory(c: unknown): c is ClaimCategory {
  return typeof c === 'string' && VALID_CLAIM_CATEGORIES.has(c as ClaimCategory)
}

export function isValidEvidenceType(t: unknown): t is EvidenceType {
  return typeof t === 'string' && VALID_EVIDENCE_TYPES.has(t as EvidenceType)
}

export function isValidConflictReason(r: unknown): r is ConflictReason {
  return typeof r === 'string' && VALID_CONFLICT_REASONS.has(r as ConflictReason)
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidEvidenceItem(e: unknown): e is EvidenceItem {
  if (!isObject(e)) return false
  if (typeof e.evidenceId !== 'string' || e.evidenceId.length === 0) return false
  if (!isValidEvidenceType(e.type)) return false
  if (typeof e.description !== 'string') return false
  if (!isValidScore(e.strength)) return false
  return true
}

export function isValidScientificClaim(c: unknown): c is ScientificClaim {
  if (!isObject(c)) return false
  if (typeof c.claimId !== 'string' || c.claimId.length === 0) return false
  if (typeof c.statement !== 'string' || c.statement.length === 0) return false
  if (typeof c.sourceId !== 'string' || c.sourceId.length === 0) return false
  if (!Array.isArray(c.evidence)) return false
  if (!c.evidence.every((e) => isValidEvidenceItem(e))) return false
  if (!isValidScore(c.confidence)) return false
  if (!isValidClaimCategory(c.category)) return false
  assertNoSecret(c, 'ScientificClaim')
  return true
}

export function isValidResearchConflict(r: unknown): r is ResearchConflict {
  if (!isObject(r)) return false
  if (typeof r.conflictId !== 'string' || r.conflictId.length === 0) return false
  if (!isValidScientificClaim(r.claimA)) return false
  if (!isValidScientificClaim(r.claimB)) return false
  if (!Array.isArray(r.possibleReasons)) return false
  if (!r.possibleReasons.every((x) => isValidConflictReason(x))) return false
  if (r.resolution !== undefined && typeof r.resolution !== 'string') return false
  assertNoSecret(r, 'ResearchConflict')
  return true
}

export function isValidMethodRecommendation(m: unknown): m is MethodRecommendation {
  if (!isObject(m)) return false
  if (typeof m.problem !== 'string') return false
  if (typeof m.recommendedMethod !== 'string' || m.recommendedMethod.length === 0) return false
  if (typeof m.reason !== 'string') return false
  if (!isValidScore(m.confidence)) return false
  assertNoSecret(m, 'MethodRecommendation')
  return true
}

export function isValidPaperAssessment(p: unknown): p is PaperAssessment {
  if (!isObject(p)) return false
  if (typeof p.documentId !== 'string' || p.documentId.length === 0) return false
  if (!isValidScore(p.reliabilityScore)) return false
  if (!isValidScore(p.evidenceScore)) return false
  if (!isValidScore(p.methodologyScore)) return false
  if (!Array.isArray(p.limitations)) return false
  if (!Array.isArray(p.concerns)) return false
  assertNoSecret(p, 'PaperAssessment')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  CLAIM_CATEGORIES,
  EVIDENCE_TYPES,
  CONFLICT_REASONS,
  VALID_CLAIM_CATEGORIES,
  VALID_EVIDENCE_TYPES,
  VALID_CONFLICT_REASONS,
  findForbidden,
  isValidScore
}
