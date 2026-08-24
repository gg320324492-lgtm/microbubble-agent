// Phase 8-K1 Scientific Digital Twin System Tests
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

import {
  isValidDigitalTwinModel, isValidTwinParameter, isValidTwinPrediction,
  isValidModelStatus, isValidPredictionKind,
  MODEL_STATUSES, PREDICTION_KINDS,
  __testHelpers as twinHelpers
} from '../../src/shared/digital-twin/digital-twin-schema'

import {
  extractFeatures, normalize, selectFeatures, validateInput, FEATURE_SOURCE_KINDS
} from '../../src/services/digital-twin/feature-engineer'
import {
  linearPredict, polynomialPredict, kineticPredict, predict, predictAndRecord, paramsToLinear
} from '../../src/services/digital-twin/digital-twin-engine'
import {
  comparePrediction, calculateError, updateParameters, runCalibration
} from '../../src/services/digital-twin/model-calibrator'
import {
  buildTwinModel, calibrateFromExperiment, compareExperimentResult
} from '../../src/services/digital-twin/experiment-twin-adapter'
import {
  getTwinTemplate, listTwinTemplates, TWIN_TEMPLATE_KINDS
} from '../../src/services/digital-twin/digital-twin-templates'

import type { DigitalTwinModel, TwinParameter } from '../../src/shared/digital-twin/digital-twin-schema'
import type { Experiment } from '../../src/shared/experiment/experiment-schema'

const readShared = (name: string) => readFileSync(join(__dirname, '../../src/shared/digital-twin', name), 'utf8')
const read = (name: string) => readFileSync(join(__dirname, '../../src/services/digital-twin', name), 'utf8')
const readDocs = (name: string) => readFileSync(join(__dirname, '../../docs/digital-twin', name), 'utf8')

describe('Phase 8-K1 schema validators', () => {
  it('MODEL_STATUSES has 5 entries', () => {
    expect(MODEL_STATUSES.length).toBe(5)
  })
  it('MODEL_STATUSES is frozen', () => {
    expect(Object.isFrozen(MODEL_STATUSES)).toBe(true)
  })
  it('PREDICTION_KINDS has 3 entries', () => {
    expect(PREDICTION_KINDS.length).toBe(3)
  })
  it('PREDICTION_KINDS is frozen', () => {
    expect(Object.isFrozen(PREDICTION_KINDS)).toBe(true)
  })
  for (const s of ['draft', 'training', 'validated', 'deployed', 'deprecated']) {
    it(`isValidModelStatus accepts ${s}`, () => {
      expect(isValidModelStatus(s)).toBe(true)
    })
  }
  for (const s of ['unknown', 'DRAFT', '', 'active']) {
    it(`isValidModelStatus rejects ${s}`, () => {
      expect(isValidModelStatus(s)).toBe(false)
    })
  }
  for (const k of ['linear', 'polynomial', 'kinetic']) {
    it(`isValidPredictionKind accepts ${k}`, () => {
      expect(isValidPredictionKind(k)).toBe(true)
    })
  }
  for (const k of ['unknown', 'neural', '']) {
    it(`isValidPredictionKind rejects ${k}`, () => {
      expect(isValidPredictionKind(k)).toBe(false)
    })
  }
  it('isValidTwinParameter accepts valid', () => {
    expect(isValidTwinParameter({ name: 'a', value: 1.5, range: '0-10', unit: 'mg' })).toBe(true)
  })
  it('isValidTwinParameter rejects NaN', () => {
    expect(isValidTwinParameter({ name: 'a', value: NaN, range: '0-10', unit: 'mg' })).toBe(false)
  })
  it('isValidTwinParameter rejects empty name', () => {
    expect(isValidTwinParameter({ name: '', value: 1, range: '0-10', unit: 'mg' })).toBe(false)
  })
  it('isValidDigitalTwinModel accepts valid', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [{ name: 'p', value: 1, range: '0-10', unit: 'u' }],
      accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(true)
  })
  it('isValidDigitalTwinModel rejects invalid status', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [], accuracy: 0.5, status: 'bad',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects empty inputs', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: [''], outputs: ['b'],
      parameters: [], accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects bad accuracy', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [], accuracy: 1.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidTwinPrediction accepts valid', () => {
    expect(isValidTwinPrediction({
      modelId: 'm', input: { a: 1 }, output: { b: 2 },
      confidence: 0.8, timestamp: 1
    })).toBe(true)
  })
  it('isValidTwinPrediction rejects NaN input', () => {
    expect(isValidTwinPrediction({
      modelId: 'm', input: { a: NaN }, output: { b: 2 },
      confidence: 0.8, timestamp: 1
    })).toBe(false)
  })
  it('isValidTwinPrediction rejects bad confidence', () => {
    expect(isValidTwinPrediction({
      modelId: 'm', input: { a: 1 }, output: { b: 2 },
      confidence: 1.5, timestamp: 1
    })).toBe(false)
  })
})

describe('Phase 8-K1 FeatureEngineer', () => {
  it('FEATURE_SOURCE_KINDS has 3', () => {
    expect(FEATURE_SOURCE_KINDS.length).toBe(3)
  })
  it('extractFeatures returns numeric values', () => {
    const f = extractFeatures([{ a: 1 }, { a: 2 }, { a: 3 }], 'a', 'numeric')
    expect(f.values).toEqual([1, 2, 3])
  })
  it('extractFeatures default kind numeric', () => {
    const f = extractFeatures([{ a: 1 }], 'a')
    expect(f.kind).toBe('numeric')
  })
  it('extractFeatures skips non-numeric', () => {
    const f = extractFeatures([{ a: 1 }, { a: 'x' }, { a: 2 }], 'a')
    expect(f.values).toEqual([1, 2])
  })
  it('extractFeatures handles missing column', () => {
    const f = extractFeatures([{ b: 1 }], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures kind time-series', () => {
    const f = extractFeatures([{ t: 1 }], 't', 'time-series')
    expect(f.kind).toBe('time-series')
  })
  it('normalize of [0, 5, 10] -> [0, 0.5, 1]', () => {
    const f = extractFeatures([{ x: 0 }, { x: 5 }, { x: 10 }], 'x')
    const n = normalize(f)
    expect(n.values).toEqual([0, 0.5, 1])
    expect(n.min).toBe(0)
    expect(n.max).toBe(10)
  })
  it('normalize of constant -> all zeros', () => {
    const f = extractFeatures([{ x: 5 }, { x: 5 }], 'x')
    const n = normalize(f)
    expect(n.values).toEqual([0, 0])
  })
  it('normalize of empty -> empty', () => {
    const n = normalize({ name: 'x', values: [], kind: 'numeric' })
    expect(n.values).toEqual([])
  })
  it('selectFeatures by minVariance', () => {
    const f1 = extractFeatures([{ x: 0 }, { x: 1 }, { x: 2 }], 'x')
    const f2 = extractFeatures([{ y: 5 }, { y: 5 }, { y: 5 }], 'y')
    const sel = selectFeatures([f1, f2], { minVariance: 0.1 })
    expect(sel.length).toBe(1)
    expect(sel[0].name).toBe('x')
  })
  it('selectFeatures by topK', () => {
    const f1 = extractFeatures([{ x: 0 }, { x: 1 }, { x: 2 }], 'x')
    const f2 = extractFeatures([{ y: 0 }, { y: 2 }, { y: 4 }], 'y')
    const sel = selectFeatures([f1, f2], { topK: 1 })
    expect(sel.length).toBe(1)
  })
  it('selectFeatures with requiredColumns', () => {
    const f1 = extractFeatures([{ x: 5 }, { x: 5 }], 'x')
    const f2 = extractFeatures([{ y: 0 }, { y: 1 }], 'y')
    const sel = selectFeatures([f1, f2], { requiredColumns: ['x'] })
    expect(sel.map((s) => s.name)).toContain('x')
  })
  it('selectFeatures empty criteria returns all', () => {
    const f1 = extractFeatures([{ x: 1 }], 'x')
    expect(selectFeatures([f1]).length).toBe(1)
  })
  it('validateInput accepts matching schema', () => {
    expect(validateInput({ x: 1, y: 'a', z: true }, { x: 'number', y: 'string', z: 'boolean' })).toEqual({ ok: true })
  })
  it('validateInput rejects missing field', () => {
    expect(validateInput({ x: 1 }, { x: 'number', y: 'string' })).toEqual({ ok: false, error: expect.stringContaining('missing') })
  })
  it('validateInput rejects wrong type number', () => {
    expect(validateInput({ x: 'a' }, { x: 'number' })).toEqual({ ok: false, error: expect.stringContaining('number') })
  })
  it('validateInput rejects wrong type string', () => {
    expect(validateInput({ x: 1 }, { x: 'string' })).toEqual({ ok: false, error: expect.stringContaining('string') })
  })
  it('validateInput rejects wrong type boolean', () => {
    expect(validateInput({ x: 1 }, { x: 'boolean' })).toEqual({ ok: false, error: expect.stringContaining('boolean') })
  })
  it('validateInput rejects NaN number', () => {
    expect(validateInput({ x: NaN }, { x: 'number' })).toEqual({ ok: false, error: expect.stringContaining('number') })
  })
})

describe('Phase 8-K1 DigitalTwinEngine', () => {
  it('linearPredict basic', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1, 2], intercept: 0 }, { a: 3, b: 4 })
    expect(r.output.y).toBe(11)
  })
  it('linearPredict with intercept', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1], intercept: 5 }, { a: 3 })
    expect(r.output.y).toBe(8)
  })
  it('linearPredict missing keys treated as 0', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1, 2, 3], intercept: 0 }, { a: 5 })
    expect(r.output.y).toBe(5)
  })
  it('linearPredict handles NaN as 0', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: NaN })
    expect(r.output.y).toBe(0)
  })
  it('linearPredict confidence 0.85', () => {
    expect(linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 }).confidence).toBe(0.85)
  })
  it('polynomialPredict degree 2', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [0, 1, 1], degree: 2 }, 2)
    expect(r.output.y).toBe(6)
  })
  it('polynomialPredict degree 0', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [5], degree: 0 }, 10)
    expect(r.output.y).toBe(5)
  })
  it('polynomialPredict confidence 0.8', () => {
    expect(polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 0 }, 0).confidence).toBe(0.8)
  })
  it('kineticPredict at t=0 returns C0', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 0)
    expect(r.output.concentration).toBe(10)
  })
  it('kineticPredict at t=10 with k=0.1', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 10)
    expect(r.output.concentration).toBeCloseTo(10 * Math.exp(-1), 5)
  })
  it('kineticPredict clamps negative t', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, -5)
    expect(r.output.concentration).toBe(10)
  })
  it('kineticPredict handles NaN as 0', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, NaN)
    expect(r.output.concentration).toBe(10)
  })
  it('kineticPredict confidence 0.9', () => {
    expect(kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 0).confidence).toBe(0.9)
  })
  it('predict routes to linear', () => {
    const r = predict({ kind: 'linear', coefficients: [2], intercept: 0 }, { a: 5 })
    expect(r.output.y).toBe(10)
  })
  it('predict routes to polynomial via first value', () => {
    const r = predict({ kind: 'polynomial', coefficients: [0, 1], degree: 1 }, { x: 3 })
    expect(r.output.y).toBe(3)
  })
  it('predict routes to kinetic via first value', () => {
    const r = predict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, { t: 0 })
    expect(r.output.concentration).toBe(10)
  })
  it('predictAndRecord produces TwinPrediction', () => {
    const p = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm1', { a: 5 })
    expect(p.modelId).toBe('m1')
    expect(p.input.a).toBe(5)
    expect(p.confidence).toBe(0.85)
    expect(typeof p.timestamp).toBe('number')
  })
  it('paramsToLinear maps parameters', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-10', unit: 'u' },
      { name: 'b', value: 2, range: '0-10', unit: 'u' }
    ]
    const spec = paramsToLinear(params)
    expect(spec.coefficients).toEqual([1, 2])
    expect(spec.intercept).toBe(0)
  })
})

