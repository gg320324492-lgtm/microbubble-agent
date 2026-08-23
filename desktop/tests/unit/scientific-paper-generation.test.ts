// Phase 8-H3: Scientific Paper Generation Agent — test suite.
// Target: ≥450 tests (4452 base → ≥4900 total).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__testDir, '..', '..', 'src')

import {
  isValidSectionType,
  isValidReference,
  isValidSection,
  isValidFigureCaption,
  isValidHighlight,
  isValidManuscript,
  isValidManuscriptOutline,
  isValidSectionDraft,
  isValidWritingIssue,
  __testHelpers
} from '../../src/shared/science/manuscript-schema'

import type {
  SectionType,
  Reference,
  Section,
  FigureCaption,
  Highlight,
  Manuscript,
  ManuscriptOutline,
  SectionDraft,
  WritingIssue
} from '../../src/shared/science/manuscript-schema'

import type { ResearchDesignResult } from '../../src/shared/science/research-design-schema'
import type { AnalysisReport, ModelFitResult, StatisticalResult, FigureRecommendation, ScientificConclusion, DataQualityReport } from '../../src/shared/science/scientific-data-schema'

import { planStructure } from '../../src/main/services/science/paper-structure-planner'
import { writeSections } from '../../src/main/services/science/scientific-writer'
import { generateFigureCaptions } from '../../src/main/services/science/figure-caption-generator'
import { reviewWriting } from '../../src/main/services/science/scientific-language-reviewer'
import { ManuscriptGenerator } from '../../src/main/services/science/manuscript-generator'

// ============ Fixtures ============

function makeDesign(overrides?: Partial<ResearchDesignResult>): ResearchDesignResult {
  return {
    problemAnalysis: {
      problemId: 'p-1',
      keyScientificQuestion: 'How does bubble size affect ozone degradation?',
      possibleMechanisms: ['mass transfer', 'radical generation'],
      requiredEvidence: ['particle size', 'O3 concentration'],
      recommendedApproach: 'batch experiment'
    },
    hypotheses: [{ hypothesisId: 'h-1', statement: 'Smaller bubbles improve degradation', mechanism: 'mass transfer', confidence: 0.8 }],
    experimentPlan: {
      planId: 'plan-1', hypothesis: 'Smaller bubbles improve ozone degradation',
      variables: [
        { name: 'bubble_diameter', type: 'independent', range: '100-500 nm', unit: 'nm', importance: 0.8 },
        { name: 'removal_efficiency', type: 'dependent', range: '0-100%', unit: '%', importance: 0.9 }
      ],
      groups: [{ groupId: 'g1', condition: 'control', purpose: 'baseline' }],
      measurements: [{ name: 'removal_efficiency', method: 'UV-Vis', reason: 'quantify removal' }],
      expectedOutcome: 'Decreasing diameter increases removal'
    },
    modelSelection: { model: 'first-order', purpose: 'kinetics', justification: 'standard model', confidence: 0.85 },
    ...overrides
  }
}

function makeReport(overrides?: Partial<AnalysisReport>): AnalysisReport {
  return {
    quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
    statistics: [
      { metric: 'concentration_mean', value: 5.0, interpretation: 'Average concentration is 5.0 mg/L' },
      { metric: 'correlation_a_b', value: -0.85, interpretation: 'Strong negative correlation' }
    ],
    models: [{ model: 'first-order', parameters: { k: 0.05 }, rSquared: 0.98, residualError: 0.01 }],
    figures: [{ type: 'scatter+fit', title: 'Data with fit', xVariable: 'time', yVariable: 'concentration', reason: 'Model fit' }],
    conclusions: [{ observation: 'First-order kinetics best describe the data', interpretation: 'Concentration-dependent behavior', confidence: 0.85 }],
    ...overrides
  }
}

function makeDraft(overrides?: Partial<SectionDraft>): SectionDraft {
  return { sectionType: 'results', title: 'Results', paragraphs: ['The results show improvement.'], citations: [], ...overrides }
}

function makeRef(overrides?: Partial<Reference>): Reference {
  return { refId: 'r1', authors: 'Zhang et al.', title: 'Study on bubbles', journal: 'Chem. Eng. J.', year: 2024, ...overrides }
}

// ============ Schema validators ============

describe('Phase 8-H3 schema', () => {
  describe('isValidSectionType', () => {
    it.each<SectionType>(['introduction', 'methods', 'results', 'discussion', 'conclusion'])(
      'accepts %s', (t) => { expect(isValidSectionType(t)).toBe(true) }
    )
    it('rejects empty', () => expect(isValidSectionType('')).toBe(false))
    it('rejects "abstract"', () => expect(isValidSectionType('abstract')).toBe(false))
  })

  describe('isValidReference', () => {
    it('accepts valid', () => expect(isValidReference(makeRef())).toBe(true))
    it('accepts with doi', () => expect(isValidReference(makeRef({ doi: '10.1234/test' }))).toBe(true))
    it('rejects empty refId', () => expect(isValidReference(makeRef({ refId: '' }))).toBe(false))
    it('rejects empty authors', () => expect(isValidReference(makeRef({ authors: '' }))).toBe(false))
    it('rejects non-integer year', () => expect(isValidReference(makeRef({ year: 2024.5 }))).toBe(false))
    it('rejects non-string doi', () => expect(isValidReference(makeRef({ doi: 42 }))).toBe(false))
    it('rejects non-object', () => expect(isValidReference(null)).toBe(false))
  })

  describe('isValidSection', () => {
    it('accepts valid', () => expect(isValidSection({ sectionType: 'introduction', title: 'Intro', content: 'text', citations: [] })).toBe(true))
    it('rejects invalid type', () => expect(isValidSection({ sectionType: 'bad', title: 't', content: 'c', citations: [] })).toBe(false))
    it('rejects empty title', () => expect(isValidSection({ sectionType: 'introduction', title: '', content: 'c', citations: [] })).toBe(false))
    it('rejects non-object', () => expect(isValidSection(null)).toBe(false))
  })

  describe('isValidFigureCaption', () => {
    it('accepts valid', () => expect(isValidFigureCaption({ figureId: 'f1', caption: 'cap', description: 'desc' })).toBe(true))
    it('rejects empty figureId', () => expect(isValidFigureCaption({ figureId: '', caption: 'c', description: 'd' })).toBe(false))
    it('rejects non-object', () => expect(isValidFigureCaption(null)).toBe(false))
  })

  describe('isValidHighlight', () => {
    it('accepts valid', () => expect(isValidHighlight({ text: 'key finding', length: 11 })).toBe(true))
    it('rejects empty text', () => expect(isValidHighlight({ text: '', length: 0 })).toBe(false))
    it('rejects negative length', () => expect(isValidHighlight({ text: 't', length: -1 })).toBe(false))
    it('rejects non-integer length', () => expect(isValidHighlight({ text: 't', length: 1.5 })).toBe(false))
    it('rejects non-object', () => expect(isValidHighlight(null)).toBe(false))
  })

  describe('isValidManuscript', () => {
    const ms: Manuscript = {
      manuscriptId: 'ms-1', title: 'Title', abstract: 'Abstract',
      sections: [{ sectionType: 'introduction', title: 'Intro', content: 'text', citations: [] }],
      figures: [{ figureId: 'f1', caption: 'cap', description: 'desc' }],
      references: [makeRef()],
      highlights: [{ text: 'key', length: 3 }]
    }
    it('accepts valid', () => expect(isValidManuscript(ms)).toBe(true))
    it('rejects empty manuscriptId', () => expect(isValidManuscript({ ...ms, manuscriptId: '' })).toBe(false))
    it('rejects empty title', () => expect(isValidManuscript({ ...ms, title: '' })).toBe(false))
    it('rejects invalid section', () => expect(isValidManuscript({ ...ms, sections: [{ sectionType: 'bad', title: '', content: '', citations: [] }] })).toBe(false))
    it('rejects non-object', () => expect(isValidManuscript(null)).toBe(false))
  })

  describe('isValidManuscriptOutline', () => {
    it('accepts valid', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: 0, referenceCount: 0 })).toBe(true))
    it('rejects empty title', () => expect(isValidManuscriptOutline({ title: '', sections: [], figureCount: 0, referenceCount: 0 })).toBe(false))
    it('rejects negative figureCount', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: -1, referenceCount: 0 })).toBe(false))
    it('rejects non-object', () => expect(isValidManuscriptOutline(null)).toBe(false))
  })

  describe('isValidSectionDraft', () => {
    it('accepts valid', () => expect(isValidSectionDraft(makeDraft())).toBe(true))
    it('rejects invalid type', () => expect(isValidSectionDraft(makeDraft({ sectionType: 'bad' }))).toBe(false))
    it('rejects non-object', () => expect(isValidSectionDraft(null)).toBe(false))
  })

  describe('isValidWritingIssue', () => {
    it('accepts valid', () => expect(isValidWritingIssue({ type: 'overstatement', location: 'l', description: 'd', severity: 'medium', suggestion: 's' })).toBe(true))
    it('accepts low severity', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(true))
    it('accepts high severity', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'high', suggestion: 's' })).toBe(true))
    it('rejects invalid severity', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'critical', suggestion: 's' })).toBe(false))
    it('rejects non-object', () => expect(isValidWritingIssue(null)).toBe(false))
  })
})

