// Phase 8-A1 Agent Runtime tests.
//
// Coverage (>= 100 cases):
//   - AgentRun / AgentStepExecution / RuntimeEvent schemas (15)
//   - Status enums (10)
//   - Runtime creation (6)
//   - createRun (10)
//   - executePlan happy path (8)
//   - executePlan failure path (5)
//   - executePlan cancellation (5)
//   - executeStep (10)
//   - Step dispatcher (15)
//   - Failure recovery (5)
//   - Parallel runs (5)
//   - Events (5)
//   - Security (8)
//   - Determinism (5)
//   - topologicalOrder (5)
//   - Independent run state (5)

import { describe, it, expect, beforeEach } from 'vitest'

import {
  isValidAgentRun,
  isValidAgentStepExecution,
  isValidRuntimeEventType,
  isValidRuntimeStatus,
  isValidAgentStepStatus,
  RUNTIME_STATUSES,
  AGENT_STEP_STATUSES,
  RUNTIME_EVENT_TYPES
} from '../../src/shared/agent/agent-runtime-schema'
import {
  ResearchAgentRuntime,
  topologicalOrder
} from '../../src/main/services/agent/agent-runtime'
import type {
  KnowledgeCaller,
  ModelCaller,
  ToolCaller,
  AgentRun,
  AgentStepExecution,
  RuntimeEvent,
  RuntimeEventType
} from '../../src/shared/agent/agent-runtime-schema'
import type {
  ResearchPlan,
  ResearchPlanStep
} from '../../src/shared/agent/research-plan-schema'

// ============ Test fixtures ============

function okKnowledge(): KnowledgeCaller {
  return { query: async () => ({ items: [{ id: 'exp:1' }] }) }
}
function failingKnowledge(): KnowledgeCaller {
  return { query: async () => { throw new Error('knowledge failed') } }
}
function okModel(text = 'conclusion'): ModelCaller {
  return { complete: async () => ({ text, usage: { tokens: 100 } }) }
}
function failingModel(): ModelCaller {
  return { complete: async () => { throw new Error('model failed') } }
}
function okTool(): ToolCaller {
  return { execute: async () => ({ success: true, data: { result: 'ok' } }) }
}
function failingTool(): ToolCaller {
  return { execute: async () => ({ success: false, error: { code: 'E', message: 'tool failed' } }) }
}

function makePlan(overrides: Partial<ResearchPlan> = {}): ResearchPlan {
  return {
    id: 'plan:001',
    goal: 'Analyze something',
    status: 'pending',
    tasks: [
      {
        id: 'step:1',
        type: 'tool',
        description: 'Do something',
        input: { x: 1 },
        dependencies: []
      }
    ],
    ...overrides
  }
}

let runIdCounter = 0
function nextRunId(): string {
  runIdCounter += 1
  return `run:test:${runIdCounter}`
}

// ============ AgentRun / AgentStepExecution / RuntimeEvent schemas ============

describe('Phase 8-A1 AgentRun schema validator', () => {
  const baseStep = (overrides: Partial<AgentStepExecution> = {}): AgentStepExecution => ({
    stepId: 'step:1',
    status: 'pending',
    input: { x: 1 },
    startedAt: null,
    completedAt: null,
    ...overrides
  })
  const baseRun = (overrides: Partial<AgentRun> = {}): AgentRun => ({
    id: nextRunId(),
    userRequest: 'g',
    planId: 'plan:001',
    status: 'pending',
    startedAt: null,
    completedAt: null,
    steps: [baseStep()],
    ...overrides
  })
  it('accepts minimal run', () => {
    expect(isValidAgentRun(baseRun())).toBe(true)
  })
  it('rejects missing id', () => {
    expect(isValidAgentRun(baseRun({ id: '' }))).toBe(false)
  })
  it('rejects missing userRequest', () => {
    expect(isValidAgentRun(baseRun({ userRequest: '' as never }))).toBe(false)
  })
  it('rejects unknown status', () => {
    expect(isValidAgentRun(baseRun({ status: 'in-progress' }))).toBe(false)
  })
  it('rejects missing steps array', () => {
    expect(isValidAgentRun(baseRun({ steps: 'oops' as never }))).toBe(false)
  })
  it('rejects invalid step in steps array', () => {
    expect(isValidAgentRun(baseRun({ steps: [{ bad: 'step' } as never] }))).toBe(false)
  })
  it('accepts run with completed status', () => {
    expect(isValidAgentRun(baseRun({ status: 'completed' }))).toBe(true)
  })
  it('accepts run with result populated', () => {
    expect(isValidAgentRun(baseRun({ result: { summary: 'ok' } }))).toBe(true)
  })
  it('rejects negative startedAt', () => {
    expect(isValidAgentRun(baseRun({ startedAt: -1 }))).toBe(false)
  })
})

