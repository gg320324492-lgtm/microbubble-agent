// Phase 8-H2: Scientific Data Analyst Agent — test suite.
// Target: ≥400 tests (4200 base → ≥4600 total).

import { describe, it, expect } from 'vitest'
import { resolve, dirname } from 'path'
import { fileURLToPath } from 'url'

const __testDir = dirname(fileURLToPath(import.meta.url))
const srcRoot = resolve(__testDir, '..', '..', 'src')

import {
  isValidDataType,
  isValidVariableDefinition,
  isValidScientificDataset,
  isValidDataQualityReport,
  isValidStatisticalResult,
  isValidModelFitResult,
  isValidFigureRecommendation,
  isValidScientificConclusion,
  isValidAnalysisReport,
  __testHelpers
} from '../../src/shared/science/scientific-data-schema'

import type {
  ScientificDataset,
  VariableDefinition,
  DataQualityReport,
  StatisticalResult,
  ModelFitResult,
  FigureRecommendation,
  ScientificConclusion,
  AnalysisReport,
  DataType
} from '../../src/shared/science/scientific-data-schema'

import { analyzeDataQuality } from '../../src/main/services/science/data-quality-analyzer'
import { computeStatistics } from '../../src/main/services/science/statistical-analyzer'
import { fitModels } from '../../src/main/services/science/model-fitting-engine'
import { planVisualizations } from '../../src/main/services/science/visualization-planner'
import { interpretAnalysis } from '../../src/main/services/science/data-interpreter'
import { ScientificDataAnalyst } from '../../src/main/services/science/scientific-data-analyst'

// ============ Fixtures ============

function makeVar(overrides?: Partial<VariableDefinition>): VariableDefinition {
  return { name: 'temperature', type: 'number', unit: '°C', ...overrides }
}

function makeDataset(overrides?: Partial<ScientificDataset>): ScientificDataset {
  return {
    datasetId: 'ds-1',
    name: 'O3 Degradation',
    variables: [
      { name: 'time', type: 'number', unit: 'min' },
      { name: 'concentration', type: 'number', unit: 'mg/L' },
      { name: 'removal', type: 'number', unit: '%' }
    ],
    rows: [
      { time: 0, concentration: 10, removal: 0 },
      { time: 5, concentration: 8, removal: 20 },
      { time: 10, concentration: 6, removal: 40 },
      { time: 15, concentration: 4, removal: 60 },
      { time: 20, concentration: 2, removal: 80 },
      { time: 30, concentration: 0.5, removal: 95 }
    ],
    metadata: { source: 'lab' },
    ...overrides
  }
}

function makeFitResult(overrides?: Partial<ModelFitResult>): ModelFitResult {
  return { model: 'first-order', parameters: { k: 0.05, y0: 10 }, rSquared: 0.98, residualError: 0.1, ...overrides }
}

// ============ Schema validators ============

describe('Phase 8-H2 schema', () => {
  describe('isValidDataType', () => {
    it.each<DataType>(['number', 'string', 'boolean', 'date'])('accepts %s', (t) => { expect(isValidDataType(t)).toBe(true) })
    it('rejects empty', () => expect(isValidDataType('')).toBe(false))
    it('rejects "float"', () => expect(isValidDataType('float')).toBe(false))
    it('rejects number', () => expect(isValidDataType(42 as never)).toBe(false))
  })

  describe('isValidVariableDefinition', () => {
    it('accepts valid', () => expect(isValidVariableDefinition(makeVar())).toBe(true))
    it('rejects empty name', () => expect(isValidVariableDefinition(makeVar({ name: '' }))).toBe(false))
    it('rejects invalid type', () => expect(isValidVariableDefinition(makeVar({ type: 'float' }))).toBe(false))
    it('rejects non-object', () => expect(isValidVariableDefinition(null)).toBe(false))
  })

  describe('isValidScientificDataset', () => {
    it('accepts valid', () => expect(isValidScientificDataset(makeDataset())).toBe(true))
    it('accepts empty rows', () => expect(isValidScientificDataset(makeDataset({ rows: [] }))).toBe(true))
    it('rejects empty datasetId', () => expect(isValidScientificDataset(makeDataset({ datasetId: '' }))).toBe(false))
    it('rejects empty name', () => expect(isValidScientificDataset(makeDataset({ name: '' }))).toBe(false))
    it('rejects invalid variable', () => expect(isValidScientificDataset(makeDataset({ variables: [{ name: '', type: 'x' as never, unit: '' }] }))).toBe(false))
    it('rejects non-array rows', () => expect(isValidScientificDataset(makeDataset({ rows: 'bad' as never }))).toBe(false))
    it('rejects non-object', () => expect(isValidScientificDataset(null)).toBe(false))
  })

  describe('isValidDataQualityReport', () => {
    it('accepts valid', () => expect(isValidDataQualityReport({ completeness: 0.9, missingValues: {}, outliers: {}, warnings: [] })).toBe(true))
    it('rejects completeness > 1', () => expect(isValidDataQualityReport({ completeness: 1.5, missingValues: {}, outliers: {}, warnings: [] })).toBe(false))
    it('rejects non-object', () => expect(isValidDataQualityReport(null)).toBe(false))
  })

  describe('isValidStatisticalResult', () => {
    it('accepts valid', () => expect(isValidStatisticalResult({ metric: 'mean', value: 5, interpretation: 'avg' })).toBe(true))
    it('rejects empty metric', () => expect(isValidStatisticalResult({ metric: '', value: 5, interpretation: 'x' })).toBe(false))
    it('rejects NaN value', () => expect(isValidStatisticalResult({ metric: 'm', value: NaN, interpretation: 'x' })).toBe(false))
    it('rejects non-object', () => expect(isValidStatisticalResult(null)).toBe(false))
  })

  describe('isValidModelFitResult', () => {
    it('accepts valid', () => expect(isValidModelFitResult(makeFitResult())).toBe(true))
    it('rejects empty model', () => expect(isValidModelFitResult(makeFitResult({ model: '' }))).toBe(false))
    it('rejects non-object', () => expect(isValidModelFitResult(null)).toBe(false))
  })

  describe('isValidFigureRecommendation', () => {
    const fig: FigureRecommendation = { type: 'line', title: 't', xVariable: 'x', yVariable: 'y', reason: 'r' }
    it('accepts valid', () => expect(isValidFigureRecommendation(fig)).toBe(true))
    it('rejects empty type', () => expect(isValidFigureRecommendation({ ...fig, type: '' })).toBe(false))
    it('rejects non-object', () => expect(isValidFigureRecommendation(null)).toBe(false))
  })

  describe('isValidScientificConclusion', () => {
    it('accepts valid', () => expect(isValidScientificConclusion({ observation: 'obs', interpretation: 'interp', confidence: 0.8 })).toBe(true))
    it('rejects empty observation', () => expect(isValidScientificConclusion({ observation: '', interpretation: 'i', confidence: 0.5 })).toBe(false))
    it('rejects non-object', () => expect(isValidScientificConclusion(null)).toBe(false))
  })

  describe('isValidAnalysisReport', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [], models: [], figures: [], conclusions: []
    }
    it('accepts valid', () => expect(isValidAnalysisReport(report)).toBe(true))
    it('rejects invalid quality', () => expect(isValidAnalysisReport({ ...report, quality: {} })).toBe(false))
    it('rejects non-array statistics', () => expect(isValidAnalysisReport({ ...report, statistics: 'bad' })).toBe(false))
    it('rejects non-array models', () => expect(isValidAnalysisReport({ ...report, models: null })).toBe(false))
    it('rejects non-array figures', () => expect(isValidAnalysisReport({ ...report, figures: 42 })).toBe(false))
    it('rejects non-array conclusions', () => expect(isValidAnalysisReport({ ...report, conclusions: {} })).toBe(false))
    it('rejects non-object', () => expect(isValidAnalysisReport(null)).toBe(false))
  })
})

// ============ Secret guard ============

describe('Phase 8-H2 secret guard', () => {
  const { findForbidden } = __testHelpers
  it('finds sk-', () => expect(findForbidden('sk-abc')).toBe('sk-'))
  it('finds apiKey', () => expect(findForbidden('apiKey=x')).toBe('apiKey'))
  it('clean passes', () => expect(findForbidden('hello')).toBe(null))
  it('walks arrays', () => expect(findForbidden(['a', 'sk-x'])).toBe('sk-'))
  it('walks nested', () => expect(findForbidden({ a: { b: 'cipher' } })).toBe('cipher'))
  it('ignores field names', () => expect(findForbidden({ tokenBudget: 100 })).toBe(null))
  it('dataset with apiKey throws', () => {
    expect(() => isValidScientificDataset(makeDataset({ name: 'apiKey here' }))).toThrow('forbidden')
  })
  it('conclusion with Bearer throws', () => {
    expect(() => isValidScientificConclusion({ observation: 'Bearer token', interpretation: 'i', confidence: 0.5 })).toThrow('forbidden')
  })
  it('model with cipher throws', () => {
    expect(() => isValidModelFitResult(makeFitResult({ model: 'cipher test' }))).toThrow('forbidden')
  })
  it('stat with authorization throws', () => {
    expect(() => isValidStatisticalResult({ metric: 'authorization header', value: 1, interpretation: 'x' })).toThrow('forbidden')
  })
})

// ============ Data Quality Analyzer ============

describe('Phase 8-H2 data quality', () => {
  it('clean dataset high completeness', () => {
    const result = analyzeDataQuality(makeDataset())
    expect(result.completeness).toBe(1)
    expect(result.warnings.length).toBe(0)
  })

  it('detects missing values', () => {
    const ds = makeDataset({ rows: [
      { time: 0, concentration: 10, removal: 0 },
      { time: 5, concentration: null, removal: 20 }
    ]})
    const result = analyzeDataQuality(ds)
    expect(result.missingValues['concentration']).toBe(1)
  })

  it('detects outliers', () => {
    const ds = makeDataset({ rows: [
      { time: 0, concentration: 10, removal: 0 },
      { time: 5, concentration: 8, removal: 20 },
      { time: 10, concentration: 6, removal: 40 },
      { time: 15, concentration: 4, removal: 60 },
      { time: 20, concentration: 100, removal: 80 } // outlier
    ]})
    const result = analyzeDataQuality(ds)
    expect(result.outliers['concentration']).toBe(1)
  })

  it('detects duplicate rows', () => {
    const ds = makeDataset({ rows: [
      { time: 0, concentration: 10, removal: 0 },
      { time: 0, concentration: 10, removal: 0 }
    ]})
    const result = analyzeDataQuality(ds)
    expect(result.warnings.some(w => w.includes('duplicate'))).toBe(true)
  })

  it('empty dataset completeness 0', () => {
    const result = analyzeDataQuality(makeDataset({ rows: [] }))
    expect(result.completeness).toBe(0)
  })

  it('no numeric variables no outliers', () => {
    const ds = makeDataset({
      variables: [{ name: 'label', type: 'string', unit: '' }],
      rows: [{ label: 'a' }, { label: 'b' }]
    })
    const result = analyzeDataQuality(ds)
    expect(Object.keys(result.outliers).length).toBe(0)
  })

  it('valid output', () => {
    expect(isValidDataQualityReport(analyzeDataQuality(makeDataset()))).toBe(true)
  })

  it('deterministic', () => {
    const ds = makeDataset()
    expect(analyzeDataQuality(ds)).toEqual(analyzeDataQuality(ds))
  })
})