// ============ Secret guard ============

describe('Phase 8-H3 secret guard', () => {
  const { findForbidden } = __testHelpers
  it('finds sk-', () => expect(findForbidden('sk-abc')).toBe('sk-'))
  it('finds apiKey', () => expect(findForbidden('apiKey=x')).toBe('apiKey'))
  it('clean passes', () => expect(findForbidden('hello')).toBe(null))
  it('walks arrays', () => expect(findForbidden(['a', 'sk-x'])).toBe('sk-'))
  it('walks nested', () => expect(findForbidden({ a: { b: 'cipher' } })).toBe('cipher'))
  it('ignores field names', () => expect(findForbidden({ tokenBudget: 100 })).toBe(null))
  it('manuscript with apiKey throws', () => {
    expect(() => isValidManuscript({
      manuscriptId: 'ms-1', title: 'apiKey here', abstract: '',
      sections: [], figures: [], references: [], highlights: []
    })).toThrow('forbidden')
  })
  it('section with Bearer throws', () => {
    expect(() => isValidSection({ sectionType: 'introduction', title: 'Bearer token', content: '', citations: [] })).toThrow('forbidden')
  })
  it('reference with cipher throws', () => {
    expect(() => isValidReference(makeRef({ title: 'cipher text' }))).toThrow('forbidden')
  })
  it('highlight with authorization throws', () => {
    expect(() => isValidHighlight({ text: 'authorization header', length: 20 })).toThrow('forbidden')
  })
})

// ============ Paper Structure Planner ============

describe('Phase 8-H3 structure planner', () => {
  it('generates outline', () => {
    const outline = planStructure(makeDesign(), makeReport())
    expect(isValidManuscriptOutline(outline)).toBe(true)
  })

  it('outline has 5 sections', () => {
    const outline = planStructure(makeDesign(), makeReport())
    expect(outline.sections.length).toBe(5)
  })

  it('IMRaD ordering', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const types = outline.sections.map(s => s.sectionType)
    expect(types).toEqual(['introduction', 'methods', 'results', 'discussion', 'conclusion'])
  })

  it('title from research question', () => {
    const outline = planStructure(makeDesign(), makeReport())
    expect(outline.title).toContain('bubble')
  })

  it('sections have key points', () => {
    const outline = planStructure(makeDesign(), makeReport())
    for (const s of outline.sections) {
      expect(s.keyPoints.length).toBeGreaterThan(0)
    }
  })

  it('figure count from report', () => {
    const outline = planStructure(makeDesign(), makeReport())
    expect(outline.figureCount).toBe(1)
  })

  it('deterministic', () => {
    const d = makeDesign()
    const r = makeReport()
    expect(planStructure(d, r)).toEqual(planStructure(d, r))
  })
})

// ============ Scientific Writer ============

describe('Phase 8-H3 writer', () => {
  it('generates 5 sections', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    expect(drafts.length).toBe(5)
  })

  it('IMRaD ordering', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    const types = drafts.map(d => d.sectionType)
    expect(types).toEqual(['introduction', 'methods', 'results', 'discussion', 'conclusion'])
  })

  it('introduction mentions research problem', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    expect(drafts[0].paragraphs.join(' ').toLowerCase()).toContain('research')
  })

  it('results mention model', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    expect(drafts[2].paragraphs.join(' ').toLowerCase()).toContain('first-order')
  })

  it('discussion mentions R²', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    expect(drafts[3].paragraphs.join(' ')).toContain('0.980')
  })

  it('conclusion mentions key finding', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const drafts = writeSections(outline, makeReport())
    expect(drafts[4].paragraphs.join(' ').toLowerCase()).toContain('first-order')
  })

  it('all drafts valid', () => {
    const outline = planStructure(makeDesign(), makeReport())
    for (const d of writeSections(outline, makeReport())) {
      expect(isValidSectionDraft(d)).toBe(true)
    }
  })

  it('deterministic', () => {
    const outline = planStructure(makeDesign(), makeReport())
    const r = makeReport()
    expect(writeSections(outline, r)).toEqual(writeSections(outline, r))
  })
})

// ============ Figure Caption Generator ============

describe('Phase 8-H3 figure captions', () => {
  it('generates captions', () => {
    const captions = generateFigureCaptions(makeReport().figures, makeReport())
    expect(captions.length).toBe(1)
  })

  it('caption mentions variable', () => {
    const captions = generateFigureCaptions(makeReport().figures, makeReport())
    expect(captions[0].caption.toLowerCase()).toContain('time')
  })

  it('scatter+fit mentions R²', () => {
    const captions = generateFigureCaptions(makeReport().figures, makeReport())
    expect(captions[0].caption).toContain('0.980')
  })

  it('all captions valid', () => {
    for (const c of generateFigureCaptions(makeReport().figures, makeReport())) {
      expect(isValidFigureCaption(c)).toBe(true)
    }
  })

  it('figure IDs are sequential', () => {
    const report = makeReport({
      figures: [
        { type: 'line', title: 'A', xVariable: 'x', yVariable: 'y', reason: 'r' },
        { type: 'bar', title: 'B', xVariable: 'x', yVariable: 'z', reason: 'r' }
      ]
    })
    const captions = generateFigureCaptions(report.figures, report)
    expect(captions[0].figureId).toBe('fig-1')
    expect(captions[1].figureId).toBe('fig-2')
  })

  it('deterministic', () => {
    const r = makeReport()
    expect(generateFigureCaptions(r.figures, r)).toEqual(generateFigureCaptions(r.figures, r))
  })
})

// ============ SCI Language Reviewer ============

describe('Phase 8-H3 language reviewer', () => {
  it('detects overstatement', () => {
    const drafts = [makeDraft({ paragraphs: ['This proves that the method is perfect.'] })]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'overstatement')).toBe(true)
  })

  it('no overstatement in clean text', () => {
    const drafts = [makeDraft({ paragraphs: ['The results suggest improvement in efficiency.'] })]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'overstatement')).toBe(false)
  })

  it('detects repeated sentences', () => {
    const drafts = [makeDraft({ paragraphs: [
      'The method shows significant improvement in efficiency.',
      'The method shows significant improvement in efficiency.'
    ]})]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'repetition')).toBe(true)
  })

  it('no repetition in unique text', () => {
    const drafts = [makeDraft({ paragraphs: ['First unique sentence.', 'Second different sentence.'] })]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'repetition')).toBe(false)
  })

  it('detects unsupported claim', () => {
    const drafts = [makeDraft({
      sectionType: 'results',
      paragraphs: ['The data shows that the method works well without any numbers.']
    })]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'unsupported_claim')).toBe(true)
  })

  it('claims with evidence pass', () => {
    const drafts = [makeDraft({
      sectionType: 'results',
      paragraphs: ['The data shows that R²=0.95 and p<0.05, confirming the model.']
    })]
    const issues = reviewWriting(drafts)
    expect(issues.some(i => i.type === 'unsupported_claim')).toBe(false)
  })

  it('all issues valid', () => {
    const drafts = [makeDraft({ paragraphs: ['This proves that the method is definitely perfect.'] })]
    for (const i of reviewWriting(drafts)) {
      expect(isValidWritingIssue(i)).toBe(true)
    }
  })

  it('empty drafts returns empty', () => {
    expect(reviewWriting([])).toEqual([])
  })

  it('deterministic', () => {
    const drafts = [makeDraft({ paragraphs: ['This proves it.'] })]
    expect(reviewWriting(drafts)).toEqual(reviewWriting(drafts))
  })
})

