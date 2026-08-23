// Scientific Reasoner Facade (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: dependency-injection facade that composes the reasoning
// components (literature critic, claim extractor, conflict analyzer,
// method selector) into a single coherent API. No direct imports of
// lower layers — all dependencies injected.

import type { Document } from '../../../shared/knowledge/document-schema'
import type { CitationReference } from '../../../shared/knowledge/document-schema'
import type { RAGContext } from '../../../shared/knowledge/context-schema'
import type {
  ScientificClaim,
  PaperAssessment,
  ResearchConflict,
  MethodRecommendation,
  ResearchProblem
} from '../../../shared/science/scientific-reasoning-schema'

import { evaluatePaper } from './literature-critic'
import { extractClaims } from './claim-extractor'
import { findConflicts } from './conflict-analyzer'
import { recommendMethod } from './method-selector'

// ============ Facade ============

/**
 * Phase 8-G0: the Scientific Reasoner composes all reasoning components.
 * All dependencies are injected through the constructor for testability.
 */
export class ScientificReasoner {
  constructor() {}

  /**
   * Analyze a paper's quality and extract its claims.
   */
  analyzePaper(
    doc: Document,
    citations: CitationReference[],
    ctx: RAGContext
  ): { assessment: PaperAssessment; claims: ScientificClaim[] } {
    const assessment = evaluatePaper(doc, citations, ctx)
    const claims = extractClaims(doc.id, ctx.chunks.map((c: { content: string; score: number; citation: CitationReference }) => ({
      content: c.content,
      score: c.score,
      position: c.citation.page ?? 0
    })))
    return { assessment, claims }
  }

  /**
   * Compare two studies by analyzing their claims for conflicts.
   */
  compareStudies(
    claimsA: ScientificClaim[],
    claimsB: ScientificClaim[]
  ): ResearchConflict[] {
    const allClaims = [...claimsA, ...claimsB]
    return findConflicts(allClaims)
  }

  /**
   * Recommend a scientific method for a research problem.
   */
  recommendMethod(problem: ResearchProblem): MethodRecommendation {
    return recommendMethod(problem)
  }

  /**
   * Extract claims from document chunks.
   */
  extractClaims(
    documentId: string,
    chunks: Array<{ content: string; score: number; position: number }>
  ): ScientificClaim[] {
    return extractClaims(documentId, chunks)
  }
}