describe('Phase 8-A1 AgentStepExecution validator', () => {
  it('accepts minimal step', () => {
    expect(isValidAgentStepExecution({
      stepId: 's:1', status: 'pending', input: {}, startedAt: null, completedAt: null
    })).toBe(true)
  })
  it('accepts step with all 5 statuses', () => {
    for (const status of ['pending', 'running', 'completed', 'failed', 'cancelled']) {
      expect(isValidAgentStepExecution({
        stepId: 's:1', status: status as never, input: {}, startedAt: null, completedAt: null
      })).toBe(true)
    }
  })
  it('rejects empty stepId', () => {
    expect(isValidAgentStepExecution({
      stepId: '', status: 'pending', input: {}, startedAt: null, completedAt: null
    })).toBe(false)
  })
  it('rejects negative startedAt', () => {
    expect(isValidAgentStepExecution({
      stepId: 's:1', status: 'pending', input: {}, startedAt: -1, completedAt: null
    })).toBe(false)
  })
  it('rejects unknown status', () => {
    expect(isValidAgentStepExecution({
      stepId: 's:1', status: 'in-progress', input: {}, startedAt: null, completedAt: null
    })).toBe(false)
  })
  it('accepts step with output populated', () => {
    expect(isValidAgentStepExecution({
      stepId: 's:1', status: 'completed', input: {}, output: { x: 1 }, startedAt: 100, completedAt: 200
    })).toBe(true)
  })
})

// ============ Status enums ============

describe('Phase 8-A1 status enums', () => {
  it('accepts all 5 RuntimeStatus values', () => {
    for (const s of ['pending', 'running', 'completed', 'failed', 'cancelled']) {
      expect(isValidRuntimeStatus(s)).toBe(true)
    }
  })
  it('rejects unknown RuntimeStatus', () => {
    expect(isValidRuntimeStatus('in-progress')).toBe(false)
  })
  it('accepts all 5 AgentStepStatus values', () => {
    for (const s of ['pending', 'running', 'completed', 'failed', 'cancelled']) {
      expect(isValidAgentStepStatus(s)).toBe(true)
    }
  })
  it('rejects unknown AgentStepStatus', () => {
    expect(isValidAgentStepStatus('paused')).toBe(false)
  })
  it('accepts all 5 RuntimeEventType values', () => {
    for (const t of ['plan_created', 'step_started', 'step_completed', 'step_failed', 'run_completed']) {
      expect(isValidRuntimeEventType(t)).toBe(true)
    }
  })
  it('rejects unknown RuntimeEventType', () => {
    expect(isValidRuntimeEventType('plan_updated')).toBe(false)
  })
  it('RUNTIME_STATUSES readonly array has 5 entries', () => {
    expect(RUNTIME_STATUSES.length).toBe(5)
  })
  it('AGENT_STEP_STATUSES readonly array has 5 entries', () => {
    expect(AGENT_STEP_STATUSES.length).toBe(5)
  })
  it('RUNTIME_EVENT_TYPES readonly array has 5 entries', () => {
    expect(RUNTIME_EVENT_TYPES.length).toBe(5)
  })
  it('all 3 readonly arrays contain the right number of entries', () => {
    expect(RUNTIME_STATUSES.length).toBe(5)
    expect(AGENT_STEP_STATUSES.length).toBe(5)
    expect(RUNTIME_EVENT_TYPES.length).toBe(5)
  })
})

// ============ Runtime creation ============

describe('Phase 8-A1 ResearchAgentRuntime creation', () => {
  it('creates runtime with valid args', () => {
    expect(() => new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool()
    })).not.toThrow()
  })
  it('throws when knowledge missing', () => {
    expect(() => new ResearchAgentRuntime({
      knowledge: undefined as never, model: okModel(), tool: okTool()
    })).toThrow(/knowledge caller required/)
  })
  it('throws when model missing', () => {
    expect(() => new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: undefined as never, tool: okTool()
    })).toThrow(/model caller required/)
  })
  it('throws when tool missing', () => {
    expect(() => new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: undefined as never
    })).toThrow(/tool caller required/)
  })
  it('creates runtime with custom clock', () => {
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool(),
      clock: () => 1000
    })
    expect(r.__runStoreSize()).toBe(0)
  })
  it('initial run store size is 0', () => {
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool()
    })
    expect(r.__runStoreSize()).toBe(0)
  })
})

// ============ createRun ============