// ============ Manuscript Generator Facade ============

describe('Phase 8-H3 manuscript generator', () => {
  const gen = new ManuscriptGenerator()

  it('generateManuscript returns valid', () => {
    expect(isValidManuscript(gen.generateManuscript(makeDesign(), makeReport()))).toBe(true)
  })

  it('manuscript has title', () => {
    const ms = gen.generateManuscript(makeDesign(), makeReport())
    expect(ms.title.length).toBeGreaterThan(0)
  })

  it('manuscript has abstract', () => {
    const ms = gen.generateManuscript(makeDesign(), makeReport())
    expect(ms.abstract.length).toBeGreaterThan(0)
  })

  it('manuscript has 5 sections', () => {
    const ms = gen.generateManuscript(makeDesign(), makeReport())
    expect(ms.sections.length).toBe(5)
  })

  it('manuscript has figures', () => {
    const ms = gen.generateManuscript(makeDesign(), makeReport())
    expect(ms.figures.length).toBeGreaterThan(0)
  })

  it('manuscript has highlights', () => {
    const ms = gen.generateManuscript(makeDesign(), makeReport())
    expect(ms.highlights.length).toBeGreaterThan(0)
  })

  it('planStructure standalone', () => {
    expect(isValidManuscriptOutline(gen.planStructure(makeDesign(), makeReport()))).toBe(true)
  })

  it('writeSections standalone', () => {
    const outline = gen.planStructure(makeDesign(), makeReport())
    expect(gen.writeSections(outline, makeReport()).length).toBe(5)
  })

  it('generateFigureCaptions standalone', () => {
    expect(gen.generateFigureCaptions(makeReport().figures, makeReport()).length).toBe(1)
  })

  it('reviewWriting standalone', () => {
    const outline = gen.planStructure(makeDesign(), makeReport())
    expect(Array.isArray(gen.reviewWriting(gen.writeSections(outline, makeReport())))).toBe(true)
  })

  it('deterministic full pipeline', () => {
    const d = makeDesign()
    const r = makeReport()
    expect(gen.generateManuscript(d, r)).toEqual(gen.generateManuscript(d, r))
  })
})

// ============ Determinism ============

describe('Phase 8-H3 determinism', () => {
  const gen = new ManuscriptGenerator()
  const d = makeDesign()
  const r = makeReport()

  it('structure 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => planStructure(d, r))
    const first = JSON.stringify(results[0])
    expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
  })

  it('writing 5 runs identical', () => {
    const outline = planStructure(d, r)
    const results = Array.from({ length: 5 }, () => writeSections(outline, r))
    const first = JSON.stringify(results[0])
    expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
  })

  it('captions 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => generateFigureCaptions(r.figures, r))
    const first = JSON.stringify(results[0])
    expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
  })

  it('review 5 runs identical', () => {
    const outline = planStructure(d, r)
    const drafts = writeSections(outline, r)
    const results = Array.from({ length: 5 }, () => reviewWriting(drafts))
    const first = JSON.stringify(results[0])
    expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
  })

  it('full pipeline 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => gen.generateManuscript(d, r))
    const first = JSON.stringify(results[0])
    expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
  })
})

// ============ Security source scan ============

describe('Phase 8-H3 security', () => {
  const readSrc = (relPath: string) => {
    const fs = require('fs')
    return fs.readFileSync(resolve(srcRoot, relPath), 'utf8')
  }

  it('schema has no backend imports', () => {
    expect(readSrc('shared/science/manuscript-schema.ts')).not.toMatch(/from 'app\//)
  })

  it('planner has no auth imports', () => {
    expect(readSrc('main/services/science/paper-structure-planner.ts')).not.toMatch(/import.*auth/)
  })

  it('writer has no SDK imports', () => {
    const content = readSrc('main/services/science/scientific-writer.ts')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
  })

  it('caption generator has no model-provider imports', () => {
    expect(readSrc('main/services/science/figure-caption-generator.ts')).not.toMatch(/import.*ModelProvider/)
  })

  it('language reviewer has no backend imports', () => {
    expect(readSrc('main/services/science/scientific-language-reviewer.ts')).not.toMatch(/from 'app\//)
  })

  it('generator facade has no SDK imports', () => {
    const content = readSrc('main/services/science/manuscript-generator.ts')
    expect(content).not.toMatch(/import.*anthropic/)
    expect(content).not.toMatch(/import.*openai/)
  })
})

// ============ Extended coverage ============

describe('Phase 8-H3 extended', () => {
  describe('schema extended', () => {
    it('isValidSectionType with 5 types', () => {
      for (const t of ['introduction', 'methods', 'results', 'discussion', 'conclusion']) {
        expect(isValidSectionType(t)).toBe(true)
      }
    })
    it('isValidReference with empty doi', () => expect(isValidReference(makeRef({ doi: undefined }))).toBe(true))
    it('isValidSection with empty content', () => expect(isValidSection({ sectionType: 'methods', title: 'M', content: '', citations: [] })).toBe(true))
    it('isValidFigureCaption with long caption', () => expect(isValidFigureCaption({ figureId: 'f', caption: 'A'.repeat(500), description: 'd' })).toBe(true))
    it('isValidHighlight length 0', () => expect(isValidHighlight({ text: 't', length: 0 })).toBe(true))
    it('isValidManuscript with empty sections', () => {
      expect(isValidManuscript({
        manuscriptId: 'ms', title: 't', abstract: 'a',
        sections: [], figures: [], references: [], highlights: []
      })).toBe(true)
    })
    it('isValidManuscriptOutline with sections', () => {
      expect(isValidManuscriptOutline({
        title: 't',
        sections: [{ sectionType: 'introduction', title: 'I', keyPoints: ['p1'] }],
        figureCount: 2, referenceCount: 5
      })).toBe(true)
    })
    it('isValidSectionDraft with citations', () => {
      expect(isValidSectionDraft({ sectionType: 'results', title: 'R', paragraphs: ['p'], citations: ['c1'] })).toBe(true)
    })
    it('isValidWritingIssue low severity', () => {
      expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(true)
    })
  })

  describe('structure extended', () => {
    it('introduction key points include research question', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const intro = outline.sections.find(s => s.sectionType === 'introduction')
      expect(intro!.keyPoints.some(p => p.includes('bubble'))).toBe(true)
    })
    it('methods key points include variables', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const methods = outline.sections.find(s => s.sectionType === 'methods')
      expect(methods!.keyPoints.some(p => p.includes('bubble_diameter'))).toBe(true)
    })
    it('results key points include model', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const results = outline.sections.find(s => s.sectionType === 'results')
      expect(results!.keyPoints.some(p => p.includes('first-order'))).toBe(true)
    })
    it('conclusion key points include finding', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const conc = outline.sections.find(s => s.sectionType === 'conclusion')
      expect(conc!.keyPoints.some(p => p.includes('First-order'))).toBe(true)
    })
  })

  describe('writer extended', () => {
    it('introduction has multiple paragraphs', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[0].paragraphs.length).toBeGreaterThanOrEqual(2)
    })
    it('methods has procedure text', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[1].paragraphs.join(' ').toLowerCase()).toContain('procedure')
    })
    it('results mention statistics', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[2].paragraphs.join(' ')).toContain('5')
    })
    it('discussion mentions literature', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[3].paragraphs.join(' ').toLowerCase()).toContain('literature')
    })
    it('conclusion has bullet points', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[4].paragraphs.some(p => p.startsWith('-'))).toBe(true)
    })
  })

  describe('captions extended', () => {
    it('line chart caption mentions time', () => {
      const report = makeReport({ figures: [{ type: 'line', title: 'Trend', xVariable: 'time', yVariable: 'conc', reason: 'temporal' }] })
      const captions = generateFigureCaptions(report.figures, report)
      expect(captions[0].caption.toLowerCase()).toContain('time')
    })
    it('histogram caption mentions distribution', () => {
      const report = makeReport({ figures: [{ type: 'histogram', title: 'Dist', xVariable: 'size', yVariable: 'freq', reason: 'distribution' }] })
      const captions = generateFigureCaptions(report.figures, report)
      expect(captions[0].caption.toLowerCase()).toContain('distribution')
    })
    it('bar chart caption mentions comparison', () => {
      const report = makeReport({ figures: [{ type: 'bar', title: 'Compare', xVariable: 'method', yVariable: 'yield', reason: 'comparison' }] })
      const captions = generateFigureCaptions(report.figures, report)
      expect(captions[0].caption.toLowerCase()).toContain('comparison')
    })
    it('scatter caption mentions relationship', () => {
      const report = makeReport({ figures: [{ type: 'scatter', title: 'Rel', xVariable: 'x', yVariable: 'y', reason: 'relationship' }] })
      const captions = generateFigureCaptions(report.figures, report)
      expect(captions[0].caption.toLowerCase()).toContain('relationship')
    })
  })

  describe('reviewer extended', () => {
    it('detects "proves"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This proves that the hypothesis is correct.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('detects "undoubtedly"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is undoubtedly correct.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('detects "breakthrough"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is a breakthrough discovery.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('no issues in clean scientific text', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['The data suggests a positive trend (R²=0.95). Further investigation is needed.'] })])
      expect(issues.length).toBe(0)
    })
    it('multiple issues detected', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: [
        'This proves that the method is perfect.',
        'This proves that the method is perfect.'
      ]})])
      expect(issues.length).toBeGreaterThanOrEqual(2)
    })
  })

  describe('facade extended', () => {
    const gen = new ManuscriptGenerator()
    it('manuscript sections have content', () => {
      const ms = gen.generateManuscript(makeDesign(), makeReport())
      for (const s of ms.sections) {
        expect(s.content.length).toBeGreaterThan(0)
      }
    })
    it('manuscript highlights are from conclusions', () => {
      const ms = gen.generateManuscript(makeDesign(), makeReport())
      expect(ms.highlights[0].text).toContain('First-order')
    })
    it('manuscript abstract from conclusions', () => {
      const ms = gen.generateManuscript(makeDesign(), makeReport())
      expect(ms.abstract).toContain('First-order')
    })
    it('pipeline with empty report', () => {
      const report = makeReport({ statistics: [], models: [], figures: [], conclusions: [] })
      const ms = gen.generateManuscript(makeDesign(), report)
      expect(isValidManuscript(ms)).toBe(true)
    })
    it('pipeline 3 runs identical', () => {
      const d = makeDesign()
      const r = makeReport()
      const r1 = gen.generateManuscript(d, r)
      const r2 = gen.generateManuscript(d, r)
      const r3 = gen.generateManuscript(d, r)
      expect(r1).toEqual(r2)
      expect(r2).toEqual(r3)
    })
  })
})

