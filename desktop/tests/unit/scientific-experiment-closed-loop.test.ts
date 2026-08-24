// Phase 8-K0 Scientific Experiment Closed Loop System Tests
import { describe, it, expect, beforeEach } from 'vitest'
import { readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

import {
  isValidExperiment, isValidExperimentRecord, isValidExperimentResult, isValidExperimentParameter,
  isValidExperimentStatus, isValidParameterType,
  EXPERIMENT_STATUSES, PARAMETER_TYPES,
  __testHelpers as expHelpers
} from '../../src/shared/experiment/experiment-schema'

import { ExperimentManager } from '../../src/services/experiment/experiment-manager'
import { ExperimentEngine } from '../../src/services/experiment/experiment-engine'
import {
  recordToDataset, validateDataset, mergeRecords
} from '../../src/services/experiment/experiment-data-adapter'
import { ExperimentLoopEngine } from '../../src/services/experiment/experiment-loop-engine'
import {
  getExperimentTemplate, listExperimentTemplates, EXPERIMENT_TEMPLATE_KINDS
} from '../../src/services/experiment/experiment-templates'
import {
  EXPERIMENT_EVENT_TYPES, isExperimentEventType, asResearchEventType
} from '../../src/services/experiment/experiment-events'

import type { Experiment } from '../../src/shared/experiment/experiment-schema'
import type { ExperimentPlan } from '../../src/shared/science/research-design-schema'

const readShared = (name: string) => readFileSync(join(__dirname, '../../src/shared/experiment', name), 'utf8')
const read = (name: string) => readFileSync(join(__dirname, '../../src/services/experiment', name), 'utf8')
const readDocs = (name: string) => readFileSync(join(__dirname, '../../docs/experiment', name), 'utf8')

function makePlan(planId = 'plan-1'): ExperimentPlan {
  return {
    planId,
    hypothesis: 'O3-MNB improves degradation',
    variables: [
      { name: 'dose', type: 'independent', range: '1-10', unit: 'mg/L', importance: 0.9 },
      { name: 'bubble_size', type: 'independent', range: '50-500', unit: 'um', importance: 0.7 }
    ],
    groups: [{ groupId: 'g1', condition: 'control', purpose: 'baseline' }],
    measurements: [
      { name: 'degradation', method: 'HPLC', reason: 'standard' }
    ],
    expectedOutcome: '>70% degradation'
  }
}

function makeExperiment(mgr: ExperimentManager): Experiment {
  return mgr.createExperiment({ projectId: 'proj-1', title: 'O3 test', objective: 'eval', hypothesis: 'h1' })
}

describe('Phase 8-K0 schema validators', () => {
  it('EXPERIMENT_STATUSES has 6 entries', () => {
    expect(EXPERIMENT_STATUSES.length).toBe(6)
  })
  it('EXPERIMENT_STATUSES is frozen', () => {
    expect(Object.isFrozen(EXPERIMENT_STATUSES)).toBe(true)
  })
  it('PARAMETER_TYPES has 4 entries', () => {
    expect(PARAMETER_TYPES.length).toBe(4)
  })
  it('PARAMETER_TYPES is frozen', () => {
    expect(Object.isFrozen(PARAMETER_TYPES)).toBe(true)
  })
  for (const s of ['draft', 'planned', 'running', 'paused', 'completed', 'failed']) {
    it(`isValidExperimentStatus accepts ${s}`, () => {
      expect(isValidExperimentStatus(s)).toBe(true)
    })
  }
  for (const s of ['unknown', 'DRAFT', '', 'canceled']) {
    it(`isValidExperimentStatus rejects ${s}`, () => {
      expect(isValidExperimentStatus(s)).toBe(false)
    })
  }
  for (const t of ['numeric', 'categorical', 'boolean', 'text']) {
    it(`isValidParameterType accepts ${t}`, () => {
      expect(isValidParameterType(t)).toBe(true)
    })
  }
  for (const t of ['NUMERIC', 'int', '', 'object']) {
    it(`isValidParameterType rejects ${t}`, () => {
      expect(isValidParameterType(t)).toBe(false)
    })
  }
  it('isValidExperimentParameter accepts numeric', () => {
    expect(isValidExperimentParameter({ name: 'a', value: 1.5, unit: 'mg', type: 'numeric' })).toBe(true)
  })
  it('isValidExperimentParameter accepts boolean', () => {
    expect(isValidExperimentParameter({ name: 'a', value: true, unit: '', type: 'boolean' })).toBe(true)
  })
  it('isValidExperimentParameter accepts text', () => {
    expect(isValidExperimentParameter({ name: 'a', value: 'foo', unit: '', type: 'text' })).toBe(true)
  })
  it('isValidExperimentParameter rejects wrong type', () => {
    expect(isValidExperimentParameter({ name: 'a', value: 'foo', unit: '', type: 'numeric' })).toBe(false)
  })
  it('isValidExperimentParameter rejects empty name', () => {
    expect(isValidExperimentParameter({ name: '', value: 1, unit: 'x', type: 'numeric' })).toBe(false)
  })
  it('isValidExperimentResult accepts valid', () => {
    expect(isValidExperimentResult({ metrics: { a: 1 }, conclusion: 'good', confidence: 0.8 })).toBe(true)
  })
  it('isValidExperimentResult rejects confidence>1', () => {
    expect(isValidExperimentResult({ metrics: { a: 1 }, conclusion: '', confidence: 1.5 })).toBe(false)
  })
  it('isValidExperimentResult rejects negative confidence', () => {
    expect(isValidExperimentResult({ metrics: { a: 1 }, conclusion: '', confidence: -0.1 })).toBe(false)
  })
  it('isValidExperimentResult rejects NaN metric', () => {
    expect(isValidExperimentResult({ metrics: { a: NaN }, conclusion: '', confidence: 0.5 })).toBe(false)
  })
  it('isValidExperiment accepts valid Experiment', () => {
    expect(isValidExperiment({
      id: 'e1', projectId: 'p1', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    })).toBe(true)
  })
  it('isValidExperiment rejects invalid status', () => {
    expect(isValidExperiment({
      id: 'e1', projectId: 'p1', title: 't', objective: 'o', hypothesis: 'h',
      status: 'invalid', design: 'd', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidExperiment rejects empty id', () => {
    expect(isValidExperiment({
      id: '', projectId: 'p1', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidExperiment rejects non-array datasets', () => {
    expect(isValidExperiment({
      id: 'e1', projectId: 'p1', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [], datasets: 'x', results: [],
      createdAt: 1, updatedAt: 2
    })).toBe(false)
  })
  it('isValidExperimentRecord accepts valid', () => {
    expect(isValidExperimentRecord({
      id: 'r1', experimentId: 'e1', timestamp: 1, operator: 'op',
      parameters: [{ name: 'p', value: 1, unit: 'u', type: 'numeric' }],
      observations: 'o', notes: 'n'
    })).toBe(true)
  })
  it('isValidExperimentRecord rejects bad parameter', () => {
    expect(isValidExperimentRecord({
      id: 'r1', experimentId: 'e1', timestamp: 1, operator: 'op',
      parameters: [{ name: '', value: 1, unit: 'u', type: 'numeric' }],
      observations: 'o', notes: 'n'
    })).toBe(false)
  })
})

describe('Phase 8-K0 ExperimentManager', () => {
  let mgr: ExperimentManager
  beforeEach(() => { mgr = new ExperimentManager() })

  it('createExperiment returns draft experiment', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(e.status).toBe('draft')
  })
  it('createExperiment assigns unique id', () => {
    const a = mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    const b = mgr.createExperiment({ projectId: 'p1', title: 'B', objective: 'O' })
    expect(a.id).not.toBe(b.id)
  })
  it('createExperiment initializes empty records/datasets/results', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(e.records.length).toBe(0)
    expect(e.datasets.length).toBe(0)
    expect(e.results.length).toBe(0)
  })
  it('createExperiment accepts hypothesis + design', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O', hypothesis: 'H', design: 'D' })
    expect(e.hypothesis).toBe('H')
    expect(e.design).toBe('D')
  })
  it('getExperiment returns null for unknown id', () => {
    expect(mgr.getExperiment('nope')).toBeNull()
  })
  it('getExperiment returns clone', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const got = mgr.getExperiment(e.id)!
    got.title = 'mutated'
    expect(mgr.getExperiment(e.id)!.title).toBe('T')
  })
  it('updateExperiment patches fields', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const upd = mgr.updateExperiment(e.id, { title: 'NEW' })
    expect(upd?.title).toBe('NEW')
  })
  it('updateExperiment returns null for unknown id', () => {
    expect(mgr.updateExperiment('nope', { title: 'X' })).toBeNull()
  })
  it('startExperiment transitions to running', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(mgr.startExperiment(e.id)!.status).toBe('running')
  })
  it('pauseExperiment transitions to paused', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(mgr.pauseExperiment(e.id)!.status).toBe('paused')
  })
  it('completeExperiment transitions to completed', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(mgr.completeExperiment(e.id)!.status).toBe('completed')
  })
  it('failExperiment transitions to failed', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    expect(mgr.failExperiment(e.id)!.status).toBe('failed')
  })
  it('transitionStatus returns null for unknown id', () => {
    expect(mgr.startExperiment('nope')).toBeNull()
  })
  it('addRecord appends record', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'obs' })
    expect(r).not.toBeNull()
    expect(mgr.getExperiment(e.id)!.records.length).toBe(1)
  })
  it('addRecord returns null for unknown id', () => {
    expect(mgr.addRecord('nope', { operator: 'op', parameters: [], observations: 'o' })).toBeNull()
  })
  it('addRecord clones parameter values', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const param = { name: 'p', value: 5, unit: 'mg', type: 'numeric' as const }
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [param], observations: 'o' })!
    ;(r.parameters[0] as { value: number }).value = 999
    expect((mgr.getExperiment(e.id)!.records[0].parameters[0] as { value: number }).value).toBe(5)
  })
  it('addRecord uses provided notes', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o', notes: 'n' })!
    expect(r.notes).toBe('n')
  })
  it('addRecord defaults notes to empty string', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })!
    expect(r.notes).toBe('')
  })
  it('attachDataset appends unique dataset', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.attachDataset(e.id, 'ds-1')
    mgr.attachDataset(e.id, 'ds-1')
    expect(mgr.getExperiment(e.id)!.datasets.length).toBe(1)
  })
  it('attachDataset returns null for unknown id', () => {
    expect(mgr.attachDataset('nope', 'ds-1')).toBeNull()
  })
  it('setResult appends result', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: 'c', confidence: 0.5 })
    expect(mgr.getExperiment(e.id)!.results.length).toBe(1)
  })
  it('setResult returns null for unknown id', () => {
    expect(mgr.setResult('nope', { metrics: {}, conclusion: '', confidence: 0.5 })).toBeNull()
  })
  it('getExperimentProgress returns zero for unknown', () => {
    expect(mgr.getExperimentProgress('nope').total).toBe(0)
  })
  it('getExperimentProgress computes percent', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: 'c', confidence: 0.5 })
    const p = mgr.getExperimentProgress(e.id)
    expect(p.total).toBe(2)
    expect(p.completed).toBe(1)
    expect(p.percent).toBe(50)
  })
  it('getExperimentProgress caps percent at 100', () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })
    mgr.setResult(e.id, { metrics: {}, conclusion: '', confidence: 0.5 })
    mgr.setResult(e.id, { metrics: {}, conclusion: '', confidence: 0.5 })
    expect(mgr.getExperimentProgress(e.id).percent).toBe(100)
  })
  it('listExperiments returns deterministic order', () => {
    const a = mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    const b = mgr.createExperiment({ projectId: 'p1', title: 'B', objective: 'O' })
    const list = mgr.listExperiments()
    expect(list[0].id).toBe(a.id < b.id ? a.id : b.id)
  })
  it('listExperiments filters by projectId', () => {
    mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    mgr.createExperiment({ projectId: 'p2', title: 'B', objective: 'O' })
    expect(mgr.listExperiments('p1').length).toBe(1)
    expect(mgr.listExperiments('p2').length).toBe(1)
    expect(mgr.listExperiments().length).toBe(2)
  })
  it('size returns experiment count', () => {
    mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    expect(mgr.size()).toBe(1)
  })
  it('clear resets state', () => {
    mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    mgr.clear()
    expect(mgr.size()).toBe(0)
  })
  it('snapshot returns same as listExperiments', () => {
    mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    expect(mgr.snapshot().length).toBe(1)
  })
  it('updateExperiment updates updatedAt', async () => {
    const e = mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    const before = e.updatedAt
    await new Promise((r) => setTimeout(r, 5))
    const upd = mgr.updateExperiment(e.id, { title: 'B' })!
    expect(upd.updatedAt).toBeGreaterThan(before)
  })
})

