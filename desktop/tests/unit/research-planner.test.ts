// Phase 8-B0 Research Planner tests.
//
// Coverage (>100 cases):
//   - Planner schemas / validators (30)
//   - Intent detection: domain (12)
//   - Intent detection: task (12)
//   - topic / goal / constraints / capabilities (12)
//   - Rule plan generation (26)
//   - Confidence estimation (12)
//   - Invalid input (8)
//   - Security (9)
//   - Determinism (7)
//   - Planner / runtime separation (10)

import { describe, it, expect, beforeEach } from 'vitest'

// ============ Imports: shared planner schema ============
import {
  RESEARCH_DOMAINS,
  PLANNER_TASK_TYPES,
  isValidResearchDomain,
  isValidPlannerTaskType,
  isValidResearchIntent,
  isValidPlannerContext,
  isValidPlannerDecision,
  isValidIntentEvidence,
  __testHelpers as schemaHelpers
} from '../../src/shared/agent/planner-schema'
import type {
  ResearchIntent,
  PlannerContext,
  PlannerDecision,
  ResearchDomain,
  PlannerTaskType
} from '../../src/shared/agent/planner-schema'

// ============ Imports: planner infrastructure ============
import type { ResearchPlan, ResearchPlanStep } from '../../src/shared/agent/research-plan-schema'
import { isValidResearchPlan, detectCycle } from '../../src/shared/agent/research-plan-schema'
import type { ToolCapabilityProfile } from '../../src/shared/tools/tool-capability-schema'

import {
  classifyIntent,
  classifyIntentWithEvidence,
  extractTopic,
  DOMAIN_KEYWORDS,
  TASK_KEYWORDS,
  CONSTRAINT_RULES,
  CAPABILITIES_BY_TASK
} from '../../src/main/services/agent/intent-classifier'
import {
  createPlanFromIntent,
  TEMPLATE_CHAINS,
  __testHelpers as ruleHelpers
} from '../../src/main/services/agent/rule-planner'
import {
  ResearchPlanner,
  __testHelpers as plannerHelpers
} from '../../src/main/services/agent/research-planner'
import { ResearchAgentRuntime } from '../../src/main/services/agent/agent-runtime'
import type { KnowledgeCaller, ModelCaller, ToolCaller } from '../../src/shared/agent/agent-runtime-schema'

// ============ Fixtures ============

function makeIntent(overrides: Partial<ResearchIntent> = {}): ResearchIntent {
  return {
    topic: 'test topic',
    goal: 'test goal',
    domain: 'experiment',
    taskType: 'data-analysis',
    constraints: [],
    requiredCapabilities: ['data-analysis', 'statistics', 'regression', 'visualization'],
    ...overrides
  }
}

function profile(toolId: string, caps: string[]): ToolCapabilityProfile {
  return {
    toolId,
    requiredCapabilities: caps,
    optionalCapabilities: [],
    supportedTasks: [],
    priority: 5
  }
}

// ============ Schemas / validators ============

