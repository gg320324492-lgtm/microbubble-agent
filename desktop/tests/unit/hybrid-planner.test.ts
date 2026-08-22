// Phase 8-B1 Hybrid LLM Planner tests.
//
// Coverage (>= 120 cases):
//   - Schema validators: modes / request / response (28)
//   - Planner model adapter: prompt construction (14)
//   - Planner model adapter: response parsing (27)
//   - Planner model adapter: generatePlan (10)
//   - Hybrid planner: modes + rule fallback + LLM acceptance (36)
//   - Determinism (8)
//   - Planner separation + security source scans (11)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Shared schemas ============
import {
  PLANNER_MODES,
  isValidPlannerMode,
  isValidLLMPlannerRequest,
  isValidLLMPlannerResponse,
  __testHelpers as llmSchemaHelpers
} from '../../src/shared/agent/llm-planner-schema'
import type { PlannerMode, LLMPlannerRequest, LLMPlannerResponse } from '../../src/shared/agent/llm-planner-schema'
import type { ResearchIntent, PlannerContext } from '../../src/shared/agent/planner-schema'
import { isValidResearchPlan } from '../../src/shared/agent/research-plan-schema'
import type { ResearchPlan } from '../../src/shared/agent/research-plan-schema'
import type { ModelCaller } from '../../src/shared/agent/agent-runtime-schema'

// ============ Planner infrastructure ============
import {
  ModelCallerPlannerAdapter,
  buildModelPrompt,
  normalizeParsedPlan,
  computeLlmConfidence,
  parseModelResponse,
  DEFAULT_SYSTEM_PROMPT
} from '../../src/main/services/agent/planner-model-adapter'
import type { PlannerModelAdapter } from '../../src/main/services/agent/planner-model-adapter'
import { HybridPlanner } from '../../src/main/services/agent/hybrid-planner'

// ============ Fixtures ============

function intent(overrides: Partial<ResearchIntent> = {}): ResearchIntent {
  return {
    topic: 'bubble data',
    goal: 'analyze bubble data',
    domain: 'experiment',
    taskType: 'data-analysis',
    constraints: [],
    requiredCapabilities: ['data-analysis', 'statistics', 'regression', 'visualization'],
    ...overrides
  }
}

function profile(toolId: string, caps: string[] = []): { toolId: string; requiredCapabilities: string[]; optionalCapabilities: string[]; supportedTasks: never[]; priority: number } {
  return { toolId, requiredCapabilities: caps, optionalCapabilities: [], supportedTasks: [], priority: 5 }
}

// A canonical valid LLM plan the adapter can parse into a valid ResearchPlan.
function cleanLLMJson(conf = 0.9): string {
  return JSON.stringify({
    plan: {
      id: 'plan:llm:xyz',
      goal: 'analyze bubble data',
      tasks: [
        { id: 'step:1:knowledge', type: 'knowledge', description: 'retrieve experiment', input: { entityType: 'experiment' }, dependencies: [] },
        { id: 'step:2:tool', type: 'tool', description: 'analyze dataset', input: { toolId: 'tool:dataset-analysis' }, dependencies: ['step:1:knowledge'] },
        { id: 'step:3:synthesis', type: 'synthesis', description: 'synthesize', input: { format: 'summary' }, dependencies: ['step:2:tool'] }
      ]
    },
    confidence: conf,
    explanation: 'better plan'
  })
}

function fakeModel(text: string, record?: { options?: unknown[] }): ModelCaller {
  return {
    complete: async (prompt: string, options?: { maxTokens?: number; temperature?: number }) => {
      if (record) record.options = [prompt, options]
      return { text }
    }
  }
}

const RULE_CONF_DATA_ANALYSIS = 0.73

function makeRequest(): LLMPlannerRequest {
  return { intent: intent() }
}

// ============ Schema — modes ============

describe('Phase 8-B1 PlannerMode', () => {
  it('PLANNER_MODES has exactly 3 entries', () => {
    expect(PLANNER_MODES.length).toBe(3)
  })
  it('contains rule-only', () => {
    expect(PLANNER_MODES).toContain('rule-only')
  })
  it('contains hybrid', () => {
    expect(PLANNER_MODES).toContain('hybrid')
  })
  it('contains llm-only', () => {
    expect(PLANNER_MODES).toContain('llm-only')
  })
  it('accepts rule-only as valid mode', () => {
    expect(isValidPlannerMode('rule-only')).toBe(true)
  })
  it('accepts hybrid as valid mode', () => {
    expect(isValidPlannerMode('hybrid')).toBe(true)
  })
  it('accepts llm-only as valid mode', () => {
    expect(isValidPlannerMode('llm-only')).toBe(true)
  })
  it('rejects unknown mode', () => {
    expect(isValidPlannerMode('auto')).toBe(false)
  })
  it('rejects non-string mode', () => {
    expect(isValidPlannerMode(7)).toBe(false)
  })
  it('hybrid is the documented default ordering (rule-only first, llm-only last)', () => {
    expect(PLANNER_MODES.indexOf('hybrid')).toBe(1)
    expect(PLANNER_MODES.indexOf('llm-only')).toBe(2)
  })
})