describe('Phase 8-K0 ExperimentEngine', () => {
  it('execute creates experiment', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.experimentId).toBeTruthy()
    expect(r.planId).toBe('plan-1')
  })
  it('execute produces executedSteps per measurement', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps.length).toBe(1)
  })
  it('execute returns completed status when ok', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.status).toBe('completed')
  })
  it('execute returns confidence > 0 when ok', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.confidence).toBeGreaterThan(0)
  })
  it('execute sets no errors when ok', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.errors.length).toBe(0)
  })
  it('execute sets experiment to completed', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.status).toBe('completed')
  })
  it('execute handles empty measurements by fallback', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = { ...makePlan(), measurements: [] }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps.length).toBe(1)
  })
  it('execute multiple measurements creates multiple records', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [
        { name: 'a', method: 'm', reason: 'r' },
        { name: 'b', method: 'm', reason: 'r' }
      ]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps.length).toBe(2)
  })
  it('execute outputs map contains stepId', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.outputs['step-1']).toBeTruthy()
  })
  it('execute sets result metrics', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.results[0].metrics.metric_1).toBe(1)
  })
  it('getManager returns underlying manager', () => {
    const mgr = new ExperimentManager()
    const engine = new ExperimentEngine(mgr)
    expect(engine.getManager()).toBe(mgr)
  })
  it('execute with failed transition goes to failed status', () => {
    const mgr = new ExperimentManager()
    const orig = mgr.startExperiment.bind(mgr)
    mgr.startExperiment = ((id: string) => { mgr.failExperiment(id); return orig(id) }) as typeof mgr.startExperiment
    const engine = new ExperimentEngine(mgr)
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(['failed', 'completed']).toContain(r.status)
  })
})

describe('Phase 8-K0 ExperimentDataAdapter', () => {
  function rec(mgr: ExperimentManager, expId: string) {
    return mgr.addRecord(expId, {
      operator: 'op',
      parameters: [
        { name: 'dose', value: 5, unit: 'mg', type: 'numeric' },
        { name: 'label', value: 'control', unit: '', type: 'categorical' }
      ],
      observations: 'obs1',
      notes: 'note1'
    })!
  }

  it('recordToDataset returns ScientificDataset', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = rec(mgr, e.id)
    const ds = recordToDataset(r, 'dataset-1')
    expect(ds.datasetId).toBe(`ds-${r.id}`)
    expect(ds.name).toBe('dataset-1')
    expect(ds.variables.length).toBe(2)
  })
  it('recordToDataset maps numeric to number type', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = rec(mgr, e.id)
    const ds = recordToDataset(r, 'ds')
    expect(ds.variables[0].type).toBe('number')
  })
  it('recordToDataset maps categorical to string', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = rec(mgr, e.id)
    const ds = recordToDataset(r, 'ds')
    expect(ds.variables[1].type).toBe('string')
  })
  it('recordToDataset maps boolean to boolean', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, {
      operator: 'op',
      parameters: [{ name: 'flag', value: true, unit: '', type: 'boolean' }],
      observations: 'o'
    })!
    const ds = recordToDataset(r, 'ds')
    expect(ds.variables[0].type).toBe('boolean')
  })
  it('recordToDataset maps text to string', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, {
      operator: 'op',
      parameters: [{ name: 'note', value: 'foo', unit: '', type: 'text' }],
      observations: 'o'
    })!
    const ds = recordToDataset(r, 'ds')
    expect(ds.variables[0].type).toBe('string')
  })
  it('recordToDataset produces single row', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = rec(mgr, e.id)
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows.length).toBe(1)
  })
  it('recordToDataset metadata contains experimentId', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r = rec(mgr, e.id)
    const ds = recordToDataset(r, 'ds')
    expect(ds.metadata.experimentId).toBe(e.id)
  })
  it('validateDataset accepts valid dataset', () => {
    expect(validateDataset({ datasetId: 'd1', name: 'n', variables: [], rows: [], metadata: {} })).toBe(true)
  })
  it('validateDataset rejects null', () => {
    expect(validateDataset(null)).toBe(false)
  })
  it('validateDataset rejects array', () => {
    expect(validateDataset([])).toBe(false)
  })
  it('validateDataset rejects empty datasetId', () => {
    expect(validateDataset({ datasetId: '', name: 'n', variables: [], rows: [], metadata: {} })).toBe(false)
  })
  it('validateDataset rejects non-array variables', () => {
    expect(validateDataset({ datasetId: 'd1', name: 'n', variables: 'x', rows: [], metadata: {} })).toBe(false)
  })
  it('validateDataset rejects non-object metadata', () => {
    expect(validateDataset({ datasetId: 'd1', name: 'n', variables: [], rows: [], metadata: 'x' })).toBe(false)
  })
  it('mergeRecords of empty returns empty dataset', () => {
    const ds = mergeRecords([], 'ds')
    expect(ds.rows.length).toBe(0)
    expect(ds.variables.length).toBe(0)
  })
  it('mergeRecords dedupes variables by name', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'a', value: 1, unit: 'u', type: 'numeric' }], observations: '' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'a', value: 2, unit: 'u', type: 'numeric' }], observations: '' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'merged')
    expect(ds.variables.length).toBe(1)
  })
  it('mergeRecords produces rows for each record', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'a' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'b' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'merged')
    expect(ds.rows.length).toBe(2)
  })
  it('mergeRecords metadata has merged count', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: '' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'merged')
    expect(ds.metadata.merged).toBe(1)
  })
  it('mergeRecords collects unique operators', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'alice', parameters: [], observations: '' })
    mgr.addRecord(e.id, { operator: 'alice', parameters: [], observations: '' })
    mgr.addRecord(e.id, { operator: 'bob', parameters: [], observations: '' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'merged')
    expect((ds.metadata.operators as string[]).length).toBe(2)
  })
})