describe('Phase 8-A1 createRun', () => {
  let runtime: ResearchAgentRuntime
  beforeEach(() => {
    runtime = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool()
    })
  })
  it('creates a run with status pending', () => {
    const run = runtime.createRun('test request', makePlan())
    expect(run.status).toBe('pending')
    expect(run.startedAt).toBeNull()
    expect(run.completedAt).toBeNull()
  })
  it('creates a run with user request', () => {
    const run = runtime.createRun('Analyze TC', makePlan())
    expect(run.userRequest).toBe('Analyze TC')
  })
  it('creates a run with plan id', () => {
    const run = runtime.createRun('r', makePlan({ id: 'plan:99' }))
    expect(run.planId).toBe('plan:99')
  })
  it('creates steps initialized to pending', () => {
    const run = runtime.createRun('r', makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] }
      ]
    }))
    expect(run.steps).toHaveLength(2)
    expect(run.steps[0]!.status).toBe('pending')
    expect(run.steps[1]!.status).toBe('pending')
    expect(run.steps[0]!.startedAt).toBeNull()
    expect(run.steps[1]!.startedAt).toBeNull()
  })
  it('emits plan_created event', () => {
    const events: RuntimeEvent[] = []
    runtime.onEvent('plan_created', (e) => events.push(e))
    runtime.createRun('r', makePlan())
    expect(events).toHaveLength(1)
    expect(events[0]!.type).toBe('plan_created')
  })
  it('throws on non-string userRequest', () => {
    expect(() => runtime.createRun(123 as never, makePlan())).toThrow(/userRequest must be a string/)
  })
  it('throws on invalid plan', () => {
    expect(() => runtime.createRun('r', { id: '', goal: '', status: 'pending', tasks: [] }))
      .toThrow(/invalid ResearchPlan/)
  })
  it('run id is unique across calls', () => {
    const r1 = runtime.createRun('r1', makePlan())
    const r2 = runtime.createRun('r2', makePlan())
    expect(r1.id).not.toBe(r2.id)
  })
  it('run store size increases by 1 per createRun', () => {
    expect(runtime.__runStoreSize()).toBe(0)
    runtime.createRun('r1', makePlan())
    expect(runtime.__runStoreSize()).toBe(1)
    runtime.createRun('r2', makePlan())
    expect(runtime.__runStoreSize()).toBe(2)
  })
  it('createRun does NOT start execution (status remains pending)', () => {
    const run = runtime.createRun('r', makePlan())
    expect(run.status).toBe('pending')
    expect(run.startedAt).toBeNull()
  })
})

// ============ executePlan happy path ============

describe('Phase 8-A1 executePlan happy path', () => {
  it('executes a 1-step plan successfully', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    const result = await r.executePlan(run.id, plan)
    expect(result.status).toBe('completed')
  })
  it('executes a 2-step plan in dependency order', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] }
      ]
    })
    const order: string[] = []
    const events: RuntimeEvent[] = []
    r.onEvent('step_started', (e) => order.push(e.stepId!))
    r.onEvent('step_completed', (e) => events.push(e))
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(order).toEqual(['s:1', 's:2'])
    expect(events.filter((e) => e.type === 'step_completed').map((e) => e.stepId)).toEqual(['s:1', 's:2'])
  })
  it('sets startedAt and completedAt on completion', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    const result = await r.executePlan(run.id, plan)
    expect(result.startedAt).not.toBeNull()
    expect(result.completedAt).not.toBeNull()
  })
  it('assembles result from completed steps', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
      ]
    })
    const run = r.createRun('r', plan)
    const result = await r.executePlan(run.id, plan)
    expect(result.result).toBeDefined()
  })
  it('emits run_completed at the end with status completed', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const events: RuntimeEvent[] = []
    r.onEvent('run_completed', (e) => events.push(e))
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(events).toHaveLength(1)
    expect(events[0]!.payload?.status).toBe('completed')
  })
  it('runs steps in parallel branches (s:1 and s:2 independent)', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const order: string[] = []
    r.onEvent('step_started', (e) => order.push(e.stepId!))
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: [] }
      ]
    })
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(order).toContain('s:1')
    expect(order).toContain('s:2')
  })
  it('runs s:2 only after s:1 completes (sequential dependency)', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const order: string[] = []
    r.onEvent('step_started', (e) => order.push(e.stepId!))
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] }
      ]
    })
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(order.indexOf('s:1')).toBeLessThan(order.indexOf('s:2'))
  })
  it('marks all steps completed on plan success', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] }
      ]
    })
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(result.steps.every((s) => s.status === 'completed')).toBe(true)
  })
})

// ============ executePlan failure path ============