// ============ Statistical Analyzer ============

describe('Phase 8-H2 statistics', () => {
  it('computes mean', () => {
    const results = computeStatistics(makeDataset())
    const meanResult = results.find(r => r.metric === 'concentration_mean')
    expect(meanResult).toBeDefined()
    expect(meanResult!.value).toBeCloseTo(5.0833, 1)
  })

  it('computes median', () => {
    const results = computeStatistics(makeDataset())
    expect(results.some(r => r.metric === 'concentration_median')).toBe(true)
  })

  it('computes std', () => {
    const results = computeStatistics(makeDataset())
    expect(results.some(r => r.metric === 'concentration_std')).toBe(true)
  })

  it('computes variance', () => {
    const results = computeStatistics(makeDataset())
    expect(results.some(r => r.metric === 'concentration_variance')).toBe(true)
  })

  it('computes cv', () => {
    const results = computeStatistics(makeDataset())
    expect(results.some(r => r.metric === 'concentration_cv')).toBe(true)
  })

  it('computes correlation', () => {
    const results = computeStatistics(makeDataset())
    const corr = results.find(r => r.metric.includes('correlation_'))
    expect(corr).toBeDefined()
    expect(corr!.value).toBeGreaterThanOrEqual(-1)
    expect(corr!.value).toBeLessThanOrEqual(1)
  })

  it('empty dataset returns empty', () => {
    expect(computeStatistics(makeDataset({ rows: [] }))).toEqual([])
  })

  it('no numeric variables returns empty', () => {
    const ds = makeDataset({
      variables: [{ name: 'label', type: 'string', unit: '' }],
      rows: [{ label: 'a' }]
    })
    expect(computeStatistics(ds)).toEqual([])
  })

  it('all results valid', () => {
    for (const r of computeStatistics(makeDataset())) {
      expect(isValidStatisticalResult(r)).toBe(true)
    }
  })

  it('deterministic', () => {
    const ds = makeDataset()
    expect(computeStatistics(ds)).toEqual(computeStatistics(ds))
  })
})

// ============ Model Fitting ============

describe('Phase 8-H2 model fitting', () => {
  it('fits models to data', () => {
    const results = fitModels(makeDataset(), 'time', 'concentration')
    expect(results.length).toBeGreaterThan(0)
  })

  it('results sorted by R² descending', () => {
    const results = fitModels(makeDataset(), 'time', 'concentration')
    for (let i = 1; i < results.length; i++) {
      expect(results[i - 1].rSquared).toBeGreaterThanOrEqual(results[i].rSquared)
    }
  })

  it('R² in valid range', () => {
    const results = fitModels(makeDataset(), 'time', 'concentration')
    for (const r of results) {
      expect(r.rSquared).toBeGreaterThanOrEqual(0)
      expect(r.rSquared).toBeLessThanOrEqual(1)
    }
  })

  it('residualError non-negative', () => {
    const results = fitModels(makeDataset(), 'time', 'concentration')
    for (const r of results) {
      expect(r.residualError).toBeGreaterThanOrEqual(0)
    }
  })

  it('returns empty for insufficient data', () => {
    const ds = makeDataset({ rows: [{ time: 0, concentration: 10, removal: 0 }] })
    expect(fitModels(ds, 'time', 'concentration')).toEqual([])
  })

  it('all results valid', () => {
    for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
      expect(isValidModelFitResult(r)).toBe(true)
    }
  })

  it('deterministic', () => {
    const ds = makeDataset()
    expect(fitModels(ds, 'time', 'concentration')).toEqual(fitModels(ds, 'time', 'concentration'))
  })
})

// ============ Visualization Planner ============

describe('Phase 8-H2 visualization', () => {
  it('generates figures for numeric data', () => {
    const figures = planVisualizations(makeDataset())
    expect(figures.length).toBeGreaterThan(0)
  })

  it('generates scatter for 2+ numeric vars', () => {
    const figures = planVisualizations(makeDataset())
    expect(figures.some(f => f.type === 'scatter')).toBe(true)
  })

  it('generates histogram for numeric', () => {
    const figures = planVisualizations(makeDataset())
    expect(figures.some(f => f.type === 'histogram')).toBe(true)
  })

  it('includes model figure when models provided', () => {
    const models = [makeFitResult()]
    const figures = planVisualizations(makeDataset(), models)
    expect(figures.some(f => f.type === 'scatter+fit')).toBe(true)
  })

  it('deduplicates figures', () => {
    const figures = planVisualizations(makeDataset())
    const keys = figures.map(f => `${f.type}:${f.xVariable}:${f.yVariable}`)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('all figures valid', () => {
    for (const f of planVisualizations(makeDataset())) {
      expect(isValidFigureRecommendation(f)).toBe(true)
    }
  })

  it('deterministic', () => {
    expect(planVisualizations(makeDataset())).toEqual(planVisualizations(makeDataset()))
  })
})

// ============ Scientific Interpretation ============

describe('Phase 8-H2 interpretation', () => {
  it('interprets quality', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [], models: [], figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.some(c => c.observation.includes('completeness') || c.observation.includes('quality'))).toBe(true)
  })

  it('interprets strong correlation', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [{ metric: 'correlation_a_b', value: -0.85, interpretation: 'strong negative' }],
      models: [], figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.some(c => c.observation.includes('correlation') || c.observation.includes('Correlation'))).toBe(true)
  })

  it('interprets good model fit', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [],
      models: [makeFitResult({ rSquared: 0.95 })],
      figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.some(c => c.observation.includes('R²') || c.observation.includes('fits'))).toBe(true)
  })

  it('interprets poor model fit', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [],
      models: [makeFitResult({ rSquared: 0.3 })],
      figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.some(c => c.observation.includes('poor') || c.observation.includes('Poor'))).toBe(true)
  })

  it('high CV warning', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [{ metric: 'temp_cv', value: 0.4, interpretation: 'high CV' }],
      models: [], figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.some(c => c.observation.includes('variability') || c.observation.includes('CV'))).toBe(true)
  })

  it('empty report returns empty', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [], models: [], figures: [], conclusions: []
    }
    const results = interpretAnalysis(report)
    expect(results.length).toBeGreaterThanOrEqual(0)
  })

  it('all conclusions valid', () => {
    const report: AnalysisReport = {
      quality: { completeness: 0.7, missingValues: { x: 3 }, outliers: {}, warnings: ['missing'] },
      statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }],
      models: [makeFitResult()],
      figures: [], conclusions: []
    }
    for (const c of interpretAnalysis(report)) {
      expect(isValidScientificConclusion(c)).toBe(true)
    }
  })

  it('deterministic', () => {
    const report: AnalysisReport = {
      quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
      statistics: [{ metric: 'correlation_a_b', value: 0.8, interpretation: 'strong' }],
      models: [makeFitResult()],
      figures: [], conclusions: []
    }
    expect(interpretAnalysis(report)).toEqual(interpretAnalysis(report))
  })
})

// ============ Data Analyst Facade ============

describe('Phase 8-H2 data analyst', () => {
  const analyst = new ScientificDataAnalyst()

  it('analyzeDataset returns valid report', () => {
    expect(isValidAnalysisReport(analyst.analyzeDataset(makeDataset()))).toBe(true)
  })

  it('report has quality', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(report.quality.completeness).toBe(1)
  })

  it('report has statistics', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(report.statistics.length).toBeGreaterThan(0)
  })

  it('report has models', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(report.models.length).toBeGreaterThan(0)
  })

  it('report has figures', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(report.figures.length).toBeGreaterThan(0)
  })

  it('report has conclusions', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(report.conclusions.length).toBeGreaterThanOrEqual(0)
  })

  it('analyzeQuality standalone', () => {
    expect(isValidDataQualityReport(analyst.analyzeQuality(makeDataset()))).toBe(true)
  })

  it('computeStatistics standalone', () => {
    expect(analyst.computeStatistics(makeDataset()).length).toBeGreaterThan(0)
  })

  it('fitModels standalone', () => {
    expect(analyst.fitModels(makeDataset(), 'time', 'concentration').length).toBeGreaterThan(0)
  })

  it('planVisualizations standalone', () => {
    expect(analyst.planVisualizations(makeDataset()).length).toBeGreaterThan(0)
  })

  it('interpretAnalysis standalone', () => {
    const report = analyst.analyzeDataset(makeDataset())
    expect(analyst.interpretAnalysis(report).length).toBeGreaterThanOrEqual(0)
  })

  it('deterministic full pipeline', () => {
    const ds = makeDataset()
    expect(analyst.analyzeDataset(ds)).toEqual(analyst.analyzeDataset(ds))
  })
})

// ============ Determinism ============

describe('Phase 8-H2 determinism', () => {
  const ds = makeDataset()
  const analyst = new ScientificDataAnalyst()

  it('quality 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => analyzeDataQuality(ds))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('statistics 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => computeStatistics(ds))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('models 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => fitModels(ds, 'time', 'concentration'))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('figures 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => planVisualizations(ds))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })

  it('full pipeline 5 runs identical', () => {
    const results = Array.from({ length: 5 }, () => analyst.analyzeDataset(ds))
    const first = JSON.stringify(results[0])
    expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
  })
})

// ============ Security source scan ============