// ============ Schema — LLMPlannerRequest ============

describe('Phase 8-B1 LLMPlannerRequest validator', () => {
  it('accepts minimal request (intent only)', () => {
    expect(isValidLLMPlannerRequest({ intent: intent() })).toBe(true)
  })
  it('accepts request with context', () => {
    expect(isValidLLMPlannerRequest({ intent: intent(), context: {} })).toBe(true)
  })
  it('accepts request with tools + knowledge', () => {
    expect(isValidLLMPlannerRequest({
      intent: intent(),
      availableTools: [profile('tool:a', ['data-analysis'])],
      availableKnowledge: ['experiment', 'dataset']
    })).toBe(true)
  })
  it('rejects missing intent', () => {
    expect(isValidLLMPlannerRequest({} as never)).toBe(false)
  })
  it('rejects invalid intent', () => {
    expect(isValidLLMPlannerRequest({ intent: { topic: '' } as never })).toBe(false)
  })
  it('rejects non-array availableKnowledge', () => {
    expect(isValidLLMPlannerRequest({ intent: intent(), availableKnowledge: 'experiment' as never })).toBe(false)
  })
  it('rejects non-string knowledge entries', () => {
    expect(isValidLLMPlannerRequest({ intent: intent(), availableKnowledge: ['experiment', 3 as never] })).toBe(false)
  })
  it('rejects non-array availableTools', () => {
    expect(isValidLLMPlannerRequest({ intent: intent(), availableTools: 'tool' as never })).toBe(false)
  })
  it('rejects invalid tool profile entry', () => {
    expect(isValidLLMPlannerRequest({ intent: intent(), availableTools: [{ bad: true } as never] })).toBe(false)
  })
  it('rejects non-object request', () => {
    expect(isValidLLMPlannerRequest(null)).toBe(false)
  })
  it('throws on secret in intent goal', () => {
    expect(() => isValidLLMPlannerRequest({ intent: intent({ goal: 'Bearer token leaked' }) })).toThrow(/forbidden/)
  })
})

// ============ Schema — LLMPlannerResponse ============

