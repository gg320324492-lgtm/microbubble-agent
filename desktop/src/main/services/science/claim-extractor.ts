// Scientific Claim Extractor (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: deterministic extraction of ScientificClaim objects from document
// metadata and RAG context. Uses structural heuristics — no LLM. Each extracted
// claim includes evidence items and confidence derived from retrieval scores.

import type {
  ScientificClaim,
  EvidenceItem,
  ClaimCategory,
  EvidenceType
} from '../../../shared/science/scientific-reasoning-schema'

// ============ Category detection keywords ============

const CATEGORY_SIGNALS: ReadonlyMap<ClaimCategory, readonly string[]> = new Map([
  ['mechanism', ['mechanism', 'pathway', 'process', 'how', 'through', 'via', 'catalyz', 'react']],
  ['observation', ['observed', 'measured', 'found', 'detected', 'identified', 'noticed', 'showed']],
  ['correlation', ['correlat', 'associat', 'relat', 'link', 'trend', 'pattern', 'co-occur']],
  ['causation', ['caus', 'induc', 'lead to', 'result in', 'responsible', 'effect of', 'impact']],
  ['prediction', ['predict', 'forecast', 'project', 'anticipate', 'expect', 'will', 'should lead']]
])

const EVIDENCE_SIGNALS: ReadonlyMap<EvidenceType, readonly string[]> = new Map([
  ['experiment', ['experiment', 'measured', 'lab', 'trial', 'test', 'assay', 'sample']],
  ['simulation', ['simulat', 'model', 'computational', 'cfd', 'fem', 'numerical', 'finite']],
  ['theory', ['theory', 'theoretical', 'derived', 'according to', 'based on theory', 'principle']],
  ['statistical', ['statistical', 'p-value', 'significance', 'regression', 'anova', 'confidence interval']],
  ['review', ['review', 'meta-analysis', 'survey', 'overview', 'summary of', 'literature']]
])

// ============ Internal helpers ============

function textMatchesSignals(text: string, signals: readonly string[]): number {
  const lower = text.toLowerCase()
  let matches = 0
  for (const sig of signals) {
    if (lower.includes(sig)) matches++
  }
  return matches / signals.length
}

function detectCategory(text: string): ClaimCategory {
  let bestCategory: ClaimCategory = 'observation'
  let bestScore = 0
  for (const [cat, signals] of CATEGORY_SIGNALS) {
    const score = textMatchesSignals(text, signals)
    if (score > bestScore) {
      bestScore = score
      bestCategory = cat
    }
  }
  return bestCategory
}

function detectEvidenceType(text: string): EvidenceType {
  let bestType: EvidenceType = 'review'
  let bestScore = 0
  for (const [type, signals] of EVIDENCE_SIGNALS) {
    const score = textMatchesSignals(text, signals)
    if (score > bestScore) {
      bestScore = score
      bestType = type
    }
  }
  return bestType
}

function estimateConfidence(text: string, retrievalScore: number): number {
  let confidence = retrievalScore
  // Boost for quantitative content
  const numberMatches = text.match(/\d+\.?\d*/g)
  if (numberMatches && numberMatches.length > 2) confidence += 0.1
  // Boost for explicit significance mentions
  if (text.match(/p\s*[<>=]|significant|significant/i)) confidence += 0.05
  // Penalty for hedging language
  const hedging = ['might', 'possibly', 'may', 'unclear', 'uncertain', 'suggest']
  const hedgingCount = hedging.filter(h => text.toLowerCase().includes(h)).length
  confidence -= hedgingCount * 0.05
  return Math.max(0, Math.min(1, Math.round(confidence * 100) / 100))
}

// Deterministic strength based on position (first chunk = stronger)
function deterministicStrength(position: number, total: number): number {
  if (total <= 1) return 0.7
  return Math.round((0.9 - (position / total) * 0.4) * 100) / 100
}

// ============ Public API ============

/**
 * Phase 8-G0: extract scientific claims from document chunks. Each chunk
 * that contains substantive content becomes one claim. Deterministic —
 * no randomness, no LLM.
 */
export function extractClaims(
  documentId: string,
  chunks: Array<{ content: string; score: number; position: number }>
): ScientificClaim[] {
  const claims: ScientificClaim[] = []
  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i]
    if (chunk.content.trim().length < 20) continue // skip trivial fragments

    const text = chunk.content
    const category = detectCategory(text)
    const confidence = estimateConfidence(text, chunk.score)

    const evidence: EvidenceItem = {
      evidenceId: `ev-${documentId}-${i}`,
      type: detectEvidenceType(text),
      description: text.slice(0, 200),
      strength: deterministicStrength(i, chunks.length)
    }

    claims.push({
      claimId: `claim-${documentId}-${i}`,
      statement: text.slice(0, 300),
      sourceId: documentId,
      evidence: [evidence],
      confidence,
      category
    })
  }
  return claims
}

/**
 * Phase 8-G0: extract a single claim from a text fragment. Used for
 * inline claim identification during conversation.
 */
export function extractSingleClaim(
  text: string,
  sourceId: string
): ScientificClaim | null {
  if (text.trim().length < 20) return null
  return {
    claimId: `claim-${sourceId}-single`,
    statement: text.slice(0, 300),
    sourceId,
    evidence: [{
      evidenceId: `ev-${sourceId}-single`,
      type: detectEvidenceType(text),
      description: text.slice(0, 200),
      strength: 0.6
    }],
    confidence: estimateConfidence(text, 0.5),
    category: detectCategory(text)
  }
}