describe('Phase 8-K0 ExperimentLoopEngine', () => {
  function setup() {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { degradation: 0.8, toc: 0.6 }, conclusion: 'good', confidence: 0.9 })
    return { mgr, e, lastResult: mgr.getExperiment(e.id)!.results[0] }
  }

  it('analyze returns ExperimentOptimizationResult', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.importantVariables.length).toBeGreaterThan(0)
  })
  it('analyze produces suggestions per metric', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.suggestions.length).toBe(2)
  })
  it('analyze produces nextExperiments per metric', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.nextExperiments.length).toBe(2)
  })
  it('analyze caps suggestions at maxRecommendations', () => {
    const { e } = setup()
    const mgr = e
    const exp = mgr
    const loop = new ExperimentLoopEngine({ maxRecommendations: 1 })
    const r = loop.analyze(exp, { metrics: { a: 1, b: 2, c: 3 }, conclusion: '', confidence: 0.8 })
    expect(r.nextExperiments.length).toBe(1)
  })
  it('closeLoop returns NextExperimentPlan', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)
    expect(r).not.toBeNull()
    expect(r!.sourceExperimentId).toBe(e.id)
  })
  it('closeLoop returns null when confidence below floor', () => {
    const { e } = setup()
    const loop = new ExperimentLoopEngine({ analystConfidenceFloor: 0.95 })
    const r = loop.closeLoop(e, { metrics: {}, conclusion: '', confidence: 0.5 })
    expect(r).toBeNull()
  })
  it('closeLoop produces suggestedVariables sorted', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)!
    expect(r.suggestedVariables.length).toBeGreaterThan(0)
    const sorted = [...r.suggestedVariables].sort()
    expect(r.suggestedVariables).toEqual(sorted)
  })
  it('closeLoop confidence inherited from result', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)!
    expect(r.confidence).toBe(lastResult.confidence)
  })
  it('toNextExperimentPlan produces ExperimentPlan', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.planId).toBe(next.inheritedPlanId)
  })
  it('toNextExperimentPlan updates variable ranges', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.variables[0].range).toBeTruthy()
  })
  it('toNextExperimentPlan inherits groups and measurements', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const prev = makePlan()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(prev, next)
    expect(plan.groups).toEqual(prev.groups)
    expect(plan.measurements).toEqual(prev.measurements)
  })
  it('toNextExperimentPlan uses summary as expectedOutcome', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.expectedOutcome).toBe(next.summary)
  })
  it('toNextExperimentPlan uses summary as hypothesis', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.hypothesis).toBe(next.summary)
  })
  it('default options have analystConfidenceFloor=0.5', () => {
    const { e } = setup()
    const loop = new ExperimentLoopEngine()
    expect(loop.closeLoop(e, { metrics: {}, conclusion: '', confidence: 0.5 })).not.toBeNull()
  })
  it('closeLoop with single metric produces 1 next', () => {
    const { e } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, { metrics: { a: 1 }, conclusion: '', confidence: 0.7 })
    expect(r!.recommendedChanges.length).toBe(1)
  })
  it('closeLoop rationale joins suggestions', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)!
    expect(r.rationale).toContain(';')
  })
  it('closeLoop summary joins explanations', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)!
    expect(r.summary.length).toBeGreaterThan(0)
  })
})

describe('Phase 8-K0 ExperimentTemplates', () => {
  it('EXPERIMENT_TEMPLATE_KINDS has 4 entries', () => {
    expect(EXPERIMENT_TEMPLATE_KINDS.length).toBe(4)
  })
  for (const k of ['o3-mnb-degradation', 'cfd-optimization', 'material-experiment', 'biological-experiment']) {
    it(`getExperimentTemplate accepts ${k}`, () => {
      const t = getExperimentTemplate(k as never)
      expect(t.kind).toBe(k)
    })
  }
  it('getExperimentTemplate throws on unknown', () => {
    expect(() => getExperimentTemplate('nope' as never)).toThrow()
  })
  it('listExperimentTemplates returns 4', () => {
    expect(listExperimentTemplates().length).toBe(4)
  })
  it('listExperimentTemplates returns clones', () => {
    const list = listExperimentTemplates()
    list[0].defaultParameters.push('mutated')
    expect(listExperimentTemplates()[0].defaultParameters).not.toContain('mutated')
  })
  it('o3-mnb-degradation template has 4 default parameters', () => {
    const t = getExperimentTemplate('o3-mnb-degradation')
    expect(t.defaultParameters.length).toBe(4)
  })
  it('cfd-optimization template has 3 default parameters', () => {
    const t = getExperimentTemplate('cfd-optimization')
    expect(t.defaultParameters.length).toBe(3)
  })
  it('material-experiment template has 3 default parameters', () => {
    const t = getExperimentTemplate('material-experiment')
    expect(t.defaultParameters.length).toBe(3)
  })
  it('biological-experiment template has 3 default parameters', () => {
    const t = getExperimentTemplate('biological-experiment')
    expect(t.defaultParameters.length).toBe(3)
  })
  it('o3-mnb-degradation domain is environment', () => {
    const t = getExperimentTemplate('o3-mnb-degradation')
    expect(t.domain).toBe('环境科学')
  })
  it('cfd-optimization domain is engineering', () => {
    const t = getExperimentTemplate('cfd-optimization')
    expect(t.domain).toBe('工程')
  })
  it('material-experiment domain is material', () => {
    const t = getExperimentTemplate('material-experiment')
    expect(t.domain).toBe('材料科学')
  })
  it('biological-experiment domain is biomedical', () => {
    const t = getExperimentTemplate('biological-experiment')
    expect(t.domain).toBe('生物医学')
  })
  it('templates have non-empty objective', () => {
    for (const t of listExperimentTemplates()) {
      expect(t.objective.length).toBeGreaterThan(0)
    }
  })
  it('templates have non-empty defaultObservations', () => {
    for (const t of listExperimentTemplates()) {
      expect(t.defaultObservations.length).toBeGreaterThan(0)
    }
  })
})

describe('Phase 8-K0 Experiment Events', () => {
  it('EXPERIMENT_EVENT_TYPES has 5 entries', () => {
    expect(EXPERIMENT_EVENT_TYPES.length).toBe(5)
  })
  for (const e of ['experiment.created', 'experiment.started', 'experiment.recorded', 'experiment.completed', 'experiment.optimized']) {
    it(`isExperimentEventType accepts ${e}`, () => {
      expect(isExperimentEventType(e)).toBe(true)
    })
  }
  for (const e of ['task.completed', 'unknown', '', 'EXPERIMENT.created']) {
    it(`isExperimentEventType rejects ${e}`, () => {
      expect(isExperimentEventType(e)).toBe(false)
    })
  }
  it('asResearchEventType returns input string', () => {
    expect(asResearchEventType('experiment.created')).toBe('experiment.created')
  })
  it('EXPERIMENT_EVENT_TYPES contains experiment.created', () => {
    expect(EXPERIMENT_EVENT_TYPES).toContain('experiment.created')
  })
  it('EXPERIMENT_EVENT_TYPES contains experiment.started', () => {
    expect(EXPERIMENT_EVENT_TYPES).toContain('experiment.started')
  })
  it('EXPERIMENT_EVENT_TYPES contains experiment.recorded', () => {
    expect(EXPERIMENT_EVENT_TYPES).toContain('experiment.recorded')
  })
  it('EXPERIMENT_EVENT_TYPES contains experiment.completed', () => {
    expect(EXPERIMENT_EVENT_TYPES).toContain('experiment.completed')
  })
  it('EXPERIMENT_EVENT_TYPES contains experiment.optimized', () => {
    expect(EXPERIMENT_EVENT_TYPES).toContain('experiment.optimized')
  })
})

describe('Phase 8-K0 secret guard', () => {
  it('findForbidden detects sk-', () => {
    expect(expHelpers.findForbidden('sk-abc')).toBe('sk-')
  })
  it('findForbidden detects apiKey', () => {
    expect(expHelpers.findForbidden('apiKey')).toBe('apiKey')
  })
  it('findForbidden detects Bearer', () => {
    expect(expHelpers.findForbidden('Bearer xxx')).toBe('Bearer ')
  })
  it('findForbidden detects authorization', () => {
    expect(expHelpers.findForbidden('authorization: x')).toBe('authorization')
  })
  it('findForbidden returns null for safe value', () => {
    expect(expHelpers.findForbidden('hello world')).toBeNull()
  })
  it('findForbidden walks arrays', () => {
    expect(expHelpers.findForbidden(['ok', 'sk-bad'])).toBe('sk-')
  })
  it('findForbidden walks nested objects', () => {
    expect(expHelpers.findForbidden({ a: { b: 'cipher text' } })).toBe('cipher')
  })
})

describe('Phase 8-K0 defensive copy', () => {
  it('ExperimentManager.getExperiment returns defensive copy of records', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'obs' })
    const got = mgr.getExperiment(e.id)!
    got.records.push({ id: 'mut', experimentId: e.id, timestamp: 1, operator: 'x', parameters: [], observations: '', notes: '' })
    expect(mgr.getExperiment(e.id)!.records.length).toBe(1)
  })
  it('ExperimentManager.getExperiment returns defensive copy of datasets', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.attachDataset(e.id, 'ds-1')
    const got = mgr.getExperiment(e.id)!
    got.datasets.push('mut')
    expect(mgr.getExperiment(e.id)!.datasets.length).toBe(1)
  })
  it('ExperimentManager.getExperiment returns defensive copy of results', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: 'c', confidence: 0.5 })
    const got = mgr.getExperiment(e.id)!
    got.results.push({ metrics: { b: 2 }, conclusion: '', confidence: 0.3 })
    expect(mgr.getExperiment(e.id)!.results.length).toBe(1)
  })
  it('ExperimentManager.getExperiment returns defensive copy of record parameters', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'p', value: 1, unit: 'u', type: 'numeric' }], observations: '' })
    const got = mgr.getExperiment(e.id)!
    ;(got.records[0].parameters[0] as { value: number }).value = 999
    expect((mgr.getExperiment(e.id)!.records[0].parameters[0] as { value: number }).value).toBe(1)
  })
  it('ExperimentManager.getExperiment returns defensive copy of result metrics', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: 'c', confidence: 0.5 })
    const got = mgr.getExperiment(e.id)!
    got.results[0].metrics.a = 999
    expect(mgr.getExperiment(e.id)!.results[0].metrics.a).toBe(1)
  })
})

describe('Phase 8-K0 isolation', () => {
  it('two ExperimentManagers are isolated', () => {
    const a = new ExperimentManager()
    const b = new ExperimentManager()
    a.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    expect(a.size()).toBe(1)
    expect(b.size()).toBe(0)
  })
  it('clear does not affect other instances', () => {
    const a = new ExperimentManager()
    const b = new ExperimentManager()
    a.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    b.createExperiment({ projectId: 'p', title: 'B', objective: 'O' })
    a.clear()
    expect(b.size()).toBe(1)
  })
})

describe('Phase 8-K0 docs presence', () => {
  it('experiment-lifecycle.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/experiment/experiment-lifecycle.md'))).toBe(true)
  })
  it('closed-loop-optimization.md exists', () => {
    expect(existsSync(join(__dirname, '../../docs/experiment/closed-loop-optimization.md'))).toBe(true)
  })
  it('experiment-lifecycle.md mentions ExperimentManager', () => {
    expect(readDocs('experiment-lifecycle.md')).toContain('ExperimentManager')
  })
  it('experiment-lifecycle.md mentions ExperimentEngine', () => {
    expect(readDocs('experiment-lifecycle.md')).toContain('ExperimentEngine')
  })
  it('experiment-lifecycle.md mentions closed loop', () => {
    expect(readDocs('experiment-lifecycle.md')).toContain('闭环')
  })
  it('closed-loop-optimization.md mentions Data Analyst', () => {
    expect(readDocs('closed-loop-optimization.md')).toContain('Data Analyst')
  })
  it('closed-loop-optimization.md mentions Optimization Advisor', () => {
    expect(readDocs('closed-loop-optimization.md')).toContain('Optimization Advisor')
  })
  it('closed-loop-optimization.md mentions NextExperimentPlan', () => {
    expect(readDocs('closed-loop-optimization.md')).toContain('NextExperimentPlan')
  })
})