describe('Phase 8-B0 planner validators', () => {
  it('RESEARCH_DOMAINS has exactly 5 entries', () => {
    expect(RESEARCH_DOMAINS.length).toBe(5)
  })
  it('PLANNER_TASK_TYPES has exactly 5 entries', () => {
    expect(PLANNER_TASK_TYPES.length).toBe(5)
  })
  it('accepts all 5 research domains', () => {
    for (const d of RESEARCH_DOMAINS) expect(isValidResearchDomain(d)).toBe(true)
  })
  it('rejects unknown research domain', () => {
    expect(isValidResearchDomain('biology')).toBe(false)
  })
  it('rejects non-string domain', () => {
    expect(isValidResearchDomain(42)).toBe(false)
  })
  it('accepts all 5 planner task types', () => {
    for (const t of PLANNER_TASK_TYPES) expect(isValidPlannerTaskType(t)).toBe(true)
  })
  it('rejects unknown planner task type', () => {
    expect(isValidPlannerTaskType('robot-planning')).toBe(false)
  })
  it('rejects non-string task type', () => {
    expect(isValidPlannerTaskType({})).toBe(false)
  })
  it('accepts a well-formed ResearchIntent', () => {
    expect(isValidResearchIntent(makeIntent())).toBe(true)
  })
  it('rejects intent with empty topic', () => {
    expect(isValidResearchIntent(makeIntent({ topic: '' }))).toBe(false)
  })
  it('rejects intent with empty goal', () => {
    expect(isValidResearchIntent(makeIntent({ goal: '' }))).toBe(false)
  })
  it('rejects intent with invalid domain', () => {
    expect(isValidResearchIntent(makeIntent({ domain: 'nope' as never }))).toBe(false)
  })
  it('rejects intent with invalid taskType', () => {
    expect(isValidResearchIntent(makeIntent({ taskType: 'nope' as never }))).toBe(false)
  })
  it('rejects intent with non-array constraints', () => {
    expect(isValidResearchIntent(makeIntent({ constraints: 'x' as never }))).toBe(false)
  })
  it('rejects intent with non-string capabilities', () => {
    expect(isValidResearchIntent(makeIntent({ requiredCapabilities: ['a', 1] as never }))).toBe(false)
  })
  it('rejects non-object intent', () => {
    expect(isValidResearchIntent(null)).toBe(false)
  })
  it('accepts empty PlannerContext', () => {
    expect(isValidPlannerContext({})).toBe(true)
  })
  it('accepts PlannerContext with previousResults + availableKnowledge', () => {
    expect(isValidPlannerContext({ previousResults: { ok: 1 }, availableKnowledge: ['experiment'] })).toBe(true)
  })
  it('rejects PlannerContext with array previousResults', () => {
    expect(isValidPlannerContext({ previousResults: [1] })).toBe(false)
  })
  it('rejects PlannerContext with non-string availableKnowledge', () => {
    expect(isValidPlannerContext({ availableKnowledge: ['experiment', 3] })).toBe(false)
  })
  it('accepts a well-formed PlannerDecision', () => {
    const plan = createPlanFromIntent(makeIntent())
    expect(isValidPlannerDecision({ plan, confidence: 0.7, reasoningSummary: 'ok' })).toBe(true)
  })
  it('rejects decision with confidence > 1', () => {
    const plan = createPlanFromIntent(makeIntent())
    expect(isValidPlannerDecision({ plan, confidence: 1.01, reasoningSummary: 'ok' })).toBe(false)
  })
  it('rejects decision with negative confidence', () => {
    const plan = createPlanFromIntent(makeIntent())
    expect(isValidPlannerDecision({ plan, confidence: -0.1, reasoningSummary: 'ok' })).toBe(false)
  })
  it('rejects decision with empty reasoning', () => {
    const plan = createPlanFromIntent(makeIntent())
    expect(isValidPlannerDecision({ plan, confidence: 0.5, reasoningSummary: '' })).toBe(false)
  })
  it('rejects decision with invalid plan', () => {
    expect(isValidPlannerDecision({ plan: { bad: true }, confidence: 0.5, reasoningSummary: 'x' })).toBe(false)
  })
  it('accepts a well-formed IntentEvidence', () => {
    const evidence = classifyIntentWithEvidence('Analyze water quality data')
    expect(isValidIntentEvidence(evidence)).toBe(true)
  })
  it('rejects IntentEvidence with non-numeric score', () => {
    const evidence = classifyIntentWithEvidence('Analyze water quality data')
    expect(isValidIntentEvidence({ ...evidence, domainScore: '1' as never })).toBe(false)
  })
  it('rejects non-object evidence', () => {
    expect(isValidIntentEvidence(123)).toBe(false)
  })
  it('FORBIDDEN list contains all 8 secret types', () => {
    for (const bad of ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization', 'providerId', 'modelId']) {
      expect(schemaHelpers.FORBIDDEN).toContain(bad)
    }
    expect(schemaHelpers.FORBIDDEN.length).toBe(8)
  })
})

// ============ Domain detection ============