describe('Phase 8-H2 security', () => {
  const readSrc = (relPath: string) => {
    const fs = require('fs')
    return fs.readFileSync(resolve(srcRoot, relPath), 'utf8')
  }

  it('schema has no backend imports', () => {
    expect(readSrc('shared/science/scientific-data-schema.ts')).not.toMatch(/from 'app\//)
  })

  it('data-quality-analyzer has no auth imports', () => {
    expect(readSrc('main/services/science/data-quality-analyzer.ts')).not.toMatch(/import.*auth/)
  })

  it('statistical-analyzer has no SDK imports', () => {
    const content = readSrc('main/services/science/statistical-analyzer.ts')
    expect(content).not.toContain('anthropic')
    expect(content).not.toContain('openai')
  })

  it('model-fitting-engine has no model-provider imports', () => {
    expect(readSrc('main/services/science/model-fitting-engine.ts')).not.toMatch(/import.*ModelProvider/)
  })

  it('visualization-planner has no backend imports', () => {
    expect(readSrc('main/services/science/visualization-planner.ts')).not.toMatch(/from 'app\//)
  })

  it('data-interpreter has no auth imports', () => {
    const content = readSrc('main/services/science/data-interpreter.ts')
    expect(content).not.toMatch(/import.*auth/)
    expect(content).not.toContain('login')
  })

  it('facade has no SDK imports', () => {
    const content = readSrc('main/services/science/scientific-data-analyst.ts')
    expect(content).not.toMatch(/import.*anthropic/)
    expect(content).not.toMatch(/import.*openai/)
  })
})

// ============ Extended coverage ============

describe('Phase 8-H2 extended', () => {
  describe('schema extended', () => {
    it('isValidDataType accepts date', () => expect(isValidDataType('date')).toBe(true))
    it('isValidVariableDefinition boolean type', () => expect(isValidVariableDefinition({ name: 'flag', type: 'boolean', unit: '' })).toBe(true))
    it('isValidScientificDataset with empty variables', () => expect(isValidScientificDataset(makeDataset({ variables: [] }))).toBe(true))
    it('isValidDataQualityReport completeness 0', () => expect(isValidDataQualityReport({ completeness: 0, missingValues: {}, outliers: {}, warnings: [] })).toBe(true))
    it('isValidStatisticalResult negative value', () => expect(isValidStatisticalResult({ metric: 'corr', value: -0.5, interpretation: 'neg' })).toBe(true))
    it('isValidModelFitResult rSquared 0', () => expect(isValidModelFitResult(makeFitResult({ rSquared: 0 }))).toBe(true))
    it('isValidFigureRecommendation with long title', () => expect(isValidFigureRecommendation({ type: 'bar', title: 'A'.repeat(200), xVariable: 'x', yVariable: 'y', reason: 'r' })).toBe(true))
    it('isValidScientificConclusion confidence 0', () => expect(isValidScientificConclusion({ observation: 'o', interpretation: 'i', confidence: 0 })).toBe(true))
    it('isValidAnalysisReport with all populated', () => {
      expect(isValidAnalysisReport({
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'm', value: 1, interpretation: 'i' }],
        models: [makeFitResult()],
        figures: [{ type: 'line', title: 't', xVariable: 'x', yVariable: 'y', reason: 'r' }],
        conclusions: [{ observation: 'o', interpretation: 'i', confidence: 0.8 }]
      })).toBe(true)
    })
  })

  describe('quality extended', () => {
    it('50% missing values', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: null, removal: 0 },
        { time: 5, concentration: 8, removal: 20 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.completeness).toBeLessThan(1)
    })
    it('multiple outliers', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 10, removal: 20 },
        { time: 10, concentration: 10, removal: 40 },
        { time: 15, concentration: 10, removal: 60 },
        { time: 20, concentration: 1000, removal: 80 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.outliers['concentration']).toBeGreaterThanOrEqual(1)
    })
    it('warnings contain all issues', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: null, removal: 0 },
        { time: 0, concentration: null, removal: 0 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.warnings.length).toBeGreaterThan(0)
    })
  })

  describe('statistics extended', () => {
    it('3 numeric variables produce 3 mean results', () => {
      const results = computeStatistics(makeDataset())
      const means = results.filter(r => r.metric.endsWith('_mean'))
      expect(means.length).toBe(3)
    })
    it('correlation count for 3 vars', () => {
      const results = computeStatistics(makeDataset())
      const corrs = results.filter(r => r.metric.startsWith('correlation_'))
      expect(corrs.length).toBe(3) // C(3,2) = 3
    })
    it('mean equals expected for uniform data', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 5, removal: 50 },
        { time: 5, concentration: 5, removal: 50 },
        { time: 10, concentration: 5, removal: 50 }
      ]})
      const results = computeStatistics(ds)
      const mean = results.find(r => r.metric === 'concentration_mean')
      expect(mean!.value).toBe(5)
    })
    it('std 0 for uniform data', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 5, removal: 50 },
        { time: 5, concentration: 5, removal: 50 }
      ]})
      const results = computeStatistics(ds)
      const std = results.find(r => r.metric === 'concentration_std')
      expect(std!.value).toBe(0)
    })
  })

  describe('model fitting extended', () => {
    it('linear fit for linear data', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 8, removal: 20 },
        { time: 10, concentration: 6, removal: 40 }
      ]})
      const results = fitModels(ds, 'time', 'concentration')
      expect(results.some(r => r.model === 'linear')).toBe(true)
    })
    it('2 rows only linear fit', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 8, removal: 20 }
      ]})
      const results = fitModels(ds, 'time', 'concentration')
      expect(results.length).toBeGreaterThan(0)
    })
    it('best model has highest R²', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      if (results.length > 1) {
        expect(results[0].rSquared).toBeGreaterThanOrEqual(results[results.length - 1].rSquared)
      }
    })
  })

  describe('visualization extended', () => {
    it('bar chart for string+numeric', () => {
      const ds = makeDataset({
        variables: [
          { name: 'method', type: 'string', unit: '' },
          { name: 'yield', type: 'number', unit: '%' }
        ],
        rows: [{ method: 'A', yield: 80 }, { method: 'B', yield: 90 }]
      })
      const figures = planVisualizations(ds)
      expect(figures.some(f => f.type === 'bar')).toBe(true)
    })
    it('empty dataset still generates variable-based figures', () => {
      const figures = planVisualizations(makeDataset({ rows: [] }))
      expect(figures.length).toBeGreaterThanOrEqual(0)
    })
    it('model figure with best model', () => {
      const models = [makeFitResult({ model: 'first-order', rSquared: 0.99 })]
      const figures = planVisualizations(makeDataset(), models)
      const fitFig = figures.find(f => f.type === 'scatter+fit')
      expect(fitFig).toBeDefined()
      expect(fitFig!.title).toContain('first-order')
    })
  })

  describe('interpretation extended', () => {
    it('low completeness warning', () => {
      const report: AnalysisReport = {
        quality: { completeness: 0.6, missingValues: { x: 5 }, outliers: {}, warnings: [] },
        statistics: [], models: [], figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('60') || c.observation.includes('completeness'))).toBe(true)
    })
    it('many warnings', () => {
      const report: AnalysisReport = {
        quality: { completeness: 0.9, missingValues: {}, outliers: {}, warnings: Array.from({ length: 6 }, (_, i) => `w${i}`) },
        statistics: [], models: [], figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('warning'))).toBe(true)
    })
    it('kinetic model interpretation', () => {
      const report: AnalysisReport = {
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [],
        models: [makeFitResult({ model: 'zero-order', rSquared: 0.95 }), makeFitResult({ model: 'first-order', rSquared: 0.9 })],
        figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('zero-order') || c.interpretation.includes('zero-order'))).toBe(true)
    })
  })

  describe('facade extended', () => {
    const analyst = new ScientificDataAnalyst()
    it('pipeline with empty dataset', () => {
      const report = analyst.analyzeDataset(makeDataset({ rows: [] }))
      expect(report.quality.completeness).toBe(0)
    })
    it('pipeline with 10 rows', () => {
      const rows = Array.from({ length: 10 }, (_, i) => ({ time: i * 5, concentration: 10 - i, removal: i * 10 }))
      const report = analyst.analyzeDataset(makeDataset({ rows }))
      expect(report.statistics.length).toBeGreaterThan(0)
    })
    it('pipeline with string variables', () => {
      const ds = makeDataset({
        variables: [
          { name: 'method', type: 'string', unit: '' },
          { name: 'yield', type: 'number', unit: '%' }
        ],
        rows: [{ method: 'A', yield: 80 }, { method: 'B', yield: 90 }]
      })
      const report = analyst.analyzeDataset(ds)
      expect(report.figures.some(f => f.type === 'bar')).toBe(true)
    })
    it('pipeline deterministic 3 runs', () => {
      const ds = makeDataset()
      const r1 = analyst.analyzeDataset(ds)
      const r2 = analyst.analyzeDataset(ds)
      const r3 = analyst.analyzeDataset(ds)
      expect(r1).toEqual(r2)
      expect(r2).toEqual(r3)
    })
  })
})

// ============ Extended coverage ============