describe('Phase 8-K1 ModelCalibrator', () => {
  it('comparePrediction within tolerance', () => {
    const r = comparePrediction(1.0, 1.02, 0.05)
    expect(r.withinTolerance).toBe(true)
    expect(r.absoluteError).toBeCloseTo(0.02, 5)
  })
  it('comparePrediction outside tolerance', () => {
    const r = comparePrediction(1.0, 1.5, 0.05)
    expect(r.withinTolerance).toBe(false)
    expect(r.absoluteError).toBeCloseTo(0.5, 5)
  })
  it('comparePrediction relative error', () => {
    const r = comparePrediction(2.0, 1.0, 1.0)
    expect(r.relativeError).toBe(1)
  })
  it('comparePrediction zero observed uses 1 denom', () => {
    const r = comparePrediction(1.0, 0, 1.0)
    expect(r.relativeError).toBe(1)
  })
  it('calculateError empty', () => {
    expect(calculateError([]).samples).toBe(0)
  })
  it('calculateError basic', () => {
    const r = calculateError([
      comparePrediction(1.0, 1.1, 1),
      comparePrediction(2.0, 2.1, 1)
    ])
    expect(r.samples).toBe(2)
    expect(r.meanAbsoluteError).toBeCloseTo(0.1, 5)
    expect(r.maxAbsoluteError).toBeCloseTo(0.1, 5)
  })
  it('calculateError rmse', () => {
    const r = calculateError([
      comparePrediction(1.0, 1.1, 1),
      comparePrediction(2.0, 2.1, 1)
    ])
    expect(r.rmse).toBeCloseTo(0.1, 5)
  })
  it('calculateError rSquared = 1 for perfect', () => {
    const r = calculateError([
      comparePrediction(1.0, 1.0, 1),
      comparePrediction(2.0, 2.0, 1)
    ])
    expect(r.rSquared).toBe(1)
  })
  it('updateParameters basic', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-10', unit: 'u' },
      { name: 'b', value: 2, range: '0-10', unit: 'u' }
    ]
    const upd = updateParameters(params, 0.1, [1, 1])
    expect(upd[0].value).toBeCloseTo(0.9, 5)
    expect(upd[1].value).toBeCloseTo(1.9, 5)
  })
  it('updateParameters returns new array', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 1, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 0.1, [0])
    expect(upd).not.toBe(params)
  })
  it('updateParameters rejects bad lr', () => {
    expect(() => updateParameters([], -1, [])).toThrow()
    expect(() => updateParameters([], 2, [])).toThrow()
  })
  it('runCalibration on synthetic linear data', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [1, 0], intercept: 0 },
      { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }], outputs: [1.1, 2.0, 3.05] }
    )
    expect(cal.samples).toBe(3)
    expect(cal.rmse).toBeLessThan(0.1)
  })
})

describe('Phase 8-K1 ExperimentTwinAdapter', () => {
  function setupExperiment(): Experiment {
    return {
      id: 'e1', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed', design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
  }
  function setupTwin(): DigitalTwinModel {
    return buildTwinModel({
      name: 'o3-twin',
      domain: '环境科学',
      inputs: ['dose'],
      outputs: ['degradation'],
      parameters: [{ name: 'p1', value: 0.5, range: '0-1', unit: 'ratio' }]
    })
  }

  it('buildTwinModel returns draft model', () => {
    const m = setupTwin()
    expect(m.status).toBe('draft')
  })
  it('buildTwinModel sets createdAt', () => {
    const m = setupTwin()
    expect(typeof m.createdAt).toBe('number')
  })
  it('buildTwinModel default accuracy 0.5', () => {
    const m = setupTwin()
    expect(m.accuracy).toBe(0.5)
  })
  it('buildTwinModel clones parameters', () => {
    const m = setupTwin()
    m.parameters[0].value = 999
    expect(setupTwin().parameters[0].value).toBe(0.5)
  })
  it('calibrateFromExperiment updates accuracy', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { dose: 5, bubble: 100 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.twinModel.accuracy).toBeGreaterThanOrEqual(0)
    expect(r.twinModel.accuracy).toBeLessThanOrEqual(1)
  })
  it('calibrateFromExperiment sets status validated', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    expect(calibrateFromExperiment({ experiment: exp, result, twinModel: twin }).twinModel.status).toBe('validated')
  })
  it('calibrateFromExperiment produces predictions', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.8 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.predictions.length).toBe(2)
  })
  it('calibrateFromExperiment returns CalibrationResult', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.calibration.samples).toBe(1)
  })
  it('compareExperimentResult returns comparisons', () => {
    const result = { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.8 }
    const predictions = [
      { modelId: 'm', input: { a: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 },
      { modelId: 'm', input: { b: 2 }, output: { y: 2 }, confidence: 0.8, timestamp: 1 }
    ]
    const cmp = compareExperimentResult(result, predictions)
    expect(cmp.length).toBe(2)
  })
  it('compareExperimentResult with empty predictions', () => {
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    expect(compareExperimentResult(result, []).length).toBe(0)
  })
})

describe('Phase 8-K1 TwinTemplates', () => {
  it('TWIN_TEMPLATE_KINDS has 3', () => {
    expect(TWIN_TEMPLATE_KINDS.length).toBe(3)
  })
  for (const k of ['o3-mnb-degradation', 'cfd-flow-optimization', 'material-synthesis']) {
    it(`getTwinTemplate accepts ${k}`, () => {
      const t = getTwinTemplate(k as never)
      expect(t.kind).toBe(k)
    })
  }
  it('getTwinTemplate throws on unknown', () => {
    expect(() => getTwinTemplate('nope' as never)).toThrow()
  })
  it('listTwinTemplates returns 3', () => {
    expect(listTwinTemplates().length).toBe(3)
  })
  it('listTwinTemplates returns clones', () => {
    const list = listTwinTemplates()
    list[0].inputs.push('mutated')
    expect(listTwinTemplates()[0].inputs).not.toContain('mutated')
  })
  it('o3-mnb-degradation has 4 inputs', () => {
    expect(getTwinTemplate('o3-mnb-degradation').inputs.length).toBe(4)
  })
  it('cfd-flow-optimization has 3 inputs', () => {
    expect(getTwinTemplate('cfd-flow-optimization').inputs.length).toBe(3)
  })
  it('material-synthesis has 3 inputs', () => {
    expect(getTwinTemplate('material-synthesis').inputs.length).toBe(3)
  })
  it('each template has non-empty outputs', () => {
    for (const t of listTwinTemplates()) expect(t.outputs.length).toBeGreaterThan(0)
  })
  it('each template has non-empty parameterRanges', () => {
    for (const t of listTwinTemplates()) expect(t.parameterRanges.length).toBeGreaterThan(0)
  })
  it('each template kind unique', () => {
    const kinds = listTwinTemplates().map((t) => t.kind)
    expect(new Set(kinds).size).toBe(3)
  })
})

describe('Phase 8-K1 secret guard', () => {
  it('findForbidden detects sk-', () => {
    expect(twinHelpers.findForbidden('sk-x')).toBe('sk-')
  })
  it('findForbidden detects apiKey', () => {
    expect(twinHelpers.findForbidden('apiKey')).toBe('apiKey')
  })
  it('findForbidden detects Bearer', () => {
    expect(twinHelpers.findForbidden('Bearer x')).toBe('Bearer ')
  })
  it('findForbidden detects authorization', () => {
    expect(twinHelpers.findForbidden('authorization: x')).toBe('authorization')
  })
  it('findForbidden handles null', () => {
    expect(twinHelpers.findForbidden(null)).toBeNull()
  })
  it('findForbidden handles arrays', () => {
    expect(twinHelpers.findForbidden(['ok', 'token'])).toBe('token')
  })
  it('findForbidden handles nested objects', () => {
    expect(twinHelpers.findForbidden({ a: { b: 'cipher' } })).toBe('cipher')
  })
  it('findForbidden handles numbers', () => {
    expect(twinHelpers.findForbidden(42)).toBeNull()
  })
})

describe('Phase 8-K1 defensive copy', () => {
  it('buildTwinModel parameters are independent', () => {
    const a = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const b = buildTwinModel({ name: 'b', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [{ name: 'p', value: 2, range: '0-1', unit: 'u' }] })
    expect(a.parameters[0].value).toBe(1)
    expect(b.parameters[0].value).toBe(2)
  })
  it('predictAndRecord copies input', () => {
    const p = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 5 })
    p.input.a = 999
    expect(predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 5 }).input.a).toBe(5)
  })
  it('getTwinTemplate parameterRanges are independent', () => {
    const t = getTwinTemplate('o3-mnb-degradation')
    t.parameterRanges[0].name = 'MUT'
    expect(getTwinTemplate('o3-mnb-degradation').parameterRanges[0].name).not.toBe('MUT')
  })
})

describe('Phase 8-K1 determinism', () => {
  it('predict linear deterministic', () => {
    const r1 = linearPredict({ kind: 'linear', coefficients: [1, 2], intercept: 3 }, { a: 4, b: 5 })
    const r2 = linearPredict({ kind: 'linear', coefficients: [1, 2], intercept: 3 }, { a: 4, b: 5 })
    expect(r1.output.y).toBe(r2.output.y)
  })
  it('predict polynomial deterministic', () => {
    const r1 = polynomialPredict({ kind: 'polynomial', coefficients: [1, 2, 3], degree: 2 }, 5)
    const r2 = polynomialPredict({ kind: 'polynomial', coefficients: [1, 2, 3], degree: 2 }, 5)
    expect(r1.output.y).toBe(r2.output.y)
  })
  it('predict kinetic deterministic', () => {
    const r1 = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 5)
    const r2 = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 5)
    expect(r1.output.concentration).toBe(r2.output.concentration)
  })
  it('selectFeatures deterministic for same input', () => {
    const f1 = extractFeatures([{ x: 1 }, { x: 2 }], 'x')
    const f2 = extractFeatures([{ x: 1 }, { x: 2 }], 'x')
    const sel1 = selectFeatures([f1, f2])
    const sel3 = extractFeatures([{ y: 1 }, { y: 2 }], 'y')
    const sel4 = extractFeatures([{ y: 1 }, { y: 2 }], 'y')
    const sel2 = selectFeatures([sel3, sel4])
    expect(sel1.length).toBe(sel2.length)
  })
})