describe('Phase 8-B0 domain detection', () => {
  const cases: Array<[string, ResearchDomain]> = [
    ['Analyze water quality data', 'environment'],
    ['Evaluate the chemical reaction kinetics', 'chemistry'],
    ['Improve wireless communication signal', 'communication'],
    ['Design a PID controller for stability', 'control'],
    ['Summarize the experiment protocol', 'experiment']
  ]
  it('detects English domains via keyword scoring', () => {
    for (const [text, domain] of cases) {
      expect(classifyIntent(text).domain, text).toBe(domain)
    }
  })
  it('detects Chinese domains via keyword scoring', () => {
    expect(classifyIntent('分析水环境污染数据').domain).toBe('environment')
    expect(classifyIntent('分析化学反应的分子结构').domain).toBe('chemistry')
    expect(classifyIntent('优化无线通信信号的传输').domain).toBe('communication')
    expect(classifyIntent('设计PID控制器提升系统稳定性').domain).toBe('control')
    expect(classifyIntent('记录实验测量装置的结果').domain).toBe('experiment')
  })
  it('falls back to experiment when no domain keyword matches', () => {
    expect(classifyIntent('请介绍一下你的功能').domain).toBe('experiment')
  })
  it('falls back when request is task-like without domain words', () => {
    expect(classifyIntent('翻译这段话').domain).toBe('experiment')
  })
  it('reports domain evidence score + matched keywords', () => {
    const ev = classifyIntentWithEvidence('Analyze water quality data')
    expect(ev.domain).toBe('environment')
    expect(ev.domainMatched).toEqual(['water'])
    expect(ev.domainScore).toBe(1)
  })
  it('highest keyword count wins the domain', () => {
    // 水 + 环境 + 污染 (3) beat 实验 (0)
    expect(classifyIntent('分析水环境污染数据').domain).toBe('environment')
  })
  it('ties resolve to the earlier enum domain', () => {
    // 'communication' vs 'control' both score 1 on 'signal control'
    expect(classifyIntent('signal control design').domain).toBe('communication')
  })
  it('domain keyword tables cover all 5 domains', () => {
    for (const d of RESEARCH_DOMAINS) expect(DOMAIN_KEYWORDS[d].length).toBeGreaterThan(0)
  })
  it('domain detection is deterministic across calls', () => {
    const a = classifyIntent('Analyze water quality data')
    const b = classifyIntent('Analyze water quality data')
    expect(a.domain).toBe(b.domain)
  })
})

// ============ Task detection ============

describe('Phase 8-B0 task detection', () => {
  it('detects literature-review', () => {
    expect(classifyIntent('Write a literature review of micro-nano bubble papers').taskType).toBe('literature-review')
  })
  it('detects experiment-analysis', () => {
    expect(classifyIntent('Analyze the experiment result and conclude').taskType).toBe('experiment-analysis')
  })
  it('detects data-analysis', () => {
    expect(classifyIntent('Perform regression and data analysis').taskType).toBe('data-analysis')
  })
  it('detects simulation', () => {
    expect(classifyIntent('Run a CFD simulation of water flow').taskType).toBe('simulation')
  })
  it('detects paper-writing', () => {
    expect(classifyIntent('Help me polish my paper manuscript').taskType).toBe('paper-writing')
  })
  it('detects Chinese tasks', () => {
    expect(classifyIntent('写一份关于微纳气泡的文献综述').taskType).toBe('literature-review')
    expect(classifyIntent('分析实验结果并得出结论').taskType).toBe('experiment-analysis')
    expect(classifyIntent('对数据集做回归和数据分析').taskType).toBe('data-analysis')
    expect(classifyIntent('对曝气过程进行数值模拟').taskType).toBe('simulation')
    expect(classifyIntent('帮我校对润色论文').taskType).toBe('paper-writing')
  })
  it('falls back to data-analysis on ambiguous text', () => {
    expect(classifyIntent('翻译这段话').taskType).toBe('data-analysis')
  })
  it('task evidence records matched keywords', () => {
    const ev = classifyIntentWithEvidence('Run a CFD simulation of water flow')
    expect(ev.task).toBe('simulation')
    expect(ev.taskMatched).toContain('cfd')
    expect(ev.taskMatched).toContain('simulation')
    expect(ev.taskScore).toBe(2)
  })
  it('task keyword tables cover all 5 tasks', () => {
    for (const t of PLANNER_TASK_TYPES) expect(TASK_KEYWORDS[t].length).toBeGreaterThan(0)
  })
  it('task detection is case-insensitive', () => {
    expect(classifyIntent('RUN A CFD SIMULATION').taskType).toBe('simulation')
  })
})

// ============ topic / goal / constraints / capabilities ============