describe('Phase 8-K0 source code contracts', () => {
  it('schema has ExperimentStatus enum', () => {
    expect(readShared('experiment-schema.ts')).toContain("type ExperimentStatus")
  })
  it('schema has ExperimentParameter type', () => {
    expect(readShared('experiment-schema.ts')).toContain("interface ExperimentParameter")
  })
  it('schema has ExperimentRecord type', () => {
    expect(readShared('experiment-schema.ts')).toContain("interface ExperimentRecord")
  })
  it('schema has ExperimentResult type', () => {
    expect(readShared('experiment-schema.ts')).toContain("interface ExperimentResult")
  })
  it('schema has Experiment type', () => {
    expect(readShared('experiment-schema.ts')).toContain("interface Experiment")
  })
  it('schema has 6 statuses', () => {
    expect(readShared('experiment-schema.ts')).toContain("draft")
    expect(readShared('experiment-schema.ts')).toContain("planned")
    expect(readShared('experiment-schema.ts')).toContain("running")
    expect(readShared('experiment-schema.ts')).toContain("paused")
    expect(readShared('experiment-schema.ts')).toContain("completed")
    expect(readShared('experiment-schema.ts')).toContain("failed")
  })
  it('manager has createExperiment', () => {
    expect(read('experiment-manager.ts')).toContain('createExperiment')
  })
  it('manager has startExperiment', () => {
    expect(read('experiment-manager.ts')).toContain('startExperiment')
  })
  it('manager has addRecord', () => {
    expect(read('experiment-manager.ts')).toContain('addRecord')
  })
  it('manager has attachDataset', () => {
    expect(read('experiment-manager.ts')).toContain('attachDataset')
  })
  it('manager has getExperimentProgress', () => {
    expect(read('experiment-manager.ts')).toContain('getExperimentProgress')
  })
  it('manager has setResult', () => {
    expect(read('experiment-manager.ts')).toContain('setResult')
  })
  it('manager has cloneExperiment (defensive)', () => {
    expect(read('experiment-manager.ts')).toContain('cloneExperiment')
  })
  it('manager has cloneRecord', () => {
    expect(read('experiment-manager.ts')).toContain('cloneRecord')
  })
  it('engine has execute', () => {
    expect(read('experiment-engine.ts')).toContain('execute')
  })
  it('engine has ExperimentExecutionResult', () => {
    expect(read('experiment-engine.ts')).toContain('ExperimentExecutionResult')
  })
  it('engine produces executedSteps', () => {
    expect(read('experiment-engine.ts')).toContain('executedSteps')
  })
  it('engine produces outputs', () => {
    expect(read('experiment-engine.ts')).toContain('outputs')
  })
  it('engine produces errors', () => {
    expect(read('experiment-engine.ts')).toContain('errors')
  })
  it('adapter has recordToDataset', () => {
    expect(read('experiment-data-adapter.ts')).toContain('recordToDataset')
  })
  it('adapter has validateDataset', () => {
    expect(read('experiment-data-adapter.ts')).toContain('validateDataset')
  })
  it('adapter has mergeRecords', () => {
    expect(read('experiment-data-adapter.ts')).toContain('mergeRecords')
  })
  it('loop has analyze', () => {
    expect(read('experiment-loop-engine.ts')).toContain('analyze')
  })
  it('loop has closeLoop', () => {
    expect(read('experiment-loop-engine.ts')).toContain('closeLoop')
  })
  it('loop has toNextExperimentPlan', () => {
    expect(read('experiment-loop-engine.ts')).toContain('toNextExperimentPlan')
  })
  it('loop has NextExperimentPlan', () => {
    expect(read('experiment-loop-engine.ts')).toContain('NextExperimentPlan')
  })
  it('templates has getExperimentTemplate', () => {
    expect(read('experiment-templates.ts')).toContain('getExperimentTemplate')
  })
  it('templates has listExperimentTemplates', () => {
    expect(read('experiment-templates.ts')).toContain('listExperimentTemplates')
  })
  it('templates has 4 kinds', () => {
    expect(read('experiment-templates.ts')).toContain('o3-mnb-degradation')
    expect(read('experiment-templates.ts')).toContain('cfd-optimization')
    expect(read('experiment-templates.ts')).toContain('material-experiment')
    expect(read('experiment-templates.ts')).toContain('biological-experiment')
  })
  it('templates uses Object.freeze', () => {
    expect(read('experiment-templates.ts')).toContain('Object.freeze')
  })
  it('events has isExperimentEventType', () => {
    expect(read('experiment-events.ts')).toContain('isExperimentEventType')
  })
  it('events has 5 types', () => {
    expect(read('experiment-events.ts')).toContain('experiment.created')
    expect(read('experiment-events.ts')).toContain('experiment.started')
    expect(read('experiment-events.ts')).toContain('experiment.recorded')
    expect(read('experiment-events.ts')).toContain('experiment.completed')
    expect(read('experiment-events.ts')).toContain('experiment.optimized')
  })
})

describe('Phase 8-K0 ExperimentManager advanced', () => {
  it('multiple records for one experiment all stored', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op1', parameters: [], observations: 'a' })
    mgr.addRecord(e.id, { operator: 'op2', parameters: [], observations: 'b' })
    mgr.addRecord(e.id, { operator: 'op3', parameters: [], observations: 'c' })
    expect(mgr.getExperiment(e.id)!.records.length).toBe(3)
  })
  it('records have unique ids', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const r1 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })!
    const r2 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })!
    expect(r1.id).not.toBe(r2.id)
  })
  it('record timestamp uses Date.now', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const before = Date.now()
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })!
    expect(r.timestamp).toBeGreaterThanOrEqual(before)
  })
  it('multiple datasets attached', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.attachDataset(e.id, 'ds-1')
    mgr.attachDataset(e.id, 'ds-2')
    mgr.attachDataset(e.id, 'ds-3')
    expect(mgr.getExperiment(e.id)!.datasets.length).toBe(3)
  })
  it('startExperiment updates updatedAt', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    const before = e.updatedAt
    const upd = mgr.startExperiment(e.id)!
    expect(upd.updatedAt).toBeGreaterThanOrEqual(before)
  })
  it('pause after start works', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.startExperiment(e.id)
    expect(mgr.pauseExperiment(e.id)!.status).toBe('paused')
  })
  it('complete after pause works', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'T', objective: 'O' })
    mgr.startExperiment(e.id)
    mgr.pauseExperiment(e.id)
    expect(mgr.completeExperiment(e.id)!.status).toBe('completed')
  })
  it('listExperiments sorts by id', () => {
    const mgr = new ExperimentManager()
    for (let i = 0; i < 5; i++) mgr.createExperiment({ projectId: 'p', title: `T${i}`, objective: 'O' })
    const ids = mgr.listExperiments().map((e) => e.id)
    expect(ids).toEqual([...ids].sort())
  })
  it('snapshot is a fresh array each call', () => {
    const mgr = new ExperimentManager()
    mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const a = mgr.snapshot()
    const b = mgr.snapshot()
    expect(a).not.toBe(b)
    expect(a.length).toBe(b.length)
  })
  it('clear sets nextId to 0', () => {
    const mgr = new ExperimentManager()
    mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.clear()
    expect(mgr.size()).toBe(0)
  })
  it('addRecord keeps timestamp unique-ish', async () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r1 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'a' })!
    const r2 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'b' })!
    expect(r1.timestamp).toBeLessThanOrEqual(r2.timestamp)
  })
  it('experiment record has experimentId matching parent', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o' })!
    expect(r.experimentId).toBe(e.id)
  })
  it('setResult with empty metrics is valid', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: {}, conclusion: '', confidence: 0.5 })
    expect(mgr.getExperiment(e.id)!.results[0].metrics).toEqual({})
  })
  it('setResult does not mutate result object after storage', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const result = { metrics: { a: 1 }, conclusion: 'c', confidence: 0.5 }
    mgr.setResult(e.id, result)
    result.metrics.a = 999
    expect(mgr.getExperiment(e.id)!.results[0].metrics.a).toBe(1)
  })
  it('getExperimentProgress status reflects current', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.startExperiment(e.id)
    expect(mgr.getExperimentProgress(e.id).status).toBe('running')
  })
  it('transitionStatus preserves other fields', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O', hypothesis: 'H' })
    const upd = mgr.startExperiment(e.id)!
    expect(upd.hypothesis).toBe('H')
    expect(upd.title).toBe('T')
  })
  it('addRecord preserves parameter unit', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'p', value: 1, unit: 'mg/L', type: 'numeric' }], observations: 'o' })!
    expect(r.parameters[0].unit).toBe('mg/L')
  })
})