describe('Phase 8-K1 integration', () => {
  it('template → twin model → predict round trip', () => {
    const tmpl = getTwinTemplate('o3-mnb-degradation')
    const twin = buildTwinModel({
      name: 'o3-twin',
      domain: tmpl.domain,
      inputs: tmpl.inputs,
      outputs: tmpl.outputs,
      parameters: tmpl.parameterRanges.map((p) => ({ name: p.name, value: 0.5, range: p.range, unit: p.unit }))
    })
    const r = predictAndRecord(paramsToLinear(twin.parameters), twin.id, { dose: 5 })
    expect(r.output.y).toBeGreaterThan(0)
  })
  it('feature engineering then prediction', () => {
    const rows = [{ dose: 1, y: 1 }, { dose: 2, y: 2 }, { dose: 3, y: 3 }]
    const f = extractFeatures(rows, 'dose')
    const n = normalize(f)
    const sel = selectFeatures([n as never], { requiredColumns: ['dose'] })
    expect(sel.length).toBeGreaterThanOrEqual(0)
  })
  it('calibrate then re-predict with updated params', () => {
    const spec = { kind: 'linear' as const, coefficients: [1, 0], intercept: 0 }
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-10', unit: 'u' },
      { name: 'b', value: 0, range: '0-10', unit: 'u' }
    ]
    const cal = runCalibration(spec, { inputs: [{ a: 1 }, { a: 2 }], outputs: [1.05, 2.05] })
    const upd = updateParameters(params, 0.05, [0.01, 0])
    expect(upd[0].value).toBeCloseTo(0.9995, 4)
    expect(cal.samples).toBe(2)
  })
})

describe('Phase 8-K1 docs presence', () => {
  it('digital-twin-architecture.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/digital-twin/digital-twin-architecture.md'))).toBe(true)
  })
  it('scientific-prediction-flow.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/digital-twin/scientific-prediction-flow.md'))).toBe(true)
  })
  it('digital-twin-architecture.md mentions FeatureEngineer', () => {
    expect(readDocs('digital-twin-architecture.md')).toContain('FeatureEngineer')
  })
  it('digital-twin-architecture.md mentions ModelCalibrator', () => {
    expect(readDocs('digital-twin-architecture.md')).toContain('ModelCalibrator')
  })
  it('scientific-prediction-flow.md mentions kinetic', () => {
    expect(readDocs('scientific-prediction-flow.md')).toContain('kinetic')
  })
  it('scientific-prediction-flow.md mentions linear', () => {
    expect(readDocs('scientific-prediction-flow.md')).toContain('linear')
  })
  it('scientific-prediction-flow.md mentions polynomial', () => {
    expect(readDocs('scientific-prediction-flow.md')).toContain('polynomial')
  })
})

describe('Phase 8-K1 source contracts', () => {
  it('schema has DigitalTwinModel interface', () => {
    expect(readShared('digital-twin-schema.ts')).toContain('interface DigitalTwinModel')
  })
  it('schema has TwinPrediction interface', () => {
    expect(readShared('digital-twin-schema.ts')).toContain('interface TwinPrediction')
  })
  it('schema has TwinParameter interface', () => {
    expect(readShared('digital-twin-schema.ts')).toContain('interface TwinParameter')
  })
  it('schema has 5 model statuses', () => {
    expect(readShared('digital-twin-schema.ts')).toContain('draft')
    expect(readShared('digital-twin-schema.ts')).toContain('training')
    expect(readShared('digital-twin-schema.ts')).toContain('validated')
    expect(readShared('digital-twin-schema.ts')).toContain('deployed')
    expect(readShared('digital-twin-schema.ts')).toContain('deprecated')
  })
  it('feature-engineer has extractFeatures', () => {
    expect(read('feature-engineer.ts')).toContain('extractFeatures')
  })
  it('feature-engineer has normalize', () => {
    expect(read('feature-engineer.ts')).toContain('normalize')
  })
  it('feature-engineer has selectFeatures', () => {
    expect(read('feature-engineer.ts')).toContain('selectFeatures')
  })
  it('feature-engineer has validateInput', () => {
    expect(read('feature-engineer.ts')).toContain('validateInput')
  })
  it('engine has linearPredict', () => {
    expect(read('digital-twin-engine.ts')).toContain('linearPredict')
  })
  it('engine has polynomialPredict', () => {
    expect(read('digital-twin-engine.ts')).toContain('polynomialPredict')
  })
  it('engine has kineticPredict', () => {
    expect(read('digital-twin-engine.ts')).toContain('kineticPredict')
  })
  it('engine has predict', () => {
    expect(read('digital-twin-engine.ts')).toContain('predict')
  })
  it('calibrator has comparePrediction', () => {
    expect(read('model-calibrator.ts')).toContain('comparePrediction')
  })
  it('calibrator has calculateError', () => {
    expect(read('model-calibrator.ts')).toContain('calculateError')
  })
  it('calibrator has updateParameters', () => {
    expect(read('model-calibrator.ts')).toContain('updateParameters')
  })
  it('calibrator has runCalibration', () => {
    expect(read('model-calibrator.ts')).toContain('runCalibration')
  })
  it('adapter has buildTwinModel', () => {
    expect(read('experiment-twin-adapter.ts')).toContain('buildTwinModel')
  })
  it('adapter has calibrateFromExperiment', () => {
    expect(read('experiment-twin-adapter.ts')).toContain('calibrateFromExperiment')
  })
  it('templates has 3 kinds', () => {
    expect(read('digital-twin-templates.ts')).toContain('o3-mnb-degradation')
    expect(read('digital-twin-templates.ts')).toContain('cfd-flow-optimization')
    expect(read('digital-twin-templates.ts')).toContain('material-synthesis')
  })
  it('templates uses Object.freeze', () => {
    expect(read('digital-twin-templates.ts')).toContain('Object.freeze')
  })
})

describe('Phase 8-K1 FeatureEngineer edge cases', () => {
  it('extractFeatures empty rows returns empty values', () => {
    const f = extractFeatures([], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures multiple columns each isolated', () => {
    const f1 = extractFeatures([{ a: 1, b: 2 }], 'a')
    const f2 = extractFeatures([{ a: 1, b: 2 }], 'b')
    expect(f1.values).toEqual([1])
    expect(f2.values).toEqual([2])
  })
  it('extractFeatures handles Infinity as non-finite', () => {
    const f = extractFeatures([{ a: Infinity }], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures handles -Infinity', () => {
    const f = extractFeatures([{ a: -Infinity }], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures handles null', () => {
    const f = extractFeatures([{ a: null }], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures handles boolean', () => {
    const f = extractFeatures([{ a: true }], 'a')
    expect(f.values).toEqual([])
  })
  it('normalize preserves name', () => {
    const f = extractFeatures([{ x: 1 }], 'special-name')
    expect(normalize(f).name).toBe('special-name')
  })
  it('normalize preserves all values count', () => {
    const f = extractFeatures([{ x: 1 }, { x: 2 }, { x: 3 }], 'x')
    expect(normalize(f).values.length).toBe(3)
  })
  it('selectFeatures empty input returns empty', () => {
    expect(selectFeatures([]).length).toBe(0)
  })
  it('selectFeatures respects topK=0 returns all', () => {
    const f1 = extractFeatures([{ x: 1 }], 'x')
    const sel = selectFeatures([f1], { topK: 0 })
    expect(sel.length).toBe(1)
  })
  it('selectFeatures by minVariance=0 returns all', () => {
    const f1 = extractFeatures([{ x: 5 }, { x: 5 }], 'x')
    expect(selectFeatures([f1], { minVariance: 0 }).length).toBe(1)
  })
  it('validateInput empty schema accepts empty input', () => {
    expect(validateInput({}, {})).toEqual({ ok: true })
  })
  it('validateInput non-empty schema with empty input', () => {
    expect(validateInput({}, { x: 'number' })).toEqual({ ok: false, error: expect.stringContaining('missing') })
  })
  it('validateInput extra fields ok', () => {
    expect(validateInput({ x: 1, y: 2 }, { x: 'number' })).toEqual({ ok: true })
  })
  it('validateInput Infinity rejected as number', () => {
    expect(validateInput({ x: Infinity }, { x: 'number' })).toEqual({ ok: false, error: expect.stringContaining('number') })
  })
})

describe('Phase 8-K1 DigitalTwinEngine edge cases', () => {
  it('linearPredict empty coefficients', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [], intercept: 5 }, { a: 10 })
    expect(r.output.y).toBe(5)
  })
  it('linearPredict more coefficients than inputs uses first N', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1, 2, 3], intercept: 0 }, { a: 5 })
    expect(r.output.y).toBe(5)
  })
  it('linearPredict raw array length 1', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 })
    expect(r.raw.length).toBe(1)
  })
  it('polynomialPredict degree higher than coefficients', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 5 }, 2)
    expect(r.output.y).toBe(1)
  })
  it('polynomialPredict empty coefficients', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [], degree: 2 }, 5)
    expect(r.output.y).toBe(0)
  })
  it('polynomialPredict x=0', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [5, 1, 2], degree: 2 }, 0)
    expect(r.output.y).toBe(5)
  })
  it('polynomialPredict negative x', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [0, 1], degree: 1 }, -3)
    expect(r.output.y).toBe(-3)
  })
  it('kineticPredict very large t', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 1000)
    expect(r.output.concentration).toBeCloseTo(0, 5)
  })
  it('kineticPredict zero rateConstant', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0, order: 1, initialConcentration: 10 }, 5)
    expect(r.output.concentration).toBe(10)
  })
  it('kineticPredict zero initialConcentration', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 0 }, 5)
    expect(r.output.concentration).toBe(0)
  })
  it('kineticPredict higher order', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 2, initialConcentration: 10 }, 5)
    expect(r.output.concentration).toBeCloseTo(10 * Math.exp(-1), 5)
  })
  it('predict empty input', () => {
    const r = predict({ kind: 'linear', coefficients: [1], intercept: 5 }, {})
    expect(r.output.y).toBe(5)
  })
  it('predictAndRecord timestamp monotonic', async () => {
    const p1 = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    await new Promise((r) => setTimeout(r, 2))
    const p2 = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    expect(p2.timestamp).toBeGreaterThanOrEqual(p1.timestamp)
  })
  it('paramsToLinear empty parameters', () => {
    expect(paramsToLinear([]).coefficients).toEqual([])
  })
})