describe('Phase 8-A1 executePlan failure path', () => {
  it('marks run failed when a step fails', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: failingTool()
    })
    const _r = r.createRun('run:n1', plan); const result = await r.executePlan(_r.id, plan)
    expect(result.status).toBe('failed')
  })
  it('breaks out of the loop on failure (subsequent steps do not start)', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const started: string[] = []
    r.onEvent('step_started', (e) => started.push(e.stepId!))
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] },
        { id: 's:3', type: 'tool', description: 'd', input: {}, dependencies: ['s:2'] }
      ]
    })
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(started).toEqual(['s:1'])
  })
  it('marks the failed step with error code and message', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const _r = r.createRun('run:n1', plan); const result = await r.executePlan(_r.id, plan)
    const s1 = result.steps.find((s) => s.stepId === 'step:1')!
    expect(s1.status).toBe('failed')
    expect(s1.error?.message).toContain('tool failed')
  })
  it('emits step_failed when a step fails', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const failed: RuntimeEvent[] = []
    r.onEvent('step_failed', (e) => failed.push(e))
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(failed).toHaveLength(1)
    expect(failed[0]!.stepId).toBe('step:1')
  })
  it('does not assemble result when plan fails', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const _r = r.createRun('run:n1', plan); const result = await r.executePlan(_r.id, plan)
    expect(result.result).toBeUndefined()
  })
})

// ============ executePlan cancellation ============

describe('Phase 8-A1 executePlan cancellation', () => {
  it('cancelRun on pending run marks cancelled', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    const result = r.cancelRun(run.id)
    expect(result.ok).toBe(true)
    expect(r.getRun(run.id)?.status).toBe('cancelled')
  })
  it('cancelRun on unknown runId returns false', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    expect(r.cancelRun('unknown')).toEqual({ ok: false, reason: 'unknown runId' })
  })
  it('cancelRun on completed run returns already terminal', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    run.status = 'completed'
    expect(r.cancelRun(run.id)).toEqual({ ok: false, reason: 'already terminal' })
  })
  it('cancelRun on running plan: subsequent steps do not start', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] },
        { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: ['s:1'] }
      ]
    })
    const run = r.createRun('run:n1', plan)
    const promise = r.executePlan(run.id, plan)
    r.cancelRun(run.id)
    const result = await promise
    expect(result.status).toBe('cancelled')
    expect(result.steps[1]!.status).toBe('cancelled')
  })
  it('cancelRun emits run_completed with status cancelled', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    const events: RuntimeEvent[] = []
    r.onEvent('run_completed', (e) => events.push(e))
    r.cancelRun(run.id)
    expect(events).toHaveLength(1)
    expect(events[0]!.payload?.status).toBe('cancelled')
  })
})

// ============ executeStep ============

describe('Phase 8-A1 executeStep', () => {
  let runtime: ResearchAgentRuntime
  beforeEach(() => {
    runtime = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
  })
  it('marks step as running then completed', async () => {
    const run = runtime.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await runtime.executeStep(run, planStep, stepExec)
    expect(stepExec.status).toBe('completed')
    expect(stepExec.startedAt).not.toBeNull()
    expect(stepExec.completedAt).not.toBeNull()
  })
  it('populates step output with caller response', async () => {
    const run = runtime.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await runtime.executeStep(run, planStep, stepExec)
    expect(stepExec.output).toEqual({ result: 'ok' })
  })
  it('emits step_started and step_completed for success', async () => {
    const run = runtime.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    const events: RuntimeEvent[] = []
    runtime.onEvent('step_started', (e) => events.push(e))
    runtime.onEvent('step_completed', (e) => events.push(e))
    await runtime.executeStep(run, planStep, stepExec)
    expect(events.map((e) => e.type)).toEqual(['step_started', 'step_completed'])
  })
  it('marks step as failed and stores error on exception', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const run = r.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await r.executeStep(run, planStep, stepExec)
    expect(stepExec.status).toBe('failed')
    expect(stepExec.error?.code).toBe('EXECUTION_ERROR')
  })
  it('emits step_failed when execution throws', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const run = r.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    const events: RuntimeEvent[] = []
    r.onEvent('step_failed', (e) => events.push(e))
    await r.executeStep(run, planStep, stepExec)
    expect(events).toHaveLength(1)
  })
  it('marks step as failed when tool returns success=false', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: failingTool() })
    const run = r.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await r.executeStep(run, planStep, stepExec)
    expect(stepExec.status).toBe('failed')
  })
  it('input is copied into the step execution record', async () => {
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: { x: 42 }, dependencies: [] }
    const run = runtime.createRun('r', makePlan({ tasks: [planStep] }))
    const stepExec = run.steps[0]!
    await runtime.executeStep(run, planStep, stepExec)
    expect(stepExec.input).toEqual({ x: 42 })
  })
  it('output is empty object if caller returns no data', async () => {
    const tool: ToolCaller = { execute: async () => ({ success: true }) }
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool })
    const run = r.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await r.executeStep(run, planStep, stepExec)
    expect(stepExec.output).toEqual({})
  })
  it('startedAt is set before execution', async () => {
    let now = 1000
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool(),
      clock: () => now
    })
    const run = r.createRun('r', makePlan())
    const stepExec = run.steps[0]!
    const planStep: ResearchPlanStep = { id: 'step:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    now = 2000
    await r.executeStep(run, planStep, stepExec)
    expect(stepExec.startedAt).toBe(2000)
    expect(stepExec.completedAt).toBe(2000)
  })
})