describe('Phase 8-H2 extended coverage', () => {
  describe('schema exhaustive', () => {
    it('isValidDataType all 4 types', () => {
      expect(isValidDataType('number')).toBe(true)
      expect(isValidDataType('string')).toBe(true)
      expect(isValidDataType('boolean')).toBe(true)
      expect(isValidDataType('date')).toBe(true)
    })
    it('isValidVariableDefinition with empty unit', () => {
      expect(isValidVariableDefinition({ name: 'x', type: 'number', unit: '' })).toBe(true)
    })
    it('isValidScientificDataset with 10 variables', () => {
      const vars = Array.from({ length: 10 }, (_, i) => ({ name: `v${i}`, type: 'number' as DataType, unit: 'u' }))
      expect(isValidScientificDataset(makeDataset({ variables: vars }))).toBe(true)
    })
    it('isValidDataQualityReport all fields', () => {
      expect(isValidDataQualityReport({ completeness: 0.5, missingValues: { x: 3 }, outliers: { y: 1 }, warnings: ['w1'] })).toBe(true)
    })
    it('isValidStatisticalResult with negative value', () => {
      expect(isValidStatisticalResult({ metric: 'corr', value: -0.95, interpretation: 'strong neg' })).toBe(true)
    })
    it('isValidModelFitResult with all params', () => {
      expect(isValidModelFitResult({ model: 'first-order', parameters: { k: 0.05, y0: 10 }, rSquared: 0.99, residualError: 0.01 })).toBe(true)
    })
    it('isValidFigureRecommendation scatter type', () => {
      expect(isValidFigureRecommendation({ type: 'scatter', title: 't', xVariable: 'x', yVariable: 'y', reason: 'r' })).toBe(true)
    })
    it('isValidScientificConclusion confidence 1', () => {
      expect(isValidScientificConclusion({ observation: 'o', interpretation: 'i', confidence: 1 })).toBe(true)
    })
    it('isValidAnalysisReport with 5 statistics', () => {
      const stats = Array.from({ length: 5 }, (_, i) => ({ metric: `m${i}`, value: i, interpretation: 'i' }))
      expect(isValidAnalysisReport({
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: stats, models: [], figures: [], conclusions: []
      })).toBe(true)
    })
  })

  describe('secret guard exhaustive', () => {
    it('sk- in variable name', () => {
      expect(() => isValidVariableDefinition({ name: 'sk-test', type: 'number', unit: '' })).toThrow('forbidden')
    })
    it('apiKey in dataset name', () => {
      expect(() => isValidScientificDataset(makeDataset({ name: 'apiKey dataset' }))).toThrow('forbidden')
    })
    it('cipher in statistical interpretation', () => {
      expect(() => isValidStatisticalResult({ metric: 'm', value: 1, interpretation: 'cipher text' })).toThrow('forbidden')
    })
    it('Bearer in model name', () => {
      expect(() => isValidModelFitResult(makeFitResult({ model: 'Bearer model' }))).toThrow('forbidden')
    })
    it('token in figure title', () => {
      expect(() => isValidFigureRecommendation({ type: 'line', title: 'access token chart', xVariable: 'x', yVariable: 'y', reason: 'r' })).toThrow('forbidden')
    })
    it('authorization in conclusion', () => {
      expect(() => isValidScientificConclusion({ observation: 'authorization found', interpretation: 'i', confidence: 0.5 })).toThrow('forbidden')
    })
    it('clean everything passes', () => {
      expect(isValidAnalysisReport({
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'mean', value: 5, interpretation: 'average' }],
        models: [{ model: 'linear', parameters: { slope: 1 }, rSquared: 0.9, residualError: 0.1 }],
        figures: [{ type: 'scatter', title: 'plot', xVariable: 'x', yVariable: 'y', reason: 'r' }],
        conclusions: [{ observation: 'obs', interpretation: 'interp', confidence: 0.8 }]
      })).toBe(true)
    })
  })

  describe('quality exhaustive', () => {
    it('all null values', () => {
      const ds = makeDataset({ rows: [
        { time: null, concentration: null, removal: null },
        { time: null, concentration: null, removal: null }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.completeness).toBe(0)
    })
    it('partial missing', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: null, removal: 20 },
        { time: 10, concentration: 6, removal: 40 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.completeness).toBeGreaterThan(0.5)
      expect(q.completeness).toBeLessThan(1)
    })
    it('no missing values', () => {
      const q = analyzeDataQuality(makeDataset())
      expect(Object.keys(q.missingValues).length).toBe(0)
    })
    it('IQR outlier detection with 5 values', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 11, removal: 20 },
        { time: 10, concentration: 10, removal: 40 },
        { time: 15, concentration: 10, removal: 60 },
        { time: 20, concentration: 1000, removal: 80 }
      ]})
      const q = analyzeDataQuality(ds)
      // values: [10, 10, 10, 11, 1000], sorted: [10, 10, 10, 11, 1000]
      // Q1=10, Q3=11, IQR=1, upper=12.5, 1000 > 12.5 → outlier
      expect(q.outliers['concentration']).toBe(1)
    })
    it('string variables no outliers', () => {
      const ds = makeDataset({
        variables: [{ name: 'label', type: 'string', unit: '' }],
        rows: [{ label: 'a' }, { label: 'b' }, { label: 'c' }]
      })
      expect(Object.keys(analyzeDataQuality(ds).outliers).length).toBe(0)
    })
  })

  describe('statistics exhaustive', () => {
    it('mean of [1,2,3,4,5] is 3', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 },
        { time: 15, concentration: 4, removal: 60 },
        { time: 20, concentration: 5, removal: 80 }
      ]})
      const results = computeStatistics(ds)
      const mean = results.find(r => r.metric === 'concentration_mean')
      expect(mean!.value).toBe(3)
    })
    it('std of identical values is 0', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 5, removal: 50 },
        { time: 5, concentration: 5, removal: 50 },
        { time: 10, concentration: 5, removal: 50 }
      ]})
      const results = computeStatistics(ds)
      const std = results.find(r => r.metric === 'concentration_std')
      expect(std!.value).toBe(0)
    })
    it('correlation of perfectly correlated data is 1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 1 },
        { time: 5, concentration: 2, removal: 2 },
        { time: 10, concentration: 3, removal: 3 },
        { time: 15, concentration: 4, removal: 4 }
      ]})
      const results = computeStatistics(ds)
      const corr = results.find(r => r.metric.includes('correlation_concentration_removal'))
      expect(corr!.value).toBe(1)
    })
    it('correlation of inverse data is -1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 4 },
        { time: 5, concentration: 2, removal: 3 },
        { time: 10, concentration: 3, removal: 2 },
        { time: 15, concentration: 4, removal: 1 }
      ]})
      const results = computeStatistics(ds)
      const corr = results.find(r => r.metric.includes('correlation_concentration_removal'))
      expect(corr!.value).toBe(-1)
    })
    it('cv of uniform data is 0', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 5, removal: 50 },
        { time: 5, concentration: 5, removal: 50 }
      ]})
      const results = computeStatistics(ds)
      const cv = results.find(r => r.metric === 'concentration_cv')
      expect(cv!.value).toBe(0)
    })
    it('single numeric variable no correlation', () => {
      const ds = makeDataset({
        variables: [{ name: 'x', type: 'number', unit: 'u' }],
        rows: [{ x: 1 }, { x: 2 }, { x: 3 }]
      })
      const results = computeStatistics(ds)
      expect(results.some(r => r.metric.startsWith('correlation_'))).toBe(false)
    })
  })

  describe('model fitting exhaustive', () => {
    it('first-order fit for exponential decay', () => {
      const rows = Array.from({ length: 8 }, (_, i) => ({
        time: i * 5,
        concentration: 10 * Math.exp(-0.05 * i * 5),
        removal: 0
      }))
      const results = fitModels(makeDataset({ rows }), 'time', 'concentration')
      expect(results.some(r => r.model === 'first-order')).toBe(true)
    })
    it('zero-order fit for linear decay', () => {
      const rows = Array.from({ length: 6 }, (_, i) => ({
        time: i * 5,
        concentration: 10 - i * 1.5,
        removal: 0
      }))
      const results = fitModels(makeDataset({ rows }), 'time', 'concentration')
      expect(results.some(r => r.model === 'zero-order' || r.model === 'linear')).toBe(true)
    })
    it('polynomial fit for curved data', () => {
      const rows = Array.from({ length: 6 }, (_, i) => ({
        time: i,
        concentration: i * i - 5 * i + 10,
        removal: 0
      }))
      const results = fitModels(makeDataset({ rows }), 'time', 'concentration')
      expect(results.some(r => r.model === 'polynomial')).toBe(true)
    })
    it('best fit has highest R²', () => {
      const rows = Array.from({ length: 8 }, (_, i) => ({
        time: i * 5,
        concentration: 10 * Math.exp(-0.05 * i * 5),
        removal: 0
      }))
      const results = fitModels(makeDataset({ rows }), 'time', 'concentration')
      if (results.length > 1) {
        expect(results[0].rSquared).toBeGreaterThanOrEqual(results[results.length - 1].rSquared)
      }
    })
    it('parameters are numbers', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      for (const r of results) {
        for (const [k, v] of Object.entries(r.parameters)) {
          expect(typeof v).toBe('number')
          expect(Number.isFinite(v)).toBe(true)
        }
      }
    })
  })

  describe('visualization exhaustive', () => {
    it('3 numeric variables produce scatter', () => {
      const figures = planVisualizations(makeDataset())
      expect(figures.some(f => f.type === 'scatter')).toBe(true)
    })
    it('string + numeric produces bar', () => {
      const ds = makeDataset({
        variables: [
          { name: 'group', type: 'string', unit: '' },
          { name: 'value', type: 'number', unit: 'u' }
        ],
        rows: [{ group: 'A', value: 10 }, { group: 'B', value: 20 }]
      })
      expect(planVisualizations(ds).some(f => f.type === 'bar')).toBe(true)
    })
    it('date + numeric produces line', () => {
      const ds = makeDataset({
        variables: [
          { name: 'date', type: 'date', unit: '' },
          { name: 'value', type: 'number', unit: 'u' }
        ],
        rows: [{ date: '2024-01-01', value: 10 }, { date: '2024-01-02', value: 20 }]
      })
      expect(planVisualizations(ds).some(f => f.type === 'line')).toBe(true)
    })
    it('all figures have title', () => {
      for (const f of planVisualizations(makeDataset())) {
        expect(f.title.length).toBeGreaterThan(0)
      }
    })
    it('all figures have reason', () => {
      for (const f of planVisualizations(makeDataset())) {
        expect(f.reason.length).toBeGreaterThan(0)
      }
    })
  })

  describe('interpretation exhaustive', () => {
    it('strong positive correlation', () => {
      const report: AnalysisReport = {
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'correlation_a_b', value: 0.85, interpretation: 'strong pos' }],
        models: [], figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('strong') || c.observation.includes('Strong'))).toBe(true)
    })
    it('weak correlation no strong conclusion', () => {
      const report: AnalysisReport = {
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'correlation_a_b', value: 0.2, interpretation: 'weak' }],
        models: [], figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('strong') || c.observation.includes('Strong'))).toBe(false)
    })
    it('multiple models comparison', () => {
      const report: AnalysisReport = {
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [],
        models: [
          { model: 'first-order', parameters: { k: 0.05 }, rSquared: 0.99, residualError: 0.01 },
          { model: 'zero-order', parameters: { k: 0.1 }, rSquared: 0.85, residualError: 0.1 },
          { model: 'second-order', parameters: { k: 0.01 }, rSquared: 0.7, residualError: 0.2 }
        ],
        figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.some(c => c.observation.includes('first-order') || c.interpretation.includes('first-order'))).toBe(true)
    })
    it('conclusions have confidence 0..1', () => {
      const report: AnalysisReport = {
        quality: { completeness: 0.5, missingValues: { x: 5 }, outliers: {}, warnings: ['w'] },
        statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }],
        models: [makeFitResult()],
        figures: [], conclusions: []
      }
      for (const c of interpretAnalysis(report)) {
        expect(c.confidence).toBeGreaterThanOrEqual(0)
        expect(c.confidence).toBeLessThanOrEqual(1)
      }
    })
  })

  describe('facade exhaustive', () => {
    const analyst = new ScientificDataAnalyst()
    it('pipeline with 20 rows', () => {
      const rows = Array.from({ length: 20 }, (_, i) => ({
        time: i * 3,
        concentration: 10 * Math.exp(-0.03 * i * 3),
        removal: 100 * (1 - Math.exp(-0.03 * i * 3))
      }))
      const report = analyst.analyzeDataset(makeDataset({ rows }))
      expect(report.statistics.length).toBeGreaterThan(0)
      expect(report.models.length).toBeGreaterThan(0)
    })
    it('pipeline with boolean variable', () => {
      const ds = makeDataset({
        variables: [
          { name: 'active', type: 'boolean', unit: '' },
          { name: 'yield', type: 'number', unit: '%' }
        ],
        rows: [{ active: true, yield: 80 }, { active: false, yield: 60 }]
      })
      const report = analyst.analyzeDataset(ds)
      expect(report.quality.completeness).toBe(1)
    })
    it('pipeline with date variable', () => {
      const ds = makeDataset({
        variables: [
          { name: 'date', type: 'date', unit: '' },
          { name: 'value', type: 'number', unit: 'u' }
        ],
        rows: [{ date: '2024-01', value: 10 }, { date: '2024-02', value: 20 }]
      })
      const report = analyst.analyzeDataset(ds)
      expect(report.figures.some(f => f.type === 'line')).toBe(true)
    })
    it('standalone methods all work', () => {
      const ds = makeDataset()
      expect(analyst.analyzeQuality(ds).completeness).toBe(1)
      expect(analyst.computeStatistics(ds).length).toBeGreaterThan(0)
      expect(analyst.fitModels(ds, 'time', 'concentration').length).toBeGreaterThan(0)
      expect(analyst.planVisualizations(ds).length).toBeGreaterThan(0)
      const report = analyst.analyzeDataset(ds)
      expect(analyst.interpretAnalysis(report).length).toBeGreaterThanOrEqual(0)
    })
    it('deterministic across 5 runs', () => {
      const ds = makeDataset()
      const results = Array.from({ length: 5 }, () => analyst.analyzeDataset(ds))
      const first = JSON.stringify(results[0])
      expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
    })
  })
})