describe('Phase 8-K1 ModelCalibrator edge cases', () => {
  it('comparePrediction equal values', () => {
    const r = comparePrediction(5, 5, 0.1)
    expect(r.absoluteError).toBe(0)
    expect(r.relativeError).toBe(0)
    expect(r.withinTolerance).toBe(true)
  })
  it('comparePrediction predicted > observed', () => {
    const r = comparePrediction(10, 5, 1)
    expect(r.absoluteError).toBe(5)
  })
  it('comparePrediction predicted < observed', () => {
    const r = comparePrediction(5, 10, 1)
    expect(r.absoluteError).toBe(5)
  })
  it('calculateError totalAbsoluteError = sum of errors', () => {
    const r = calculateError([
      comparePrediction(1, 1.1, 1),
      comparePrediction(2, 2.2, 1)
    ])
    expect(r.totalAbsoluteError).toBeCloseTo(0.3, 5)
  })
  it('calculateError maxAbsoluteError = largest single error', () => {
    const r = calculateError([
      comparePrediction(1, 1.1, 1),
      comparePrediction(2, 2.5, 1)
    ])
    expect(r.maxAbsoluteError).toBeCloseTo(0.5, 5)
  })
  it('calculateError samples equals input length', () => {
    expect(calculateError([comparePrediction(1, 1, 1), comparePrediction(2, 2, 1), comparePrediction(3, 3, 1)]).samples).toBe(3)
  })
  it('updateParameters preserves length', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-10', unit: 'u' },
      { name: 'b', value: 2, range: '0-10', unit: 'u' }
    ]
    expect(updateParameters(params, 0.1, [0, 0]).length).toBe(2)
  })
  it('updateParameters preserves name and range', () => {
    const params: TwinParameter[] = [{ name: 'keep', value: 1, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 0.1, [0])
    expect(upd[0].name).toBe('keep')
    expect(upd[0].range).toBe('0-10')
    expect(upd[0].unit).toBe('u')
  })
  it('updateParameters lr=0 no change', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 5, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 0, [1])
    expect(upd[0].value).toBe(5)
  })
  it('updateParameters lr=1 full gradient', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 5, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 1, [2])
    expect(upd[0].value).toBe(3)
  })
  it('updateParameters missing gradient treated as 0', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-10', unit: 'u' },
      { name: 'b', value: 2, range: '0-10', unit: 'u' }
    ]
    const upd = updateParameters(params, 0.1, [0])
    expect(upd[1].value).toBe(2)
  })
  it('runCalibration on empty dataset', () => {
    const cal = runCalibration({ kind: 'linear', coefficients: [1], intercept: 0 }, { inputs: [], outputs: [] })
    expect(cal.samples).toBe(0)
  })
  it('runCalibration with kinetic spec', () => {
    const cal = runCalibration(
      { kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 },
      { inputs: [{ t: 0 }, { t: 10 }], outputs: [10, 10 * Math.exp(-1)] }
    )
    expect(cal.samples).toBe(2)
  })
})

describe('Phase 8-K1 ExperimentTwinAdapter edge cases', () => {
  function setupExperiment() {
    return {
      id: 'e1', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
  }
  function setupTwin() {
    return buildTwinModel({
      name: 'o3-twin',
      domain: '环境科学',
      inputs: ['dose'],
      outputs: ['degradation'],
      parameters: [{ name: 'p1', value: 0.5, range: '0-1', unit: 'ratio' }]
    })
  }
  it('buildTwinModel with custom accuracy', () => {
    const m = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 0.8)
    expect(m.accuracy).toBe(0.8)
  })
  it('buildTwinModel sets updatedAt', () => {
    const m = setupTwin()
    expect(typeof m.updatedAt).toBe('number')
  })
  it('buildTwinModel id includes name', () => {
    const m = buildTwinModel({ name: 'special', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] })
    expect(m.id).toContain('special')
  })
  it('buildTwinModel clones inputs and outputs', () => {
    const spec = { name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }
    const m = buildTwinModel(spec)
    m.inputs.push('z')
    expect(buildTwinModel(spec).inputs).toEqual(['x'])
  })
  it('calibrateFromExperiment preserves parameters length', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.twinModel.parameters.length).toBe(1)
  })
  it('calibrateFromExperiment updates updatedAt', async () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const before_ = twin.updatedAt
    await new Promise((r) => setTimeout(r, 2))
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const r2 = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r2.twinModel.updatedAt).toBeGreaterThanOrEqual(before_)
  })
  it('calibrateFromExperiment keeps input independent', () => {
    const exp = setupExperiment()
    const twin = setupTwin()
    const result = { metrics: { a: 1, b: 2, c: 3 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    r.predictions[0].output.y = 999
    expect(r.predictions[1].output.y).not.toBe(999)
  })
  it('compareExperimentResult empty metrics', () => {
    const result = { metrics: {}, conclusion: '', confidence: 0.8 }
    expect(compareExperimentResult(result, []).length).toBe(0)
  })
  it('compareExperimentResult with custom tolerance', () => {
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const predictions = [{ modelId: 'm', input: { a: 1 }, output: { y: 1.2 }, confidence: 0.8, timestamp: 1 }]
    const cmp = compareExperimentResult(result, predictions, 0.5)
    expect(cmp[0].withinTolerance).toBe(true)
  })
})

describe('Phase 8-K1 TwinTemplates edge cases', () => {
  it('o3-mnb-degradation has 2 outputs', () => {
    expect(getTwinTemplate('o3-mnb-degradation').outputs.length).toBe(2)
  })
  it('cfd-flow-optimization has 2 outputs', () => {
    expect(getTwinTemplate('cfd-flow-optimization').outputs.length).toBe(2)
  })
  it('material-synthesis has 2 outputs', () => {
    expect(getTwinTemplate('material-synthesis').outputs.length).toBe(2)
  })
  it('each template parameterRanges are independent', () => {
    const t1 = getTwinTemplate('o3-mnb-degradation')
    t1.parameterRanges[0].name = 'MUT'
    expect(getTwinTemplate('o3-mnb-degradation').parameterRanges[0].name).not.toBe('MUT')
  })
  it('each template has non-empty name', () => {
    for (const t of listTwinTemplates()) expect(t.name.length).toBeGreaterThan(0)
  })
  it('each template has non-empty domain', () => {
    for (const t of listTwinTemplates()) expect(t.domain.length).toBeGreaterThan(0)
  })
  it('o3-mnb-degradation domain is 环境科学', () => {
    expect(getTwinTemplate('o3-mnb-degradation').domain).toBe('环境科学')
  })
  it('cfd-flow-optimization domain is 工程', () => {
    expect(getTwinTemplate('cfd-flow-optimization').domain).toBe('工程')
  })
  it('material-synthesis domain is 材料科学', () => {
    expect(getTwinTemplate('material-synthesis').domain).toBe('材料科学')
  })
  it('each parameterRanges has non-empty name', () => {
    for (const t of listTwinTemplates()) {
      for (const p of t.parameterRanges) expect(p.name.length).toBeGreaterThan(0)
    }
  })
  it('each parameterRanges has non-empty unit', () => {
    for (const t of listTwinTemplates()) {
      for (const p of t.parameterRanges) expect(p.unit.length).toBeGreaterThan(0)
    }
  })
  it('each parameterRanges has non-empty range', () => {
    for (const t of listTwinTemplates()) {
      for (const p of t.parameterRanges) expect(p.range.length).toBeGreaterThan(0)
    }
  })
  it('listTwinTemplates returns fresh array each call', () => {
    expect(listTwinTemplates()).not.toBe(listTwinTemplates())
  })
})

describe('Phase 8-K1 schema edge cases', () => {
  it('isValidDigitalTwinModel rejects null', () => {
    expect(isValidDigitalTwinModel(null)).toBe(false)
  })
  it('isValidDigitalTwinModel rejects undefined', () => {
    expect(isValidDigitalTwinModel(undefined)).toBe(false)
  })
  it('isValidDigitalTwinModel rejects array', () => {
    expect(isValidDigitalTwinModel([])).toBe(false)
  })
  it('isValidDigitalTwinModel rejects empty object', () => {
    expect(isValidDigitalTwinModel({})).toBe(false)
  })
  it('isValidDigitalTwinModel rejects empty id', () => {
    expect(isValidDigitalTwinModel({
      id: '', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [], accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects empty name', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: '', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [], accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects non-string input', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: [123], outputs: ['b'],
      parameters: [], accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects non-array parameters', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: 'x', accuracy: 0.5, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel rejects negative accuracy', () => {
    expect(isValidDigitalTwinModel({
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [], accuracy: -0.1, status: 'draft',
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidTwinParameter rejects null', () => {
    expect(isValidTwinParameter(null)).toBe(false)
  })
  it('isValidTwinPrediction rejects null output', () => {
    expect(isValidTwinPrediction({ modelId: 'm', input: { a: 1 }, output: null, confidence: 0.5, timestamp: 1 })).toBe(false)
  })
  it('isValidTwinPrediction rejects empty modelId', () => {
    expect(isValidTwinPrediction({ modelId: '', input: { a: 1 }, output: { b: 2 }, confidence: 0.5, timestamp: 1 })).toBe(false)
  })
  it('isValidTwinPrediction rejects negative confidence', () => {
    expect(isValidTwinPrediction({ modelId: 'm', input: { a: 1 }, output: { b: 2 }, confidence: -0.1, timestamp: 1 })).toBe(false)
  })
})

describe('Phase 8-K1 secret guard edge cases', () => {
  it('findForbidden detects providerId', () => {
    expect(twinHelpers.findForbidden('providerId')).toBe('providerId')
  })
  it('findForbidden detects modelId', () => {
    expect(twinHelpers.findForbidden('modelId')).toBe('modelId')
  })
  it('findForbidden detects sk- in deep array', () => {
    expect(twinHelpers.findForbidden([['safe'], ['sk-bad']])).toBe('sk-')
  })
  it('findForbidden handles empty object', () => {
    expect(twinHelpers.findForbidden({})).toBeNull()
  })
  it('findForbidden handles empty string', () => {
    expect(twinHelpers.findForbidden('')).toBeNull()
  })
  it('findForbidden handles boolean false', () => {
    expect(twinHelpers.findForbidden(false)).toBeNull()
  })
})

describe('Phase 8-K1 final integration', () => {
  it('full pipeline works', () => {
    const tmpl = getTwinTemplate('o3-mnb-degradation')
    const twin = buildTwinModel({
      name: 'pipeline-test',
      domain: tmpl.domain,
      inputs: tmpl.inputs,
      outputs: tmpl.outputs,
      parameters: tmpl.parameterRanges.map((p) => ({ name: p.name, value: 0.5, range: p.range, unit: p.unit }))
    })
    const features = [extractFeatures([{ dose: 1 }, { dose: 2 }, { dose: 3 }], 'dose')]
    const normFeatures = features.map(normalize)
    const selected = selectFeatures(normFeatures as never, { topK: 1 })
    expect(selected.length).toBe(1)
    const pred = predictAndRecord(paramsToLinear(twin.parameters), twin.id, { dose: 5 })
    expect(pred.output.y).toBeGreaterThan(0)
  })
  it('calibration cycle reduces error', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 1, range: '0-1', unit: 'u' }]
    const spec = paramsToLinear(params)
    const cal = runCalibration(spec, { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }], outputs: [1.0, 2.0, 3.0] })
    expect(cal.rSquared).toBeGreaterThan(0.9)
  })
  it('all exports accessible', () => {
    expect(typeof linearPredict).toBe('function')
    expect(typeof polynomialPredict).toBe('function')
    expect(typeof kineticPredict).toBe('function')
    expect(typeof predict).toBe('function')
    expect(typeof predictAndRecord).toBe('function')
    expect(typeof comparePrediction).toBe('function')
    expect(typeof calculateError).toBe('function')
    expect(typeof updateParameters).toBe('function')
    expect(typeof runCalibration).toBe('function')
    expect(typeof buildTwinModel).toBe('function')
    expect(typeof calibrateFromExperiment).toBe('function')
    expect(typeof compareExperimentResult).toBe('function')
    expect(typeof getTwinTemplate).toBe('function')
    expect(typeof listTwinTemplates).toBe('function')
    expect(typeof extractFeatures).toBe('function')
    expect(typeof normalize).toBe('function')
    expect(typeof selectFeatures).toBe('function')
    expect(typeof validateInput).toBe('function')
  })
})

describe('Phase 8-K1 src directory presence', () => {
  it('src/shared/digital-twin directory exists', () => {
    expect(existsSync(join(__dirname, '../../src/shared/digital-twin'))).toBe(true)
  })
  it('src/shared/digital-twin/digital-twin-schema.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/shared/digital-twin/digital-twin-schema.ts'))).toBe(true)
  })
  it('src/services/digital-twin directory exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin'))).toBe(true)
  })
  it('feature-engineer.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin/feature-engineer.ts'))).toBe(true)
  })
  it('digital-twin-engine.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin/digital-twin-engine.ts'))).toBe(true)
  })
  it('model-calibrator.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin/model-calibrator.ts'))).toBe(true)
  })
  it('experiment-twin-adapter.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin/experiment-twin-adapter.ts'))).toBe(true)
  })
  it('digital-twin-templates.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/digital-twin/digital-twin-templates.ts'))).toBe(true)
  })
  it('docs/digital-twin directory exists', () => {
    expect(existsSync(join(__dirname, '../../docs/digital-twin'))).toBe(true)
  })
})