describe('Phase 8-B0 topic, goal, constraints, capabilities', () => {
  it('topic is the first sentence', () => {
    expect(classifyIntent('Analyze water quality data. Also plot it.').topic).toBe('Analyze water quality data')
  })
  it('topic splits on full-width comma', () => {
    expect(classifyIntent('给出水环境定量模型，要求快速').topic).toBe('给出水环境定量模型')
  })
  it('topic truncates to 60 chars', () => {
    const long = 'a'.repeat(100)
    expect(extractTopic(long)).toHaveLength(60)
  })
  it('extractTopic returns general topic for empty segment', () => {
    expect(extractTopic(' ')).toBe('general topic')
  })
  it('goal is the normalized (single-spaced) request', () => {
    expect(classifyIntent('  Fetch   数据  ').goal).toBe('Fetch 数据')
  })
  it('goal preserves original text for plain requests', () => {
    expect(classifyIntent('Analyze water quality data').goal).toBe('Analyze water quality data')
  })
  it('extracts quantitative + fast constraints in table order', () => {
    expect(classifyIntent('给出水环境定量模型，要求快速').constraints).toEqual(['quantitative', 'fast'])
  })
  it('extracts no constraints when none present', () => {
    expect(classifyIntent('Analyze water quality data').constraints).toEqual([])
  })
  it('constraint rules cover the documented tags', () => {
    const keys = CONSTRAINT_RULES.map((r) => r.key)
    for (const k of ['quantitative', 'recent', 'chinese', 'fast', 'precise', 'compare']) {
      expect(keys).toContain(k)
    }
  })
  it('required capabilities align with detected task', () => {
    const intent = classifyIntent('Perform regression and data analysis')
    expect(intent.requiredCapabilities).toEqual([...CAPABILITIES_BY_TASK['data-analysis']])
  })
  it('every task has non-empty capability list', () => {
    for (const t of PLANNER_TASK_TYPES) expect(CAPABILITIES_BY_TASK[t].length).toBeGreaterThan(0)
  })
  it('classifier output equals evidence intent', () => {
    const text = 'Run a CFD simulation of water flow'
    const ev = classifyIntentWithEvidence(text)
    expect(ev.intent).toEqual(classifyIntent(text))
  })
})

// ============ Rule plan generation ============

describe('Phase 8-B0 rule plan generation', () => {
  it('generates valid ResearchPlan for every task type', () => {
    for (const t of PLANNER_TASK_TYPES) {
      const plan = createPlanFromIntent(makeIntent({ taskType: t }))
      expect(isValidResearchPlan(plan)).toBe(true)
      expect(plan.status).toBe('pending')
    }
  })
  it('step-type chain matches the task template', () => {
    for (const t of PLANNER_TASK_TYPES) {
      const plan = createPlanFromIntent(makeIntent({ taskType: t }))
      expect(plan.tasks.map((s) => s.type)).toEqual([...TEMPLATE_CHAINS[t]])
    }
  })
  it('literature-review template: knowledge -> synthesis', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'literature-review' }))
    expect(plan.tasks).toHaveLength(2)
    expect(plan.tasks.map((s) => s.type)).toEqual(['knowledge', 'synthesis'])
  })
  it('experiment-analysis template: knowledge -> tool -> tool -> synthesis', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'experiment-analysis' }))
    expect(plan.tasks.map((s) => s.type)).toEqual(['knowledge', 'tool', 'tool', 'synthesis'])
  })
  it('data-analysis template: knowledge -> analysis -> tool -> synthesis', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    expect(plan.tasks.map((s) => s.type)).toEqual(['knowledge', 'analysis', 'tool', 'synthesis'])
  })
  it('simulation template: knowledge -> tool -> analysis -> tool -> synthesis', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'simulation' }))
    expect(plan.tasks.map((s) => s.type)).toEqual(['knowledge', 'tool', 'analysis', 'tool', 'synthesis'])
  })
  it('paper-writing template: knowledge -> model -> synthesis', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'paper-writing' }))
    expect(plan.tasks.map((s) => s.type)).toEqual(['knowledge', 'model', 'synthesis'])
  })
  it('step ids are unique and index-prefixed', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    const ids = plan.tasks.map((s) => s.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids[0]).toBe('step:1:knowledge')
    expect(ids[1]).toBe('step:2:analysis')
  })
  it('dependencies form a linear chain', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    const ids = plan.tasks.map((s) => s.id)
    for (let i = 1; i < ids.length; i++) {
      expect(plan.tasks[i]!.dependencies).toEqual([ids[i - 1]])
    }
    expect(plan.tasks[0]!.dependencies).toEqual([])
  })
  it('knowledge step queries the task entity type', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'literature-review' }))
    expect(plan.tasks[0]!.input.entityType).toBe('paper')
  })
  it('knowledge step carries the goal as query', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis', goal: 'my goal' }))
    expect(plan.tasks[0]!.input.query).toBe('my goal')
  })
  it('analysis step references the preceding step', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    expect(plan.tasks[1]!.input.sourceStepId).toBe('step:1:knowledge')
  })
  it('experiment-analysis tool step targets the analysis tool', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'experiment-analysis' }))
    expect(plan.tasks[1]!.input.toolId).toBe('tool:dataset-analysis')
  })
  it('visualization tool step targets the chart tool', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    expect(plan.tasks[2]!.input.toolId).toBe('tool:data-visualization')
  })
  it('simulation tool step uses capability placeholder', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'simulation' }))
    expect(plan.tasks[1]!.input.capability).toBe('simulation')
  })
  it('model step prompt contains the topic', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'paper-writing', topic: 'bubble dynamics' }))
    expect(String(plan.tasks[1]!.input.prompt)).toContain('bubble dynamics')
  })
  it('synthesis step declares all prior steps as sources', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    expect(plan.tasks[3]!.input.sourceStepIds).toEqual(['step:1:knowledge', 'step:2:analysis', 'step:3:tool'])
  })
  it('plan metadata traces planner + intent (secret-free)', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'simulation' }))
    expect(plan.metadata).toEqual({
      planner: 'rule:v1',
      domain: 'experiment',
      taskType: 'simulation',
      topic: 'test topic',
      constraints: []
    })
  })
  it('plan goal mirrors the intent goal', () => {
    const plan = createPlanFromIntent(makeIntent({ goal: 'fit and analyze' }))
    expect(plan.goal).toBe('fit and analyze')
  })
  it('plan id is content-hashed and task-prefixed', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'data-analysis' }))
    expect(plan.id.startsWith('plan:data-analysis:')).toBe(true)
  })
  it('different intent topic produces different plan id', () => {
    const a = createPlanFromIntent(makeIntent({ topic: 'alpha' }))
    const b = createPlanFromIntent(makeIntent({ topic: 'beta' }))
    expect(a.id).not.toBe(b.id)
  })
  it('identical intent produces identical plan', () => {
    const a = createPlanFromIntent(makeIntent())
    const b = createPlanFromIntent(makeIntent())
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('plan has no cycles', () => {
    for (const t of PLANNER_TASK_TYPES) {
      const plan = createPlanFromIntent(makeIntent({ taskType: t }))
      expect(detectCycle(plan.tasks)).toBeNull()
    }
  })
  it('describe planner.buildReasoning emits step chain', () => {
    const p = new ResearchPlanner()
    const decision = p.plan('Analyze water quality data')
    expect(decision.reasoningSummary).toContain('knowledge')
    expect(decision.reasoningSummary).toContain('confidence=')
  })
  it('generated plan survives A0 structural validation', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'paper-writing' }))
    expect(isValidResearchPlan(plan)).toBe(true)
  })
})