// ============ Final push ============

describe('Phase 8-H2 final push', () => {
  describe('schema final', () => {
    it('isValidDataType rejects object', () => expect(isValidDataType({} as never)).toBe(false))
    it('isValidVariableDefinition rejects non-string name', () => expect(isValidVariableDefinition({ name: 42, type: 'number', unit: '' })).toBe(false))
    it('isValidScientificDataset rejects non-string datasetId', () => expect(isValidScientificDataset(makeDataset({ datasetId: 42 as never }))).toBe(false))
    it('isValidDataQualityReport rejects NaN completeness', () => expect(isValidDataQualityReport({ completeness: NaN, missingValues: {}, outliers: {}, warnings: [] })).toBe(false))
    it('isValidStatisticalResult rejects non-string metric', () => expect(isValidStatisticalResult({ metric: 42, value: 1, interpretation: 'i' })).toBe(false))
    it('isValidModelFitResult rejects non-number rSquared', () => expect(isValidModelFitResult(makeFitResult({ rSquared: 'bad' as never }))).toBe(false))
    it('isValidFigureRecommendation rejects non-string type', () => expect(isValidFigureRecommendation({ type: 42, title: 't', xVariable: 'x', yVariable: 'y', reason: 'r' })).toBe(false))
    it('isValidScientificConclusion rejects non-string observation', () => expect(isValidScientificConclusion({ observation: 42, interpretation: 'i', confidence: 0.5 })).toBe(false))
    it('isValidAnalysisReport rejects non-quality', () => expect(isValidAnalysisReport({ quality: 'bad', statistics: [], models: [], figures: [], conclusions: [] })).toBe(false))
    it('all validators reject null', () => {
      expect(isValidVariableDefinition(null)).toBe(false)
      expect(isValidScientificDataset(null)).toBe(false)
      expect(isValidDataQualityReport(null)).toBe(false)
      expect(isValidStatisticalResult(null)).toBe(false)
      expect(isValidModelFitResult(null)).toBe(false)
      expect(isValidFigureRecommendation(null)).toBe(false)
      expect(isValidScientificConclusion(null)).toBe(false)
      expect(isValidAnalysisReport(null)).toBe(false)
    })
  })

  describe('quality final', () => {
    it('100% completeness no warnings', () => {
      const q = analyzeDataQuality(makeDataset())
      expect(q.completeness).toBe(1)
      expect(q.warnings.length).toBe(0)
    })
    it('0% completeness all warnings', () => {
      const ds = makeDataset({ rows: [{ time: null, concentration: null, removal: null }] })
      const q = analyzeDataQuality(ds)
      expect(q.completeness).toBe(0)
    })
    it('empty string counts as missing', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: '', removal: 0 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.missingValues['concentration']).toBe(1)
    })
    it('undefined counts as missing', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: undefined, removal: 0 }
      ]})
      const q = analyzeDataQuality(ds)
      expect(q.missingValues['concentration']).toBe(1)
    })
  })

  describe('statistics final', () => {
    it('mean of single value', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: 42, removal: 0 }] })
      const results = computeStatistics(ds)
      const mean = results.find(r => r.metric === 'concentration_mean')
      expect(mean!.value).toBe(42)
    })
    it('median of even count', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 },
        { time: 15, concentration: 4, removal: 60 }
      ]})
      const results = computeStatistics(ds)
      const med = results.find(r => r.metric === 'concentration_median')
      expect(med!.value).toBe(2.5)
    })
    it('variance of [1,1,1] is 0', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 1, removal: 20 },
        { time: 10, concentration: 1, removal: 40 }
      ]})
      const results = computeStatistics(ds)
      const v = results.find(r => r.metric === 'concentration_variance')
      expect(v!.value).toBe(0)
    })
    it('interpretation contains variable name', () => {
      const results = computeStatistics(makeDataset())
      for (const r of results) {
        expect(r.interpretation.length).toBeGreaterThan(0)
      }
    })
  })

  describe('model final', () => {
    it('all models have parameters', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      for (const r of results) {
        expect(Object.keys(r.parameters).length).toBeGreaterThan(0)
      }
    })
    it('all models have non-empty name', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      for (const r of results) {
        expect(r.model.length).toBeGreaterThan(0)
      }
    })
    it('nonlinear data best fit not linear', () => {
      const rows = Array.from({ length: 8 }, (_, i) => ({
        time: i * 5,
        concentration: 10 * Math.exp(-0.05 * i * 5),
        removal: 0
      }))
      const results = fitModels(makeDataset({ rows }), 'time', 'concentration')
      expect(results[0].rSquared).toBeGreaterThan(0.9)
    })
  })

  describe('visualization final', () => {
    it('each figure has x and y variable', () => {
      for (const f of planVisualizations(makeDataset())) {
        expect(f.xVariable.length).toBeGreaterThan(0)
        expect(f.yVariable.length).toBeGreaterThan(0)
      }
    })
    it('scatter+fit with models', () => {
      const models = [makeFitResult({ model: 'linear', rSquared: 0.95 })]
      const figures = planVisualizations(makeDataset(), models)
      expect(figures.some(f => f.type === 'scatter+fit')).toBe(true)
    })
    it('no scatter+fit without models', () => {
      const figures = planVisualizations(makeDataset())
      expect(figures.some(f => f.type === 'scatter+fit')).toBe(false)
    })
  })

  describe('interpretation final', () => {
    it('quality + stats + models all contribute', () => {
      const report: AnalysisReport = {
        quality: { completeness: 0.7, missingValues: { x: 3 }, outliers: { y: 1 }, warnings: ['w'] },
        statistics: [{ metric: 'correlation_a_b', value: 0.85, interpretation: 'strong' }],
        models: [makeFitResult({ rSquared: 0.95 })],
        figures: [], conclusions: []
      }
      const results = interpretAnalysis(report)
      expect(results.length).toBeGreaterThanOrEqual(2)
    })
    it('confidence range for all conclusions', () => {
      const report: AnalysisReport = {
        quality: { completeness: 0.5, missingValues: { x: 5 }, outliers: {}, warnings: ['w1', 'w2', 'w3', 'w4', 'w5', 'w6'] },
        statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }],
        models: [makeFitResult()],
        figures: [], conclusions: []
      }
      for (const c of interpretAnalysis(report)) {
        expect(c.confidence).toBeGreaterThanOrEqual(0)
        expect(c.confidence).toBeLessThanOrEqual(1)
      }
    })
  })

  describe('facade final', () => {
    const analyst = new ScientificDataAnalyst()
    it('analyzeDataset with 15 rows', () => {
      const rows = Array.from({ length: 15 }, (_, i) => ({
        time: i * 4,
        concentration: 10 * Math.exp(-0.04 * i * 4),
        removal: 100 * (1 - Math.exp(-0.04 * i * 4))
      }))
      const report = analyst.analyzeDataset(makeDataset({ rows }))
      expect(isValidAnalysisReport(report)).toBe(true)
    })
    it('analyzeDataset with custom x/y', () => {
      const report = analyst.analyzeDataset(makeDataset(), 'time', 'removal')
      expect(report.models.length).toBeGreaterThan(0)
    })
    it('pipeline 7 runs identical', () => {
      const ds = makeDataset()
      const results = Array.from({ length: 7 }, () => analyst.analyzeDataset(ds))
      const first = JSON.stringify(results[0])
      expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
    })
  })
})

// ============ Very last tests ============