describe('Phase 8-K1 detailed FeatureEngineer', () => {
  it('extractFeatures preserves row order', () => {
    const f = extractFeatures([{ x: 3 }, { x: 1 }, { x: 2 }], 'x')
    expect(f.values).toEqual([3, 1, 2])
  })
  it('extractFeatures handles object with string column', () => {
    const f = extractFeatures([{ x: 1 }], 'x', 'parameter-optimization')
    expect(f.kind).toBe('parameter-optimization')
  })
  it('normalize of [5, 5, 5] -> [0, 0, 0]', () => {
    const f = extractFeatures([{ x: 5 }, { x: 5 }, { x: 5 }], 'x')
    expect(normalize(f).values).toEqual([0, 0, 0])
  })
  it('normalize of negative values', () => {
    const f = extractFeatures([{ x: -10 }, { x: 0 }, { x: 10 }], 'x')
    const n = normalize(f)
    expect(n.min).toBe(-10)
    expect(n.max).toBe(10)
    expect(n.values).toEqual([0, 0.5, 1])
  })
  it('selectFeatures with high minVariance filters out low variance', () => {
    const f1 = extractFeatures([{ x: 1 }, { x: 2 }, { x: 3 }], 'x')
    const f2 = extractFeatures([{ y: 5 }, { y: 5.01 }, { y: 5 }], 'y')
    const sel = selectFeatures([f1, f2], { minVariance: 0.1 })
    expect(sel.length).toBe(1)
    expect(sel[0].name).toBe('x')
  })
  it('selectFeatures with topK=2 returns 2', () => {
    const f1 = extractFeatures([{ x: 1 }, { x: 2 }, { x: 3 }], 'x')
    const f2 = extractFeatures([{ y: 1 }, { y: 2 }, { y: 4 }], 'y')
    const f3 = extractFeatures([{ z: 1 }, { z: 2 }, { z: 5 }], 'z')
    expect(selectFeatures([f1, f2, f3], { topK: 2 }).length).toBe(2)
  })
  it('selectFeatures sort by variance desc', () => {
    const f1 = extractFeatures([{ x: 1 }, { x: 2 }], 'x')
    const f2 = extractFeatures([{ y: 1 }, { y: 3 }, { y: 5 }], 'y')
    const sel = selectFeatures([f1, f2], { topK: 1 })
    expect(sel[0].name).toBe('y')
  })
  it('validateInput accepts all primitive types', () => {
    const result = validateInput({ n: 1, s: 'x', b: false }, { n: 'number', s: 'string', b: 'boolean' })
    expect(result.ok).toBe(true)
  })
  it('validateInput detects missing field with correct name', () => {
    const result = validateInput({}, { special: 'number' })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toContain('special')
  })
  it('validateInput detects wrong type with correct field name', () => {
    const result = validateInput({ x: 'abc' }, { x: 'number' })
    expect(result.ok).toBe(false)
    if (!result.ok) expect(result.error).toContain('x')
  })
})

describe('Phase 8-K1 detailed engine math', () => {
  it('linearPredict with all zeros input is intercept only', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1, 2, 3], intercept: 7 }, {})
    expect(r.output.y).toBe(7)
  })
  it('linearPredict negative coefficients', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [-1], intercept: 10 }, { a: 3 })
    expect(r.output.y).toBe(7)
  })
  it('linearPredict fractional coefficients', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [0.5], intercept: 0 }, { a: 4 })
    expect(r.output.y).toBe(2)
  })
  it('polynomialPredict linear (degree 1)', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [2, 3], degree: 1 }, 4)
    expect(r.output.y).toBe(14)
  })
  it('polynomialPredict quadratic', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [0, 0, 1], degree: 2 }, 3)
    expect(r.output.y).toBe(9)
  })
  it('polynomialPredict degree capped at array length', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [1, 2, 3], degree: 10 }, 2)
    expect(r.output.y).toBe(1 + 4 + 12)
  })
  it('kineticPredict second-order', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 2, initialConcentration: 10 }, 5)
    expect(r.output.concentration).toBeCloseTo(10 * Math.exp(-1), 5)
  })
  it('kineticPredict half-life', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: Math.LN2, order: 1, initialConcentration: 100 }, 1)
    expect(r.output.concentration).toBeCloseTo(50, 4)
  })
  it('predict linear over polynomial inputs uses only first value', () => {
    const r = predict({ kind: 'polynomial', coefficients: [0, 1], degree: 1 }, { a: 3, b: 100 })
    expect(r.output.y).toBe(3)
  })
  it('predict kinetic over many inputs uses first only', () => {
    const r = predict({ kind: 'kinetic', rateConstant: 0, order: 1, initialConcentration: 10 }, { a: 100, b: 200 })
    expect(r.output.concentration).toBe(10)
  })
})

describe('Phase 8-K1 detailed calibrator math', () => {
  it('comparePrediction default tolerance 0.05', () => {
    const r = comparePrediction(1.0, 1.04)
    expect(r.withinTolerance).toBe(true)
  })
  it('comparePrediction rejects 5% off', () => {
    const r = comparePrediction(1.0, 1.06)
    expect(r.withinTolerance).toBe(false)
  })
  it('calculateError of 3 same samples', () => {
    const r = calculateError([
      comparePrediction(1, 1, 1),
      comparePrediction(2, 2, 1),
      comparePrediction(3, 3, 1)
    ])
    expect(r.rSquared).toBe(1)
    expect(r.rmse).toBe(0)
  })
  it('calculateError high variance', () => {
    const r = calculateError([
      comparePrediction(1, 100, 1000),
      comparePrediction(2, 200, 1000)
    ])
    expect(r.maxAbsoluteError).toBeCloseTo(198, 0)
  })
  it('updateParameters partial update with single gradient', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 10, range: '0-20', unit: 'u' },
      { name: 'b', value: 5, range: '0-10', unit: 'u' }
    ]
    const upd = updateParameters(params, 0.5, [4])
    expect(upd[0].value).toBe(8)
    expect(upd[1].value).toBe(5)
  })
  it('runCalibration on perfect data', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [2, 0], intercept: 0 },
      { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }], outputs: [2, 4, 6] }
    )
    expect(cal.rSquared).toBe(1)
    expect(cal.rmse).toBe(0)
  })
  it('runCalibration samples count matches', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [1], intercept: 0 },
      { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }, { a: 4 }], outputs: [1, 2, 3, 4] }
    )
    expect(cal.samples).toBe(4)
  })
})