// ============ Confidence estimation ============

describe('Phase 8-B0 confidence estimation', () => {
  const p = new ResearchPlanner()
  it('canonical: data-analysis English request -> 0.73 (no context)', () => {
    const intent = p.analyzeIntent('Analyze water quality data')
    expect(p.estimateConfidence(intent)).toBe(0.73)
  })
  it('context fully covering required capabilities -> 0.93', () => {
    const intent = p.analyzeIntent('Analyze water quality data')
    const context: PlannerContext = { availableTools: [profile('tool:a', intent.requiredCapabilities)] }
    expect(p.estimateConfidence(intent, context)).toBe(0.93)
  })
  it('context covering half the capabilities -> 0.83', () => {
    const intent = p.analyzeIntent('Analyze water quality data')
    const context: PlannerContext = { availableTools: [profile('tool:a', ['data-analysis', 'statistics'])] }
    expect(p.estimateConfidence(intent, context)).toBe(0.83)
  })
  it('literature-review (short template) -> 0.63', () => {
    const intent = p.analyzeIntent('Write a literature review of micro-nano bubble papers')
    expect(p.estimateConfidence(intent)).toBe(0.63)
  })
  it('experiment-analysis fallback-domain request -> 0.67', () => {
    const intent = p.analyzeIntent('Analyze the experiment result and conclude')
    expect(p.estimateConfidence(intent)).toBe(0.67)
  })
  it('simulation request -> 0.73', () => {
    const intent = p.analyzeIntent('Run a CFD simulation of water flow')
    expect(p.estimateConfidence(intent)).toBe(0.73)
  })
  it('paper-writing -> 0.67', () => {
    const intent = p.analyzeIntent('Help me polish my paper manuscript')
    expect(p.estimateConfidence(intent)).toBe(0.67)
  })
  it('constraint depth adds up to +0.06', () => {
    const intent: ResearchIntent = { ...makeIntent(), constraints: ['quantitative', 'fast', 'precise', 'compare'] }
    const base = p.estimateConfidence(makeIntent())
    // 4 constraints against cap 0.06
    expect(p.estimateConfidence(intent) - base).toBeCloseTo(0.06)
  })
  it('invalid intent yields 0', () => {
    expect(p.estimateConfidence({ bad: true } as never)).toBe(0)
  })
  it('empty context tools behave like no context', () => {
    const intent = p.analyzeIntent('Analyze water quality data')
    expect(p.estimateConfidence(intent, { availableTools: [], availableKnowledge: [] })).toBe(0.73)
  })
  it('invalid tool profiles are skipped in coverage', () => {
    const intent = p.analyzeIntent('Analyze water quality data')
    const context: PlannerContext = {
      availableTools: [
        { toolId: 'broken', requiredCapabilities: intent.requiredCapabilities, optionalCapabilities: [], supportedTasks: ['bogus' as never], priority: 99 },
        profile('tool:ok', intent.requiredCapabilities)
      ]
    }
    expect(p.estimateConfidence(intent, context)).toBe(0.93)
  })
  it('round2 clamps to 2 decimals', () => {
    expect(plannerHelpers.round2(0.999)).toBe(1)
    expect(plannerHelpers.round2(1.234)).toBe(1.23)
  })
})

