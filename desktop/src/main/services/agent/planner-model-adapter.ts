// Planner Model Adapter (Phase 8-B1: Hybrid LLM Planner).
//
// Phase 8-B1: the ONLY seam where the planner may talk to an LLM.
// It wraps an injected Phase 8-A1 ModelCaller (never a model-provider
// implementation), builds a deterministic prompt, and parses the model
// text back into a validated ResearchPlan.
//
// Phase 8-B1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - NO direct model-provider import, NO SDK call, NO API-key access
//   - generatePlan only PRODUCES a plan — it never executes tools/knowledge

import type { LLMPlannerRequest, LLMPlannerResponse } from '../../../shared/agent/llm-planner-schema'
import { isValidLLMPlannerRequest } from '../../../shared/agent/llm-planner-schema'
import type { ResearchPlan, ResearchPlanStep, StepType } from '../../../shared/agent/research-plan-schema'
import { STEP_TYPES, detectCycle, isValidResearchPlan } from '../../../shared/agent/research-plan-schema'
import type { ModelCaller } from '../../../shared/agent/agent-runtime-schema'
import { hashStr } from './rule-planner'

// ============ Contract ============

export interface PlannerModelAdapter {
  generatePlan(request: LLMPlannerRequest): Promise<LLMPlannerResponse>
}

// ============ Prompt construction (deterministic) ============

export const DEFAULT_SYSTEM_PROMPT =
  'You are a research planning assistant. Produce only a JSON plan object.'

/**
 * Phase 8-B1: deterministic prompt text for a request. Secret-free by
 * construction (tool/knowledge lists only, never credentials).
 */
export function buildModelPrompt(request: LLMPlannerRequest, systemPrompt: string = DEFAULT_SYSTEM_PROMPT): string {
  const a = request.intent
  const tools = (request.availableTools ?? request.context?.availableTools ?? [])
    .map((t) => t.toolId)
    .sort()
  const caps = Array.from(new Set(
    (request.availableTools ?? request.context?.availableTools ?? []).flatMap((t) => t.requiredCapabilities)
  )).sort()
  const knowledge = (request.availableKnowledge ?? request.context?.availableKnowledge ?? [])
    .slice()
    .sort()

  const intent = JSON.stringify({
    topic: a.topic,
    goal: a.goal,
    domain: a.domain,
    taskType: a.taskType,
    constraints: a.constraints,
    requiredCapabilities: a.requiredCapabilities
  })

  return [
    systemPrompt,
    '---',
    `RESEARCH REQUEST: ${a.goal}`,
    `INTENT: ${intent}`,
    `AVAILABLE TOOLS: ${tools.length > 0 ? tools.join(', ') : '(none)'}`,
    `AVAILABLE CAPABILITIES: ${caps.length > 0 ? caps.join(', ') : '(none)'}`,
    `AVAILABLE KNOWLEDGE ENTITY TYPES: ${knowledge.length > 0 ? knowledge.join(', ') : '(none)'}`,
    'Respond ONLY with a JSON object of the shape',
    '{"plan":{"id":"...","goal":"...","tasks":[{"id":"step:N:type","type":"knowledge|tool|model|analysis|synthesis","description":"...","input":{},"dependencies":["..."]}]},"confidence":0.7,"explanation":"..."}',
    'Use step ids referenced by other steps\' dependencies. Include a final synthesis step.'
  ].join('\n')
}

// ============ Response parsing (tolerant, deterministic) ============

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}

function round2(x: number): number {
  return Math.round(x * 100) / 100
}

function extractJson(text: string): unknown {
  const start = text.indexOf('{')
  const end = text.lastIndexOf('}')
  if (start === -1 || end === -1 || end <= start) {
    throw new Error('no JSON object found in model output')
  }
  return JSON.parse(text.slice(start, end + 1))
}

export interface ParsedPlan {
  plan?: ResearchPlan
  repairs: number
  error?: string
}

/**
 * Phase 8-B1: normalize an arbitrary model object into a valid ResearchPlan.
 * Pure + deterministic. Repairs count structural fixes (surfaced to tests).
 */
