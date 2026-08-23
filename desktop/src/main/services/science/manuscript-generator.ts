// Manuscript Generator Facade (Phase 8-H3: Scientific Paper Generation Agent).
//
// Phase 8-H3: dependency-injection facade that composes paper structure
// planning, section writing, figure captioning, and language review into
// a complete manuscript generation pipeline. All components are deterministic
// — no LLM, no backend, no SDK, no auth.

import type {
  Manuscript,
  SectionDraft,
  WritingIssue
} from '../../../shared/science/manuscript-schema'
import type { ResearchDesignResult } from '../../../shared/science/research-design-schema'
import type { AnalysisReport } from '../../../shared/science/scientific-data-schema'

import { planStructure } from './paper-structure-planner'
import { writeSections } from './scientific-writer'
import { generateFigureCaptions } from './figure-caption-generator'
import { reviewWriting } from './scientific-language-reviewer'

// ============ Facade ============

/**
 * Phase 8-H3: the Manuscript Generator composes all paper generation
 * components. Input: ResearchDesignResult + AnalysisReport. Output: Manuscript.
 */
export class ManuscriptGenerator {
  constructor() {}

  /**
   * Full manuscript generation pipeline.
   */
  generateManuscript(
    design: ResearchDesignResult,
    report: AnalysisReport
  ): Manuscript {
    const outline = planStructure(design, report)
    const sectionDrafts = writeSections(outline, report)
    const figures = generateFigureCaptions(report.figures, report)
    reviewWriting(sectionDrafts) // run review (results not used in manuscript)

    // Convert drafts to sections
    const sections = sectionDrafts.map(d => ({
      sectionType: d.sectionType,
      title: d.title,
      content: d.paragraphs.join('\n\n'),
      citations: d.citations
    }))

    // Generate highlights from conclusions
    const highlights = report.conclusions.slice(0, 4).map((c: { observation: string }) => ({
      text: c.observation,
      length: c.observation.length
    }))

    // Generate abstract from conclusions
    const abstract = report.conclusions.length > 0
      ? report.conclusions.slice(0, 3).map((c: { observation: string }) => c.observation).join(' ')
      : 'This study presents a systematic investigation of the research problem.'

    return {
      manuscriptId: `ms-${design.problemAnalysis.problemId}-${report.statistics.length}-${report.models.length}`,
      title: outline.title,
      abstract,
      sections,
      figures,
      references: [],
      highlights
    }
  }

  /**
   * Plan structure only (step 1).
   */
  planStructure(design: ResearchDesignResult, report: AnalysisReport) {
    return planStructure(design, report)
  }

  /**
   * Write sections only (step 2).
   */
  writeSections(outline: Parameters<typeof writeSections>[0], report: AnalysisReport): SectionDraft[] {
    return writeSections(outline, report)
  }

  /**
   * Generate figure captions only (step 3).
   */
  generateFigureCaptions(figures: Parameters<typeof generateFigureCaptions>[0], report: AnalysisReport) {
    return generateFigureCaptions(figures, report)
  }

  /**
   * Review writing only (step 4).
   */
  reviewWriting(drafts: SectionDraft[]): WritingIssue[] {
    return reviewWriting(drafts)
  }
}