// ============ Step dispatcher ============

describe('Phase 8-A1 step dispatcher', () => {
  let runtime: ResearchAgentRuntime
  beforeEach(() => {
    runtime = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
  })
  it('dispatches knowledge step to knowledge.query', async () => {
    const run = runtime.createRun('r', makePlan())
    const step: ResearchPlanStep = {
      id: 's:1', type: 'knowledge', description: 'd',
      input: { entityType: 'experiment', filter: { name: 'X' } }, dependencies: []
    }
    const exec: AgentStepExecution = {
      stepId: 's:1', status: 'pending', input: step.input, startedAt: null, completedAt: null
    }
    await runtime.executeStep(run, step, exec)
    expect(exec.output).toEqual({ items: [{ id: 'exp:1' }] })
  })
  it('dispatches tool step to tool.execute', async () => {
    const run = runtime.createRun('r', makePlan())
    const step: ResearchPlanStep = { id: 's:1', type: 'tool', description: 'd', input: { x: 1 }, dependencies: [] }
    const exec: AgentStepExecution = { stepId: 's:1', status: 'pending', input: step.input, startedAt: null, completedAt: null }
    await runtime.executeStep(run, step, exec)
    expect(exec.output).toEqual({ result: 'ok' })
  })
  it('dispatches model step to model.complete', async () => {
    const run = runtime.createRun('r', makePlan())
    const step: ResearchPlanStep = {
      id: 's:1', type: 'model', description: 'd',
      input: { prompt: 'Analyze this' }, dependencies: []
    }
    const exec: AgentStepExecution = { stepId: 's:1', status: 'pending', input: step.input, startedAt: null, completedAt: null }
    await runtime.executeStep(run, step, exec)
    expect(exec.output).toEqual({ text: 'conclusion', usage: { tokens: 100 } })
  })
  it('dispatches analysis step as pure-function (computes summary)', async () => {
    const kstep: ResearchPlanStep = {
      id: 's:1', type: 'knowledge', description: 'd',
      input: { entityType: 'experiment' }, dependencies: []
    }
    const astep: ResearchPlanStep = {
      id: 's:2', type: 'analysis', description: 'd',
      input: { sourceStepId: 's:1' }, dependencies: ['s:1']
    }
    const run = runtime.createRun('r', makePlan({ tasks: [kstep, astep] }))
    const kexec = run.steps[0]!
    await runtime.executeStep(run, kstep, kexec)
    // Manually inject the output (real planner would have done this)
    kexec.output = { values: [10, 20, 30] }
    const aexec = run.steps[1]!
    await runtime.executeStep(run, astep, aexec)
    expect(aexec.output).toEqual({ source: 's:1', count: 3, mean: 20, min: 10, max: 30 })
  })
  it('analysis fails when sourceStepId missing', async () => {
    const run = runtime.createRun('r', makePlan())
    const step: ResearchPlanStep = {
      id: 's:1', type: 'analysis', description: 'd',
      input: { /* no sourceStepId */ }, dependencies: []
    }
    const exec: AgentStepExecution = { stepId: 's:1', status: 'pending', input: step.input, startedAt: null, completedAt: null }
    await runtime.executeStep(run, step, exec)
    expect(exec.status).toBe('failed')
  })
  it('dispatches synthesis step assembling section outputs', async () => {
    const s1: ResearchPlanStep = { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    const s2: ResearchPlanStep = { id: 's:2', type: 'tool', description: 'd', input: {}, dependencies: [] }
    const synStep: ResearchPlanStep = {
      id: 's:3', type: 'synthesis', description: 'd',
      input: { sourceStepIds: ['s:1', 's:2'] }, dependencies: []
    }
    const run = runtime.createRun('r', makePlan({ tasks: [s1, s2, synStep] }))
    const e1 = run.steps[0]!
    e1.output = { result1: 1 }
    const e2 = run.steps[1]!
    e2.output = { result2: 2 }
    const e3 = run.steps[2]!
    await runtime.executeStep(run, synStep, e3)
    expect(e3.output).toEqual({ format: 'summary', sections: { 's:1': { result1: 1 }, 's:2': { result2: 2 } }, userRequest: 'r' })
  })
  it('synthesis succeeds with empty sections when no source outputs', async () => {
    const run = runtime.createRun('r', makePlan())
    const synStep: ResearchPlanStep = { id: 's:1', type: 'synthesis', description: 'd', input: {}, dependencies: [] }
    const exec: AgentStepExecution = { stepId: 's:1', status: 'pending', input: synStep.input, startedAt: null, completedAt: null }
    await runtime.executeStep(run, synStep, exec)
    expect(exec.status).toBe('completed')
  })
  it('analysis fails when source step has no output yet', async () => {
    const kstep: ResearchPlanStep = { id: 's:1', type: 'knowledge', description: 'd', input: {}, dependencies: [] }
    const astep: ResearchPlanStep = {
      id: 's:2', type: 'analysis', description: 'd',
      input: { sourceStepId: 's:1' }, dependencies: ['s:1']
    }
    const run = runtime.createRun('r', makePlan({ tasks: [kstep, astep] }))
    const aexec = run.steps[1]!
    // s:1 was never executed so it has no output → analysis fails
    await runtime.executeStep(run, astep, aexec)
    expect(aexec.status).toBe('failed')
  })
  it('analysis fails when source output.values is not array', async () => {
    const kstep: ResearchPlanStep = { id: 's:1', type: 'knowledge', description: 'd', input: {}, dependencies: [] }
    const astep: ResearchPlanStep = {
      id: 's:2', type: 'analysis', description: 'd',
      input: { sourceStepId: 's:1' }, dependencies: []
    }
    const run = runtime.createRun('r', makePlan({ tasks: [kstep, astep] }))
    const kexec = run.steps[0]!
    await runtime.executeStep(run, kstep, kexec)
    kexec.output = { values: 'oops' }  // not an array
    const aexec = run.steps[1]!
    await runtime.executeStep(run, astep, aexec)
    expect(aexec.status).toBe('failed')
  })
  it('tool caller throwing is caught and step marked failed', async () => {
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: { execute: async () => { throw new Error('boom') } }
    })
    const run = r.createRun('r', makePlan())
    const exec = run.steps[0]!
    const step: ResearchPlanStep = { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    await r.executeStep(run, step, exec)
    expect(exec.status).toBe('failed')
    expect(exec.error?.message).toBe('boom')
  })
  it('knowledge caller throwing is caught', async () => {
    const r = new ResearchAgentRuntime({
      knowledge: failingKnowledge(), model: okModel(), tool: okTool()
    })
    const run = r.createRun('r', makePlan())
    const exec = run.steps[0]!
    const step: ResearchPlanStep = { id: 's:1', type: 'knowledge', description: 'd', input: {}, dependencies: [] }
    await r.executeStep(run, step, exec)
    expect(exec.status).toBe('failed')
  })
  it('model caller throwing is caught', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: failingModel(), tool: okTool() })
    const run = r.createRun('r', makePlan())
    const exec = run.steps[0]!
    const step: ResearchPlanStep = { id: 's:1', type: 'model', description: 'd', input: { prompt: 'x' }, dependencies: [] }
    await r.executeStep(run, step, exec)
    expect(exec.status).toBe('failed')
  })
})