describe('Phase 8-B1 LLMPlannerResponse validator', () => {
  it('accepts a well-formed response', () => {
    const response = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(isValidLLMPlannerResponse(response)).toBe(true)
  })
  it('rejects invalid plan', () => {
    expect(isValidLLMPlannerResponse({ plan: { bad: true }, confidence: 0.5, explanation: 'x' })).toBe(false)
  })
  it('rejects confidence > 1', () => {
    const response = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(isValidLLMPlannerResponse({ ...response, confidence: 1.1 })).toBe(false)
  })
  it('rejects negative confidence', () => {
    const response = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(isValidLLMPlannerResponse({ ...response, confidence: -0.2 })).toBe(false)
  })
  it('rejects empty explanation', () => {
    const response = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(isValidLLMPlannerResponse({ ...response, explanation: '' })).toBe(false)
  })
  it('rejects non-string explanation', () => {
    const response = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(isValidLLMPlannerResponse({ ...response, explanation: 3 as never })).toBe(false)
  })
  it('throws on secret in explanation', () => {
    const parsed = normalizeParsedPlan(JSON.parse(cleanLLMJson()), 'g')
    const valid = isValidResearchPlan(parsed.plan!)
    expect(valid).toBe(true)
    expect(() => isValidLLMPlannerResponse({ plan: parsed.plan!, confidence: 0.5, explanation: 'sk-leak inside' })).toThrow(/forbidden/)
  })
  it('FORBIDDEN list contains all 8 secret types', () => {
    for (const bad of ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']) {
      expect(llmSchemaHelpers.FORBIDDEN).toContain(bad)
    }
    expect(llmSchemaHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ Adapter — prompt construction ============

describe('Phase 8-B1 planner model adapter: prompt', () => {
  it('constructor requires a model caller', () => {
    expect(() => new ModelCallerPlannerAdapter({ model: undefined as never })).toThrow(/model caller required/)
  })
  it('constructor accepts a model caller', () => {
    expect(() => new ModelCallerPlannerAdapter({ model: fakeModel('x') })).not.toThrow()
  })
  it('buildModelPrompt includes the research goal', () => {
    expect(buildModelPrompt({ intent: intent({ goal: 'fit kinetic model' }) })).toContain('fit kinetic model')
  })
  it('buildModelPrompt includes the domain', () => {
    expect(buildModelPrompt({ intent: intent({ domain: 'environment' }) })).toContain('"domain":"environment"')
  })
  it('buildModelPrompt includes the task type', () => {
    expect(buildModelPrompt({ intent: intent({ taskType: 'simulation' }) })).toContain('"taskType":"simulation"')
  })
  it('buildModelPrompt lists available tool ids', () => {
    const prompt = buildModelPrompt({ intent: intent(), availableTools: [profile('tool:b'), profile('tool:a')] })
    expect(prompt).toContain('tool:a, tool:b')
  })
  it('buildModelPrompt lists available capabilities', () => {
    const prompt = buildModelPrompt({ intent: intent(), availableTools: [profile('tool:a', ['data-analysis', 'visualization'])] })
    expect(prompt).toContain('data-analysis')
    expect(prompt).toContain('visualization')
  })
  it('buildModelPrompt lists available knowledge entity types', () => {
    const prompt = buildModelPrompt({ intent: intent(), availableKnowledge: ['experiment', 'paper'] })
    expect(prompt).toContain('experiment, paper')
  })
  it('buildModelPrompt falls back to context lists', () => {
    const prompt = buildModelPrompt({ intent: intent(), context: { availableKnowledge: ['dataset'] } })
    expect(prompt).toContain('dataset')
  })
  it('buildModelPrompt emits [none] when no tools', () => {
    expect(buildModelPrompt({ intent: intent() })).toContain('AVAILABLE TOOLS: (none)')
  })
  it('buildModelPrompt emits [none] when no knowledge', () => {
    expect(buildModelPrompt({ intent: intent() })).toContain('AVAILABLE KNOWLEDGE ENTITY TYPES: (none)')
  })
  it('buildModelPrompt instructs a pure JSON-only response', () => {
    const prompt = buildModelPrompt({ intent: intent() })
    expect(prompt).toContain('"tasks"')
    expect(prompt).toContain('Respond ONLY with a JSON object')
  })
  it('buildModelPrompt sorts tool ids deterministically', () => {
    const a = buildModelPrompt({ intent: intent(), availableTools: [profile('tool:b'), profile('tool:a')] })
    const b = buildModelPrompt({ intent: intent(), availableTools: [profile('tool:b'), profile('tool:a')] })
    expect(a).toBe(b)
  })
  it('uses the constructor system prompt when provided', () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('x'), systemPrompt: 'custom planner prompt' })
    expect(adapter.buildPrompt({ intent: intent() })).toContain('custom planner prompt')
  })
  it('uses the default system prompt otherwise', () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('x') })
    expect(adapter.buildPrompt({ intent: intent() })).toContain(DEFAULT_SYSTEM_PROMPT)
  })
})

// ============ Adapter — response parsing ============

describe('Phase 8-B1 planner model adapter: parsing', () => {
  it('parses a plain JSON object', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.tasks).toHaveLength(3)
  })
  it('parses a fenced ```json block', () => {
    const text = `Here you go:\n\`\`\`json\n${cleanLLMJson()}\n\`\`\``
    expect(parseModelResponse(text, makeRequest())).not.toBeNull()
  })
  it('ignores surrounding prose', () => {
    const text = `Sure. ${cleanLLMJson()} Hope this helps!`
    expect(parseModelResponse(text, makeRequest())).not.toBeNull()
  })
  it('returns a valid ResearchPlan', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(isValidResearchPlan(resp!.plan)).toBe(true)
  })
  it('preserves plan id', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp!.plan.id).toBe('plan:llm:xyz')
  })
  it('preserves step ids', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp!.plan.tasks[0]!.id).toBe('step:1:knowledge')
    expect(resp!.plan.tasks[1]!.id).toBe('step:2:tool')
  })
  it('sets status pending', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp!.plan.status).toBe('pending')
  })
  it('sets metadata planner llm:v1', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp!.plan.metadata).toEqual({ planner: 'llm:v1' })
  })
  it('injects a generated step id when missing', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.tasks[1].id
    const text = JSON.stringify(raw)
    const resp = parseModelResponse(text, makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.tasks[1]!.id.length).toBeGreaterThan(0)
  })
  it('defaults missing description', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.tasks[2].description
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.tasks[2]!.description.length).toBeGreaterThan(0)
  })
  it('drops steps with invalid type', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[1].type = 'shell'
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.tasks).toHaveLength(2)
  })
  it('defaults missing input to empty object', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.tasks[0].input
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp!.plan.tasks[0]!.input).toEqual({})
  })
  it('handles missing dependencies array', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.tasks[0].dependencies
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp!.plan.tasks[0]!.dependencies).toEqual([])
  })
  it('filters dependencies to known step ids', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[0].dependencies = ['step:7:ghost']
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp!.plan.tasks[0]!.dependencies).toEqual([])
  })
  it('drops self-referencing dependencies', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[1].dependencies = ['step:2:tool']
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp!.plan.tasks[1]!.dependencies).toEqual([])
  })
  it('injects the request goal when the model omits it', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.goal
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.goal).toBe('analyze bubble data')
  })
  it('rejects cyclic plans', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[0].dependencies = ['step:3:synthesis']
    raw.plan.tasks[2].dependencies = ['step:1:knowledge']
    expect(parseModelResponse(JSON.stringify(raw), makeRequest())).toBeNull()
  })
  it('repairs counter is 0 for a clean plan', () => {
    const parsed = normalizeParsedPlan(JSON.parse(cleanLLMJson()), 'g')
    expect(parsed.repairs).toBe(0)
    expect(parsed.error).toBeUndefined()
  })
  it('repairs counter grows on structural fixes', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.plan.tasks[1].description
    delete raw.plan.tasks[1].id
    const parsed = normalizeParsedPlan(raw, 'g')
    expect(parsed.repairs).toBeGreaterThan(0)
  })
  it('returns null on garbage text', () => {
    expect(parseModelResponse('not json at all', makeRequest())).toBeNull()
  })
  it('returns null when no braces present', () => {
    expect(parseModelResponse('just words', makeRequest())).toBeNull()
  })
  it('returns null when inner JSON is malformed', () => {
    expect(parseModelResponse('{ "plan": {tasks:', makeRequest())).toBeNull()
  })
  it('returns null when the plan fails structural validation', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks = raw.plan.tasks.map((t) => ({ ...t, type: 'nope' }))
    expect(parseModelResponse(JSON.stringify(raw), makeRequest())).toBeNull()
  })
  it('parse is deterministic for the same text', () => {
    const a = parseModelResponse(cleanLLMJson(), makeRequest())
    const b = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})