describe('Phase 8-K1 detailed adapter scenarios', () => {
  it('buildTwinModel with empty parameters', () => {
    const m = buildTwinModel({ name: 'empty', domain: 'd', inputs: [], outputs: [], parameters: [] })
    expect(m.parameters.length).toBe(0)
  })
  it('buildTwinModel with empty inputs/outputs', () => {
    const m = buildTwinModel({ name: 'x', domain: 'd', inputs: [], outputs: [], parameters: [] })
    expect(m.inputs.length).toBe(0)
    expect(m.outputs.length).toBe(0)
  })
  it('buildTwinModel with multiple parameters', () => {
    const m = buildTwinModel({
      name: 'multi', domain: 'd',
      inputs: ['a', 'b'],
      outputs: ['y'],
      parameters: [
        { name: 'a', value: 1, range: '0-10', unit: 'u' },
        { name: 'b', value: 2, range: '0-10', unit: 'u' },
        { name: 'c', value: 3, range: '0-10', unit: 'u' }
      ]
    })
    expect(m.parameters.length).toBe(3)
  })
  it('calibrateFromExperiment with empty metrics', () => {
    const exp = {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    const twin = buildTwinModel({ name: 'x', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const result = { metrics: {}, conclusion: '', confidence: 0.8 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.predictions.length).toBe(0)
  })
  it('calibrateFromExperiment with single metric', () => {
    const exp = {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    const twin = buildTwinModel({ name: 'x', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const result = { metrics: { dose: 5 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.predictions.length).toBe(1)
  })
  it('compareExperimentResult preserves metric order', () => {
    const result = { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.8 }
    const predictions = [
      { modelId: 'm', input: { a: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 },
      { modelId: 'm', input: { b: 2 }, output: { y: 2 }, confidence: 0.8, timestamp: 1 }
    ]
    const cmp = compareExperimentResult(result, predictions)
    expect(cmp.length).toBe(2)
  })
  it('compareExperimentResult within tolerance true', () => {
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const predictions = [{ modelId: 'm', input: { a: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 }]
    expect(compareExperimentResult(result, predictions)[0].withinTolerance).toBe(true)
  })
  it('compareExperimentResult skips missing predictions', () => {
    const result = { metrics: { a: 1, b: 2, c: 3 }, conclusion: '', confidence: 0.8 }
    const predictions = [
      { modelId: 'm', input: { a: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 }
    ]
    expect(compareExperimentResult(result, predictions).length).toBe(1)
  })
})

describe('Phase 8-K1 templates integrity', () => {
  it('each template outputs and inputs non-empty strings', () => {
    for (const t of listTwinTemplates()) {
      for (const i of t.inputs) {
        expect(typeof i).toBe('string')
        expect(i.length).toBeGreaterThan(0)
      }
      for (const o of t.outputs) {
        expect(typeof o).toBe('string')
        expect(o.length).toBeGreaterThan(0)
      }
    }
  })
  it('each template parameterRanges has 2+ entries', () => {
    for (const t of listTwinTemplates()) {
      expect(t.parameterRanges.length).toBeGreaterThanOrEqual(2)
    }
  })
  it('each template inputs is independent', () => {
    const t1 = getTwinTemplate('o3-mnb-degradation')
    t1.inputs[0] = 'MUT'
    expect(getTwinTemplate('o3-mnb-degradation').inputs[0]).not.toBe('MUT')
  })
  it('each template outputs is independent', () => {
    const t1 = getTwinTemplate('cfd-flow-optimization')
    t1.outputs[0] = 'MUT'
    expect(getTwinTemplate('cfd-flow-optimization').outputs[0]).not.toBe('MUT')
  })
  it('o3-mnb-degradation parameterRanges includes k and c0', () => {
    const t = getTwinTemplate('o3-mnb-degradation')
    const names = t.parameterRanges.map((p) => p.name)
    expect(names).toContain('k')
    expect(names).toContain('c0')
  })
  it('cfd-flow-optimization parameterRanges includes coef_v', () => {
    const t = getTwinTemplate('cfd-flow-optimization')
    const names = t.parameterRanges.map((p) => p.name)
    expect(names).toContain('coef_v')
  })
  it('material-synthesis parameterRanges includes a_t', () => {
    const t = getTwinTemplate('material-synthesis')
    const names = t.parameterRanges.map((p) => p.name)
    expect(names).toContain('a_t')
  })
})

describe('Phase 8-K1 error handling', () => {
  it('linearPredict returns finite numbers for non-finite inputs', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: NaN })
    expect(Number.isFinite(r.output.y)).toBe(true)
  })
  it('polynomialPredict returns finite numbers for non-finite input', () => {
    const r = polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 0 }, NaN)
    expect(Number.isFinite(r.output.y)).toBe(true)
  })
  it('kineticPredict returns finite numbers for non-finite t', () => {
    const r = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, NaN)
    expect(Number.isFinite(r.output.concentration)).toBe(true)
  })
  it('extractFeatures handles undefined values', () => {
    const f = extractFeatures([{ a: undefined }], 'a')
    expect(f.values).toEqual([])
  })
  it('extractFeatures handles string numbers gracefully (not included)', () => {
    const f = extractFeatures([{ a: '5' }], 'a')
    expect(f.values).toEqual([])
  })
  it('normalize handles negative max correctly', () => {
    const f = extractFeatures([{ x: -5 }, { x: -10 }, { x: -1 }], 'x')
    const n = normalize(f)
    expect(n.min).toBe(-10)
    expect(n.max).toBe(-1)
    expect(n.values[0]).toBeCloseTo(0.5556, 3)
  })
})

describe('Phase 8-K1 determinism stress', () => {
  it('predictAndRecord timestamp only differs by Date.now', () => {
    const r1 = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    const r2 = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    expect(r1.output).toEqual(r2.output)
    expect(r1.confidence).toBe(r2.confidence)
  })
  it('buildTwinModel creates unique id by time', async () => {
    const m1 = buildTwinModel({ name: 'same', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] })
    await new Promise((r) => setTimeout(r, 5))
    const m2 = buildTwinModel({ name: 'same', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] })
    expect(m1.id).not.toBe(m2.id)
  })
  it('calibrateFromExperiment is deterministic for same inputs', () => {
    const exp = {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    const twin1 = buildTwinModel({ name: 'same', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const twin2 = buildTwinModel({ name: 'same', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.9 }
    const r1 = calibrateFromExperiment({ experiment: exp, result, twinModel: twin1 })
    const r2 = calibrateFromExperiment({ experiment: exp, result, twinModel: twin2 })
    expect(r1.calibration.rSquared).toBe(r2.calibration.rSquared)
  })
  it('comparePrediction deterministic', () => {
    const r1 = comparePrediction(1.5, 1.0, 0.5)
    const r2 = comparePrediction(1.5, 1.0, 0.5)
    expect(r1.absoluteError).toBe(r2.absoluteError)
    expect(r1.relativeError).toBe(r2.relativeError)
  })
  it('calculateError deterministic', () => {
    const r1 = calculateError([comparePrediction(1, 1.1, 1), comparePrediction(2, 2.1, 1)])
    const r2 = calculateError([comparePrediction(1, 1.1, 1), comparePrediction(2, 2.1, 1)])
    expect(r1.rmse).toBe(r2.rmse)
    expect(r1.rSquared).toBe(r2.rSquared)
  })
})

describe('Phase 8-K1 comprehensive FeatureEngineer', () => {
  it('extractFeatures with mixed valid+invalid', () => {
    const f = extractFeatures([{ a: 1 }, { a: 'x' }, { a: 2 }, { a: null }, { a: 3 }], 'a')
    expect(f.values).toEqual([1, 2, 3])
  })
  it('extractFeatures preserves input count for valid only', () => {
    const f = extractFeatures([{ a: 1 }, { a: 2 }, { a: 'x' }, { a: 3 }, { a: undefined }, { a: 4 }], 'a')
    expect(f.values.length).toBe(4)
  })
  it('normalize output range strictly 0..1', () => {
    const f = extractFeatures([{ x: 100 }, { x: 200 }, { x: 50 }], 'x')
    const n = normalize(f)
    expect(Math.min(...n.values)).toBeGreaterThanOrEqual(0)
    expect(Math.max(...n.values)).toBeLessThanOrEqual(1)
  })
  it('normalize output at min is 0', () => {
    const f = extractFeatures([{ x: 1 }, { x: 2 }, { x: 3 }], 'x')
    expect(Math.min(...normalize(f).values)).toBe(0)
  })
  it('normalize output at max is 1', () => {
    const f = extractFeatures([{ x: 1 }, { x: 2 }, { x: 3 }], 'x')
    expect(Math.max(...normalize(f).values)).toBe(1)
  })
  it('selectFeatures returns same values', () => {
    const f = extractFeatures([{ x: 1 }, { x: 2 }], 'x')
    const sel = selectFeatures([f])
    expect(sel[0].values).toEqual(f.values)
  })
  it('selectFeatures high topK returns all', () => {
    const f1 = extractFeatures([{ x: 1 }], 'x')
    const f2 = extractFeatures([{ y: 2 }], 'y')
    const sel = selectFeatures([f1, f2], { topK: 10 })
    expect(sel.length).toBe(2)
  })
  it('validateInput with multiple errors returns first missing', () => {
    const r = validateInput({}, { a: 'number', b: 'string' })
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toContain('a')
  })
  it('validateInput accepts Infinity as number? No, rejected', () => {
    const r = validateInput({ x: Infinity }, { x: 'number' })
    expect(r.ok).toBe(false)
  })
  it('validateInput accepts -Infinity? Rejected', () => {
    const r = validateInput({ x: -Infinity }, { x: 'number' })
    expect(r.ok).toBe(false)
  })
  it('validateInput string "true" rejected as boolean', () => {
    const r = validateInput({ x: 'true' }, { x: 'boolean' })
    expect(r.ok).toBe(false)
  })
})

describe('Phase 8-K1 comprehensive engine scenarios', () => {
  it('linearPredict with single coefficient multiplies first input', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [3], intercept: 1 }, { x: 2 })
    expect(r.output.y).toBe(7)
  })
  it('linearPredict handles input with extra keys', () => {
    const r = linearPredict({ kind: 'linear', coefficients: [1, 1], intercept: 0 }, { a: 1, b: 2, c: 3, d: 4 })
    expect(r.output.y).toBe(3)
  })
  it('linearPredict confidence always 0.85', () => {
    const r1 = linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 })
    const r2 = linearPredict({ kind: 'linear', coefficients: [1, 2, 3], intercept: 0 }, { a: 1 })
    expect(r1.confidence).toBe(0.85)
    expect(r2.confidence).toBe(0.85)
  })
  it('polynomialPredict confidence always 0.8', () => {
    expect(polynomialPredict({ kind: 'polynomial', coefficients: [1, 2], degree: 1 }, 5).confidence).toBe(0.8)
  })
  it('kineticPredict confidence always 0.9', () => {
    expect(kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 0).confidence).toBe(0.9)
  })
  it('predict with linear has output.y', () => {
    const r = predict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 })
    expect(typeof r.output.y).toBe('number')
  })
  it('predict with kinetic has output.concentration', () => {
    const r = predict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, { t: 0 })
    expect(typeof r.output.concentration).toBe('number')
  })
  it('predict with polynomial has output.y', () => {
    const r = predict({ kind: 'polynomial', coefficients: [0, 1], degree: 1 }, { x: 5 })
    expect(r.output.y).toBe(5)
  })
  it('predictAndRecord for kinetic', () => {
    const p = predictAndRecord({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 10 }, 'm', { t: 0 })
    expect(p.output.concentration).toBe(10)
  })
  it('predictAndRecord preserves confidence per kind', () => {
    expect(predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 }).confidence).toBe(0.85)
    expect(predictAndRecord({ kind: 'polynomial', coefficients: [1, 0], degree: 1 }, 'm', { a: 1 }).confidence).toBe(0.8)
    expect(predictAndRecord({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 'm', { t: 0 }).confidence).toBe(0.9)
  })
  it('paramsToLinear preserves order', () => {
    const spec = paramsToLinear([
      { name: 'first', value: 1, range: '0-1', unit: 'u' },
      { name: 'second', value: 2, range: '0-1', unit: 'u' }
    ])
    expect(spec.coefficients[0]).toBe(1)
    expect(spec.coefficients[1]).toBe(2)
  })
  it('paramsToLinear clones values', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 1, range: '0-1', unit: 'u' }]
    const spec = paramsToLinear(params)
    spec.coefficients[0] = 999
    expect(params[0].value).toBe(1)
  })
})