export function normalizeParsedPlan(raw: unknown, fallbackGoal: string): ParsedPlan {
  try {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
      return { repairs: 0, error: 'model output is not an object' }
    }
    const o = raw as Record<string, unknown>
    const body = (o.plan && typeof o.plan === 'object' && !Array.isArray(o.plan))
      ? o.plan as Record<string, unknown>
      : o
    let repairs = 0

    let id: string
    if (typeof body.id === 'string' && body.id.length > 0) {
      id = body.id
    } else {
      repairs++
      id = `plan:llm:${hashStr(`${String(body.goal ?? fallbackGoal)}${JSON.stringify(body.tasks ?? [])}`)}`
    }

    let goal = typeof body.goal === 'string' && body.goal.length > 0
      ? body.goal
      : ''
    if (goal.length === 0) {
      repairs++
      goal = fallbackGoal
    }

    const rawTasks = Array.isArray(body.tasks) ? body.tasks : []
    if (!Array.isArray(body.tasks)) repairs++

    const tasks: ResearchPlanStep[] = []
    const seenIds = new Set<string>()
    rawTasks.forEach((t: unknown, idx: number) => {
      if (!t || typeof t !== 'object') {
        repairs++
        return
      }
      const to = t as Record<string, unknown>
      const type = to.type
      if (typeof type !== 'string' || !STEP_TYPES.includes(type as StepType)) {
        repairs++
        return
      }
      let tid = typeof to.id === 'string' && to.id.length > 0 ? to.id : `step:${idx + 1}:${String(type)}`
      if (tid.length === 0) repairs++
      if (seenIds.has(tid)) {
        tid = `${tid}:${idx + 1}`
        repairs++
      }
      seenIds.add(tid)

      let description = typeof to.description === 'string' && to.description.length > 0 ? to.description : ''
      if (description.length === 0) {
        repairs++
        description = `Step ${idx + 1} (${String(type)})`
      }

      const input = (to.input && typeof to.input === 'object' && !Array.isArray(to.input))
        ? to.input as Record<string, unknown>
        : {}

      const depsRaw = Array.isArray(to.dependencies) ? to.dependencies : []
      if (!Array.isArray(to.dependencies)) repairs++
      const deps = depsRaw.filter((d: unknown): d is string => typeof d === 'string' && d !== tid)

      tasks.push({ id: tid, type: type as StepType, description, input, dependencies: deps })
    })

    // Drop dependency refs to unknown / external step ids (deterministic).
    const known = new Set(tasks.map((s) => s.id))
    let depRepairs = 0
    for (const s of tasks) {
      const kept = s.dependencies.filter((d) => known.has(d))
      if (kept.length !== s.dependencies.length) depRepairs++
      s.dependencies = kept
    }
    if (depRepairs > 0) repairs++

    const plan: ResearchPlan = {
      id,
      goal,
      tasks,
      status: 'pending',
      metadata: { planner: 'llm:v1' }
    }

    if (plan.tasks.length === 0) return { repairs, error: 'plan has no steps' }
    const cycle = detectCycle(plan.tasks)
    if (cycle) return { repairs, error: `cycle detected: ${cycle.join(' -> ')}` }
    if (!isValidResearchPlan(plan)) return { repairs, error: 'plan failed Phase 8-A0 validation' }
    return { plan, repairs }
  } catch (e) {
    return { repairs: 0, error: e instanceof Error ? e.message : 'unknown parse error' }
  }
}

/**
 * Phase 8-B1: deterministic model-assisted confidence for a parsed plan.
 * Uses the model-provided value when present (clamped); falls back to a
 * structural default that degrades when repairs were needed.
 */
export function computeLlmConfidence(raw: unknown, repairs: number): number {
  const o = (raw && typeof raw === 'object') ? raw as Record<string, unknown> : {}
  if (repairs > 0) return round2(Math.min(0.6, clamp01(typeof o.confidence === 'number' ? o.confidence : 0.6)))
  const provided = typeof o.confidence === 'number' ? o.confidence : 0.85
  return round2(clamp01(provided))
}

/**
 * Phase 8-B1: parse model text into a validated LLMPlannerResponse, or null.
 * Pure + deterministic for a given text + request.
 */
export function parseModelResponse(text: string, request: LLMPlannerRequest): LLMPlannerResponse | null {
  let raw: unknown
  try {
    raw = extractJson(text)
  } catch {
    return null
  }
  const parsed = normalizeParsedPlan(raw, request.intent.goal)
  if (!parsed.plan || parsed.error) return null
  return {
    plan: parsed.plan,
    confidence: computeLlmConfidence(raw, parsed.repairs),
    explanation: `llm plan parsed: ${parsed.plan.tasks.length} steps; repairs=${parsed.repairs}`
  }
}

// ============ Adapter implementations ============

/**
 * Phase 8-B1: ModelCaller-backed planner adapter.
 * No model-provider import, no SDK call — only the injected ModelCaller.
 */
export class ModelCallerPlannerAdapter implements PlannerModelAdapter {
  private readonly model: ModelCaller
  private readonly systemPrompt: string
  private readonly maxTokens: number

  constructor(options: { model: ModelCaller; systemPrompt?: string; maxTokens?: number }) {
    if (!options?.model) {
      throw new Error('planner model adapter: model caller required (Phase 8-B1 strict)')
    }
    this.model = options.model
    this.systemPrompt = options.systemPrompt ?? DEFAULT_SYSTEM_PROMPT
    this.maxTokens = options.maxTokens ?? 2048
  }

  buildPrompt(request: LLMPlannerRequest): string {
    return buildModelPrompt(request, this.systemPrompt)
  }

  async generatePlan(request: LLMPlannerRequest): Promise<LLMPlannerResponse> {
    if (!isValidLLMPlannerRequest(request)) {
      throw new Error('planner model adapter: invalid LLMPlannerRequest (Phase 8-B1 strict)')
    }
    const prompt = buildModelPrompt(request, this.systemPrompt)
    const r = await this.model.complete(prompt, { maxTokens: this.maxTokens })
    const text = typeof r.text === 'string' ? r.text : ''
    const resp = parseModelResponse(text, request)
    if (!resp) {
      throw new Error('planner model adapter: model output could not be parsed into a valid plan (Phase 8-B1 strict)')
    }
    return resp
  }
}

export const __testHelpers = {
  buildModelPrompt,
  normalizeParsedPlan,
  computeLlmConfidence,
  parseModelResponse,
  extractJson,
  DEFAULT_SYSTEM_PROMPT,
  clamp01,
  round2
}