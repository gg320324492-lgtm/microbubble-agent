// SCI Language Reviewer (Phase 8-H3: Scientific Paper Generation Agent).
//
// Phase 8-H3: deterministic detection of writing issues in manuscript
// sections — unsupported claims, missing evidence, repeated sentences,
// overstatement. No LLM.

import type {
  SectionDraft,
  WritingIssue
} from '../../../shared/science/manuscript-schema'

// ============ Issue detectors ============

const OVERSTATEMENT_PATTERNS = [
  'proves that', 'definitely', 'certainly', 'undoubtedly',
  'always', 'never fails', 'guaranteed', 'perfect',
  'the best', 'unprecedented', 'revolutionary', 'breakthrough'
]

const HEDGING_PATTERNS = [
  'suggests', 'indicates', 'appears', 'seems',
  'may', 'might', 'could', 'possibly'
]

function detectOverstatement(draft: SectionDraft): WritingIssue[] {
  const issues: WritingIssue[] = []
  const text = draft.paragraphs.join(' ').toLowerCase()

  for (const pattern of OVERSTATEMENT_PATTERNS) {
    if (text.includes(pattern)) {
      issues.push({
        type: 'overstatement',
        location: `${draft.sectionType}: "${pattern}"`,
        description: `Overstatement detected: "${pattern}" — scientific writing should use hedged language`,
        severity: 'medium',
        suggestion: `Replace "${pattern}" with a more measured alternative (e.g., "suggests", "indicates")`
      })
    }
  }
  return issues
}

function detectRepeatedSentences(draft: SectionDraft): WritingIssue[] {
  const issues: WritingIssue[] = []
  const sentences: string[] = []

  for (const para of draft.paragraphs) {
    const splits = para.split(/[.!?]+/).map((s: string) => s.trim().toLowerCase()).filter((s: string) => s.length > 10)
    sentences.push(...splits)
  }

  const seen = new Map<string, number>()
  for (const sent of sentences) {
    const count = (seen.get(sent) ?? 0) + 1
    seen.set(sent, count)
    if (count === 2) {
      issues.push({
        type: 'repetition',
        location: `${draft.sectionType}: "${sent.slice(0, 50)}..."`,
        description: `Repeated sentence detected in ${draft.sectionType} section`,
        severity: 'low',
        suggestion: 'Rephrase or remove the repeated sentence'
      })
    }
  }
  return issues
}

function detectUnsupportedClaims(draft: SectionDraft): WritingIssue[] {
  const issues: WritingIssue[] = []
  const text = draft.paragraphs.join(' ')

  // Check for claims without evidence indicators
  const claimPatterns = ['shows that', 'demonstrates', 'confirms', 'establishes']
  for (const pattern of claimPatterns) {
    if (text.toLowerCase().includes(pattern)) {
      // Check if there's supporting data nearby (numbers, R², p-value, etc.)
      const hasEvidence = /\d+\.?\d*|R²|p\s*[<>]|confidence/i.test(text)
      if (!hasEvidence) {
        issues.push({
          type: 'unsupported_claim',
          location: `${draft.sectionType}: "${pattern}"`,
          description: `Claim "${pattern}" without supporting numerical evidence`,
          severity: 'medium',
          suggestion: 'Add quantitative evidence (R², p-value, confidence interval) to support the claim'
        })
      }
    }
  }
  return issues
}

function detectMissingHedging(draft: SectionDraft): WritingIssue[] {
  const issues: WritingIssue[] = []
  const text = draft.paragraphs.join(' ').toLowerCase()

  // Results section should have some hedging
  if (draft.sectionType === 'results') {
    const hasHedging = HEDGING_PATTERNS.some(p => text.includes(p))
    if (!hasHedging && draft.paragraphs.length > 2) {
      issues.push({
        type: 'missing_hedging',
        location: `${draft.sectionType}`,
        description: 'Results section lacks hedging language — scientific results should acknowledge uncertainty',
        severity: 'low',
        suggestion: 'Consider adding qualifiers like "suggests", "indicates", or "appears to"'
      })
    }
  }
  return issues
}

// ============ Public API ============

/**
 * Phase 8-H3: review manuscript sections for writing issues.
 * Deterministic — pattern matching, no LLM.
 */
export function reviewWriting(drafts: SectionDraft[]): WritingIssue[] {
  const issues: WritingIssue[] = []
  for (const draft of drafts) {
    issues.push(...detectOverstatement(draft))
    issues.push(...detectRepeatedSentences(draft))
    issues.push(...detectUnsupportedClaims(draft))
    issues.push(...detectMissingHedging(draft))
  }
  return issues
}