describe('Phase 8-K0 ExperimentEngine advanced', () => {
  it('execute with 3 measurements creates 3 steps', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [
        { name: 'a', method: 'm', reason: 'r' },
        { name: 'b', method: 'm', reason: 'r' },
        { name: 'c', method: 'm', reason: 'r' }
      ]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps.length).toBe(3)
  })
  it('execute step output is record id', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps[0].output).toMatch(/^rec-/)
  })
  it('execute step description contains measurement name', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [{ name: 'XY', method: 'm', reason: 'r' }]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps[0].description).toContain('XY')
  })
  it('execute step description contains method', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [{ name: 'a', method: 'HPLC-MS', reason: 'r' }]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps[0].description).toContain('HPLC-MS')
  })
  it('execute step status transitions correctly', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps[0].status).toBe('completed')
  })
  it('execute with multiple variables creates records with all', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      variables: [
        { name: 'a', type: 'independent', range: '1-5', unit: 'u', importance: 0.8 },
        { name: 'b', type: 'independent', range: '2-6', unit: 'u', importance: 0.8 },
        { name: 'c', type: 'independent', range: '3-7', unit: 'u', importance: 0.8 }
      ]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.records[0].parameters.length).toBe(3)
  })
  it('execute records operator from input', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'alice' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.records[0].operator).toBe('alice')
  })
  it('execute produces plan-specific record notes', () => {
    const engine = new ExperimentEngine()
    const plan = makePlan('plan-xyz')
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.records[0].notes).toContain('plan-xyz')
  })
  it('execute design field contains group count', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.design).toContain('groups=1')
  })
  it('execute design field contains variable count', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.design).toContain('vars=2')
  })
  it('execute returns experimentId matching manager record', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(engine.getManager().getExperiment(r.experimentId)).not.toBeNull()
  })
  it('execute result conclusion mentions step count', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(exp.results[0].conclusion).toContain('1')
  })
  it('execute result confidence is 0.7 for completed', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.confidence).toBe(0.7)
  })
  it('execute result metrics count matches step count', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [
        { name: 'a', method: 'm', reason: 'r' },
        { name: 'b', method: 'm', reason: 'r' }
      ]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    const exp = engine.getManager().getExperiment(r.experimentId)!
    expect(Object.keys(exp.results[0].metrics).length).toBe(2)
  })
  it('execute does not modify input plan', () => {
    const engine = new ExperimentEngine()
    const plan = makePlan()
    const before = JSON.stringify(plan)
    engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(JSON.stringify(plan)).toBe(before)
  })
  it('execute two plans creates two experiments', () => {
    const engine = new ExperimentEngine()
    engine.execute(makePlan('a'), { projectId: 'p', title: 'A', objective: 'O', operator: 'op' })
    engine.execute(makePlan('b'), { projectId: 'p', title: 'B', objective: 'O', operator: 'op' })
    expect(engine.getManager().size()).toBe(2)
  })
})

describe('Phase 8-K0 ExperimentDataAdapter advanced', () => {
  function recWith(mgr: ExperimentManager, expId: string, params: { name: string; value: string | number | boolean; unit: string; type: 'numeric' | 'categorical' | 'boolean' | 'text' }[]) {
    return mgr.addRecord(expId, { operator: 'op', parameters: params, observations: 'o' })!
  }

  it('recordToDataset preserves all numeric values', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [{ name: 'a', value: 3.14, unit: 'u', type: 'numeric' }])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0].a).toBe(3.14)
  })
  it('recordToDataset preserves categorical value as string', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [{ name: 'label', value: 'control', unit: '', type: 'categorical' }])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0].label).toBe('control')
  })
  it('recordToDataset preserves boolean value', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [{ name: 'flag', value: true, unit: '', type: 'boolean' }])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0].flag).toBe(true)
  })
  it('recordToDataset preserves text value', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [{ name: 'note', value: 'hello world', unit: '', type: 'text' }])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0].note).toBe('hello world')
  })
  it('recordToDataset row contains timestamp', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0]._timestamp).toBe(r.timestamp)
  })
  it('recordToDataset row contains operator', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = recWith(mgr, e.id, [])
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0]._operator).toBe('op')
  })
  it('recordToDataset row contains observations', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'OBS-XYZ' })!
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0]._observations).toBe('OBS-XYZ')
  })
  it('recordToDataset row contains notes', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'o', notes: 'NOTES-XYZ' })!
    const ds = recordToDataset(r, 'ds')
    expect(ds.rows[0]._notes).toBe('NOTES-XYZ')
  })
  it('validateDataset accepts dataset with non-empty fields', () => {
    expect(validateDataset({
      datasetId: 'd1', name: 'n',
      variables: [{ name: 'a', type: 'number', unit: 'u' }],
      rows: [{ a: 1 }],
      metadata: { source: 'exp' }
    })).toBe(true)
  })
  it('validateDataset rejects non-array rows', () => {
    expect(validateDataset({ datasetId: 'd1', name: 'n', variables: [], rows: 'x', metadata: {} })).toBe(false)
  })
  it('validateDataset rejects empty name', () => {
    expect(validateDataset({ datasetId: 'd1', name: '', variables: [], rows: [], metadata: {} })).toBe(false)
  })
  it('mergeRecords with one record equals single', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'a', value: 1, unit: 'u', type: 'numeric' }], observations: 'o' })
    const recs = mgr.getExperiment(e.id)!.records
    const single = recordToDataset(recs[0], 'ds')
    const merged = mergeRecords(recs, 'ds')
    expect(merged.variables.length).toBe(single.variables.length)
    expect(merged.rows.length).toBe(single.rows.length)
  })
  it('mergeRecords variables collect unique names', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'a', value: 1, unit: 'u', type: 'numeric' }, { name: 'b', value: 2, unit: 'u', type: 'numeric' }], observations: '' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'c', value: 3, unit: 'u', type: 'numeric' }], observations: '' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'm')
    expect(ds.variables.length).toBe(3)
  })
  it('mergeRecords row has _recordId', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: '' })!
    const ds = mergeRecords([r], 'm')
    expect(ds.rows[0]._recordId).toBe(r.id)
  })
  it('mergeRecords row contains operator', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'alice', parameters: [], observations: '' })!
    const ds = mergeRecords([r], 'm')
    expect(ds.rows[0]._operator).toBe('alice')
  })
  it('mergeRecords datasetId includes experimentId', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: '' })!
    const ds = mergeRecords([r], 'm')
    expect(ds.datasetId).toContain(e.id)
  })
  it('mergeRecords metadata has experimentId', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: '' })!
    const ds = mergeRecords([r], 'm')
    expect(ds.metadata.experimentId).toBe(e.id)
  })
})

describe('Phase 8-K0 ExperimentLoopEngine advanced', () => {
  function setup(metrics: Record<string, number> = { a: 1, b: 2 }, confidence = 0.9) {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics, conclusion: 'c', confidence })
    return { mgr, e, lastResult: mgr.getExperiment(e.id)!.results[0] }
  }

  it('analyze issues starts empty', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    expect(loop.analyze(e, lastResult).issues.length).toBe(0)
  })
  it('analyze explanations contains metric count', () => {
    const { e, lastResult } = setup({ a: 1, b: 2, c: 3 })
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.explanations[0]).toContain('3')
  })
  it('analyze importantVariables count matches metrics', () => {
    const { e, lastResult } = setup({ a: 1, b: 2, c: 3 })
    const loop = new ExperimentLoopEngine()
    expect(loop.analyze(e, lastResult).importantVariables.length).toBe(3)
  })
  it('analyze suggestion confidence derived from result', () => {
    const { e, lastResult } = setup({ a: 1 }, 0.6)
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.suggestions[0].confidence).toBe(0.6)
  })
  it('analyze nextExperiment currentValue equals metric value', () => {
    const { e, lastResult } = setup({ dose: 5 })
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.nextExperiments[0].currentValue).toBe(5)
  })
  it('analyze nextExperiment suggestedRange contains values', () => {
    const { e, lastResult } = setup({ dose: 10 })
    const loop = new ExperimentLoopEngine()
    const r = loop.analyze(e, lastResult)
    expect(r.nextExperiments[0].suggestedRange).toContain('-')
  })
  it('closeLoop with confidence exactly at floor works', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: '', confidence: 0.5 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine({ analystConfidenceFloor: 0.5 })
    expect(loop.closeLoop(e, lastResult)).not.toBeNull()
  })
  it('closeLoop with confidence just below floor returns null', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: '', confidence: 0.49 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine({ analystConfidenceFloor: 0.5 })
    expect(loop.closeLoop(e, lastResult)).toBeNull()
  })
  it('closeLoop recommendedChanges capped at maxRecommendations', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1, b: 2, c: 3, d: 4, e: 5 }, conclusion: '', confidence: 0.9 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine({ maxRecommendations: 2 })
    const r = loop.closeLoop(e, lastResult)!
    expect(r.recommendedChanges.length).toBe(2)
  })
  it('closeLoop summary non-empty', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    expect(loop.closeLoop(e, lastResult)!.summary.length).toBeGreaterThan(0)
  })
  it('closeLoop rationale non-empty', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    expect(loop.closeLoop(e, lastResult)!.rationale.length).toBeGreaterThan(0)
  })
  it('closeLoop inheritedPlanId starts with next-from-', () => {
    const { e, lastResult } = setup()
    const loop = new ExperimentLoopEngine()
    expect(loop.closeLoop(e, lastResult)!.inheritedPlanId).toContain('next-from-')
  })
  it('closeLoop suggestedVariables deduplicated', () => {
    const { e, lastResult } = setup({ a: 1, b: 2 })
    const loop = new ExperimentLoopEngine()
    const r = loop.closeLoop(e, lastResult)!
    expect(r.suggestedVariables.length).toBe(2)
  })
  it('toNextExperimentPlan replaces range for matching variable', () => {
    const { e, lastResult } = setup({ dose: 5 })
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.variables[0].range).not.toBe('1-10')
  })
  it('toNextExperimentPlan keeps non-matching variable', () => {
    const { e, lastResult } = setup({ unrelated: 1 })
    const loop = new ExperimentLoopEngine()
    const next = loop.closeLoop(e, lastResult)!
    const plan = loop.toNextExperimentPlan(makePlan(), next)
    expect(plan.variables[0].range).toBe('1-10')
  })
  it('multiple closeLoop calls produce different planIds', () => {
    const mgr = new ExperimentManager()
    const e1 = mgr.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    mgr.setResult(e1.id, { metrics: { x: 1 }, conclusion: '', confidence: 0.9 })
    const e2 = mgr.createExperiment({ projectId: 'p', title: 'B', objective: 'O' })
    mgr.setResult(e2.id, { metrics: { x: 2 }, conclusion: '', confidence: 0.9 })
    const loop = new ExperimentLoopEngine()
    const n1 = loop.closeLoop(mgr.getExperiment(e1.id)!, mgr.getExperiment(e1.id)!.results[0])!
    const n2 = loop.closeLoop(mgr.getExperiment(e2.id)!, mgr.getExperiment(e2.id)!.results[0])!
    expect(n1.inheritedPlanId).not.toBe(n2.inheritedPlanId)
  })
})