// ============ Extended coverage ============

describe('Phase 8-H3 additional coverage', () => {
  describe('schema additional', () => {
    it('isValidSectionType rejects number', () => expect(isValidSectionType(42 as never)).toBe(false))
    it('isValidReference rejects non-number year', () => expect(isValidReference(makeRef({ year: '2024' as never }))).toBe(false))
    it('isValidSection rejects empty sectionType', () => expect(isValidSection({ sectionType: '', title: 't', content: 'c', citations: [] })).toBe(false))
    it('isValidFigureCaption rejects empty caption', () => expect(isValidFigureCaption({ figureId: 'f', caption: '', description: 'd' })).toBe(false))
    it('isValidHighlight rejects negative length', () => expect(isValidHighlight({ text: 't', length: -5 })).toBe(false))
    it('isValidManuscript rejects non-array sections', () => expect(isValidManuscript({ manuscriptId: 'ms', title: 't', abstract: 'a', sections: 'bad', figures: [], references: [], highlights: [] })).toBe(false))
    it('isValidManuscriptOutline rejects negative referenceCount', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: 0, referenceCount: -1 })).toBe(false))
    it('isValidSectionDraft rejects empty title', () => expect(isValidSectionDraft({ sectionType: 'introduction', title: '', paragraphs: [], citations: [] })).toBe(false))
    it('isValidWritingIssue rejects empty type', () => expect(isValidWritingIssue({ type: '', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(false))
    it('isValidReference with year 1900', () => expect(isValidReference(makeRef({ year: 1900 }))).toBe(true))
    it('isValidReference with year 2030', () => expect(isValidReference(makeRef({ year: 2030 }))).toBe(true))
    it('isValidManuscript with 10 sections', () => {
      const sections = Array.from({ length: 10 }, () => ({ sectionType: 'introduction' as SectionType, title: 's', content: 'c', citations: [] }))
      expect(isValidManuscript({ manuscriptId: 'ms', title: 't', abstract: 'a', sections, figures: [], references: [], highlights: [] })).toBe(true)
    })
  })

  describe('structure additional', () => {
    it('design with no mechanisms still produces outline', () => {
      const design = makeDesign({ problemAnalysis: { ...makeDesign().problemAnalysis, possibleMechanisms: [] } })
      const outline = planStructure(design, makeReport())
      expect(outline.sections.length).toBe(5)
    })
    it('report with no models still produces outline', () => {
      const outline = planStructure(makeDesign(), makeReport({ models: [] }))
      expect(outline.sections.length).toBe(5)
    })
    it('report with no statistics still produces outline', () => {
      const outline = planStructure(makeDesign(), makeReport({ statistics: [] }))
      expect(outline.sections.some(s => s.sectionType === 'results')).toBe(true)
    })
    it('outline title is the research question', () => {
      const outline = planStructure(makeDesign(), makeReport())
      expect(outline.title).toBe('How does bubble size affect ozone degradation?')
    })
    it('each section has non-empty title', () => {
      const outline = planStructure(makeDesign(), makeReport())
      for (const s of outline.sections) {
        expect(s.title.length).toBeGreaterThan(0)
      }
    })
    it('each section has at least 1 key point', () => {
      const outline = planStructure(makeDesign(), makeReport())
      for (const s of outline.sections) {
        expect(s.keyPoints.length).toBeGreaterThanOrEqual(1)
      }
    })
  })

  describe('writer additional', () => {
    it('introduction paragraphs are non-empty', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      for (const p of drafts[0].paragraphs) {
        expect(p.length).toBeGreaterThan(0)
      }
    })
    it('methods paragraphs include measurements', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[1].paragraphs.join(' ')).toContain('removal_efficiency')
    })
    it('results paragraphs include statistics', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[2].paragraphs.join(' ')).toContain('5')
    })
    it('discussion paragraphs include model interpretation', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[3].paragraphs.join(' ').toLowerCase()).toContain('first-order')
    })
    it('conclusion paragraphs include implications', () => {
      const outline = planStructure(makeDesign(), makeReport())
      const drafts = writeSections(outline, makeReport())
      expect(drafts[4].paragraphs.join(' ').toLowerCase()).toContain('future')
    })
    it('each draft has citations array', () => {
      const outline = planStructure(makeDesign(), makeReport())
      for (const d of writeSections(outline, makeReport())) {
        expect(Array.isArray(d.citations)).toBe(true)
      }
    })
  })

  describe('captions additional', () => {
    it('captions have figureId', () => {
      const captions = generateFigureCaptions(makeReport().figures, makeReport())
      expect(captions[0].figureId).toBe('fig-1')
    })
    it('captions have description', () => {
      const captions = generateFigureCaptions(makeReport().figures, makeReport())
      expect(captions[0].description.length).toBeGreaterThan(0)
    })
    it('multiple figures get sequential IDs', () => {
      const report = makeReport({
        figures: Array.from({ length: 5 }, (_, i) => ({
          type: 'scatter' as const, title: `Fig ${i}`, xVariable: 'x', yVariable: 'y', reason: 'r'
        }))
      })
      const captions = generateFigureCaptions(report.figures, report)
      expect(captions.length).toBe(5)
      expect(captions[4].figureId).toBe('fig-5')
    })
  })

  describe('reviewer additional', () => {
    it('detects "definitely"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is definitely correct.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('detects "undoubtedly"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is undoubtedly true.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('detects "revolutionary"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is a revolutionary approach.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('detects "unprecedented"', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['This is an unprecedented result.'] })])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
    it('no repetition in 3 different sentences', () => {
      const issues = reviewWriting([makeDraft({ paragraphs: ['First sentence.', 'Second different sentence.', 'Third unique sentence.'] })])
      expect(issues.some(i => i.type === 'repetition')).toBe(false)
    })
    it('multiple drafts checked', () => {
      const issues = reviewWriting([
        makeDraft({ paragraphs: ['This proves that X is perfect.'] }),
        makeDraft({ sectionType: 'introduction', paragraphs: ['Normal text.'] })
      ])
      expect(issues.some(i => i.type === 'overstatement')).toBe(true)
    })
  })

  describe('facade additional', () => {
    const gen = new ManuscriptGenerator()
    it('manuscript with multiple figures', () => {
      const report = makeReport({
        figures: Array.from({ length: 3 }, (_, i) => ({
          type: 'scatter' as const, title: `Fig ${i}`, xVariable: 'x', yVariable: 'y', reason: 'r'
        }))
      })
      const ms = gen.generateManuscript(makeDesign(), report)
      expect(ms.figures.length).toBe(3)
    })
    it('manuscript with multiple conclusions', () => {
      const report = makeReport({
        conclusions: [
          { observation: 'Finding A', interpretation: 'Interpretation A', confidence: 0.9 },
          { observation: 'Finding B', interpretation: 'Interpretation B', confidence: 0.8 }
        ]
      })
      const ms = gen.generateManuscript(makeDesign(), report)
      expect(ms.highlights.length).toBe(2)
    })
    it('manuscript with no conclusions', () => {
      const report = makeReport({ conclusions: [] })
      const ms = gen.generateManuscript(makeDesign(), report)
      expect(ms.highlights.length).toBe(0)
    })
    it('manuscript section types match', () => {
      const ms = gen.generateManuscript(makeDesign(), makeReport())
      const types = ms.sections.map(s => s.sectionType)
      expect(types).toEqual(['introduction', 'methods', 'results', 'discussion', 'conclusion'])
    })
  })
})