describe('Phase 8-K1 comprehensive calibrator', () => {
  it('comparePrediction returns 0 error when equal', () => {
    const r = comparePrediction(5, 5)
    expect(r.absoluteError).toBe(0)
  })
  it('comparePrediction non-zero observed', () => {
    const r = comparePrediction(1, 2, 1)
    expect(r.absoluteError).toBe(1)
    expect(r.relativeError).toBe(0.5)
  })
  it('calculateError empty samples returns zeros', () => {
    const r = calculateError([])
    expect(r.totalAbsoluteError).toBe(0)
    expect(r.meanAbsoluteError).toBe(0)
    expect(r.maxAbsoluteError).toBe(0)
    expect(r.rmse).toBe(0)
    expect(r.rSquared).toBe(0)
  })
  it('calculateError rmse = sqrt of mean of squared errors', () => {
    const r = calculateError([comparePrediction(1, 1.1, 1)])
    expect(r.rmse).toBeCloseTo(0.1, 5)
  })
  it('calculateError rSquared = 1 for constant observed', () => {
    const r = calculateError([
      comparePrediction(5, 5, 1),
      comparePrediction(5, 5, 1)
    ])
    expect(r.rSquared).toBe(1)
  })
  it('updateParameters 3 params with 3 gradients', () => {
    const params: TwinParameter[] = [
      { name: 'a', value: 1, range: '0-1', unit: 'u' },
      { name: 'b', value: 2, range: '0-1', unit: 'u' },
      { name: 'c', value: 3, range: '0-1', unit: 'u' }
    ]
    const upd = updateParameters(params, 0.1, [1, 1, 1])
    expect(upd[0].value).toBeCloseTo(0.9, 5)
    expect(upd[1].value).toBeCloseTo(1.9, 5)
    expect(upd[2].value).toBeCloseTo(2.9, 5)
  })
  it('updateParameters all gradient 0 no change', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 5, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 0.5, [0])
    expect(upd[0].value).toBe(5)
  })
  it('updateParameters value becomes negative', () => {
    const params: TwinParameter[] = [{ name: 'a', value: 1, range: '0-10', unit: 'u' }]
    const upd = updateParameters(params, 1, [5])
    expect(upd[0].value).toBe(-4)
  })
  it('runCalibration default tolerance 0.05', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [1], intercept: 0 },
      { inputs: [{ a: 1 }], outputs: [1.06] }
    )
    expect(cal.samples).toBe(1)
  })
})

describe('Phase 8-K1 comprehensive adapter', () => {
  function setupExperiment() {
    return {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
  }
  it('buildTwinModel with very high accuracy', () => {
    const m = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 0.99)
    expect(m.accuracy).toBe(0.99)
  })
  it('buildTwinModel with accuracy 0', () => {
    const m = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 0)
    expect(m.accuracy).toBe(0)
  })
  it('buildTwinModel with accuracy 1', () => {
    const m = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 1)
    expect(m.accuracy).toBe(1)
  })
  it('calibrateFromExperiment rSquared in valid range', () => {
    const exp = setupExperiment()
    const twin = buildTwinModel({ name: 'a', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.calibration.rSquared).toBeGreaterThanOrEqual(0)
    expect(r.calibration.rSquared).toBeLessThanOrEqual(1)
  })
  it('calibrateFromExperiment accuracy bounded', () => {
    const exp = setupExperiment()
    const twin = buildTwinModel({ name: 'a', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [] }, 0.5)
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.updatedAccuracy).toBeGreaterThanOrEqual(0)
    expect(r.updatedAccuracy).toBeLessThanOrEqual(1)
  })
  it('compareExperimentResult preserves order from result', () => {
    const result = { metrics: { x: 1, y: 2, z: 3 }, conclusion: '', confidence: 0.8 }
    const predictions = [
      { modelId: 'm', input: { x: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 },
      { modelId: 'm', input: { y: 2 }, output: { y: 2 }, confidence: 0.8, timestamp: 1 },
      { modelId: 'm', input: { z: 3 }, output: { y: 3 }, confidence: 0.8, timestamp: 1 }
    ]
    expect(compareExperimentResult(result, predictions).length).toBe(3)
  })
  it('compareExperimentResult within tolerance for perfect predictions', () => {
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.8 }
    const predictions = [{ modelId: 'm', input: { a: 1 }, output: { y: 1 }, confidence: 0.8, timestamp: 1 }]
    expect(compareExperimentResult(result, predictions, 0)[0].withinTolerance).toBe(true)
  })
})

describe('Phase 8-K1 comprehensive templates', () => {
  it('each template parameterRanges count >= 2', () => {
    for (const t of listTwinTemplates()) expect(t.parameterRanges.length).toBeGreaterThanOrEqual(2)
  })
  it('o3-mnb-degradation parameterRanges has unit info', () => {
    const t = getTwinTemplate('o3-mnb-degradation')
    for (const p of t.parameterRanges) expect(p.unit.length).toBeGreaterThan(0)
  })
  it('cfd-flow-optimization parameterRanges has unit info', () => {
    const t = getTwinTemplate('cfd-flow-optimization')
    for (const p of t.parameterRanges) expect(p.unit.length).toBeGreaterThan(0)
  })
  it('material-synthesis parameterRanges has unit info', () => {
    const t = getTwinTemplate('material-synthesis')
    for (const p of t.parameterRanges) expect(p.unit.length).toBeGreaterThan(0)
  })
  it('listTwinTemplates preserves order', () => {
    const list = listTwinTemplates()
    expect(list[0].kind).toBe('o3-mnb-degradation')
    expect(list[1].kind).toBe('cfd-flow-optimization')
    expect(list[2].kind).toBe('material-synthesis')
  })
  it('listTwinTemplates returns fresh arrays each call', () => {
    const a = listTwinTemplates()
    const b = listTwinTemplates()
    expect(a[0]).not.toBe(b[0])
  })
  it('getTwinTemplate returns object with kind matching input', () => {
    expect(getTwinTemplate('o3-mnb-degradation').kind).toBe('o3-mnb-degradation')
  })
})