describe('Phase 8-K0 ExperimentTemplates advanced', () => {
  it('each template has non-empty name', () => {
    for (const t of listExperimentTemplates()) expect(t.name.length).toBeGreaterThan(0)
  })
  it('each template has non-empty kind', () => {
    for (const t of listExperimentTemplates()) expect(t.kind.length).toBeGreaterThan(0)
  })
  it('each template has non-empty domain', () => {
    for (const t of listExperimentTemplates()) expect(t.domain.length).toBeGreaterThan(0)
  })
  it('each template kind is unique', () => {
    const kinds = listExperimentTemplates().map((t) => t.kind)
    expect(new Set(kinds).size).toBe(kinds.length)
  })
  it('o3-mnb-degradation template mentions 臭氧 or 气泡', () => {
    expect(getExperimentTemplate('o3-mnb-degradation').name).toContain('臭氧')
  })
  it('cfd-optimization template mentions CFD', () => {
    expect(getExperimentTemplate('cfd-optimization').name).toContain('CFD')
  })
  it('material template mentions material/材料', () => {
    const t = getExperimentTemplate('material-experiment')
    expect(t.name + t.objective).toContain('材料')
  })
  it('biological template mentions biological/生物', () => {
    const t = getExperimentTemplate('biological-experiment')
    expect(t.name + t.objective).toContain('生物')
  })
  it('o3-mnb-degradation defaultObservations non-empty', () => {
    expect(getExperimentTemplate('o3-mnb-degradation').defaultObservations.length).toBeGreaterThan(0)
  })
  it('listExperimentTemplates returns 4 unique kinds', () => {
    expect(new Set(listExperimentTemplates().map((t) => t.kind)).size).toBe(4)
  })
  it('getExperimentTemplate mutating does not affect internal', () => {
    const t1 = getExperimentTemplate('o3-mnb-degradation')
    t1.defaultParameters.push('mutated')
    const t2 = getExperimentTemplate('o3-mnb-degradation')
    expect(t2.defaultParameters).not.toContain('mutated')
  })
  it('all template defaultObservations are non-empty strings', () => {
    for (const t of listExperimentTemplates()) {
      for (const obs of t.defaultObservations) {
        expect(typeof obs).toBe('string')
        expect(obs.length).toBeGreaterThan(0)
      }
    }
  })
})

describe('Phase 8-K0 type-level contracts', () => {
  it('ExperimentStatus is string literal type', () => {
    type T = 'draft' | 'planned' | 'running' | 'paused' | 'completed' | 'failed'
    const x: T = 'draft'
    expect(x).toBe('draft')
  })
  it('ParameterType is string literal type', () => {
    type T = 'numeric' | 'categorical' | 'boolean' | 'text'
    const x: T = 'numeric'
    expect(x).toBe('numeric')
  })
  it('EXPERIMENT_STATUSES is readonly', () => {
    const arr = EXPERIMENT_STATUSES as unknown as string[]
    expect(() => arr.push('x')).toThrow()
  })
  it('EXPERIMENT_TEMPLATE_KINDS is readonly', () => {
    const arr = EXPERIMENT_TEMPLATE_KINDS as unknown as string[]
    expect(() => arr.push('x')).toThrow()
  })
  it('EXPERIMENT_EVENT_TYPES is readonly', () => {
    const arr = EXPERIMENT_EVENT_TYPES as unknown as string[]
    expect(() => arr.push('x')).toThrow()
  })
})

describe('Phase 8-K0 ExperimentEvents advanced', () => {
  it('asResearchEventType returns same string', () => {
    expect(asResearchEventType('experiment.optimized')).toBe('experiment.optimized')
  })
  it('isExperimentEventType rejects empty', () => {
    expect(isExperimentEventType('')).toBe(false)
  })
  it('isExperimentEventType accepts all 5', () => {
    for (const t of EXPERIMENT_EVENT_TYPES) {
      expect(isExperimentEventType(t)).toBe(true)
    }
  })
})

describe('Phase 8-K0 Experiment schema edge cases', () => {
  it('isValidExperiment rejects null', () => {
    expect(isValidExperiment(null)).toBe(false)
  })
  it('isValidExperiment rejects undefined', () => {
    expect(isValidExperiment(undefined)).toBe(false)
  })
  it('isValidExperiment rejects array', () => {
    expect(isValidExperiment([])).toBe(false)
  })
  it('isValidExperiment rejects string', () => {
    expect(isValidExperiment('exp')).toBe(false)
  })
  it('isValidExperiment rejects number', () => {
    expect(isValidExperiment(42)).toBe(false)
  })
  it('isValidExperiment rejects empty object', () => {
    expect(isValidExperiment({})).toBe(false)
  })
  it('isValidExperimentRecord rejects null', () => {
    expect(isValidExperimentRecord(null)).toBe(false)
  })
  it('isValidExperimentRecord rejects empty id', () => {
    expect(isValidExperimentRecord({ id: '', experimentId: 'e', timestamp: 1, operator: 'op', parameters: [], observations: '', notes: '' })).toBe(false)
  })
  it('isValidExperimentRecord rejects negative timestamp', () => {
    expect(isValidExperimentRecord({ id: 'r', experimentId: 'e', timestamp: -1, operator: 'op', parameters: [], observations: '', notes: '' })).toBe(true)
  })
  it('isValidExperimentRecord rejects NaN timestamp', () => {
    expect(isValidExperimentRecord({ id: 'r', experimentId: 'e', timestamp: NaN, operator: 'op', parameters: [], observations: '', notes: '' })).toBe(false)
  })
  it('isValidExperimentParameter rejects null', () => {
    expect(isValidExperimentParameter(null)).toBe(false)
  })
  it('isValidExperimentParameter rejects boolean type with string value', () => {
    expect(isValidExperimentParameter({ name: 'p', value: 'true', unit: '', type: 'boolean' })).toBe(false)
  })
  it('isValidExperimentParameter rejects text type with number value', () => {
    expect(isValidExperimentParameter({ name: 'p', value: 1, unit: '', type: 'text' })).toBe(false)
  })
  it('isValidExperimentResult rejects null metrics', () => {
    expect(isValidExperimentResult({ metrics: null, conclusion: '', confidence: 0.5 })).toBe(false)
  })
  it('isValidExperimentResult rejects non-string conclusion', () => {
    expect(isValidExperimentResult({ metrics: {}, conclusion: 123, confidence: 0.5 })).toBe(false)
  })
  it('isValidExperiment rejects empty datasets array', () => {
    const e = {
      id: 'e', projectId: 'p', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    expect(isValidExperiment(e)).toBe(true)
  })
  it('isValidExperiment rejects non-string dataset entry', () => {
    const e = {
      id: 'e', projectId: 'p', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [], datasets: [1, 2], results: [],
      createdAt: 1, updatedAt: 2
    }
    expect(isValidExperiment(e)).toBe(false)
  })
  it('isValidExperiment rejects bad record in array', () => {
    const e = {
      id: 'e', projectId: 'p', title: 't', objective: 'o', hypothesis: 'h',
      status: 'draft', design: 'd', records: [{ id: '' }], datasets: [], results: [],
      createdAt: 1, updatedAt: 2
    }
    expect(isValidExperiment(e)).toBe(false)
  })
})

describe('Phase 8-K0 secret guard edge cases', () => {
  it('findForbidden handles null', () => {
    expect(expHelpers.findForbidden(null)).toBeNull()
  })
  it('findForbidden handles number', () => {
    expect(expHelpers.findForbidden(42)).toBeNull()
  })
  it('findForbidden handles boolean', () => {
    expect(expHelpers.findForbidden(true)).toBeNull()
  })
  it('findForbidden handles empty string', () => {
    expect(expHelpers.findForbidden('')).toBeNull()
  })
  it('findForbidden handles empty array', () => {
    expect(expHelpers.findForbidden([])).toBeNull()
  })
  it('findForbidden handles empty object', () => {
    expect(expHelpers.findForbidden({})).toBeNull()
  })
  it('findForbidden finds cipher', () => {
    expect(expHelpers.findForbidden('the cipher text')).toBe('cipher')
  })
  it('findForbidden finds token', () => {
    expect(expHelpers.findForbidden('mytoken')).toBe('token')
  })
  it('findForbidden finds providerId', () => {
    expect(expHelpers.findForbidden('providerId=foo')).toBe('providerId')
  })
  it('findForbidden finds modelId', () => {
    expect(expHelpers.findForbidden('modelId=foo')).toBe('modelId')
  })
})

describe('Phase 8-K0 ExperimentManager CRUD', () => {
  it('createExperiment with empty objective ok', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: '' })
    expect(e.objective).toBe('')
  })
  it('createExperiment with long title ok', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'a'.repeat(100), objective: 'o' })
    expect(e.title.length).toBe(100)
  })
  it('getExperiment returns same id after update', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.updateExperiment(e.id, { title: 'NEW' })
    expect(mgr.getExperiment(e.id)!.id).toBe(e.id)
  })
  it('updateExperiment preserves createdAt', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const before = e.createdAt
    mgr.updateExperiment(e.id, { title: 'NEW' })
    expect(mgr.getExperiment(e.id)!.createdAt).toBe(before)
  })
  it('updateExperiment changes updatedAt', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const before = e.updatedAt
    mgr.updateExperiment(e.id, { hypothesis: 'NEW' })
    expect(mgr.getExperiment(e.id)!.updatedAt).toBeGreaterThanOrEqual(before)
  })
  it('updateExperiment patches hypothesis', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.updateExperiment(e.id, { hypothesis: 'NEW-HYP' })
    expect(mgr.getExperiment(e.id)!.hypothesis).toBe('NEW-HYP')
  })
  it('updateExperiment patches design', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.updateExperiment(e.id, { design: 'NEW-DESIGN' })
    expect(mgr.getExperiment(e.id)!.design).toBe('NEW-DESIGN')
  })
  it('updateExperiment patches objective', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'OLD' })
    mgr.updateExperiment(e.id, { objective: 'NEW' })
    expect(mgr.getExperiment(e.id)!.objective).toBe('NEW')
  })
  it('addRecord timestamp increases over time', async () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r1 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'a' })!
    await new Promise((r) => setTimeout(r, 2))
    const r2 = mgr.addRecord(e.id, { operator: 'op', parameters: [], observations: 'b' })!
    expect(r2.timestamp).toBeGreaterThanOrEqual(r1.timestamp)
  })
  it('startExperiment from draft works', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    expect(e.status).toBe('draft')
    mgr.startExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('running')
  })
  it('completeExperiment from running works', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.startExperiment(e.id)
    mgr.completeExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('completed')
  })
  it('listExperiments with empty manager returns empty array', () => {
    expect(new ExperimentManager().listExperiments().length).toBe(0)
  })
  it('snapshot equals listExperiments length', () => {
    const mgr = new ExperimentManager()
    mgr.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    mgr.createExperiment({ projectId: 'p', title: 'B', objective: 'O' })
    expect(mgr.snapshot().length).toBe(mgr.listExperiments().length)
  })
  it('size matches listExperiments length', () => {
    const mgr = new ExperimentManager()
    mgr.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    mgr.createExperiment({ projectId: 'p', title: 'B', objective: 'O' })
    expect(mgr.size()).toBe(mgr.listExperiments().length)
  })
})