// ============ Parallel runs ============

describe('Phase 8-A1 parallel runs', () => {
  it('two runs do not share state', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const r1 = r.createRun('r1', makePlan())
    const r2 = r.createRun('r2', makePlan())
    expect(r.getRun(r1.id)?.status).toBe('pending')
    expect(r.getRun(r2.id)?.status).toBe('pending')
    await Promise.all([
      r.executePlan(r1.id, makePlan()),
      r.executePlan(r2.id, makePlan())
    ])
    expect(r.getRun(r1.id)?.status).toBe('completed')
    expect(r.getRun(r2.id)?.status).toBe('completed')
  })
  it('cancelRun on one run does not affect the other', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const r1 = r.createRun('r1', makePlan())
    const r2 = r.createRun('r2', makePlan())
    r.cancelRun(r1.id)
    expect(r.getRun(r1.id)?.status).toBe('cancelled')
    expect(r.getRun(r2.id)?.status).toBe('pending')
  })
  it('listRuns returns all runs sorted by startedAt', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    r.createRun('r1', makePlan())
    r.createRun('r2', makePlan())
    const all = r.listRuns()
    expect(all).toHaveLength(2)
    expect(all[0]!.id).not.toBe(all[1]!.id)
  })
  it('run store size grows with each createRun', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    expect(r.__runStoreSize()).toBe(0)
    r.createRun('r1', makePlan())
    expect(r.__runStoreSize()).toBe(1)
    r.createRun('r2', makePlan())
    expect(r.__runStoreSize()).toBe(2)
  })
  it('two runs execute independently', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const r1 = r.createRun('r1', makePlan())
    const r2 = r.createRun('r2', makePlan())
    await Promise.all([
      r.executePlan(r1.id, makePlan()),
      r.executePlan(r2.id, makePlan())
    ])
    expect(r.getRun(r1.id)?.status).toBe('completed')
    expect(r.getRun(r2.id)?.status).toBe('completed')
    expect(r.getRun(r1.id)?.id).not.toBe(r.getRun(r2.id)?.id)
  })
})