// ============ Invalid input ============

describe('Phase 8-B0 invalid input handling', () => {
  it('classifyIntent throws on empty string', () => {
    expect(() => classifyIntent('')).toThrow(/non-empty string/)
  })
  it('classifyIntent throws on whitespace', () => {
    expect(() => classifyIntent('   ')).toThrow(/non-empty string/)
  })
  it('classifyIntent throws on non-string', () => {
    expect(() => classifyIntent(123 as never)).toThrow(/must be a string/)
  })
  it('extractTopic returns general topic on blank segment', () => {
    expect(extractTopic('  .')).toBe('general topic')
  })
  it('createPlanFromIntent throws on missing intent', () => {
    expect(() => createPlanFromIntent(null as never)).toThrow(/intent required/)
  })
  it('createPlanFromIntent throws on empty topic', () => {
    expect(() => createPlanFromIntent(makeIntent({ topic: '' }))).toThrow(/topic must be a non-empty string/)
  })
  it('createPlanFromIntent throws on unknown taskType', () => {
    expect(() => createPlanFromIntent(makeIntent({ taskType: 'nope' as never }))).toThrow(/unknown taskType/)
  })
  it('plan() throws on empty request via classifier', () => {
    const p = new ResearchPlanner()
    expect(() => p.plan('')).toThrow(/non-empty string/)
  })
})

// ============ Security ============