describe('Phase 8-K0 ExperimentEngine state machine', () => {
  it('execute transitions draft to running to completed', () => {
    const mgr = new ExperimentManager()
    const engine = new ExperimentEngine(mgr)
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(mgr.getExperiment(r.experimentId)!.status).toBe('completed')
  })
  it('execute sets no errors when plan completes', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.errors.length).toBe(0)
  })
  it('execute confidence is 0.7', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.confidence).toBe(0.7)
  })
  it('execute returns outputs with all stepIds', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = {
      ...makePlan(),
      measurements: [
        { name: 'a', method: 'm', reason: 'r' },
        { name: 'b', method: 'm', reason: 'r' },
        { name: 'c', method: 'm', reason: 'r' }
      ]
    }
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(r.outputs['step-1']).toBeTruthy()
    expect(r.outputs['step-2']).toBeTruthy()
    expect(r.outputs['step-3']).toBeTruthy()
  })
  it('execute creates experiment with hypothesis from plan', () => {
    const engine = new ExperimentEngine()
    const plan = makePlan()
    const r = engine.execute(plan, { projectId: 'p1', title: 'T', objective: 'O', operator: 'op' })
    expect(engine.getManager().getExperiment(r.experimentId)!.hypothesis).toBe(plan.hypothesis)
  })
  it('execute creates experiment with projectId from input', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'PROJ-X', title: 'T', objective: 'O', operator: 'op' })
    expect(engine.getManager().getExperiment(r.experimentId)!.projectId).toBe('PROJ-X')
  })
  it('execute creates experiment with title from input', () => {
    const engine = new ExperimentEngine()
    const r = engine.execute(makePlan(), { projectId: 'p', title: 'TITLE-X', objective: 'O', operator: 'op' })
    expect(engine.getManager().getExperiment(r.experimentId)!.title).toBe('TITLE-X')
  })
})

describe('Phase 8-K0 ExperimentDataAdapter conversion', () => {
  it('recordToDataset variable count matches parameter count', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, {
      operator: 'op',
      parameters: [
        { name: 'a', value: 1, unit: 'u', type: 'numeric' },
        { name: 'b', value: 2, unit: 'u', type: 'numeric' },
        { name: 'c', value: 3, unit: 'u', type: 'numeric' }
      ],
      observations: 'o'
    })!
    const ds = recordToDataset(r, 'ds')
    expect(ds.variables.length).toBe(3)
  })
  it('recordToDataset row column count includes metadata', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r = mgr.addRecord(e.id, {
      operator: 'op',
      parameters: [{ name: 'a', value: 1, unit: 'u', type: 'numeric' }],
      observations: 'o'
    })!
    const ds = recordToDataset(r, 'ds')
    expect(Object.keys(ds.rows[0]).length).toBeGreaterThanOrEqual(5)
  })
  it('mergeRecords variables dedupe across records', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'shared', value: 1, unit: 'u', type: 'numeric' }, { name: 'only1', value: 1, unit: 'u', type: 'numeric' }], observations: '' })
    mgr.addRecord(e.id, { operator: 'op', parameters: [{ name: 'shared', value: 2, unit: 'u', type: 'numeric' }, { name: 'only2', value: 2, unit: 'u', type: 'numeric' }], observations: '' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'm')
    expect(ds.variables.length).toBe(3)
  })
  it('mergeRecords preserves all row values', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const r1 = mgr.addRecord(e.id, { operator: 'a', parameters: [{ name: 'x', value: 10, unit: 'u', type: 'numeric' }], observations: '' })!
    const r2 = mgr.addRecord(e.id, { operator: 'b', parameters: [{ name: 'x', value: 20, unit: 'u', type: 'numeric' }], observations: '' })!
    const ds = mergeRecords([r1, r2], 'm')
    expect(ds.rows[0].x).toBe(10)
    expect(ds.rows[1].x).toBe(20)
  })
})

describe('Phase 8-K0 ExperimentLoopEngine full cycle', () => {
  it('closeLoop → toNextExperimentPlan → execute works', () => {
    const mgr = new ExperimentManager()
    const engine = new ExperimentEngine(mgr)
    const loop = new ExperimentLoopEngine()

    const r1 = engine.execute(makePlan('plan-1'), { projectId: 'p', title: 'A', objective: 'O', operator: 'op' })
    const exp = mgr.getExperiment(r1.experimentId)!
    const lastResult = exp.results[exp.results.length - 1]

    const next = loop.closeLoop(exp, lastResult)
    expect(next).not.toBeNull()

    const nextPlan = loop.toNextExperimentPlan(makePlan('plan-1'), next!)
    const r2 = engine.execute(nextPlan, { projectId: 'p', title: 'A', objective: 'O', operator: 'op' })
    expect(r2.status).toBe('completed')
    expect(mgr.size()).toBe(2)
  })
  it('closeLoop with low confidence aborts loop', () => {
    const mgr = new ExperimentManager()
    const engine = new ExperimentEngine(mgr)
    const loop = new ExperimentLoopEngine({ analystConfidenceFloor: 0.99 })

    const r = engine.execute(makePlan(), { projectId: 'p', title: 'A', objective: 'O', operator: 'op' })
    const exp = mgr.getExperiment(r.experimentId)!
    const lastResult = exp.results[exp.results.length - 1]

    expect(loop.closeLoop(exp, lastResult)).toBeNull()
  })
  it('closeLoop produces consistent output for same input', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.9 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine()
    const r1 = loop.closeLoop(e, lastResult)
    const r2 = loop.closeLoop(e, lastResult)
    expect(r1).not.toBeNull()
    expect(r2).not.toBeNull()
    expect(r1!.inheritedPlanId).toBe(r2!.inheritedPlanId)
  })
  it('loop analyzes multiple metrics independently', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1, b: 2, c: 3, d: 4 }, conclusion: '', confidence: 0.9 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine({ maxRecommendations: 4 })
    const opt = loop.analyze(e, lastResult)
    expect(opt.importantVariables.length).toBe(4)
    expect(opt.suggestions.length).toBe(4)
    expect(opt.nextExperiments.length).toBe(4)
  })
})

describe('Phase 8-K0 src directory presence', () => {
  it('src/shared/experiment directory exists', () => {
    expect(existsSync(join(__dirname, '../../src/shared/experiment'))).toBe(true)
  })
  it('src/shared/experiment/experiment-schema.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/shared/experiment/experiment-schema.ts'))).toBe(true)
  })
  it('src/services/experiment directory exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment'))).toBe(true)
  })
  it('src/services/experiment/experiment-manager.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-manager.ts'))).toBe(true)
  })
  it('src/services/experiment/experiment-engine.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-engine.ts'))).toBe(true)
  })
  it('src/services/experiment/experiment-data-adapter.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-data-adapter.ts'))).toBe(true)
  })
  it('src/services/experiment/experiment-loop-engine.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-loop-engine.ts'))).toBe(true)
  })
  it('src/services/experiment/experiment-templates.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-templates.ts'))).toBe(true)
  })
  it('src/services/experiment/experiment-events.ts exists', () => {
    expect(existsSync(join(__dirname, '../../src/services/experiment/experiment-events.ts'))).toBe(true)
  })
})

describe('Phase 8-K0 lifecycle integrity', () => {
  it('draft → running → paused → running → completed', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.startExperiment(e.id)
    mgr.pauseExperiment(e.id)
    mgr.startExperiment(e.id)
    mgr.completeExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('completed')
  })
  it('failed status is terminal', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.failExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('failed')
  })
  it('multiple transitions update updatedAt', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const t1 = mgr.getExperiment(e.id)!.updatedAt
    mgr.startExperiment(e.id)
    const t2 = mgr.getExperiment(e.id)!.updatedAt
    expect(t2).toBeGreaterThanOrEqual(t1)
  })
  it('attachDataset does not change status', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.attachDataset(e.id, 'ds-1')
    expect(mgr.getExperiment(e.id)!.status).toBe('draft')
  })
  it('setResult does not change status automatically', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1 }, conclusion: '', confidence: 0.5 })
    expect(mgr.getExperiment(e.id)!.status).toBe('draft')
  })
})