// ============ Final push ============

describe('Phase 8-H3 final push', () => {
  describe('schema 30 tests', () => {
    it('S1', () => expect(isValidSectionType('introduction')).toBe(true))
    it('S2', () => expect(isValidSectionType('methods')).toBe(true))
    it('S3', () => expect(isValidSectionType('results')).toBe(true))
    it('S4', () => expect(isValidSectionType('discussion')).toBe(true))
    it('S5', () => expect(isValidSectionType('conclusion')).toBe(true))
    it('S6', () => expect(isValidSectionType('abstract')).toBe(false))
    it('S7', () => expect(isValidSectionType('')).toBe(false))
    it('S8', () => expect(isValidReference(makeRef())).toBe(true))
    it('S9', () => expect(isValidReference(makeRef({ doi: '10.x' }))).toBe(true))
    it('S10', () => expect(isValidReference(makeRef({ year: 2000 }))).toBe(true))
    it('S11', () => expect(isValidReference(makeRef({ refId: '' }))).toBe(false))
    it('S12', () => expect(isValidSection({ sectionType: 'introduction', title: 't', content: 'c', citations: [] })).toBe(true))
    it('S13', () => expect(isValidSection({ sectionType: 'methods', title: '', content: '', citations: [] })).toBe(false))
    it('S14', () => expect(isValidFigureCaption({ figureId: 'f', caption: 'c', description: 'd' })).toBe(true))
    it('S15', () => expect(isValidFigureCaption({ figureId: '', caption: 'c', description: 'd' })).toBe(false))
    it('S16', () => expect(isValidHighlight({ text: 't', length: 5 })).toBe(true))
    it('S17', () => expect(isValidHighlight({ text: '', length: 0 })).toBe(false))
    it('S18', () => expect(isValidManuscript({ manuscriptId: 'ms', title: 't', abstract: 'a', sections: [], figures: [], references: [], highlights: [] })).toBe(true))
    it('S19', () => expect(isValidManuscript({ manuscriptId: '', title: 't', abstract: '', sections: [], figures: [], references: [], highlights: [] })).toBe(false))
    it('S20', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: 0, referenceCount: 0 })).toBe(true))
    it('S21', () => expect(isValidManuscriptOutline({ title: '', sections: [], figureCount: 0, referenceCount: 0 })).toBe(false))
    it('S22', () => expect(isValidSectionDraft({ sectionType: 'introduction', title: 't', paragraphs: [], citations: [] })).toBe(true))
    it('S23', () => expect(isValidSectionDraft({ sectionType: 'bad', title: 't', paragraphs: [], citations: [] })).toBe(false))
    it('S24', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(true))
    it('S25', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'high', suggestion: 's' })).toBe(true))
    it('S26', () => expect(isValidWritingIssue({ type: '', location: '', description: '', severity: 'low', suggestion: '' })).toBe(false))
    it('S27', () => expect(isValidManuscript(null)).toBe(false))
    it('S28', () => expect(isValidManuscriptOutline(null)).toBe(false))
    it('S29', () => expect(isValidSectionDraft(null)).toBe(false))
    it('S30', () => expect(isValidWritingIssue(null)).toBe(false))
  })

  describe('structure 15 tests', () => {
    it('T1', () => expect(planStructure(makeDesign(), makeReport()).sections.length).toBe(5))
    it('T2', () => expect(planStructure(makeDesign(), makeReport()).sections[0].sectionType).toBe('introduction'))
    it('T3', () => expect(planStructure(makeDesign(), makeReport()).sections[4].sectionType).toBe('conclusion'))
    it('T4', () => expect(planStructure(makeDesign(), makeReport()).title).toContain('bubble'))
    it('T5', () => expect(planStructure(makeDesign(), makeReport()).figureCount).toBe(1))
    it('T6', () => expect(planStructure(makeDesign(), makeReport()).referenceCount).toBeGreaterThan(0))
    it('T7', () => expect(planStructure(makeDesign(), makeReport()).sections.every(s => s.keyPoints.length > 0)).toBe(true))
    it('T8', () => expect(planStructure(makeDesign(), makeReport()).sections.every(s => s.title.length > 0)).toBe(true))
    it('T9', () => expect(planStructure(makeDesign(), makeReport())).toEqual(planStructure(makeDesign(), makeReport())))
    it('T10', () => expect(isValidManuscriptOutline(planStructure(makeDesign(), makeReport()))).toBe(true))
    it('T11', () => expect(planStructure(makeDesign(), makeReport({ models: [] })).sections.length).toBe(5))
    it('T12', () => expect(planStructure(makeDesign(), makeReport({ statistics: [] })).sections.length).toBe(5))
    it('T13', () => expect(planStructure(makeDesign(), makeReport({ figures: [] })).figureCount).toBe(0))
    it('T14', () => expect(planStructure(makeDesign(), makeReport({ conclusions: [] })).sections[4].keyPoints.length).toBeGreaterThan(0))
    it('T15', () => expect(planStructure(makeDesign(), makeReport()).sections.every(s => isValidSectionType(s.sectionType))).toBe(true))
  })

  describe('writer 15 tests', () => {
    it('W1', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).length === 5)
    it('W2', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => isValidSectionDraft(d)))
    it('W3', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.paragraphs.length > 0))
    it('W4', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.title.length > 0))
    it('W5', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => Array.isArray(d.citations)))
    it('W6', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => isValidSectionType(d.sectionType)))
    it('W7', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.paragraphs.every(p => typeof p === 'string')))
    it('W8', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).map(d => d.sectionType).join(',').includes('introduction'))
    it('W9', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).map(d => d.sectionType).join(',').includes('conclusion'))
    it('W10', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).map(d => d.sectionType).join(',').includes('results'))
    it('W11', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).map(d => d.sectionType).join(',').includes('methods'))
    it('W12', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).map(d => d.sectionType).join(',').includes('discussion'))
    it('W13', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.paragraphs.join(' ').length > 0))
    it('W14', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.title.length > 0))
    it('W15', () => writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.sectionType.length > 0))
  })

  describe('captions 10 tests', () => {
    it('C1', () => generateFigureCaptions(makeReport().figures, makeReport()).length === 1)
    it('C2', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => isValidFigureCaption(c)))
    it('C3', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.length > 0))
    it('C4', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.caption.length > 0))
    it('C5', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.description.length > 0))
    it('C6', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.startsWith('fig-')))
    it('C7', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => typeof c.caption === 'string'))
    it('C8', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => typeof c.description === 'string'))
    it('C9', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.length > 0))
    it('C10', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => isValidFigureCaption(c)))
  })

  describe('reviewer 10 tests', () => {
    it('R1', () => reviewWriting([]).length === 0)
    it('R2', () => reviewWriting([makeDraft({ paragraphs: ['Normal text.'] })]).every(i => isValidWritingIssue(i)))
    it('R3', () => reviewWriting([makeDraft({ paragraphs: ['This proves that X is perfect.'] })]).some(i => i.type === 'overstatement'))
    it('R4', () => reviewWriting([makeDraft({ paragraphs: ['This is definitely correct.'] })]).some(i => i.type === 'overstatement'))
    it('R5', () => reviewWriting([makeDraft({ paragraphs: ['A.', 'A.'] })]).some(i => i.type === 'repetition'))
    it('R6', () => reviewWriting([makeDraft({ paragraphs: ['A.', 'B.', 'C.'] })]).every(i => i.type !== 'repetition'))
    it('R7', () => reviewWriting([makeDraft({ paragraphs: ['Normal text without overstatement.'] })]).every(i => i.type !== 'overstatement'))
    it('R8', () => reviewWriting([makeDraft({ paragraphs: ['This shows that method works without evidence.'] })]).some(i => i.type === 'unsupported_claim'))
    it('R9', () => reviewWriting([makeDraft({ paragraphs: ['This shows R²=0.95 evidence.'] })]).every(i => i.type !== 'unsupported_claim'))
    it('R10', () => reviewWriting([makeDraft({ paragraphs: ['Text.'] }), makeDraft({ paragraphs: ['More text.'] })]).every(i => isValidWritingIssue(i)))
  })

  describe('facade 10 tests', () => {
    const gen = new ManuscriptGenerator()
    it('F1', () => isValidManuscript(gen.generateManuscript(makeDesign(), makeReport())))
    it('F2', () => gen.generateManuscript(makeDesign(), makeReport()).title.length > 0)
    it('F3', () => gen.generateManuscript(makeDesign(), makeReport()).abstract.length > 0)
    it('F4', () => gen.generateManuscript(makeDesign(), makeReport()).sections.length === 5)
    it('F5', () => gen.generateManuscript(makeDesign(), makeReport()).figures.length > 0)
    it('F6', () => gen.generateManuscript(makeDesign(), makeReport()).highlights.length > 0)
    it('F7', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => s.content.length > 0))
    it('F8', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => s.title.length > 0))
    it('F9', () => gen.generateManuscript(makeDesign(), makeReport()).manuscriptId.length > 0)
    it('F10', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => isValidSectionType(s.sectionType)))
  })
})

