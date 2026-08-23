// Research Conflict Analyzer (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: deterministic comparison of two ScientificClaim objects to
// identify conflicts and suggest resolution reasons. Uses structural text
// analysis and numerical extraction — no LLM.

import type {
  ScientificClaim,
  ResearchConflict,
  ConflictReason
} from '../../../shared/science/scientific-reasoning-schema'

// ============ Numeric extraction ============

function extractNumbers(text: string): number[] {
  const matches = text.match(/-?\d+\.?\d*/g)
  if (!matches) return []
  return matches.map(Number).filter(n => Number.isFinite(n) && n !== 0)
}

function hasOverlappingTerms(a: string, b: string): boolean {
  const wordsA = new Set(a.toLowerCase().split(/\s+/).filter(w => w.length > 3))
  const wordsB = new Set(b.toLowerCase().split(/\s+/).filter(w => w.length > 3))
  let overlap = 0
  for (const w of wordsA) {
    if (wordsB.has(w)) overlap++
  }
  const minSize = Math.min(wordsA.size, wordsB.size)
  return minSize > 0 && overlap / minSize > 0.3
}

// ============ Conflict detection ============

function detectScaleDifference(a: ScientificClaim, b: ScientificClaim): boolean {
  const numsA = extractNumbers(a.statement)
  const numsB = extractNumbers(b.statement)
  if (numsA.length === 0 || numsB.length === 0) return false
  // Different orders of magnitude in numeric claims
  const maxA = Math.max(...numsA.map(Math.abs))
  const maxB = Math.max(...numsB.map(Math.abs))
  if (maxA === 0 || maxB === 0) return false
  const ratio = maxA > maxB ? maxA / maxB : maxB / maxA
  return ratio > 5
}

function detectMethodDifference(a: ScientificClaim, b: ScientificClaim): boolean {
  const methodKeywords = ['simulation', 'experiment', 'analytical', 'numerical', 'theoretical', 'empirical']
  const aText = a.statement.toLowerCase() + ' ' + a.evidence.map((e: { description: string }) => e.description).join(' ').toLowerCase()
  const bText = b.statement.toLowerCase() + ' ' + b.evidence.map((e: { description: string }) => e.description).join(' ').toLowerCase()
  const aMethods = methodKeywords.filter(k => aText.includes(k))
  const bMethods = methodKeywords.filter(k => bText.includes(k))
  return aMethods.length > 0 && bMethods.length > 0 && !aMethods.some(m => bMethods.includes(m))
}

function detectParameterDifference(a: ScientificClaim, b: ScientificClaim): boolean {
  // Different category but overlapping topic keywords
  if (a.category === b.category) return false
  return hasOverlappingTerms(a.statement, b.statement)
}

function detectMeasurementError(a: ScientificClaim, b: ScientificClaim): boolean {
  // Both claim observation/correlation but disagree
  const observationCategories = new Set(['observation', 'correlation'])
  if (!observationCategories.has(a.category) || !observationCategories.has(b.category)) return false
  // Check if confidence is low for either
  return a.confidence < 0.5 || b.confidence < 0.5
}

function detectInsufficientData(a: ScientificClaim, b: ScientificClaim): boolean {
  // Both have low confidence or very little evidence
  const totalEvidence = a.evidence.length + b.evidence.length
  const avgConfidence = (a.confidence + b.confidence) / 2
  return totalEvidence < 2 && avgConfidence < 0.5
}

// ============ Public API ============

/**
 * Phase 8-G0: analyze two claims for conflicts. Returns possible reasons
 * the claims disagree. Deterministic — no LLM.
 */
export function analyzeConflict(
  claimA: ScientificClaim,
  claimB: ScientificClaim
): ResearchConflict {
  const reasons: ConflictReason[] = []

  if (detectScaleDifference(claimA, claimB)) reasons.push('scale_difference')
  if (detectMethodDifference(claimA, claimB)) reasons.push('method_difference')
  if (detectParameterDifference(claimA, claimB)) reasons.push('parameter_difference')
  if (detectMeasurementError(claimA, claimB)) reasons.push('measurement_error')
  if (detectInsufficientData(claimA, claimB)) reasons.push('insufficient_data')

  // If no specific reason found, default to insufficient_data
  if (reasons.length === 0) reasons.push('insufficient_data')

  let resolution: string | undefined
  if (reasons.includes('scale_difference')) {
    resolution = 'Claims may refer to different experimental scales or conditions'
  } else if (reasons.includes('method_difference')) {
    resolution = 'Claims use different methodologies — cross-validation recommended'
  } else if (reasons.length === 1 && reasons[0] === 'insufficient_data') {
    resolution = 'Insufficient evidence to determine which claim is more reliable'
  }

  return {
    conflictId: `conflict-${claimA.claimId}-${claimB.claimId}`,
    claimA,
    claimB,
    possibleReasons: reasons,
    resolution
  }
}

/**
 * Phase 8-G0: batch analyze a list of claims for pairwise conflicts.
 * Returns only conflicts where at least one reason was detected.
 */
export function findConflicts(claims: ScientificClaim[]): ResearchConflict[] {
  const conflicts: ResearchConflict[] = []
  for (let i = 0; i < claims.length; i++) {
    for (let j = i + 1; j < claims.length; j++) {
      const conflict = analyzeConflict(claims[i], claims[j])
      // Only return conflicts with meaningful reasons (not just the default)
      if (conflict.possibleReasons.length > 1 ||
          conflict.possibleReasons[0] !== 'insufficient_data') {
        conflicts.push(conflict)
      }
    }
  }
  return conflicts
}