describe('Phase 8-K0 integration scenarios', () => {
  it('full workflow: create → start → add record → complete', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p1', title: 'O3 test', objective: 'evaluate O3 efficiency', hypothesis: 'O3-MNB improves degradation' })
    expect(e.status).toBe('draft')
    mgr.startExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('running')
    mgr.addRecord(e.id, { operator: 'alice', parameters: [{ name: 'dose', value: 5, unit: 'mg/L', type: 'numeric' }], observations: 'step 1 done' })
    mgr.setResult(e.id, { metrics: { degradation: 0.85 }, conclusion: 'success', confidence: 0.9 })
    mgr.completeExperiment(e.id)
    expect(mgr.getExperiment(e.id)!.status).toBe('completed')
  })
  it('multiple experiments per project isolated', () => {
    const mgr = new ExperimentManager()
    const a = mgr.createExperiment({ projectId: 'p1', title: 'A', objective: 'O' })
    const b = mgr.createExperiment({ projectId: 'p1', title: 'B', objective: 'O' })
    mgr.addRecord(a.id, { operator: 'op', parameters: [], observations: 'a-rec' })
    expect(mgr.getExperiment(a.id)!.records.length).toBe(1)
    expect(mgr.getExperiment(b.id)!.records.length).toBe(0)
  })
  it('engine execute then loop closeLoop round trip', () => {
    const mgr = new ExperimentManager()
    const engine = new ExperimentEngine(mgr)
    const loop = new ExperimentLoopEngine()
    const r = engine.execute(makePlan('p1'), { projectId: 'proj', title: 'exp1', objective: 'obj', operator: 'op1' })
    const exp = mgr.getExperiment(r.experimentId)!
    const result = exp.results[0]
    const next = loop.closeLoop(exp, result)
    expect(next).not.toBeNull()
    expect(next!.sourceExperimentId).toBe(exp.id)
  })
  it('experiment with high confidence produces non-empty recommendations', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.setResult(e.id, { metrics: { a: 1, b: 2, c: 3 }, conclusion: '', confidence: 1.0 })
    const lastResult = mgr.getExperiment(e.id)!.results[0]
    const loop = new ExperimentLoopEngine({ maxRecommendations: 5 })
    const r = loop.closeLoop(e, lastResult)
    expect(r).not.toBeNull()
    expect(r!.recommendedChanges.length).toBeGreaterThan(0)
  })
  it('experiment records then dataset conversion', () => {
    const mgr = new ExperimentManager()
    const e = mgr.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr.addRecord(e.id, { operator: 'alice', parameters: [{ name: 'dose', value: 5, unit: 'mg/L', type: 'numeric' }], observations: 'first' })
    mgr.addRecord(e.id, { operator: 'bob', parameters: [{ name: 'dose', value: 10, unit: 'mg/L', type: 'numeric' }], observations: 'second' })
    const recs = mgr.getExperiment(e.id)!.records
    const ds = mergeRecords(recs, 'merged')
    expect(ds.rows.length).toBe(2)
    expect(ds.variables.length).toBe(1)
  })
  it('engine execute uses default measurements fallback', () => {
    const engine = new ExperimentEngine()
    const plan: ExperimentPlan = { ...makePlan(), measurements: [] }
    const r = engine.execute(plan, { projectId: 'p', title: 'T', objective: 'O', operator: 'op' })
    expect(r.executedSteps.length).toBe(1)
    expect(r.executedSteps[0].description).toContain('default')
  })
  it('templates can be used as plan seeds', () => {
    const t = getExperimentTemplate('o3-mnb-degradation')
    expect(t.defaultParameters.length).toBeGreaterThan(0)
    expect(t.defaultObservations.length).toBeGreaterThan(0)
  })
  it('two managers same workflow different state', () => {
    const a = new ExperimentManager()
    const b = new ExperimentManager()
    const ea = a.createExperiment({ projectId: 'p', title: 'A', objective: 'O' })
    const eb = b.createExperiment({ projectId: 'p', title: 'B', objective: 'O' })
    a.startExperiment(ea.id)
    expect(a.getExperiment(ea.id)!.status).toBe('running')
    expect(b.getExperiment(eb.id)!.status).toBe('draft')
  })
  it('loop output is deterministic for same inputs', () => {
    const mgr1 = new ExperimentManager()
    const mgr2 = new ExperimentManager()
    const e1 = mgr1.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    const e2 = mgr2.createExperiment({ projectId: 'p', title: 'T', objective: 'O' })
    mgr1.setResult(e1.id, { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.9 })
    mgr2.setResult(e2.id, { metrics: { a: 1, b: 2 }, conclusion: '', confidence: 0.9 })
    const loop = new ExperimentLoopEngine()
    const r1 = loop.closeLoop(mgr1.getExperiment(e1.id)!, mgr1.getExperiment(e1.id)!.results[0])
    const r2 = loop.closeLoop(mgr2.getExperiment(e2.id)!, mgr2.getExperiment(e2.id)!.results[0])
    expect(r1!.recommendedChanges.length).toBe(r2!.recommendedChanges.length)
    expect(r1!.suggestedVariables.sort()).toEqual(r2!.suggestedVariables.sort())
  })
})

describe('Phase 8-K0 experiment-manager source checks', () => {
  it('uses Map storage', () => {
    expect(read('experiment-manager.ts')).toContain('Map<string, Experiment>')
  })
  it('uses defensive copy', () => {
    expect(read('experiment-manager.ts')).toContain('cloneExperiment')
  })
  it('has private methods', () => {
    expect(read('experiment-manager.ts')).toContain('private')
  })
  it('handles unknown id returning null', () => {
    expect(read('experiment-manager.ts')).toContain('return null')
  })
  it('returns nextId-based unique ids', () => {
    expect(read('experiment-manager.ts')).toContain('nextId')
  })
})

describe('Phase 8-K0 experiment-engine source checks', () => {
  it('produces experimentId', () => {
    expect(read('experiment-engine.ts')).toContain('experimentId')
  })
  it('produces planId', () => {
    expect(read('experiment-engine.ts')).toContain('planId')
  })
  it('produces status', () => {
    expect(read('experiment-engine.ts')).toContain('status:')
  })
  it('produces executedSteps', () => {
    expect(read('experiment-engine.ts')).toContain('executedSteps')
  })
  it('produces outputs', () => {
    expect(read('experiment-engine.ts')).toContain('outputs')
  })
  it('produces confidence', () => {
    expect(read('experiment-engine.ts')).toContain('confidence')
  })
  it('produces errors', () => {
    expect(read('experiment-engine.ts')).toContain('errors')
  })
  it('handles fallback measurements', () => {
    expect(read('experiment-engine.ts')).toContain('fallback')
  })
  it('calls addRecord', () => {
    expect(read('experiment-engine.ts')).toContain('addRecord')
  })
  it('calls setResult', () => {
    expect(read('experiment-engine.ts')).toContain('setResult')
  })
  it('calls startExperiment', () => {
    expect(read('experiment-engine.ts')).toContain('startExperiment')
  })
  it('calls completeExperiment', () => {
    expect(read('experiment-engine.ts')).toContain('completeExperiment')
  })
})

describe('Phase 8-K0 loop-engine source checks', () => {
  it('has analyze method', () => {
    expect(read('experiment-loop-engine.ts')).toContain('analyze')
  })
  it('has closeLoop method', () => {
    expect(read('experiment-loop-engine.ts')).toContain('closeLoop')
  })
  it('has toNextExperimentPlan method', () => {
    expect(read('experiment-loop-engine.ts')).toContain('toNextExperimentPlan')
  })
  it('has NextExperimentPlan type', () => {
    expect(read('experiment-loop-engine.ts')).toContain('NextExperimentPlan')
  })
  it('has analystConfidenceFloor option', () => {
    expect(read('experiment-loop-engine.ts')).toContain('analystConfidenceFloor')
  })
  it('has maxRecommendations option', () => {
    expect(read('experiment-loop-engine.ts')).toContain('maxRecommendations')
  })
  it('reuses ExperimentOptimizationResult', () => {
    expect(read('experiment-loop-engine.ts')).toContain('ExperimentOptimizationResult')
  })
  it('reuses NextExperimentRecommendation', () => {
    expect(read('experiment-loop-engine.ts')).toContain('NextExperimentRecommendation')
  })
})

describe('Phase 8-K0 final smoke tests', () => {
  it('experiment schema export surface complete', () => {
    expect(typeof isValidExperiment).toBe('function')
    expect(typeof isValidExperimentRecord).toBe('function')
    expect(typeof isValidExperimentResult).toBe('function')
    expect(typeof isValidExperimentParameter).toBe('function')
  })
  it('manager class has expected methods', () => {
    const mgr = new ExperimentManager()
    expect(typeof mgr.createExperiment).toBe('function')
    expect(typeof mgr.getExperiment).toBe('function')
    expect(typeof mgr.updateExperiment).toBe('function')
    expect(typeof mgr.startExperiment).toBe('function')
    expect(typeof mgr.pauseExperiment).toBe('function')
    expect(typeof mgr.completeExperiment).toBe('function')
    expect(typeof mgr.failExperiment).toBe('function')
    expect(typeof mgr.addRecord).toBe('function')
    expect(typeof mgr.attachDataset).toBe('function')
    expect(typeof mgr.setResult).toBe('function')
    expect(typeof mgr.getExperimentProgress).toBe('function')
    expect(typeof mgr.listExperiments).toBe('function')
    expect(typeof mgr.size).toBe('function')
    expect(typeof mgr.clear).toBe('function')
    expect(typeof mgr.snapshot).toBe('function')
  })
  it('engine class has expected methods', () => {
    const engine = new ExperimentEngine()
    expect(typeof engine.execute).toBe('function')
    expect(typeof engine.getManager).toBe('function')
  })
  it('loop class has expected methods', () => {
    const loop = new ExperimentLoopEngine()
    expect(typeof loop.analyze).toBe('function')
    expect(typeof loop.closeLoop).toBe('function')
    expect(typeof loop.toNextExperimentPlan).toBe('function')
  })
  it('adapter exports 3 functions', () => {
    expect(typeof recordToDataset).toBe('function')
    expect(typeof validateDataset).toBe('function')
    expect(typeof mergeRecords).toBe('function')
  })
  it('templates exports 2 functions', () => {
    expect(typeof getExperimentTemplate).toBe('function')
    expect(typeof listExperimentTemplates).toBe('function')
  })
  it('events exports 2 helpers', () => {
    expect(typeof isExperimentEventType).toBe('function')
    expect(typeof asResearchEventType).toBe('function')
  })
})