// ============ Adapter — confidence ============

describe('Phase 8-B1 planner model adapter: confidence', () => {
  it('uses the provided confidence', () => {
    const resp = parseModelResponse(cleanLLMJson(0.9), makeRequest())
    expect(resp!.confidence).toBe(0.9)
  })
  it('clamps confidence above 1 to 1', () => {
    expect(computeLlmConfidence(JSON.parse(cleanLLMJson(2)) as never, 0)).toBe(1)
  })
  it('clamps negative confidence to 0', () => {
    const resp = parseModelResponse(JSON.stringify({ plan: JSON.parse(cleanLLMJson()).plan, confidence: -5, explanation: 'x' }), makeRequest())
    expect(resp!.confidence).toBe(0)
  })
  it('defaults clean plans to 0.85', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.confidence
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp!.confidence).toBe(0.85)
  })
  it('caps repaired plan confidence at 0.6 even with high provided confidence', () => {
    const raw = JSON.parse(cleanLLMJson(0.9))
    delete raw.plan.id
    const resp = parseModelResponse(JSON.stringify(raw), makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.confidence).toBe(0.6)
  })
  it('explanation is always non-empty', () => {
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())
    expect(resp!.explanation.length).toBeGreaterThan(0)
  })
})

// ============ Adapter — generatePlan ============

describe('Phase 8-B1 planner model adapter: generatePlan', () => {
  it('returns a parsed plan from valid model text', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson()) })
    const resp = await adapter.generatePlan(makeRequest())
    expect(resp.plan.tasks).toHaveLength(3)
    expect(resp.confidence).toBe(0.9)
  })
  it('calls model.complete once with the built prompt', async () => {
    const record: { options?: unknown[] } = {}
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(), record) })
    await adapter.generatePlan(makeRequest())
    expect(record.options).toHaveLength(2)
    expect(String(record.options![0])).toContain('analyze bubble data')
  })
  it('passes the configured maxTokens option', async () => {
    const record: { options?: unknown[] } = {}
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(), record), maxTokens: 512 })
    await adapter.generatePlan(makeRequest())
    expect((record.options![1] as { maxTokens?: number }).maxTokens).toBe(512)
  })
  it('throws on unparseable model output', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('totally not json') })
    await expect(adapter.generatePlan(makeRequest())).rejects.toThrow(/could not be parsed/)
  })
  it('throws on invalid request', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson()) })
    await expect(adapter.generatePlan({ intent: undefined as never })).rejects.toThrow(/invalid LLMPlannerRequest/)
  })
  it('rejects cyclic model output', async () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[2].dependencies = ['step:1:knowledge']
    raw.plan.tasks[0].dependencies = ['step:3:synthesis']
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(JSON.stringify(raw)) })
    await expect(adapter.generatePlan(makeRequest())).rejects.toThrow(/could not be parsed/)
  })
  it('is deterministic for the same model text', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson()) })
    const a = await adapter.generatePlan(makeRequest())
    const b = await adapter.generatePlan(makeRequest())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
})