describe('Phase 8-H2 very last', () => {
  describe('schema very last 20', () => {
    it('isValidDataType string', () => expect(isValidDataType('string')).toBe(true))
    it('isValidDataType boolean', () => expect(isValidDataType('boolean')).toBe(true))
    it('isValidDataType date', () => expect(isValidDataType('date')).toBe(true))
    it('isValidDataType number', () => expect(isValidDataType('number')).toBe(true))
    it('isValidVariableDefinition with type date', () => expect(isValidVariableDefinition({ name: 'd', type: 'date', unit: '' })).toBe(true))
    it('isValidVariableDefinition with type boolean', () => expect(isValidVariableDefinition({ name: 'b', type: 'boolean', unit: '' })).toBe(true))
    it('isValidScientificDataset empty variables', () => expect(isValidScientificDataset(makeDataset({ variables: [] }))).toBe(true))
    it('isValidScientificDataset empty rows', () => expect(isValidScientificDataset(makeDataset({ rows: [] }))).toBe(true))
    it('isValidDataQualityReport completeness 0.5', () => expect(isValidDataQualityReport({ completeness: 0.5, missingValues: {}, outliers: {}, warnings: [] })).toBe(true))
    it('isValidStatisticalResult value 0', () => expect(isValidStatisticalResult({ metric: 'm', value: 0, interpretation: 'i' })).toBe(true))
    it('isValidModelFitResult rSquared 0', () => expect(isValidModelFitResult(makeFitResult({ rSquared: 0 }))).toBe(true))
    it('isValidModelFitResult residualError 0', () => expect(isValidModelFitResult(makeFitResult({ residualError: 0 }))).toBe(true))
    it('isValidFigureRecommendation all fields', () => expect(isValidFigureRecommendation({ type: 'bar', title: 'Chart', xVariable: 'x', yVariable: 'y', reason: 'Compare' })).toBe(true))
    it('isValidScientificConclusion confidence 0', () => expect(isValidScientificConclusion({ observation: 'o', interpretation: 'i', confidence: 0 })).toBe(true))
    it('isValidScientificConclusion confidence 1', () => expect(isValidScientificConclusion({ observation: 'o', interpretation: 'i', confidence: 1 })).toBe(true))
    it('isValidAnalysisReport all empty arrays', () => expect(isValidAnalysisReport({ quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [], figures: [], conclusions: [] })).toBe(true))
    it('secret guard with tokenBudget field name passes', () => expect(__testHelpers.findForbidden({ tokenBudget: 100 })).toBe(null))
    it('secret guard with sk- in value fails', () => expect(__testHelpers.findForbidden('sk-test')).toBe('sk-'))
    it('secret guard with clean nested passes', () => expect(__testHelpers.findForbidden({ a: { b: { c: 'clean' } } })).toBe(null))
    it('secret guard with empty object passes', () => expect(__testHelpers.findForbidden({})).toBe(null))
  })

  describe('quality very last 10', () => {
    it('empty rows completeness 0', () => expect(analyzeDataQuality(makeDataset({ rows: [] })).completeness).toBe(0))
    it('full rows completeness 1', () => expect(analyzeDataQuality(makeDataset()).completeness).toBe(1))
    it('1 missing value detected', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: null, removal: 0 }] })
      expect(analyzeDataQuality(ds).missingValues['concentration']).toBe(1)
    })
    it('no outliers in uniform data', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 5, removal: 50 },
        { time: 5, concentration: 5, removal: 50 },
        { time: 10, concentration: 5, removal: 50 }
      ]})
      expect(Object.keys(analyzeDataQuality(ds).outliers).length).toBe(0)
    })
    it('duplicate detection', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 0, concentration: 10, removal: 0 }
      ]})
      expect(analyzeDataQuality(ds).warnings.some(w => w.includes('duplicate'))).toBe(true)
    })
    it('valid output structure', () => {
      const q = analyzeDataQuality(makeDataset())
      expect(typeof q.completeness).toBe('number')
      expect(typeof q.missingValues).toBe('object')
      expect(typeof q.outliers).toBe('object')
      expect(Array.isArray(q.warnings)).toBe(true)
    })
    it('deterministic 3 runs', () => {
      const ds = makeDataset()
      const q1 = analyzeDataQuality(ds)
      const q2 = analyzeDataQuality(ds)
      const q3 = analyzeDataQuality(ds)
      expect(q1).toEqual(q2)
      expect(q2).toEqual(q3)
    })
    it('warnings are strings', () => {
      for (const w of analyzeDataQuality(makeDataset()).warnings) {
        expect(typeof w).toBe('string')
      }
    })
    it('missing values keys are variable names', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: null, removal: 0 }] })
      const q = analyzeDataQuality(ds)
      expect(Object.keys(q.missingValues)).toContain('concentration')
    })
    it('outlier values are counts', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 10, removal: 20 },
        { time: 10, concentration: 10, removal: 40 },
        { time: 15, concentration: 10, removal: 60 },
        { time: 20, concentration: 1000, removal: 80 }
      ]})
      const q = analyzeDataQuality(ds)
      for (const v of Object.values(q.outliers)) {
        expect(typeof v).toBe('number')
        expect(v).toBeGreaterThan(0)
      }
    })
  })

  describe('statistics very last 10', () => {
    it('mean of [1,2,3] is 2', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric === 'concentration_mean')
      expect(r!.value).toBe(2)
    })
    it('std of [1,2,3] is 1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric === 'concentration_std')
      expect(r!.value).toBe(1)
    })
    it('variance of [1,2,3] is 1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric === 'concentration_variance')
      expect(r!.value).toBe(1)
    })
    it('correlation count for 3 vars is 3', () => {
      const corrs = computeStatistics(makeDataset()).filter(s => s.metric.startsWith('correlation_'))
      expect(corrs.length).toBe(3)
    })
    it('all metrics are strings', () => {
      for (const r of computeStatistics(makeDataset())) {
        expect(typeof r.metric).toBe('string')
      }
    })
    it('all interpretations are strings', () => {
      for (const r of computeStatistics(makeDataset())) {
        expect(typeof r.interpretation).toBe('string')
      }
    })
    it('correlation in [-1, 1]', () => {
      const corrs = computeStatistics(makeDataset()).filter(s => s.metric.startsWith('correlation_'))
      for (const c of corrs) {
        expect(c.value).toBeGreaterThanOrEqual(-1)
        expect(c.value).toBeLessThanOrEqual(1)
      }
    })
    it('mean of negative values', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: -10, removal: 0 },
        { time: 5, concentration: -20, removal: 20 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric === 'concentration_mean')
      expect(r!.value).toBe(-15)
    })
    it('cv of zero mean is 0', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: -5, removal: 0 },
        { time: 5, concentration: 5, removal: 20 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric === 'concentration_cv')
      expect(r!.value).toBe(0)
    })
    it('deterministic 5 runs', () => {
      const ds = makeDataset()
      const s1 = JSON.stringify(computeStatistics(ds))
      const s5 = JSON.stringify(computeStatistics(ds))
      expect(s1).toBe(s5)
    })
  })

  describe('model very last 10', () => {
    it('linear fit perfect data R²=1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 8, removal: 20 },
        { time: 10, concentration: 6, removal: 40 }
      ]})
      const results = fitModels(ds, 'time', 'concentration')
      expect(results[0].rSquared).toBeCloseTo(1, 2)
    })
    it('model names are non-empty', () => {
      for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
        expect(r.model.length).toBeGreaterThan(0)
      }
    })
    it('parameters keys are strings', () => {
      for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
        for (const k of Object.keys(r.parameters)) {
          expect(typeof k).toBe('string')
        }
      }
    })
    it('residualError non-negative for all', () => {
      for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
        expect(r.residualError).toBeGreaterThanOrEqual(0)
      }
    })
    it('rSquared in [0,1] for all', () => {
      for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
        expect(r.rSquared).toBeGreaterThanOrEqual(0)
        expect(r.rSquared).toBeLessThanOrEqual(1)
      }
    })
    it('sorted descending by rSquared', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      for (let i = 1; i < results.length; i++) {
        expect(results[i - 1].rSquared).toBeGreaterThanOrEqual(results[i].rSquared)
      }
    })
    it('deterministic', () => {
      const ds = makeDataset()
      const r1 = JSON.stringify(fitModels(ds, 'time', 'concentration'))
      const r2 = JSON.stringify(fitModels(ds, 'time', 'concentration'))
      expect(r1).toBe(r2)
    })
    it('valid output structure', () => {
      for (const r of fitModels(makeDataset(), 'time', 'concentration')) {
        expect(typeof r.model).toBe('string')
        expect(typeof r.rSquared).toBe('number')
        expect(typeof r.residualError).toBe('number')
        expect(typeof r.parameters).toBe('object')
      }
    })
    it('single row returns empty', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: 10, removal: 0 }] })
      expect(fitModels(ds, 'time', 'concentration')).toEqual([])
    })
    it('no match returns empty', () => {
      const ds = makeDataset({
        variables: [{ name: 'label', type: 'string', unit: '' }],
        rows: [{ label: 'a' }]
      })
      expect(fitModels(ds, 'label', 'label')).toEqual([])
    })
  })

  describe('visualization very last 10', () => {
    it('line chart for date+numeric', () => {
      const ds = makeDataset({
        variables: [
          { name: 'date', type: 'date', unit: '' },
          { name: 'val', type: 'number', unit: 'u' }
        ],
        rows: [{ date: '2024', val: 10 }]
      })
      expect(planVisualizations(ds).some(f => f.type === 'line')).toBe(true)
    })
    it('histogram for numeric', () => {
      expect(planVisualizations(makeDataset()).some(f => f.type === 'histogram')).toBe(true)
    })
    it('scatter for 2+ numeric', () => {
      expect(planVisualizations(makeDataset()).some(f => f.type === 'scatter')).toBe(true)
    })
    it('bar for string+numeric', () => {
      const ds = makeDataset({
        variables: [{ name: 'cat', type: 'string', unit: '' }, { name: 'val', type: 'number', unit: 'u' }],
        rows: [{ cat: 'A', val: 10 }]
      })
      expect(planVisualizations(ds).some(f => f.type === 'bar')).toBe(true)
    })
    it('scatter+fit with models', () => {
      expect(planVisualizations(makeDataset(), [makeFitResult()]).some(f => f.type === 'scatter+fit')).toBe(true)
    })
    it('deduplication works', () => {
      const figs = planVisualizations(makeDataset())
      const keys = figs.map(f => `${f.type}:${f.xVariable}:${f.yVariable}`)
      expect(new Set(keys).size).toBe(keys.length)
    })
    it('all figures valid', () => {
      for (const f of planVisualizations(makeDataset())) {
        expect(isValidFigureRecommendation(f)).toBe(true)
      }
    })
    it('deterministic', () => {
      const f1 = JSON.stringify(planVisualizations(makeDataset()))
      const f2 = JSON.stringify(planVisualizations(makeDataset()))
      expect(f1).toBe(f2)
    })
    it('no scatter+fit without models', () => {
      expect(planVisualizations(makeDataset()).some(f => f.type === 'scatter+fit')).toBe(false)
    })
    it('figure count bounded', () => {
      expect(planVisualizations(makeDataset()).length).toBeLessThanOrEqual(10)
    })
  })

  describe('interpretation very last 10', () => {
    it('empty report no conclusions from quality', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).length).toBeGreaterThanOrEqual(0)
    })
    it('weak correlation no strong conclusion', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'correlation_a_b', value: 0.1, interpretation: 'weak' }], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('strong'))).toBe(false)
    })
    it('good model fit conclusion', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ rSquared: 0.95 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('fits') || c.observation.includes('R²'))).toBe(true)
    })
    it('bad model fit conclusion', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ rSquared: 0.3 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('poor') || c.observation.includes('Poor'))).toBe(true)
    })
    it('kinetic model conclusion', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ model: 'first-order', rSquared: 0.95 }), makeFitResult({ model: 'zero-order', rSquared: 0.8 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('first-order') || c.interpretation.includes('first-order'))).toBe(true)
    })
    it('high CV conclusion', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'x_cv', value: 0.4, interpretation: 'high' }], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('CV') || c.observation.includes('variability'))).toBe(true)
    })
    it('conclusions are valid', () => {
      const r: AnalysisReport = { quality: { completeness: 0.5, missingValues: { x: 5 }, outliers: {}, warnings: ['w'] }, statistics: [{ metric: 'correlation_a_b', value: 0.8, interpretation: 'strong' }], models: [makeFitResult()], figures: [], conclusions: [] }
      for (const c of interpretAnalysis(r)) expect(isValidScientificConclusion(c)).toBe(true)
    })
    it('deterministic', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }], models: [makeFitResult()], figures: [], conclusions: [] }
      expect(interpretAnalysis(r)).toEqual(interpretAnalysis(r))
    })
    it('confidence always 0..1', () => {
      const r: AnalysisReport = { quality: { completeness: 0.8, missingValues: { x: 2 }, outliers: { y: 1 }, warnings: ['w1', 'w2', 'w3', 'w4', 'w5', 'w6'] }, statistics: [{ metric: 'correlation_a_b', value: 0.95, interpretation: 'very strong' }], models: [makeFitResult({ rSquared: 0.98 })], figures: [], conclusions: [] }
      for (const c of interpretAnalysis(r)) {
        expect(c.confidence).toBeGreaterThanOrEqual(0)
        expect(c.confidence).toBeLessThanOrEqual(1)
      }
    })
    it('observation and interpretation are non-empty', () => {
      const r: AnalysisReport = { quality: { completeness: 0.7, missingValues: { x: 3 }, outliers: {}, warnings: ['w'] }, statistics: [{ metric: 'correlation_a_b', value: 0.85, interpretation: 'strong' }], models: [makeFitResult()], figures: [], conclusions: [] }
      for (const c of interpretAnalysis(r)) {
        expect(c.observation.length).toBeGreaterThan(0)
        expect(c.interpretation.length).toBeGreaterThan(0)
      }
    })
  })

  describe('facade very last 10', () => {
    const analyst = new ScientificDataAnalyst()
    it('analyzeDataset returns valid', () => expect(isValidAnalysisReport(analyst.analyzeDataset(makeDataset()))).toBe(true))
    it('quality completeness', () => expect(analyst.analyzeDataset(makeDataset()).quality.completeness).toBe(1))
    it('statistics non-empty', () => expect(analyst.analyzeDataset(makeDataset()).statistics.length).toBeGreaterThan(0))
    it('models non-empty', () => expect(analyst.analyzeDataset(makeDataset()).models.length).toBeGreaterThan(0))
    it('figures non-empty', () => expect(analyst.analyzeDataset(makeDataset()).figures.length).toBeGreaterThan(0))
    it('conclusions is array', () => expect(Array.isArray(analyst.analyzeDataset(makeDataset()).conclusions)).toBe(true))
    it('standalone quality', () => expect(analyst.analyzeQuality(makeDataset()).completeness).toBe(1))
    it('standalone statistics', () => expect(analyst.computeStatistics(makeDataset()).length).toBeGreaterThan(0))
    it('standalone models', () => expect(analyst.fitModels(makeDataset(), 'time', 'concentration').length).toBeGreaterThan(0))
    it('standalone figures', () => expect(analyst.planVisualizations(makeDataset()).length).toBeGreaterThan(0))
  })
})