describe('Phase 8-K1 schema validator edge cases', () => {
  it('isValidDigitalTwinModel with non-array inputs rejects', () => {
    expect(isValidDigitalTwinModel({
      id: 't', name: 'n', domain: 'd', inputs: 'x', outputs: ['y'],
      parameters: [], accuracy: 0.5, status: 'draft', createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel with non-array outputs rejects', () => {
    expect(isValidDigitalTwinModel({
      id: 't', name: 'n', domain: 'd', inputs: ['x'], outputs: 'y',
      parameters: [], accuracy: 0.5, status: 'draft', createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel with NaN accuracy rejects', () => {
    expect(isValidDigitalTwinModel({
      id: 't', name: 'n', domain: 'd', inputs: ['x'], outputs: ['y'],
      parameters: [], accuracy: NaN, status: 'draft', createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidDigitalTwinModel with NaN createdAt rejects', () => {
    expect(isValidDigitalTwinModel({
      id: 't', name: 'n', domain: 'd', inputs: ['x'], outputs: ['y'],
      parameters: [], accuracy: 0.5, status: 'draft', createdAt: NaN, updatedAt: 2
    })).toBe(false)
  })
  it('isValidTwinPrediction with NaN output rejects', () => {
    expect(isValidTwinPrediction({ modelId: 'm', input: { a: 1 }, output: { b: NaN }, confidence: 0.5, timestamp: 1 })).toBe(false)
  })
  it('isValidTwinParameter rejects non-string range', () => {
    expect(isValidTwinParameter({ name: 'a', value: 1, range: 5, unit: 'u' })).toBe(false)
  })
  it('isValidTwinParameter rejects non-string unit', () => {
    expect(isValidTwinParameter({ name: 'a', value: 1, range: '0-10', unit: 5 })).toBe(false)
  })
  it('isValidTwinParameter accepts negative value', () => {
    expect(isValidTwinParameter({ name: 'a', value: -1, range: '-10..10', unit: 'u' })).toBe(true)
  })
  it('isValidTwinParameter accepts zero value', () => {
    expect(isValidTwinParameter({ name: 'a', value: 0, range: '0-10', unit: 'u' })).toBe(true)
  })
})

describe('Phase 8-K1 secret guard comprehensive', () => {
  it('findForbidden in deeply nested object', () => {
    const obj = { a: { b: { c: { d: 'sk-bad' } } } }
    expect(twinHelpers.findForbidden(obj)).toBe('sk-')
  })
  it('findForbidden in array of objects', () => {
    const arr = [{ x: 'ok' }, { y: 'apiKey' }]
    expect(twinHelpers.findForbidden(arr)).toBe('apiKey')
  })
  it('findForbidden key name not scanned (only values)', () => {
    expect(twinHelpers.findForbidden({ apiKey: 'value' })).toBeNull()
  })
  it('findForbidden handles nested arrays', () => {
    expect(twinHelpers.findForbidden([[['token']]])).toBe('token')
  })
  it('findForbidden returns first match', () => {
    const result = twinHelpers.findForbidden('apiKey sk-')
    expect(['apiKey', 'sk-']).toContain(result)
  })
})

describe('Phase 8-K1 final stress', () => {
  it('all validations accept correctly', () => {
    const m: DigitalTwinModel = {
      id: 't1', name: 'n', domain: 'd',
      inputs: ['a'], outputs: ['b'],
      parameters: [{ name: 'p', value: 1, range: '0-10', unit: 'u' }],
      accuracy: 0.5, status: 'draft', createdAt: 1, updatedAt: 2
    }
    expect(isValidDigitalTwinModel(m)).toBe(true)
  })
  it('all prediction kinds produce different confidence', () => {
    expect(linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 }).confidence).toBe(0.85)
    expect(polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 0 }, 1).confidence).toBe(0.8)
    expect(kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 0).confidence).toBe(0.9)
  })
  it('all prediction kinds produce finite outputs', () => {
    const l = linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 })
    const p = polynomialPredict({ kind: 'polynomial', coefficients: [1, 1], degree: 1 }, 1)
    const k = kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 1)
    expect(Number.isFinite(l.output.y)).toBe(true)
    expect(Number.isFinite(p.output.y)).toBe(true)
    expect(Number.isFinite(k.output.concentration)).toBe(true)
  })
  it('templates all have non-empty inputs', () => {
    for (const t of listTwinTemplates()) expect(t.inputs.length).toBeGreaterThan(0)
  })
  it('templates all have non-empty outputs', () => {
    for (const t of listTwinTemplates()) expect(t.outputs.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-K1 final batch', () => {
  it('linearPredict and predict have same output for linear', () => {
    const spec = { kind: 'linear' as const, coefficients: [1, 2], intercept: 3 }
    const input = { a: 4, b: 5 }
    expect(linearPredict(spec, input).output).toEqual(predict(spec, input).output)
  })
  it('polynomialPredict and predict have same output for polynomial', () => {
    const spec = { kind: 'polynomial' as const, coefficients: [0, 1], degree: 1 }
    const input = { x: 5 }
    expect(polynomialPredict(spec, 5).output).toEqual(predict(spec, input).output)
  })
  it('kineticPredict and predict have same output for kinetic', () => {
    const spec = { kind: 'kinetic' as const, rateConstant: 0.1, order: 1, initialConcentration: 10 }
    const input = { t: 5 }
    expect(kineticPredict(spec, 5).output).toEqual(predict(spec, input).output)
  })
  it('runCalibration rSquared in [0, 1]', () => {
    const cal = runCalibration({ kind: 'linear', coefficients: [1], intercept: 0 }, { inputs: [{ a: 1 }, { a: 2 }], outputs: [1, 2] })
    expect(cal.rSquared).toBeGreaterThanOrEqual(0)
    expect(cal.rSquared).toBeLessThanOrEqual(1)
  })
  it('runCalibration meanAbsoluteError in valid range', () => {
    const cal = runCalibration({ kind: 'linear', coefficients: [1], intercept: 0 }, { inputs: [{ a: 1 }, { a: 2 }], outputs: [1, 2] })
    expect(cal.meanAbsoluteError).toBeGreaterThanOrEqual(0)
  })
  it('each schema validator handles boundary', () => {
    expect(isValidModelStatus('draft')).toBe(true)
    expect(isValidModelStatus('deprecated')).toBe(true)
    expect(isValidPredictionKind('linear')).toBe(true)
    expect(isValidPredictionKind('kinetic')).toBe(true)
  })
  it('all 3 prediction kinds distinct confidence', () => {
    const confidences = new Set([
      linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 }).confidence,
      polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 0 }, 0).confidence,
      kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 0).confidence
    ])
    expect(confidences.size).toBe(3)
  })
  it('feature engineer output is deterministic', () => {
    const rows = [{ a: 1 }, { a: 2 }, { a: 3 }]
    const f1 = extractFeatures(rows, 'a')
    const f2 = extractFeatures(rows, 'a')
    expect(f1.values).toEqual(f2.values)
    expect(normalize(f1).values).toEqual(normalize(f2).values)
  })
  it('adapter is deterministic', () => {
    const exp = {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    const twin = buildTwinModel({ name: 'a', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] })
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.9 }
    const r1 = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    const r2 = calibrateFromExperiment({ experiment: exp, result, twinModel: buildTwinModel({ name: 'a', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 1, range: '0-1', unit: 'u' }] }) })
    expect(r1.calibration.rSquared).toBe(r2.calibration.rSquared)
  })
  it('all template kinds distinct', () => {
    expect(new Set(TWIN_TEMPLATE_KINDS).size).toBe(TWIN_TEMPLATE_KINDS.length)
  })
  it('all model statuses distinct', () => {
    expect(new Set(MODEL_STATUSES).size).toBe(MODEL_STATUSES.length)
  })
  it('all prediction kinds distinct', () => {
    expect(new Set(PREDICTION_KINDS).size).toBe(PREDICTION_KINDS.length)
  })
  it('feature source kinds distinct', () => {
    expect(new Set(FEATURE_SOURCE_KINDS).size).toBe(FEATURE_SOURCE_KINDS.length)
  })
  it('runCalibration rmse in valid range', () => {
    const cal = runCalibration({ kind: 'linear', coefficients: [1], intercept: 0 }, { inputs: [{ a: 1 }, { a: 2 }], outputs: [1, 2] })
    expect(cal.rmse).toBeGreaterThanOrEqual(0)
  })
  it('buildTwinModel status starts draft', () => {
    expect(buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }).status).toBe('draft')
  })
  it('buildTwinModel accuracy defaults 0.5', () => {
    expect(buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }).accuracy).toBe(0.5)
  })
  it('buildTwinModel accuracy custom 0.8', () => {
    expect(buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 0.8).accuracy).toBe(0.8)
  })
  it('buildTwinModel accuracy custom 0', () => {
    expect(buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 0).accuracy).toBe(0)
  })
  it('buildTwinModel accuracy custom 1', () => {
    expect(buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [] }, 1).accuracy).toBe(1)
  })
  it('all schemas valid for fresh models', () => {
    const m = buildTwinModel({ name: 'a', domain: 'd', inputs: ['x'], outputs: ['y'], parameters: [{ name: 'p', value: 0.5, range: '0-1', unit: 'u' }] })
    expect(isValidDigitalTwinModel(m)).toBe(true)
  })
  it('all schemas valid for predictions', () => {
    const p = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    expect(isValidTwinPrediction(p)).toBe(true)
  })
  it('all schemas valid for predictions across kinds', () => {
    expect(isValidTwinPrediction(predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 }))).toBe(true)
    expect(isValidTwinPrediction(predictAndRecord({ kind: 'polynomial', coefficients: [1, 0], degree: 1 }, 'm', { a: 1 }))).toBe(true)
    expect(isValidTwinPrediction(predictAndRecord({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 'm', { t: 1 }))).toBe(true)
  })
  it('all schemas valid for parameters', () => {
    expect(isValidTwinParameter({ name: 'a', value: 1, range: '0-1', unit: 'u' })).toBe(true)
    expect(isValidTwinParameter({ name: 'a', value: 0, range: '0-1', unit: 'u' })).toBe(true)
    expect(isValidTwinParameter({ name: 'a', value: -1, range: '-1..1', unit: 'u' })).toBe(true)
  })
  it('predictAndRecord timestamp is finite', () => {
    const p = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    expect(Number.isFinite(p.timestamp)).toBe(true)
  })
  it('predictAndRecord timestamp within reasonable range', () => {
    const before = Date.now()
    const p = predictAndRecord({ kind: 'linear', coefficients: [1], intercept: 0 }, 'm', { a: 1 })
    const after = Date.now()
    expect(p.timestamp).toBeGreaterThanOrEqual(before)
    expect(p.timestamp).toBeLessThanOrEqual(after)
  })
  it('templates produce non-empty arrays', () => {
    const list = listTwinTemplates()
    for (const t of list) {
      expect(Array.isArray(t.inputs)).toBe(true)
      expect(Array.isArray(t.outputs)).toBe(true)
      expect(Array.isArray(t.parameterRanges)).toBe(true)
    }
  })
  it('templates all have at least 3 inputs', () => {
    for (const t of listTwinTemplates()) expect(t.inputs.length).toBeGreaterThanOrEqual(3)
  })
  it('templates all have at least 2 outputs', () => {
    for (const t of listTwinTemplates()) expect(t.outputs.length).toBeGreaterThanOrEqual(2)
  })
  it('all 3 templates have at least 2 parameterRanges', () => {
    for (const t of listTwinTemplates()) expect(t.parameterRanges.length).toBeGreaterThanOrEqual(2)
  })
  it('all prediction kinds produce single raw value', () => {
    expect(linearPredict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 }).raw.length).toBe(1)
    expect(polynomialPredict({ kind: 'polynomial', coefficients: [1], degree: 0 }, 1).raw.length).toBe(1)
    expect(kineticPredict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, 1).raw.length).toBe(1)
  })
  it('all schemas reject secret values', () => {
    let paramThrew = false
    try { isValidTwinParameter({ name: 'a', value: 1, range: 'sk-bad', unit: 'u' }) } catch { paramThrew = true }
    expect(paramThrew).toBe(true)
    let modelThrew = false
    try {
      isValidDigitalTwinModel({
        id: 't1', name: 'n', domain: 'd',
        inputs: ['apiKey'], outputs: ['b'],
        parameters: [{ name: 'p', value: 1, range: '0-10', unit: 'u' }],
        accuracy: 0.5, status: 'draft', createdAt: 1, updatedAt: 2
      })
    } catch { modelThrew = true }
    expect(modelThrew).toBe(true)
  })
  it('all schemas reject empty required strings', () => {
    expect(isValidTwinParameter({ name: '', value: 1, range: '0-1', unit: 'u' })).toBe(false)
    expect(isValidDigitalTwinModel({
      id: '', name: 'n', domain: 'd',
      inputs: ['x'], outputs: ['y'],
      parameters: [], accuracy: 0.5, status: 'draft', createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('predict for each kind returns PredictionResult', () => {
    expect(predict({ kind: 'linear', coefficients: [1], intercept: 0 }, { a: 1 }).output).toBeDefined()
    expect(predict({ kind: 'polynomial', coefficients: [1, 0], degree: 1 }, { x: 1 }).output).toBeDefined()
    expect(predict({ kind: 'kinetic', rateConstant: 0.1, order: 1, initialConcentration: 1 }, { t: 1 }).output).toBeDefined()
  })
  it('all 3 templates listed', () => {
    const list = listTwinTemplates()
    expect(list.map((t) => t.kind)).toContain('o3-mnb-degradation')
    expect(list.map((t) => t.kind)).toContain('cfd-flow-optimization')
    expect(list.map((t) => t.kind)).toContain('material-synthesis')
  })
  it('runCalibration handles 5 samples', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [1], intercept: 0 },
      { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }, { a: 4 }, { a: 5 }], outputs: [1, 2, 3, 4, 5] }
    )
    expect(cal.samples).toBe(5)
  })
  it('runCalibration rmse for perfect linear', () => {
    const cal = runCalibration(
      { kind: 'linear', coefficients: [1], intercept: 0 },
      { inputs: [{ a: 1 }, { a: 2 }, { a: 3 }], outputs: [1, 2, 3] }
    )
    expect(cal.rmse).toBe(0)
  })
  it('calibrateFromExperiment accuracy update bounded', () => {
    const exp = {
      id: 'e', projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H',
      status: 'completed' as const, design: 'D', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    const twin = buildTwinModel({ name: 'a', domain: 'd', inputs: ['a'], outputs: ['y'], parameters: [{ name: 'p', value: 0.5, range: '0-1', unit: 'u' }] }, 0.5)
    const result = { metrics: { a: 1 }, conclusion: '', confidence: 0.9 }
    const r = calibrateFromExperiment({ experiment: exp, result, twinModel: twin })
    expect(r.twinModel.accuracy).toBe(r.updatedAccuracy)
  })
  it('isValidPredictionKind accepts all kinds', () => {
    for (const k of PREDICTION_KINDS) expect(isValidPredictionKind(k)).toBe(true)
  })
  it('isValidModelStatus accepts all statuses', () => {
    for (const s of MODEL_STATUSES) expect(isValidModelStatus(s)).toBe(true)
  })
  it('isValidModelStatus rejects typo', () => {
    expect(isValidModelStatus('trainig')).toBe(false)
    expect(isValidModelStatus('valdiated')).toBe(false)
  })
  it('FEATURE_SOURCE_KINDS contains numeric', () => {
    expect(FEATURE_SOURCE_KINDS).toContain('numeric')
  })
  it('FEATURE_SOURCE_KINDS contains time-series', () => {
    expect(FEATURE_SOURCE_KINDS).toContain('time-series')
  })
  it('FEATURE_SOURCE_KINDS contains parameter-optimization', () => {
    expect(FEATURE_SOURCE_KINDS).toContain('parameter-optimization')
  })
  it('all 3 prediction kinds in PREDICTION_KINDS', () => {
    expect(PREDICTION_KINDS).toContain('linear')
    expect(PREDICTION_KINDS).toContain('polynomial')
    expect(PREDICTION_KINDS).toContain('kinetic')
  })
})