// ============ Hybrid planner — modes ============

describe('Phase 8-B1 HybridPlanner: modes', () => {
  it('defaults to hybrid mode', () => {
    expect(new HybridPlanner().getMode()).toBe('hybrid')
  })
  it('constructor accepts explicit mode', () => {
    expect(new HybridPlanner({ mode: 'rule-only' }).getMode()).toBe('rule-only')
  })
  it('constructor accepts llm-only mode', () => {
    expect(new HybridPlanner({ mode: 'llm-only' }).getMode()).toBe('llm-only')
  })
  it('constructor rejects invalid mode', () => {
    expect(() => new HybridPlanner({ mode: 'auto' as never })).toThrow(/invalid mode/)
  })
  it('setMode switches strategy', () => {
    const p = new HybridPlanner()
    p.setMode('llm-only')
    expect(p.getMode()).toBe('llm-only')
  })
  it('setMode rejects invalid values', () => {
    const p = new HybridPlanner()
    expect(() => p.setMode('auto' as never)).toThrow(/invalid mode/)
  })
  it('hasAdapter false without adapter', () => {
    expect(new HybridPlanner().hasAdapter()).toBe(false)
  })
  it('hasAdapter true with adapter', () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson()) })
    expect(new HybridPlanner({ adapter }).hasAdapter()).toBe(true)
  })
})

// ============ Hybrid planner — rule-only ============

describe('Phase 8-B1 HybridPlanner: rule-only', () => {
  let planner: HybridPlanner
  beforeEach(() => { planner = new HybridPlanner({ mode: 'rule-only' }) })
  it('always wins via the rule plan', async () => {
    const r = await planner.plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('rule-only')
  })
  it('returns the deterministic rule template', async () => {
    const r = await planner.plan('Analyze water quality data')
    expect(r.decision.plan.tasks.map((t) => t.type)).toEqual(['knowledge', 'analysis', 'tool', 'synthesis'])
  })
  it('returns the rule confidence', async () => {
    const r = await planner.plan('Analyze water quality data')
    expect(r.decision.confidence).toBe(RULE_CONF_DATA_ANALYSIS)
  })
  it('does not consult any adapter', async () => {
    let called = false
    const adapter: PlannerModelAdapter = { generatePlan: async () => { called = true; throw new Error('should not run') } }
    const p = new HybridPlanner({ mode: 'rule-only', adapter })
    const r = await p.plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(called).toBe(false)
  })
  it('reasoning summary is secret-free and traces winner', async () => {
    const r = await planner.plan('Analyze water quality data')
    expect(r.decision.reasoningSummary).toContain('mode=rule-only')
    expect(r.decision.reasoningSummary).toContain('winner=rule')
  })
  it('stamps metadata plannerStrategy rule', async () => {
    const r = await planner.plan('Analyze water quality data')
    expect(r.decision.plan.metadata!.plannerStrategy).toBe('rule')
  })
})

// ============ Hybrid planner — LLM acceptance + fallback ============

describe('Phase 8-B1 HybridPlanner: hybrid LLM acceptance + fallback', () => {
  it('hybrid without adapter falls back to rule (reason no-adapter)', async () => {
    const r = await new HybridPlanner().plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('no-adapter')
  })
  it('accepts a high-confidence valid LLM plan', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('llm')
    expect(r.reason).toBe('llm-accepted')
    expect(r.decision.confidence).toBe(0.9)
  })
  it('uses the LLM plan tasks when accepted', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.decision.plan.tasks).toHaveLength(3)
    expect(r.decision.plan.tasks[1]!.type).toBe('tool')
  })
  it('stamps metadata plannerStrategy llm when accepted', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.decision.plan.metadata!.plannerStrategy).toBe('llm')
  })
  it('rejects LLM plan with lower confidence than the rule baseline', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.5)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-lower-confidence')
  })
  it('rejects LLM plan with confidence equal to the baseline', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(RULE_CONF_DATA_ANALYSIS)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
  })
  it('falls back to rule when the adapter throws', async () => {
    const adapter: PlannerModelAdapter = { generatePlan: async () => { throw new Error('model down') } }
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-error')
    expect(r.decision.confidence).toBe(RULE_CONF_DATA_ANALYSIS)
  })
  it('falls back to rule when the adapter returns unparseable text', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('garbage') })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-error')
  })
  it('falls back to rule on capability mismatch (knowledge entity absent)', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const context: PlannerContext = { availableKnowledge: ['dataset'] } // llm plan wants 'experiment'
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-capability-mismatch')
  })
  it('accepts LLM when knowledge entity is present in context', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const context: PlannerContext = { availableKnowledge: ['experiment'] }
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('llm')
  })
  it('caps rule fallback confidence in result even when LLM failed', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('nope') })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.ruleConfidence).toBe(RULE_CONF_DATA_ANALYSIS)
  })
  it('capability mismatch on unknown tool id', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const context: PlannerContext = { availableTools: [profile('tool:other', ['data-analysis'])] }
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('rule')
  })
  it('capability satisfied when tool id present', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const context: PlannerContext = { availableTools: [profile('tool:dataset-analysis', ['data-analysis'])] }
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('llm')
  })
  it('accepts LLM when no context is given (nothing to verify)', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('llm')
  })
  it('per-call mode overrides the constructor default', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const p = new HybridPlanner({ mode: 'rule-only', adapter })
    const r = await p.plan('Analyze water quality data', undefined, 'hybrid')
    expect(r.winner).toBe('llm')
  })
  it('rejects an invalid per-call mode', async () => {
    const p = new HybridPlanner()
    await expect(p.plan('Analyze water quality data', undefined, 'auto' as never)).rejects.toThrow(/invalid mode/)
  })
})