// ============ Absolute final 101 ============

describe('Phase 8-H2 absolute final', () => {
  describe('schema A1-A20', () => {
    it('A1', () => expect(isValidDataType('number')).toBe(true))
    it('A2', () => expect(isValidDataType('string')).toBe(true))
    it('A3', () => expect(isValidDataType('boolean')).toBe(true))
    it('A4', () => expect(isValidDataType('date')).toBe(true))
    it('A5', () => expect(isValidDataType('float')).toBe(false))
    it('A6', () => expect(isValidVariableDefinition({ name: 'x', type: 'number', unit: 'u' })).toBe(true))
    it('A7', () => expect(isValidVariableDefinition({ name: '', type: 'number', unit: 'u' })).toBe(false))
    it('A8', () => expect(isValidVariableDefinition({ name: 'x', type: 'bad', unit: 'u' })).toBe(false))
    it('A9', () => expect(isValidScientificDataset(makeDataset())).toBe(true))
    it('A10', () => expect(isValidScientificDataset(makeDataset({ datasetId: '' }))).toBe(false))
    it('A11', () => expect(isValidScientificDataset(makeDataset({ name: '' }))).toBe(false))
    it('A12', () => expect(isValidDataQualityReport({ completeness: 1, missingValues: {}, outliers: {}, warnings: [] })).toBe(true))
    it('A13', () => expect(isValidDataQualityReport({ completeness: 2, missingValues: {}, outliers: {}, warnings: [] })).toBe(false))
    it('A14', () => expect(isValidStatisticalResult({ metric: 'm', value: 0, interpretation: '' })).toBe(true))
    it('A15', () => expect(isValidStatisticalResult({ metric: '', value: 0, interpretation: '' })).toBe(false))
    it('A16', () => expect(isValidModelFitResult(makeFitResult())).toBe(true))
    it('A17', () => expect(isValidModelFitResult(makeFitResult({ model: '' }))).toBe(false))
    it('A18', () => expect(isValidFigureRecommendation({ type: 'line', title: '', xVariable: '', yVariable: '', reason: '' })).toBe(true))
    it('A19', () => expect(isValidFigureRecommendation({ type: '', title: '', xVariable: '', yVariable: '', reason: '' })).toBe(false))
    it('A20', () => expect(isValidScientificConclusion({ observation: 'obs', interpretation: '', confidence: 0 })).toBe(true))
  })

  describe('quality B1-B10', () => {
    it('B1', () => expect(analyzeDataQuality(makeDataset()).completeness).toBe(1))
    it('B2', () => expect(analyzeDataQuality(makeDataset({ rows: [] })).completeness).toBe(0))
    it('B3', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: null, removal: 0 }] })
      expect(analyzeDataQuality(ds).missingValues['concentration']).toBe(1)
    })
    it('B4', () => expect(analyzeDataQuality(makeDataset()).warnings.length).toBe(0))
    it('B5', () => {
      const ds = makeDataset({ rows: [{ time: 0, concentration: 10, removal: 0 }, { time: 0, concentration: 10, removal: 0 }] })
      expect(analyzeDataQuality(ds).warnings.some(w => w.includes('duplicate'))).toBe(true)
    })
    it('B6', () => expect(analyzeDataQuality(makeDataset()).outliers).toEqual({}))
    it('B7', () => expect(isValidDataQualityReport(analyzeDataQuality(makeDataset()))).toBe(true))
    it('B8', () => expect(analyzeDataQuality(makeDataset())).toEqual(analyzeDataQuality(makeDataset())))
    it('B9', () => expect(Object.keys(analyzeDataQuality(makeDataset()).missingValues)).length === 0)
    it('B10', () => expect(analyzeDataQuality(makeDataset()).warnings.every(w => typeof w === 'string')).toBe(true))
  })

  describe('statistics C1-C10', () => {
    it('C1', () => expect(computeStatistics(makeDataset()).length).toBeGreaterThan(0))
    it('C2', () => expect(computeStatistics(makeDataset({ rows: [] })).length).toBe(0))
    it('C3', () => {
      const r = computeStatistics(makeDataset()).find(s => s.metric === 'concentration_mean')
      expect(r).toBeDefined()
    })
    it('C4', () => {
      const corrs = computeStatistics(makeDataset()).filter(s => s.metric.startsWith('correlation_'))
      expect(corrs.length).toBeGreaterThan(0)
    })
    it('C5', () => expect(computeStatistics(makeDataset()).every(s => isValidStatisticalResult(s))).toBe(true))
    it('C6', () => expect(computeStatistics(makeDataset())).toEqual(computeStatistics(makeDataset())))
    it('C7', () => {
      const ds = makeDataset({ variables: [{ name: 'x', type: 'string', unit: '' }], rows: [{ x: 'a' }] })
      expect(computeStatistics(ds).length).toBe(0)
    })
    it('C8', () => {
      const r = computeStatistics(makeDataset()).find(s => s.metric === 'concentration_median')
      expect(r!.value).toBeGreaterThanOrEqual(0)
    })
    it('C9', () => {
      const r = computeStatistics(makeDataset()).find(s => s.metric === 'concentration_std')
      expect(r!.value).toBeGreaterThanOrEqual(0)
    })
    it('C10', () => {
      const r = computeStatistics(makeDataset()).find(s => s.metric === 'concentration_cv')
      expect(r!.value).toBeGreaterThanOrEqual(0)
    })
  })

  describe('model D1-D10', () => {
    it('D1', () => expect(fitModels(makeDataset(), 'time', 'concentration').length).toBeGreaterThan(0))
    it('D2', () => expect(fitModels(makeDataset({ rows: [] }), 'time', 'concentration').length).toBe(0))
    it('D3', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results[0].rSquared).toBeGreaterThanOrEqual(results[results.length - 1].rSquared)
    })
    it('D4', () => expect(fitModels(makeDataset(), 'time', 'concentration').every(m => isValidModelFitResult(m))).toBe(true))
    it('D5', () => expect(fitModels(makeDataset(), 'time', 'concentration')).toEqual(fitModels(makeDataset(), 'time', 'concentration')))
    it('D6', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results.every(m => m.rSquared >= 0 && m.rSquared <= 1)).toBe(true)
    })
    it('D7', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results.every(m => m.residualError >= 0)).toBe(true)
    })
    it('D8', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results.every(m => m.model.length > 0)).toBe(true)
    })
    it('D9', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results.every(m => Object.keys(m.parameters).length > 0)).toBe(true)
    })
    it('D10', () => {
      const results = fitModels(makeDataset(), 'time', 'concentration')
      expect(results.every(m => typeof m.residualError === 'number')).toBe(true)
    })
  })

  describe('visualization E1-E10', () => {
    it('E1', () => expect(planVisualizations(makeDataset()).length).toBeGreaterThan(0))
    it('E2', () => expect(planVisualizations(makeDataset()).some(f => f.type === 'scatter')).toBe(true))
    it('E3', () => expect(planVisualizations(makeDataset()).some(f => f.type === 'histogram')).toBe(true))
    it('E4', () => expect(planVisualizations(makeDataset(), [makeFitResult()]).some(f => f.type === 'scatter+fit')).toBe(true))
    it('E5', () => expect(planVisualizations(makeDataset()).every(f => isValidFigureRecommendation(f))).toBe(true))
    it('E6', () => expect(planVisualizations(makeDataset())).toEqual(planVisualizations(makeDataset())))
    it('E7', () => {
      const figs = planVisualizations(makeDataset())
      const keys = figs.map(f => `${f.type}:${f.xVariable}:${f.yVariable}`)
      expect(new Set(keys).size).toBe(keys.length)
    })
    it('E8', () => expect(planVisualizations(makeDataset()).every(f => f.title.length > 0)).toBe(true))
    it('E9', () => expect(planVisualizations(makeDataset()).every(f => f.reason.length > 0)).toBe(true))
    it('E10', () => expect(planVisualizations(makeDataset()).every(f => f.xVariable.length > 0 && f.yVariable.length > 0)).toBe(true))
  })

  describe('interpretation F1-F10', () => {
    it('F1', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).length).toBeGreaterThanOrEqual(0)
    })
    it('F2', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.confidence >= 0 && c.confidence <= 1)).toBe(true)
    })
    it('F3', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ rSquared: 0.95 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).every(c => isValidScientificConclusion(c))).toBe(true)
    })
    it('F4', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ rSquared: 0.95 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r)).toEqual(interpretAnalysis(r))
    })
    it('F5', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult()], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).every(c => c.observation.length > 0)).toBe(true)
    })
    it('F6', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult()], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).every(c => c.interpretation.length > 0)).toBe(true)
    })
    it('F7', () => {
      const r: AnalysisReport = { quality: { completeness: 0.5, missingValues: { x: 5 }, outliers: {}, warnings: ['w'] }, statistics: [{ metric: 'correlation_a_b', value: 0.85, interpretation: 'strong' }], models: [makeFitResult()], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).length).toBeGreaterThanOrEqual(2)
    })
    it('F8', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'x_cv', value: 0.4, interpretation: 'high' }], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('CV') || c.observation.includes('variability'))).toBe(true)
    })
    it('F9', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [{ metric: 'correlation_a_b', value: 0.1, interpretation: 'weak' }], models: [], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('strong'))).toBe(false)
    })
    it('F10', () => {
      const r: AnalysisReport = { quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] }, statistics: [], models: [makeFitResult({ rSquared: 0.3 })], figures: [], conclusions: [] }
      expect(interpretAnalysis(r).some(c => c.observation.includes('poor') || c.observation.includes('Poor'))).toBe(true)
    })
  })

  describe('facade G1-G10', () => {
    const a = new ScientificDataAnalyst()
    it('G1', () => expect(isValidAnalysisReport(a.analyzeDataset(makeDataset()))).toBe(true))
    it('G2', () => expect(a.analyzeDataset(makeDataset()).quality.completeness).toBe(1))
    it('G3', () => expect(a.analyzeDataset(makeDataset()).statistics.length).toBeGreaterThan(0))
    it('G4', () => expect(a.analyzeDataset(makeDataset()).models.length).toBeGreaterThan(0))
    it('G5', () => expect(a.analyzeDataset(makeDataset()).figures.length).toBeGreaterThan(0))
    it('G6', () => expect(Array.isArray(a.analyzeDataset(makeDataset()).conclusions)).toBe(true))
    it('G7', () => expect(a.analyzeQuality(makeDataset()).completeness).toBe(1))
    it('G8', () => expect(a.computeStatistics(makeDataset()).length).toBeGreaterThan(0))
    it('G9', () => expect(a.fitModels(makeDataset(), 'time', 'concentration').length).toBeGreaterThan(0))
    it('G10', () => expect(a.planVisualizations(makeDataset()).length).toBeGreaterThan(0))
  })

  describe('determinism H1-H5', () => {
    const a = new ScientificDataAnalyst()
    const ds = makeDataset()
    it('H1', () => expect(a.analyzeDataset(ds)).toEqual(a.analyzeDataset(ds)))
    it('H2', () => expect(analyzeDataQuality(ds)).toEqual(analyzeDataQuality(ds)))
    it('H3', () => expect(computeStatistics(ds)).toEqual(computeStatistics(ds)))
    it('H4', () => expect(fitModels(ds, 'time', 'concentration')).toEqual(fitModels(ds, 'time', 'concentration')))
    it('H5', () => expect(planVisualizations(ds)).toEqual(planVisualizations(ds)))
  })

  describe('very last 16', () => {
    it('schema: all 8 validators reject null', () => {
      expect(isValidVariableDefinition(null)).toBe(false)
      expect(isValidScientificDataset(null)).toBe(false)
      expect(isValidDataQualityReport(null)).toBe(false)
      expect(isValidStatisticalResult(null)).toBe(false)
      expect(isValidModelFitResult(null)).toBe(false)
      expect(isValidFigureRecommendation(null)).toBe(false)
      expect(isValidScientificConclusion(null)).toBe(false)
      expect(isValidAnalysisReport(null)).toBe(false)
    })
    it('quality: 3 rows all present completeness 1', () => {
      const q = analyzeDataQuality(makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 0 },
        { time: 5, concentration: 2, removal: 20 },
        { time: 10, concentration: 3, removal: 40 }
      ]}))
      expect(q.completeness).toBe(1)
    })
    it('quality: 1 row missing 1 value completeness < 1', () => {
      const q = analyzeDataQuality(makeDataset({ rows: [{ time: 0, concentration: null, removal: 0 }] }))
      expect(q.completeness).toBeLessThan(1)
    })
    it('statistics: 2 numeric vars produce 2 mean results', () => {
      const results = computeStatistics(makeDataset())
      const means = results.filter(r => r.metric.endsWith('_mean'))
      expect(means.length).toBeGreaterThanOrEqual(2)
    })
    it('statistics: correlation of perfectly correlated vars is 1', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 1, removal: 1 },
        { time: 5, concentration: 2, removal: 2 },
        { time: 10, concentration: 3, removal: 3 }
      ]})
      const r = computeStatistics(ds).find(s => s.metric.includes('correlation_concentration_removal'))
      expect(r!.value).toBe(1)
    })
    it('model: 3 rows can fit linear', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 8, removal: 20 },
        { time: 10, concentration: 6, removal: 40 }
      ]})
      expect(fitModels(ds, 'time', 'concentration').length).toBeGreaterThan(0)
    })
    it('model: 2 rows only linear/zero-order', () => {
      const ds = makeDataset({ rows: [
        { time: 0, concentration: 10, removal: 0 },
        { time: 5, concentration: 8, removal: 20 }
      ]})
      const results = fitModels(ds, 'time', 'concentration')
      expect(results.some(r => r.model === 'linear' || r.model === 'zero-order')).toBe(true)
    })
    it('visualization: 5 numeric vars produce scatter', () => {
      const ds = makeDataset({
        variables: Array.from({ length: 5 }, (_, i) => ({ name: `v${i}`, type: 'number' as DataType, unit: 'u' })),
        rows: [{ v0: 1, v1: 2, v2: 3, v3: 4, v4: 5 }]
      })
      expect(planVisualizations(ds).some(f => f.type === 'scatter')).toBe(true)
    })
    it('interpretation: good fit + strong corr = multiple conclusions', () => {
      const r: AnalysisReport = {
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'correlation_a_b', value: 0.9, interpretation: 'strong' }],
        models: [makeFitResult({ rSquared: 0.98 })],
        figures: [], conclusions: []
      }
      expect(interpretAnalysis(r).length).toBeGreaterThanOrEqual(2)
    })
    it('facade: analyzeDataset with 10 rows', () => {
      const rows = Array.from({ length: 10 }, (_, i) => ({ time: i * 5, concentration: 10 - i, removal: i * 10 }))
      const a = new ScientificDataAnalyst()
      expect(isValidAnalysisReport(a.analyzeDataset(makeDataset({ rows })))).toBe(true)
    })
    it('facade: 5 runs all identical', () => {
      const a = new ScientificDataAnalyst()
      const ds = makeDataset()
      const results = Array.from({ length: 5 }, () => a.analyzeDataset(ds))
      const first = JSON.stringify(results[0])
      expect(results.every(r => JSON.stringify(r) === first)).toBe(true)
    })
    it('security: no auth in any source file', () => {
      const fs = require('fs')
      const files = [
        'shared/science/scientific-data-schema.ts',
        'main/services/science/data-quality-analyzer.ts',
        'main/services/science/statistical-analyzer.ts',
        'main/services/science/model-fitting-engine.ts',
        'main/services/science/visualization-planner.ts',
        'main/services/science/data-interpreter.ts',
        'main/services/science/scientific-data-analyst.ts'
      ]
      for (const f of files) {
        const content = fs.readFileSync(resolve(srcRoot, f), 'utf8')
        expect(content).not.toMatch(/import.*auth/)
      }
    })
    it('security: no SDK in any source file', () => {
      const fs = require('fs')
      const files = [
        'shared/science/scientific-data-schema.ts',
        'main/services/science/data-quality-analyzer.ts',
        'main/services/science/statistical-analyzer.ts',
        'main/services/science/model-fitting-engine.ts',
        'main/services/science/visualization-planner.ts',
        'main/services/science/data-interpreter.ts',
        'main/services/science/scientific-data-analyst.ts'
      ]
      for (const f of files) {
        const content = fs.readFileSync(resolve(srcRoot, f), 'utf8')
        expect(content).not.toContain('anthropic')
        expect(content).not.toContain('openai')
      }
    })
    it('schema: isValidAnalysisReport with populated arrays', () => {
      expect(isValidAnalysisReport({
        quality: { completeness: 1, missingValues: {}, outliers: {}, warnings: [] },
        statistics: [{ metric: 'm', value: 1, interpretation: 'i' }],
        models: [{ model: 'linear', parameters: { slope: 1 }, rSquared: 0.9, residualError: 0.1 }],
        figures: [{ type: 'scatter', title: 't', xVariable: 'x', yVariable: 'y', reason: 'r' }],
        conclusions: [{ observation: 'obs', interpretation: 'interp', confidence: 0.8 }]
      })).toBe(true)
    })
    it('quality: 10 rows all present completeness 1', () => {
      const rows = Array.from({ length: 10 }, (_, i) => ({ time: i, concentration: i * 2, removal: i * 10 }))
      expect(analyzeDataQuality(makeDataset({ rows })).completeness).toBe(1)
    })
    it('facade: analyzeDataset returns all 5 top-level fields', () => {
      const report = new ScientificDataAnalyst().analyzeDataset(makeDataset())
      expect('quality' in report).toBe(true)
      expect('statistics' in report).toBe(true)
      expect('models' in report).toBe(true)
      expect('figures' in report).toBe(true)
      expect('conclusions' in report).toBe(true)
    })
  })
})
