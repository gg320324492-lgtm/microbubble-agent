// Literature Critic Agent (Phase 8-G0: Scientific Reasoning Layer).
//
// Phase 8-G0: deterministic paper assessment based on document metadata,
// citation coverage, and content heuristics. No LLM dependency — the critic
// scores reliability, evidence, and methodology purely from structural signals.

import type { Document } from '../../../shared/knowledge/document-schema'
import type { RAGContext } from '../../../shared/knowledge/context-schema'
import type { CitationReference } from '../../../shared/knowledge/document-schema'
import type { PaperAssessment } from '../../../shared/science/scientific-reasoning-schema'

// ============ Heuristic weights ============

const CITATION_COVERAGE_WEIGHT = 0.3
const CONTENT_COMPLETENESS_WEIGHT = 0.3
const SOURCE_CREDIBILITY_WEIGHT = 0.2
const METADATA_RICHNESS_WEIGHT = 0.2

const HIGH_CREDIBILITY_SOURCES = new Set([
  'journal', 'review', 'conference', 'preprint'
])

// ============ Internal scoring helpers ============

function scoreCitationCoverage(citations: CitationReference[]): number {
  if (citations.length === 0) return 0.1
  const avgConf = citations.reduce((s, c) => s + c.confidence, 0) / citations.length
  const countBonus = Math.min(citations.length / 10, 1) * 0.3
  return Math.min(avgConf * 0.7 + countBonus, 1)
}

function scoreContentCompleteness(ctx: RAGContext): number {
  if (ctx.chunks.length === 0) return 0.05
  const avgLen = ctx.chunks.reduce((s: number, c: { content: string }) => s + c.content.length, 0) / ctx.chunks.length
  const lengthScore = Math.min(avgLen / 500, 1) * 0.5
  const diversityScore = Math.min(ctx.chunks.length / 5, 1) * 0.3
  const hasMetadata = Object.keys(ctx.metadata).length > 0 ? 0.2 : 0
  return Math.min(lengthScore + diversityScore + hasMetadata, 1)
}

function scoreSourceCredibility(doc: Document): number {
  const type = doc.metadata['sourceType'] as string | undefined
  if (type && HIGH_CREDIBILITY_SOURCES.has(type)) return 0.9
  if (doc.type === 'paper') return 0.7
  if (doc.type === 'experiment') return 0.6
  if (doc.type === 'report') return 0.5
  return 0.4
}

function scoreMetadataRichness(doc: Document): number {
  const keys = Object.keys(doc.metadata)
  const usefulKeys = keys.filter(k =>
    ['author', 'year', 'journal', 'doi', 'abstract', 'keywords', 'sourceType'].includes(k)
  )
  return Math.min(usefulKeys.length / 5, 1)
}

function identifyLimitations(doc: Document, ctx: RAGContext): string[] {
  const limits: string[] = []
  if (ctx.chunks.length < 3) limits.push('Limited text content available for analysis')
  if (!doc.metadata['author']) limits.push('Missing author information')
  if (!doc.metadata['year']) limits.push('Missing publication year')
  if (!doc.metadata['doi']) limits.push('No DOI for verification')
  if (ctx.citations.length === 0) limits.push('No citation references found')
  return limits
}

function identifyConcerns(doc: Document, ctx: RAGContext, reliability: number): string[] {
  const concerns: string[] = []
  if (reliability < 0.3) concerns.push('Low reliability score — results should be cross-validated')
  if (doc.type === 'manual') concerns.push('Manual-type document — not peer-reviewed')
  if (!doc.metadata['journal'] && doc.type === 'paper') concerns.push('Paper missing journal information')
  const avgChunkScore = ctx.chunks.length > 0
    ? ctx.chunks.reduce((s: number, c: { score: number }) => s + c.score, 0) / ctx.chunks.length
    : 0
  if (avgChunkScore < 0.3) concerns.push('Low retrieval relevance — context may be tangential')
  return concerns
}

// ============ Public API ============

/**
 * Phase 8-G0: evaluate a paper's quality based on its document metadata,
 * citation context, and RAG retrieval results. Fully deterministic.
 */
export function evaluatePaper(
  doc: Document,
  citations: CitationReference[],
  ctx: RAGContext
): PaperAssessment {
  const citationScore = scoreCitationCoverage(citations)
  const contentScore = scoreContentCompleteness(ctx)
  const sourceScore = scoreSourceCredibility(doc)
  const metaScore = scoreMetadataRichness(doc)

  const reliabilityScore = Math.round(
    (citationScore * CITATION_COVERAGE_WEIGHT +
     contentScore * CONTENT_COMPLETENESS_WEIGHT +
     sourceScore * SOURCE_CREDIBILITY_WEIGHT +
     metaScore * METADATA_RICHNESS_WEIGHT) * 100
  ) / 100

  const evidenceScore = Math.round(
    (citationScore * 0.5 + contentScore * 0.5) * 100
  ) / 100

  const methodologyScore = Math.round(
    (sourceScore * 0.6 + metaScore * 0.4) * 100
  ) / 100

  return {
    documentId: doc.id,
    reliabilityScore,
    evidenceScore,
    methodologyScore,
    limitations: identifyLimitations(doc, ctx),
    concerns: identifyConcerns(doc, ctx, reliabilityScore)
  }
}