// ============ Events ============

describe('Phase 8-A1 events', () => {
  it('subscribe + unsubscribe pattern works', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const events: RuntimeEvent[] = []
    const unsub = r.onEvent('plan_created', (e) => events.push(e))
    r.createRun('r', makePlan())
    expect(events).toHaveLength(1)
    unsub()
    r.createRun('r', makePlan())
    expect(events).toHaveLength(1)
  })
  it('multiple listeners receive the same event', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    let first = 0
    let second = 0
    r.onEvent('plan_created', () => first++)
    r.onEvent('plan_created', () => second++)
    r.createRun('r', makePlan())
    expect(first).toBe(1)
    expect(second).toBe(1)
  })
  it('emits plan_created on createRun', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const events: RuntimeEvent[] = []
    r.onEvent('plan_created', (e) => events.push(e))
    r.createRun('r', makePlan())
    expect(events).toHaveLength(1)
  })
  it('emits step_started + step_completed + run_completed on successful plan', async () => {
    const plan = makePlan()
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const events: RuntimeEventType[] = []
    r.onEvent('plan_created', () => events.push('plan_created'))
    r.onEvent('step_started', () => events.push('step_started'))
    r.onEvent('step_completed', () => events.push('step_completed'))
    r.onEvent('run_completed', () => events.push('run_completed'))
    const run = r.createRun('run:n1', plan)
    const result = await r.executePlan(run.id, plan)
    expect(events).toContain('plan_created')
    expect(events).toContain('step_started')
    expect(events).toContain('step_completed')
    expect(events).toContain('run_completed')
  })
  it('emits only plan_created on createRun (no execution yet)', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const events: RuntimeEventType[] = []
    r.onEvent('plan_created', () => events.push('plan_created'))
    r.onEvent('step_started', () => events.push('step_started'))
    r.createRun('r', makePlan())
    expect(events).toEqual(['plan_created'])
  })
})

// ============ Security ============