// ============ Hybrid planner — llm-only ============

describe('Phase 8-B1 HybridPlanner: llm-only', () => {
  it('throws when no adapter is configured', async () => {
    await expect(new HybridPlanner({ mode: 'llm-only' }).plan('Analyze water quality data'))
      .rejects.toThrow(/llm-only mode requires an adapter/)
  })
  it('accepts a valid LLM plan', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ mode: 'llm-only', adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('llm')
  })
  it('accepts a valid LLM plan even with low confidence (no rule baseline gate)', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.4)) })
    const r = await new HybridPlanner({ mode: 'llm-only', adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('llm')
    expect(r.decision.confidence).toBe(0.4)
  })
  it('falls back to the rule plan on unparseable output', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('garbage') })
    const r = await new HybridPlanner({ mode: 'llm-only', adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-error')
  })
  it('falls back to rule on capability mismatch', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const context: PlannerContext = { availableKnowledge: ['dataset'] }
    const r = await new HybridPlanner({ mode: 'llm-only', adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-capability-mismatch')
  })
  it('falls back to rule on an invalid (cyclic) plan', async () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[2].dependencies = ['step:1:knowledge']
    raw.plan.tasks[0].dependencies = ['step:3:synthesis']
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(JSON.stringify(raw)) })
    const r = await new HybridPlanner({ mode: 'llm-only', adapter }).plan('Analyze water quality data')
    expect(r.winner).toBe('rule')
    expect(r.reason).toBe('llm-error')
  })
})

// ============ Hybrid planner — plan validity + determinism ============

describe('Phase 8-B1 HybridPlanner: validity + determinism', () => {
  it('validateLLMPlan exposes a clean acceptance report', () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson()) })
    const p = new HybridPlanner({ adapter })
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(p.validateLLMPlan(resp.plan).ok).toBe(true)
  })
  it('validateLLMPlan rejects a cyclic plan', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks[2].dependencies = ['step:1:knowledge']
    raw.plan.tasks[0].dependencies = ['step:3:synthesis']
    const plan = normalizeParsedPlan(raw, 'g') as { plan?: ResearchPlan }
    const p = new HybridPlanner()
    const report = p.validateLLMPlan(plan.plan ?? { id: 'x', goal: 'g', tasks: [], status: 'pending' })
    expect(report.ok).toBe(false)
  })
  it('capabilitySatisfied passes with no context', () => {
    const p = new HybridPlanner()
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(p.capabilitySatisfied(resp.plan)).toBe(true)
  })
  it('capabilitySatisfied blocks a missing entity type', () => {
    const p = new HybridPlanner()
    const resp = parseModelResponse(cleanLLMJson(), makeRequest())!
    expect(p.capabilitySatisfied(resp.plan, { availableKnowledge: ['dataset'] })).toBe(false)
  })
  it('hybrid planning is deterministic for the same request + model output', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const p = new HybridPlanner({ adapter })
    const a = await p.plan('Analyze water quality data')
    const b = await p.plan('Analyze water quality data')
    expect(JSON.stringify(a.decision)).toBe(JSON.stringify(b.decision))
  })
  it('rule winner is stable across repetitions', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.5)) })
    const p = new HybridPlanner({ adapter })
    const a = await p.plan('Analyze water quality data')
    const b = await p.plan('Analyze water quality data')
    expect(a.winner).toBe(b.winner)
  })
  it('setMode then plan uses the new mode', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const p = new HybridPlanner({ mode: 'rule-only', adapter })
    p.setMode('hybrid')
    const r = await p.plan('Analyze water quality data')
    expect(r.winner).toBe('llm')
  })
  it('planFromIntent routes through the same pipeline', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).planFromIntent(intent(), undefined, 'hybrid')
    expect(r.winner).toBe('llm')
  })
})