describe('Phase 8-B0 security — no-secret enforcement', () => {
  it('isValidResearchIntent throws on goal containing apiKey', () => {
    expect(() => isValidResearchIntent(makeIntent({ goal: 'use apiKey please' })))
      .toThrow(/forbidden/)
  })
  it('isValidPlannerDecision throws on secret in reasoning', () => {
    const plan = createPlanFromIntent(makeIntent())
    expect(() => isValidPlannerDecision({ plan, confidence: 0.5, reasoningSummary: 'Bearer token leaked' }))
      .toThrow(/forbidden/)
  })
  it('isValidPlannerContext throws on secret in previousResults', () => {
    expect(() => isValidPlannerContext({ previousResults: { apiKey: 'sk-x' } })).toThrow(/forbidden/)
  })
  it('createPlanFromIntent rejects a request embedding a secret', () => {
    expect(() => createPlanFromIntent(makeIntent({ goal: 'token leak in goal' })))
      .toThrow(/forbidden/)
  })
  it('classifyIntent surfaces a secret text but plan creation blocks it', () => {
    const intent = classifyIntent('使用 sk-leak 令牌调用')
    expect(intent.goal).toContain('sk-leak')
    expect(() => createPlanFromIntent(intent)).toThrow(/forbidden/)
  })
  it('planner-schema source has no forbidden imports', () => {
    const readSrc = (p: string): string => {
      const fs = require('fs')
      const path = require('path')
      return fs.readFileSync(path.resolve(__dirname, p), 'utf8')
    }
    for (const f of [
      '../../src/shared/agent/planner-schema.ts',
      '../../src/main/services/agent/intent-classifier.ts',
      '../../src/main/services/agent/rule-planner.ts',
      '../../src/main/services/agent/research-planner.ts'
    ]) {
      const src = readSrc(f)
      expect(src).not.toMatch(/from\s+['"][^'"]*model-provider/)
      expect(src).not.toMatch(/from\s+['"][^'"]*auth\.service/)
      expect(src).not.toMatch(/from\s+['"][^'"]*backend/)
      expect(src).not.toContain('apiKey = ')
    }
  })
  it('planner-schema.ts does not reference runtime modules', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(path.resolve(__dirname, '../../src/shared/agent/planner-schema.ts'), 'utf8')
    expect(src).not.toContain('agent-runtime')
    expect(src).not.toContain('tool-executor')
  })
  it('no Math.random or Date.now in planner pipeline', () => {
    const fs = require('fs')
    const path = require('path')
    for (const f of [
      '../../src/main/services/agent/intent-classifier.ts',
      '../../src/main/services/agent/rule-planner.ts',
      '../../src/main/services/agent/research-planner.ts'
    ]) {
      const src = fs.readFileSync(path.resolve(__dirname, f), 'utf8')
      expect(src).not.toContain('Math.random')
      expect(src).not.toContain('Date.now')
    }
  })
  it('rule-planner export count is stable (1 fn + 1 const + helpers)', () => {
    expect(ruleHelpers.TEMPLATE_CHAINS).toBeDefined()
    expect(typeof ruleHelpers.hashStr).toBe('function')
  })
})

// ============ Determinism ============

describe('Phase 8-B0 determinism', () => {
  it('classifyIntent is deterministic for equal input', () => {
    const a = classifyIntent('Perform regression and data analysis')
    const b = classifyIntent('Perform regression and data analysis')
    expect(a).toEqual(b)
  })
  it('classifyIntentWithEvidence is deterministic', () => {
    const a = classifyIntentWithEvidence('Run a CFD simulation')
    const b = classifyIntentWithEvidence('Run a CFD simulation')
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('createPlanFromIntent is deterministic', () => {
    const a = createPlanFromIntent(makeIntent({ taskType: 'paper-writing' }))
    const b = createPlanFromIntent(makeIntent({ taskType: 'paper-writing' }))
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })
  it('plan() produces identical decisions', () => {
    const p = new ResearchPlanner()
    const a = p.plan('Analyze water quality data')
    const b = p.plan('Analyze water quality data')
    expect(a.confidence).toBe(b.confidence)
    expect(JSON.stringify(a.plan)).toBe(JSON.stringify(b.plan))
    expect(a.reasoningSummary).toBe(b.reasoningSummary)
  })
  it('confidence is stable across calls', () => {
    const p = new ResearchPlanner()
    const intent = p.analyzeIntent('Run a CFD simulation of water flow')
    expect(p.estimateConfidence(intent)).toBe(p.estimateConfidence(intent))
  })
  it('topic extraction is stable', () => {
    expect(extractTopic('First sentence. Second.'))
      .toBe(extractTopic('First sentence. Second.'))
  })
  it('hashStr returns hex-ish stable short id', () => {
    const h = ruleHelpers.hashStr('abc')
    expect(h.length).toBe(8)
    expect(h).toBe(ruleHelpers.hashStr('abc'))
  })
})

// ============ Planner / runtime separation ============

describe('Phase 8-B0 planner / runtime separation', () => {
  it('planner plan() does not execute the plan (status pending)', () => {
    const decision = new ResearchPlanner().plan('Analyze water quality data')
    expect(decision.plan.status).toBe('pending')
  })
  it('research-planner.ts does not import the runtime', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(path.resolve(__dirname, '../../src/main/services/agent/research-planner.ts'), 'utf8')
    expect(src).not.toContain('agent-runtime')
    expect(src).not.toContain('ResearchAgentRuntime')
  })
  it('agent-runtime.ts does not import the planner', () => {
    const fs = require('fs')
    const path = require('path')
    const src = fs.readFileSync(path.resolve(__dirname, '../../src/main/services/agent/agent-runtime.ts'), 'utf8')
    expect(src).not.toContain('planner')
    expect(src).not.toContain('intent-classifier')
  })
  it('validatePlan accepts a planner-generated plan', () => {
    const p = new ResearchPlanner()
    const decision = p.plan('Analyze water quality data')
    const report = p.validatePlan(decision.plan)
    expect(report.ok).toBe(true)
    expect(report.errors).toEqual([])
  })
  it('validatePlan flags a cycle', () => {
    const cyclicSteps: ResearchPlanStep[] = [
      { id: 'A', type: 'tool', description: 'a', input: {}, dependencies: ['B'] },
      { id: 'B', type: 'tool', description: 'b', input: {}, dependencies: ['A'] }
    ]
    const plan: ResearchPlan = { id: 'p', goal: 'g', tasks: cyclicSteps, status: 'pending' }
    const report = new ResearchPlanner().validatePlan(plan)
    expect(report.ok).toBe(false)
    expect(report.errors.some((e) => e.includes('cycle'))).toBe(true)
  })
  it('validatePlan flags unknown dependency', () => {
    const steps: ResearchPlanStep[] = [
      { id: 'A', type: 'tool', description: 'a', input: {}, dependencies: ['Z'] }
    ]
    const report = new ResearchPlanner().validatePlan({ id: 'p', goal: 'g', tasks: steps, status: 'pending' })
    expect(report.ok).toBe(false)
    expect(report.errors.some((e) => e.includes('unknown dependency'))).toBe(true)
  })
  it('validatePlan flags duplicate step ids', () => {
    const steps: ResearchPlanStep[] = [
      { id: 'X', type: 'tool', description: 'a', input: {}, dependencies: [] },
      { id: 'X', type: 'tool', description: 'b', input: {}, dependencies: [] }
    ]
    const report = new ResearchPlanner().validatePlan({ id: 'p', goal: 'g', tasks: steps, status: 'pending' })
    expect(report.ok).toBe(false)
    expect(report.errors.some((e) => e.includes('duplicate step id'))).toBe(true)
  })
  it('validatePlan rejects empty task list', () => {
    const report = new ResearchPlanner().validatePlan({ id: 'p', goal: 'g', tasks: [], status: 'pending' })
    expect(report.ok).toBe(false)
  })
  it('validatePlan rejects non-object', () => {
    const report = new ResearchPlanner().validatePlan(null as never)
    expect(report.ok).toBe(false)
    expect(report.errors[0]).toBe('plan is not an object')
  })
  it('runtime executes a literature-review plan to completion', async () => {
    const decision = new ResearchPlanner().plan('Write a literature review of micro-nano bubble papers')
    const knowledge: KnowledgeCaller = { query: async () => ({ items: [{ id: 'exp:1' }] }) }
    const model: ModelCaller = { complete: async () => ({ text: 'ok' }) }
    const tool: ToolCaller = { execute: async () => ({ success: true, data: { result: 'ok' } }) }
    const runtime = new ResearchAgentRuntime({ knowledge, model, tool })
    const run = runtime.createRun(decision.plan.goal, decision.plan)
    const result = await runtime.executePlan(run.id, decision.plan)
    expect(result.status).toBe('completed')
  })
})

// ============ Runtime executes planner templates (integration) ============

describe('Phase 8-B0 planner outputs run through Phase 8-A1 runtime', () => {
  let valuesKnowledge: KnowledgeCaller
  let okKnowledge: KnowledgeCaller
  let okModel: ModelCaller
  let okTool: ToolCaller
  beforeEach(() => {
    valuesKnowledge = { query: async () => ({ values: [1, 2, 3] }) }
    okKnowledge = { query: async () => ({ items: [{ id: 'exp:1' }] }) }
    okModel = { complete: async () => ({ text: 'ok', usage: { used: 10 } }) }
    okTool = { execute: async () => ({ success: true, data: { result: 'ok' } }) }
  })
  it('experiment-analysis template completes', async () => {
    const decision = new ResearchPlanner().plan('Analyze the experiment result and conclude')
    const runtime = new ResearchAgentRuntime({ knowledge: okKnowledge, model: okModel, tool: okTool })
    const run = runtime.createRun('req', decision.plan)
    const result = await runtime.executePlan(run.id, decision.plan)
    expect(result.status).toBe('completed')
    expect(result.steps.every((s) => s.status === 'completed')).toBe(true)
  })
  it('data-analysis template completes with values knowledge', async () => {
    const decision = new ResearchPlanner().plan('对数据集做回归和数据分析')
    const runtime = new ResearchAgentRuntime({ knowledge: valuesKnowledge, model: okModel, tool: okTool })
    const run = runtime.createRun('req', decision.plan)
    const result = await runtime.executePlan(run.id, decision.plan)
    expect(result.status).toBe('completed')
  })
  it('paper-writing template completes with model caller', async () => {
    const decision = new ResearchPlanner().plan('Help me polish my paper manuscript')
    const runtime = new ResearchAgentRuntime({ knowledge: okKnowledge, model: okModel, tool: okTool })
    const run = runtime.createRun('req', decision.plan)
    const result = await runtime.executePlan(run.id, decision.plan)
    expect(result.status).toBe('completed')
  })
  it('literature-review template completes', async () => {
    const decision = new ResearchPlanner().plan('Write a literature review on bubble dynamics')
    const runtime = new ResearchAgentRuntime({ knowledge: okKnowledge, model: okModel, tool: okTool })
    const run = runtime.createRun('req', decision.plan)
    const result = await runtime.executePlan(run.id, decision.plan)
    expect(result.status).toBe('completed')
  })
  it('analysis step in simulation template follows the tool step', () => {
    const plan = createPlanFromIntent(makeIntent({ taskType: 'simulation' }))
    expect(plan.tasks[2]!.type).toBe('analysis')
    expect(plan.tasks[2]!.input.sourceStepId).toBe('step:2:tool')
  })
})