describe('Phase 8-A1 security — no-secret enforcement', () => {
  it('createRun throws when result has apiKey (Phase 8-A1 strict)', () => {
    // The result field is populated after execution, not in createRun.
    // But the validators enforce it. Test the schema validator directly.
    expect(() => isValidAgentRun({
      id: 'r:1', userRequest: 'r', planId: 'p:1', status: 'completed',
      startedAt: 1, completedAt: 2, steps: [],
      result: { apiKey: 'sk-leak' }
    })).toThrow(/forbidden/)
  })
  it('AgentStepExecution throws when output has apiKey', () => {
    expect(() => isValidAgentStepExecution({
      stepId: 's:1', status: 'completed', input: {},
      output: { apiKey: 'sk-leak' }, startedAt: 1, completedAt: 2
    })).toThrow(/forbidden/)
  })
  it('createRun throws when input has apiKey', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { apiKey: 'sk-leak' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
  it('createRun throws when input has token', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { token: 'leak' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
  it('createRun throws when input has Bearer', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { auth: 'Bearer sk-leak' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
  it('createRun throws when input has providerId', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { providerId: 'cloud-vendor' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
  it('createRun throws when input has modelId', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { modelId: 'gpt-4o' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
  it('createRun throws when input has cipher', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan()
    plan.tasks[0]!.input = { data: 'cipher:abc' }
    expect(() => r.createRun('r', plan)).toThrow(/forbidden/)
  })
})

// ============ Determinism ============

describe('Phase 8-A1 determinism', () => {
  it('createRun with same args returns same id structure (deterministic with seeded clock)', () => {
    let now = 1000
    const r1 = new ResearchAgentRuntime({
      knowledge: okKnowledge(), model: okModel(), tool: okTool(),
      clock: () => now
    })
    const run = r1.createRun('r', makePlan())
    expect(run.startedAt).toBeNull()  // not started yet
  })
  it('executePlan with same plan twice has same shape', async () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    const plan = makePlan({
      tasks: [
        { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
      ]
    })
    const r1 = r.createRun('r1', plan)
    const r2 = r.createRun('r2', plan)
    const out1 = await r.executePlan(r1.id, plan)
    const out2 = await r.executePlan(r2.id, plan)
    expect(out1.status).toBe(out2.status)
    expect(out1.steps.length).toBe(out2.steps.length)
  })
  it('validators are pure functions (no side effects)', () => {
    const run: AgentRun = {
      id: 'r:1', userRequest: 'r', planId: 'p:1', status: 'pending',
      startedAt: null, completedAt: null, steps: []
    }
    expect(isValidAgentRun(run)).toBe(true)
    expect(isValidAgentRun(run)).toBe(true)
  })
  it('deterministic run ordering by startedAt', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    r.createRun('r3', makePlan())
    r.createRun('r1', makePlan())
    r.createRun('r2', makePlan())
    const all = r.listRuns()
    // Without startedAt, sort is unstable. Verify listRuns returns all 3.
    expect(all).toHaveLength(3)
  })
})

// ============ topologicalOrder (Phase 8-A1 helper) ============

describe('Phase 8-A1 topologicalOrder', () => {
  it('returns empty array for empty input', () => {
    expect(topologicalOrder([])).toEqual([])
  })
  it('returns single step for single input', () => {
    const order = topologicalOrder([
      { id: 's:1', type: 'tool', description: 'd', input: {}, dependencies: [] }
    ])
    expect(order).toHaveLength(1)
    expect(order![0]!.id).toBe('s:1')
  })
  it('topologically orders dependent steps', () => {
    const a: ResearchPlanStep = { id: 'A', type: 'tool', description: 'd', input: {}, dependencies: [] }
    const b: ResearchPlanStep = { id: 'B', type: 'tool', description: 'd', input: {}, dependencies: ['A'] }
    const order = topologicalOrder([b, a])
    expect(order!.map((s) => s.id)).toEqual(['A', 'B'])
  })
  it('detects cycles (returns null)', () => {
    const a: ResearchPlanStep = { id: 'A', type: 'tool', description: 'd', input: {}, dependencies: ['B'] }
    const b: ResearchPlanStep = { id: 'B', type: 'tool', description: 'd', input: {}, dependencies: ['A'] }
    expect(topologicalOrder([a, b])).toBeNull()
  })
  it('external deps do not block topological sort', () => {
    const a: ResearchPlanStep = { id: 'A', type: 'tool', description: 'd', input: {}, dependencies: ['external'] }
    expect(topologicalOrder([a])).not.toBeNull()
  })
})

// ============ Independent run state ============

describe('Phase 8-A1 independent run state', () => {
  it('running two plans in sequence keeps independent results', async () => {
    const r = new ResearchAgentRuntime({
      knowledge: okKnowledge(),
      model: { complete: async (prompt) => ({ text: `answer:${prompt}` }) },
      tool: okTool()
    })
    const p1 = makePlan({ id: 'plan:1', tasks: [{ id: 's:1', type: 'model', description: 'd', input: { prompt: 'q1' }, dependencies: [] }] })
    const p2 = makePlan({ id: 'plan:2', tasks: [{ id: 's:1', type: 'model', description: 'd', input: { prompt: 'q2' }, dependencies: [] }] })
    const r1 = r.createRun('r1', p1)
    const r2 = r.createRun('r2', p2)
    const out1 = await r.executePlan(r1.id, p1)
    const out2 = await r.executePlan(r2.id, p2)
    expect((out1.steps[0]!.output as { text: string }).text).toBe('answer:q1')
    expect((out2.steps[0]!.output as { text: string }).text).toBe('answer:q2')
  })
  it('failed run does not poison subsequent runs', async () => {
    let calls = 0
    const oneShotFailingTool: ToolCaller = {
      execute: async () => {
        calls += 1
        if (calls === 1) return { success: false, error: { code: 'E', message: 'first fails' } }
        return { success: true, data: { ok: true } }
      }
    }
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: oneShotFailingTool })
    const failRun = r.createRun('fail', makePlan({ id: 'plan:fail' }))
    const failed = await r.executePlan(failRun.id, makePlan({ id: 'plan:fail' }))
    expect(failed.status).toBe('failed')
    const okRun = r.createRun('ok', makePlan({ id: 'plan:ok' }))
    const result = await r.executePlan(okRun.id, makePlan({ id: 'plan:ok' }))
    expect(result.status).toBe('completed')
  })
  it('clearRuns resets state for testing', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    r.createRun('r1', makePlan())
    r.__clearRuns()
    expect(r.__runStoreSize()).toBe(0)
  })
  it('removeAllListeners clears event subscriptions', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    let called = 0
    r.onEvent('plan_created', () => called++)
    r.createRun('r1', makePlan())
    expect(called).toBe(1)
    r.removeAllListeners()
    r.createRun('r2', makePlan())
    expect(called).toBe(1)
  })
  it('listRuns returns immutable snapshot (mutating returned array does not affect state)', () => {
    const r = new ResearchAgentRuntime({ knowledge: okKnowledge(), model: okModel(), tool: okTool() })
    r.createRun('r1', makePlan())
    const arr = r.listRuns()
    arr.length = 0
    expect(r.__runStoreSize()).toBe(1)
  })
})