// ============ Source-level independence + security ============

describe('Phase 8-B1 planner separation — source scans', () => {
  function readSrc(p: string): string {
    const fs = require('fs')
    const path = require('path')
    return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
  }
  it('hybrid-planner.ts does not import the runtime', () => {
    const src = readSrc('../../src/main/services/agent/hybrid-planner.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*\/agent-runtime['"]/)
    expect(src).not.toContain('ResearchAgentRuntime')
  })
  it('hybrid-planner.ts does not import model-provider / auth / backend', () => {
    const src = readSrc('../../src/main/services/agent/hybrid-planner.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('planner-model-adapter.ts does not import the runtime implementation', () => {
    const src = readSrc('../../src/main/services/agent/planner-model-adapter.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*\/agent-runtime['"]/)
    expect(src).not.toContain('ResearchAgentRuntime')
  })
  it('planner-model-adapter.ts does not import model-provider / SDK', () => {
    const src = readSrc('../../src/main/services/agent/planner-model-adapter.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*@anthropic-ai/)
    expect(src).not.toMatch(/from\s+['"][^'"]*openai/)
  })
  it('adapter source contains no credential literals', () => {
    const src = readSrc('../../src/main/services/agent/planner-model-adapter.ts')
    expect(src).not.toContain('apiKey = ')
    expect(src).not.toContain('process.env')
  })
  it('adapter + hybrid sources have no randomness', () => {
    const a = readSrc('../../src/main/services/agent/planner-model-adapter.ts')
    const h = readSrc('../../src/main/services/agent/hybrid-planner.ts')
    expect(a).not.toContain('Math.random')
    expect(h).not.toContain('Math.random')
    expect(a).not.toContain('Date.now')
    expect(h).not.toContain('Date.now')
  })
  it('hybrid planner imports the B0 rule service, not runtime internals', () => {
    const src = readSrc('../../src/main/services/agent/hybrid-planner.ts')
    expect(src).toContain("./research-planner'")
    expect(src).toContain("./planner-model-adapter'")
  })
  it('llm-planner-schema.ts has no forbidden imports', () => {
    const src = readSrc('../../src/shared/agent/llm-planner-schema.ts')
    expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
    expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
    expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
  })
  it('llm-planner-schema.ts exposes the 8-item FORBIDDEN list', () => {
    expect(llmSchemaHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ Supplementary edge cases ============

describe('Phase 8-B1 supplementary adapter edge cases', () => {
  it('parses a plan object at the top level (no wrapper key)', () => {
    const raw = JSON.parse(cleanLLMJson())
    const unwrapped = JSON.stringify(raw.plan)
    const resp = parseModelResponse(unwrapped, makeRequest())
    expect(resp).not.toBeNull()
    expect(resp!.plan.tasks).toHaveLength(3)
  })
  it('safely nulls when trailing brace-groups would corrupt the JSON envelope', () => {
    const text = `maybe ${cleanLLMJson()} or ${JSON.stringify({ x: 1 })}`
    expect(parseModelResponse(text, makeRequest())).toBeNull()
  })
  it('returns null when the model emits an empty task list', () => {
    const raw = JSON.parse(cleanLLMJson())
    raw.plan.tasks = []
    expect(parseModelResponse(JSON.stringify(raw), makeRequest())).toBeNull()
  })
  it('adapter throws on empty model text', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('') })
    await expect(adapter.generatePlan(makeRequest())).rejects.toThrow(/could not be parsed/)
  })
  it('adapter throws on a bare empty object', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel('{}') })
    await expect(adapter.generatePlan(makeRequest())).rejects.toThrow(/could not be parsed/)
  })
  it('repairs do not lower an already-low provided confidence', () => {
    expect(computeLlmConfidence(JSON.parse(cleanLLMJson(0.3)), 1)).toBe(0.3)
  })
  it('repairs with negative confidence clamp to 0', () => {
    expect(computeLlmConfidence({ confidence: -5 }, 2)).toBe(0)
  })
  it('repairs with no provided confidence use the 0.6 repair floor', () => {
    const raw = JSON.parse(cleanLLMJson())
    delete raw.confidence
    expect(computeLlmConfidence(raw, 1)).toBe(0.6)
  })
  it('normalizeParsedPlan returns error for non-object input', () => {
    const parsed = normalizeParsedPlan('tasks only', 'g')
    expect(parsed.plan).toBeUndefined()
    expect(parsed.error).toBe('model output is not an object')
  })
  it('normalizeParsedPlan tolerates a missing tasks key as an empty plan error', () => {
    const parsed = normalizeParsedPlan({ id: 'p', goal: 'g' }, 'g')
    expect(parsed.error).toBe('plan has no steps')
  })
})

describe('Phase 8-B1 supplementary hybrid edge cases', () => {
  it('accepts an LLM plan for paper-writing (rule conf 0.67 < 0.9)', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Help me polish my paper manuscript')
    expect(r.winner).toBe('llm')
  })
  it('accepts a model-only LLM plan even when tool context is scarce', async () => {
    const text = JSON.stringify({
      plan: {
        id: 'p', goal: 'g', tasks: [
          { id: 's:1', type: 'model', description: 'draft', input: { prompt: 'write' }, dependencies: [] },
          { id: 's:2', type: 'synthesis', description: 'combine', input: {}, dependencies: ['s:1'] }
        ]
      },
      confidence: 0.9,
      explanation: 'model plan'
    })
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(text) })
    const context: PlannerContext = { availableTools: [profile('tool:a', ['data-analysis'])] }
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data', context)
    expect(r.winner).toBe('llm')
  })
  it('rule-only never applies a capability gate', async () => {
    const p = new HybridPlanner({ mode: 'rule-only' })
    const context: PlannerContext = { availableKnowledge: ['dataset'] } // rule knowledge step uses 'dataset'
    const r = await p.plan('对数据集做回归和数据分析', context)
    expect(r.winner).toBe('rule')
  })
  it('rejects empty user request through the classifier', async () => {
    await expect(new HybridPlanner().plan('')).rejects.toThrow(/non-empty string/)
  })
  it('rejects an invalid mode passed to planFromIntent', async () => {
    await expect(new HybridPlanner().planFromIntent(intent(), undefined, 'auto' as never))
      .rejects.toThrow(/invalid mode/)
  })
  it('llm reasoning summary records confidence=0.9', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(r.decision.reasoningSummary).toContain('confidence=0.9')
    expect(r.decision.reasoningSummary).toContain('llm-accepted')
  })
  it('rule reasoning summary records the rule step count', async () => {
    const r = await new HybridPlanner().plan('Analyze water quality data')
    expect(r.decision.reasoningSummary).toContain('steps=4')
    expect(r.decision.reasoningSummary).toContain('template=knowledge -> analysis -> tool -> synthesis')
  })
  it('llm winner decision plan passes A0 validation', async () => {
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(0.9)) })
    const r = await new HybridPlanner({ adapter }).plan('Analyze water quality data')
    expect(isValidResearchPlan(r.decision.plan)).toBe(true)
  })
  it('capabilitySatisfied passes generic tool steps even under a tool context', () => {
    const p = new HybridPlanner()
    const plan = makeMinimalPlan({ type: 'tool', input: { capability: 'data-analysis' } })
    expect(p.capabilitySatisfied(plan, { availableTools: [profile('tool:a', ['data-analysis'])] })).toBe(true)
  })
  it('capabilitySatisfied passes a model-only plan under any contexts', () => {
    const p = new HybridPlanner()
    const plan = makeMinimalPlan({ type: 'model', input: { prompt: 'x' } })
    expect(p.capabilitySatisfied(plan, { availableKnowledge: ['foo'] })).toBe(true)
  })
  it('capabilitySatisfied blocks a knowledge step for an absent entity type', () => {
    const p = new HybridPlanner()
    const plan = makeMinimalPlan({ type: 'knowledge', input: { entityType: 'paper' } })
    expect(p.capabilitySatisfied(plan, { availableKnowledge: ['experiment'] })).toBe(false)
  })
  it('capabilitySatisfied blocks a tool step for an absent capability', () => {
    const p = new HybridPlanner()
    const plan = makeMinimalPlan({ type: 'tool', input: { toolId: 'tool:nope' } })
    expect(p.capabilitySatisfied(plan, { availableTools: [profile('tool:a', ['data-analysis'])] })).toBe(false)
  })
  it('setMode is idempotent for the same value', () => {
    const p = new HybridPlanner()
    p.setMode('hybrid')
    p.setMode('hybrid')
    expect(p.getMode()).toBe('hybrid')
  })
  it('adapter passing maxTokens default is 2048', async () => {
    const record: { options?: unknown[] } = {}
    const adapter = new ModelCallerPlannerAdapter({ model: fakeModel(cleanLLMJson(), record) })
    await adapter.generatePlan(makeRequest())
    expect((record.options![1] as { maxTokens?: number }).maxTokens).toBe(2048)
  })
})

function makeMinimalPlan(step: { type: string; input: Record<string, unknown> }): ResearchPlan {
  return {
    id: 'p',
    goal: 'g',
    status: 'pending',
    tasks: [{ id: 's:1', type: step.type as never, description: 'd', input: step.input, dependencies: [] }]
  }
}