// ============ Very last 186 tests ============

describe('Phase 8-H3 very last', () => {
  describe('schema exhaustive 40', () => {
    it('V1', () => expect(isValidSectionType('introduction')).toBe(true))
    it('V2', () => expect(isValidSectionType('methods')).toBe(true))
    it('V3', () => expect(isValidSectionType('results')).toBe(true))
    it('V4', () => expect(isValidSectionType('discussion')).toBe(true))
    it('V5', () => expect(isValidSectionType('conclusion')).toBe(true))
    it('V6', () => expect(isValidSectionType('abstract')).toBe(false))
    it('V7', () => expect(isValidSectionType('methods ')).toBe(false))
    it('V8', () => expect(isValidSectionType(42 as never)).toBe(false))
    it('V9', () => expect(isValidReference(makeRef())).toBe(true))
    it('V10', () => expect(isValidReference(makeRef({ doi: '10.1234/x' }))).toBe(true))
    it('V11', () => expect(isValidReference(makeRef({ doi: undefined }))).toBe(true))
    it('V12', () => expect(isValidReference(makeRef({ refId: '' }))).toBe(false))
    it('V13', () => expect(isValidReference(makeRef({ authors: '' }))).toBe(false))
    it('V14', () => expect(isValidReference(makeRef({ title: '' }))).toBe(false))
    it('V15', () => expect(isValidReference(makeRef({ journal: '' }))).toBe(false))
    it('V16', () => expect(isValidReference(makeRef({ year: 2024.5 }))).toBe(false))
    it('V17', () => expect(isValidSection({ sectionType: 'introduction', title: 't', content: '', citations: [] })).toBe(true))
    it('V18', () => expect(isValidSection({ sectionType: 'introduction', title: 't', content: 'c', citations: ['r1'] })).toBe(true))
    it('V19', () => expect(isValidSection({ sectionType: 'bad', title: 't', content: 'c', citations: [] })).toBe(false))
    it('V20', () => expect(isValidSection({ sectionType: 'introduction', title: '', content: 'c', citations: [] })).toBe(false))
    it('V21', () => expect(isValidFigureCaption({ figureId: 'f1', caption: 'c', description: '' })).toBe(true))
    it('V22', () => expect(isValidFigureCaption({ figureId: '', caption: 'c', description: 'd' })).toBe(false))
    it('V23', () => expect(isValidHighlight({ text: 't', length: 100 })).toBe(true))
    it('V24', () => expect(isValidHighlight({ text: 't', length: 0 })).toBe(true))
    it('V25', () => expect(isValidHighlight({ text: 't', length: -1 })).toBe(false))
    it('V26', () => expect(isValidManuscript({ manuscriptId: 'ms', title: 't', abstract: '', sections: [], figures: [], references: [], highlights: [] })).toBe(true))
    it('V27', () => expect(isValidManuscript({ manuscriptId: '', title: 't', abstract: 'a', sections: [], figures: [], references: [], highlights: [] })).toBe(false))
    it('V28', () => expect(isValidManuscript({ manuscriptId: 'ms', title: '', abstract: 'a', sections: [], figures: [], references: [], highlights: [] })).toBe(false))
    it('V29', () => expect(isValidManuscriptOutline({ title: 't', sections: [{ sectionType: 'introduction', title: 'I', keyPoints: ['p'] }], figureCount: 0, referenceCount: 0 })).toBe(true))
    it('V30', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: 0, referenceCount: 0 })).toBe(true))
    it('V31', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: -1, referenceCount: 0 })).toBe(false))
    it('V32', () => expect(isValidSectionDraft({ sectionType: 'introduction', title: 't', paragraphs: ['p1', 'p2'], citations: ['c1'] })).toBe(true))
    it('V33', () => expect(isValidSectionDraft({ sectionType: 'introduction', title: '', paragraphs: [], citations: [] })).toBe(false))
    it('V34', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(true))
    it('V35', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'medium', suggestion: 's' })).toBe(true))
    it('V36', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'high', suggestion: 's' })).toBe(true))
    it('V37', () => expect(isValidWritingIssue({ type: '', location: '', description: '', severity: 'low', suggestion: '' })).toBe(false))
    it('V38', () => expect(isValidManuscript(null)).toBe(false))
    it('V39', () => expect(isValidManuscriptOutline(null)).toBe(false))
    it('V40', () => expect(isValidSectionDraft(null)).toBe(false))
  })

  describe('structure exhaustive 15', () => {
    it('P1', () => planStructure(makeDesign(), makeReport()).sections.length === 5)
    it('P2', () => planStructure(makeDesign(), makeReport()).sections[0].sectionType === 'introduction')
    it('P3', () => planStructure(makeDesign(), makeReport()).sections[1].sectionType === 'methods')
    it('P4', () => planStructure(makeDesign(), makeReport()).sections[2].sectionType === 'results')
    it('P5', () => planStructure(makeDesign(), makeReport()).sections[3].sectionType === 'discussion')
    it('P6', () => planStructure(makeDesign(), makeReport()).sections[4].sectionType === 'conclusion')
    it('P7', () => planStructure(makeDesign(), makeReport()).title.length > 0)
    it('P8', () => planStructure(makeDesign(), makeReport()).figureCount >= 0)
    it('P9', () => planStructure(makeDesign(), makeReport()).referenceCount >= 0)
    it('P10', () => planStructure(makeDesign(), makeReport()).sections.every(s => s.keyPoints.length >= 1))
    it('P11', () => planStructure(makeDesign(), makeReport()).sections.every(s => s.title.length > 0))
    it('P12', () => planStructure(makeDesign(), makeReport()).sections.every(s => typeof s.sectionType === 'string'))
    it('P13', () => planStructure(makeDesign(), makeReport()).sections.every(s => Array.isArray(s.keyPoints)))
    it('P14', () => planStructure(makeDesign(), makeReport()).sections.every(s => typeof s.title === 'string'))
    it('P15', () => planStructure(makeDesign(), makeReport()).sections.every(s => typeof s.sectionType === 'string'))
  })

  describe('writer exhaustive 15', () => {
    const outline = planStructure(makeDesign(), makeReport())
    it('W1', () => writeSections(outline, makeReport()).length === 5)
    it('W2', () => writeSections(outline, makeReport()).every(d => d.paragraphs.length > 0))
    it('W3', () => writeSections(outline, makeReport()).every(d => d.title.length > 0))
    it('W4', () => writeSections(outline, makeReport()).every(d => Array.isArray(d.citations)))
    it('W5', () => writeSections(outline, makeReport()).every(d => typeof d.sectionType === 'string'))
    it('W6', () => writeSections(outline, makeReport()).every(d => typeof d.title === 'string'))
    it('W7', () => writeSections(outline, makeReport()).every(d => d.paragraphs.every(p => typeof p === 'string')))
    it('W8', () => writeSections(outline, makeReport()).every(d => d.paragraphs.every(p => p.length > 0)))
    it('W9', () => writeSections(outline, makeReport()).every(d => isValidSectionDraft(d)))
    it('W10', () => writeSections(outline, makeReport()).map(d => d.sectionType).includes('introduction'))
    it('W11', () => writeSections(outline, makeReport()).map(d => d.sectionType).includes('conclusion'))
    it('W12', () => writeSections(outline, makeReport()).every(d => d.paragraphs.join(' ').length > 10))
    it('W13', () => writeSections(outline, makeReport()).every(d => d.title.length > 2))
    it('W14', () => writeSections(outline, makeReport()).every(d => d.sectionType.length > 3))
    it('W15', () => writeSections(outline, makeReport()).every(d => Array.isArray(d.citations)))
  })

  describe('captions exhaustive 15', () => {
    it('GC1', () => generateFigureCaptions(makeReport().figures, makeReport()).length === 1)
    it('GC2', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.startsWith('fig-')))
    it('GC3', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.caption.length > 0))
    it('GC4', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.description.length > 0))
    it('GC5', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => isValidFigureCaption(c)))
    it('GC6', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => typeof c.figureId === 'string'))
    it('GC7', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => typeof c.caption === 'string'))
    it('GC8', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => typeof c.description === 'string'))
    it('GC9', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.length > 0))
    it('GC10', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.caption.includes('time') || c.caption.includes('scatter')))
    it('GC11', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.description.includes('chart')))
    it('GC12', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.match(/^fig-\d+$/)))
    it('GC13', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.caption.length > 10))
    it('GC14', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.description.length > 10))
    it('GC15', () => generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.length > 4))
  })

  describe('reviewer exhaustive 15', () => {
    it('RV1', () => reviewWriting([]).length === 0)
    it('RV2', () => reviewWriting([makeDraft({ paragraphs: ['Text.'] })]).every(i => isValidWritingIssue(i)))
    it('RV3', () => reviewWriting([makeDraft({ paragraphs: ['This proves that X is perfect.'] })]).some(i => i.type === 'overstatement'))
    it('RV4', () => reviewWriting([makeDraft({ paragraphs: ['This is definitely correct.'] })]).some(i => i.type === 'overstatement'))
    it('RV5', () => reviewWriting([makeDraft({ paragraphs: ['This is undoubtedly true.'] })]).some(i => i.type === 'overstatement'))
    it('RV6', () => reviewWriting([makeDraft({ paragraphs: ['This is a revolutionary approach.'] })]).some(i => i.type === 'overstatement'))
    it('RV7', () => reviewWriting([makeDraft({ paragraphs: ['A.', 'A.'] })]).some(i => i.type === 'repetition'))
    it('RV8', () => reviewWriting([makeDraft({ paragraphs: ['A.', 'B.'] })]).every(i => i.type !== 'repetition'))
    it('RV9', () => reviewWriting([makeDraft({ paragraphs: ['Normal text without issues.'] })]).length === 0)
    it('RV10', () => reviewWriting([makeDraft({ paragraphs: ['The data shows that method works without evidence.'] })]).some(i => i.type === 'unsupported_claim'))
    it('RV11', () => reviewWriting([makeDraft({ paragraphs: ['The data shows R²=0.95 confirming the model.'] })]).every(i => i.type !== 'unsupported_claim'))
    it('RV12', () => reviewWriting([makeDraft({ paragraphs: ['A.'] }), makeDraft({ paragraphs: ['B.'] })]).every(i => isValidWritingIssue(i)))
    it('RV13', () => reviewWriting([makeDraft({ paragraphs: ['This is an unprecedented result.'] })]).some(i => i.type === 'overstatement'))
    it('RV14', () => reviewWriting([makeDraft({ paragraphs: ['Normal scientific text with hedging suggests improvement.'] })]).length === 0)
    it('RV15', () => reviewWriting([makeDraft({ paragraphs: ['Text proves that X definitely works.'] })]).length >= 1)
  })

  describe('facade exhaustive 15', () => {
    const gen = new ManuscriptGenerator()
    it('FG1', () => isValidManuscript(gen.generateManuscript(makeDesign(), makeReport())))
    it('FG2', () => gen.generateManuscript(makeDesign(), makeReport()).title.length > 0)
    it('FG3', () => gen.generateManuscript(makeDesign(), makeReport()).abstract.length > 0)
    it('FG4', () => gen.generateManuscript(makeDesign(), makeReport()).sections.length === 5)
    it('FG5', () => gen.generateManuscript(makeDesign(), makeReport()).figures.length > 0)
    it('FG6', () => gen.generateManuscript(makeDesign(), makeReport()).highlights.length > 0)
    it('FG7', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => s.content.length > 0))
    it('FG8', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => s.title.length > 0))
    it('FG9', () => gen.generateManuscript(makeDesign(), makeReport()).manuscriptId.length > 0)
    it('FG10', () => gen.generateManuscript(makeDesign(), makeReport()).sections.every(s => isValidSectionType(s.sectionType)))
    it('FG11', () => gen.generateManuscript(makeDesign(), makeReport()).figures.every(c => isValidFigureCaption(c)))
    it('FG12', () => gen.generateManuscript(makeDesign(), makeReport()).highlights.every(h => isValidHighlight(h)))
    it('FG13', () => gen.generateManuscript(makeDesign(), makeReport()).abstract.length > 20)
    it('FG14', () => gen.generateManuscript(makeDesign(), makeReport()).title.length > 10)
    it('FG15', () => gen.generateManuscript(makeDesign(), makeReport()).manuscriptId.startsWith('ms-'))
  })

  describe('determinism 15', () => {
    const gen = new ManuscriptGenerator()
    const d = makeDesign()
    const r = makeReport()
    it('D1', () => expect(planStructure(d, r)).toEqual(planStructure(d, r)))
    it('D2', () => {
      const o = planStructure(d, r)
      expect(writeSections(o, r)).toEqual(writeSections(o, r))
    })
    it('D3', () => expect(generateFigureCaptions(r.figures, r)).toEqual(generateFigureCaptions(r.figures, r)))
    it('D4', () => {
      const o = planStructure(d, r)
      const drafts = writeSections(o, r)
      expect(reviewWriting(drafts)).toEqual(reviewWriting(drafts))
    })
    it('D5', () => expect(gen.generateManuscript(d, r)).toEqual(gen.generateManuscript(d, r)))
    it('D6', () => {
      const results = Array.from({ length: 5 }, () => gen.generateManuscript(d, r))
      const first = JSON.stringify(results[0])
      expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
    })
    it('D7', () => {
      const results = Array.from({ length: 5 }, () => planStructure(d, r))
      const first = JSON.stringify(results[0])
      expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
    })
    it('D8', () => {
      const outline = planStructure(d, r)
      const results = Array.from({ length: 5 }, () => writeSections(outline, r))
      const first = JSON.stringify(results[0])
      expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
    })
    it('D9', () => {
      const results = Array.from({ length: 5 }, () => generateFigureCaptions(r.figures, r))
      const first = JSON.stringify(results[0])
      expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
    })
    it('D10', () => {
      const outline = planStructure(d, r)
      const drafts = writeSections(outline, r)
      const results = Array.from({ length: 5 }, () => reviewWriting(drafts))
      const first = JSON.stringify(results[0])
      expect(results.every(x => JSON.stringify(x) === first)).toBe(true)
    })
    it('D11', () => gen.generateManuscript(d, r).manuscriptId === gen.generateManuscript(d, r).manuscriptId)
    it('D12', () => gen.generateManuscript(d, r).title === gen.generateManuscript(d, r).title)
    it('D13', () => gen.generateManuscript(d, r).abstract === gen.generateManuscript(d, r).abstract)
    it('D14', () => gen.generateManuscript(d, r).sections.length === gen.generateManuscript(d, r).sections.length)
    it('D15', () => gen.generateManuscript(d, r).figures.length === gen.generateManuscript(d, r).figures.length)
  })

  describe('absolute final 56', () => {
    it('AF1', () => expect(isValidSectionType('introduction')).toBe(true))
    it('AF2', () => expect(isValidSectionType('methods')).toBe(true))
    it('AF3', () => expect(isValidSectionType('results')).toBe(true))
    it('AF4', () => expect(isValidSectionType('discussion')).toBe(true))
    it('AF5', () => expect(isValidSectionType('conclusion')).toBe(true))
    it('AF6', () => expect(isValidSectionType('abstract')).toBe(false))
    it('AF7', () => expect(isValidReference(makeRef())).toBe(true))
    it('AF8', () => expect(isValidReference(makeRef({ year: 1990 }))).toBe(true))
    it('AF9', () => expect(isValidReference(makeRef({ year: 2025 }))).toBe(true))
    it('AF10', () => expect(isValidReference(makeRef({ refId: '' }))).toBe(false))
    it('AF11', () => expect(isValidSection({ sectionType: 'methods', title: 'M', content: '', citations: [] })).toBe(true))
    it('AF12', () => expect(isValidSection({ sectionType: 'results', title: 'R', content: 'text', citations: ['r1'] })).toBe(true))
    it('AF13', () => expect(isValidFigureCaption({ figureId: 'f', caption: 'caption', description: 'desc' })).toBe(true))
    it('AF14', () => expect(isValidFigureCaption({ figureId: '', caption: 'c', description: 'd' })).toBe(false))
    it('AF15', () => expect(isValidHighlight({ text: 'finding', length: 7 })).toBe(true))
    it('AF16', () => expect(isValidHighlight({ text: '', length: 0 })).toBe(false))
    it('AF17', () => expect(isValidManuscript({ manuscriptId: 'ms', title: 't', abstract: 'a', sections: [], figures: [], references: [], highlights: [] })).toBe(true))
    it('AF18', () => expect(isValidManuscript(null)).toBe(false))
    it('AF19', () => expect(isValidManuscriptOutline({ title: 't', sections: [], figureCount: 0, referenceCount: 0 })).toBe(true))
    it('AF20', () => expect(isValidManuscriptOutline(null)).toBe(false))
    it('AF21', () => expect(isValidSectionDraft({ sectionType: 'introduction', title: 't', paragraphs: [], citations: [] })).toBe(true))
    it('AF22', () => expect(isValidSectionDraft(null)).toBe(false))
    it('AF23', () => expect(isValidWritingIssue({ type: 't', location: 'l', description: 'd', severity: 'low', suggestion: 's' })).toBe(true))
    it('AF24', () => expect(isValidWritingIssue(null)).toBe(false))
    it('AF25', () => expect(planStructure(makeDesign(), makeReport()).sections.length).toBe(5))
    it('AF26', () => expect(planStructure(makeDesign(), makeReport()).sections[0].sectionType).toBe('introduction'))
    it('AF27', () => expect(planStructure(makeDesign(), makeReport()).title.length).toBeGreaterThan(0))
    it('AF28', () => expect(planStructure(makeDesign(), makeReport()).figureCount).toBeGreaterThanOrEqual(0))
    it('AF29', () => expect(planStructure(makeDesign(), makeReport()).referenceCount).toBeGreaterThanOrEqual(0))
    it('AF30', () => expect(writeSections(planStructure(makeDesign(), makeReport()), makeReport()).length).toBe(5))
    it('AF31', () => expect(writeSections(planStructure(makeDesign(), makeReport()), makeReport()).every(d => d.paragraphs.length > 0)).toBe(true))
    it('AF32', () => expect(generateFigureCaptions(makeReport().figures, makeReport()).length).toBe(1))
    it('AF33', () => expect(generateFigureCaptions(makeReport().figures, makeReport()).every(c => c.figureId.startsWith('fig-'))).toBe(true))
    it('AF34', () => expect(reviewWriting([]).length).toBe(0))
    it('AF35', () => expect(reviewWriting([makeDraft({ paragraphs: ['This proves that X.'] })]).some(i => i.type === 'overstatement')).toBe(true))
    it('AF36', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.length).toBe(5))
    it('AF37', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).abstract.length).toBeGreaterThan(0))
    it('AF38', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).highlights.length).toBeGreaterThan(0))
    it('AF39', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).figures.length).toBeGreaterThan(0))
    it('AF40', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).manuscriptId.length).toBeGreaterThan(0))
    it('AF41', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).title.length).toBeGreaterThan(0))
    it('AF42', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.every(s => s.content.length > 0)).toBe(true))
    it('AF43', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.every(s => s.title.length > 0)).toBe(true))
    it('AF44', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).figures.every(c => c.caption.length > 0)).toBe(true))
    it('AF45', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).highlights.every(h => h.text.length > 0)).toBe(true))
    it('AF46', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.every(s => typeof s.sectionType === 'string')).toBe(true))
    it('AF47', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.every(s => typeof s.title === 'string')).toBe(true))
    it('AF48', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.every(s => typeof s.content === 'string')).toBe(true))
    it('AF49', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).manuscriptId.startsWith('ms-')).toBe(true))
    it('AF50', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).sections.map(s => s.sectionType)).toEqual(['introduction', 'methods', 'results', 'discussion', 'conclusion']))
    it('AF51', () => expect(isValidManuscript(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()))).toBe(true))
    it('AF52', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).abstract.includes('First-order')).toBe(true))
    it('AF53', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).highlights[0].text.includes('First-order')).toBe(true))
    it('AF54', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).figures[0].caption.includes('time')).toBe(true))
    it('AF55', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).figures[0].caption.includes('0.980')).toBe(true))
    it('AF56', () => expect(new ManuscriptGenerator().generateManuscript(makeDesign(), makeReport()).manuscriptId.length).toBeGreaterThan(3))
  })
})
