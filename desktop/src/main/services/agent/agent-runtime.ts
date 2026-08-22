// Agent Runtime Core (Phase 8-A1: Research Agent Runtime).
//
// Phase 8-A1: in-process orchestrator that takes a ResearchPlan and
// executes its steps via injected interfaces (Knowledge / Tool / Model /
// Analysis / Synthesis). NO direct imports from model-provider, auth,
// chat-stream, or backend.
//
// Phase 8-A1 frozen contract:
//   - ResearchAgentRuntime class (6 public methods)
//   - InMemoryRunStore for run state (process-lifetime only)
//   - StepDispatcher routes StepType -> injected caller
//   - EventEmitter for RuntimeEvent traces
//
// Phase 8-A1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - All callers injected at construction time
//   - Deterministic run ordering (topological by dependency + creation order)
//   - Multiple concurrent runs supported (independent state)

import { EventEmitter } from 'node:events'

import {
  type RuntimeEvent,
  type RuntimeEventType,
  type AgentRun,
  type AgentStepExecution,
  type KnowledgeCaller,
  type ModelCaller,
  type ToolCaller
} from '../../../shared/agent/agent-runtime-schema'
import {
  type ResearchPlan,
  type ResearchPlanStep,
  isValidResearchPlan
} from '../../../shared/agent/research-plan-schema'

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`agent runtime leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-A1 strict)`)
    }
  }
}

/**
 * Phase 8-A1: topologically order steps by their dependencies.
 * Falls back to insertion order for ties (deterministic).
 *
 * Uses Kahn's algorithm (BFS). Returns null if a cycle is detected
 * (defensive — Phase 8-A0 validators should reject cycles upstream).
 */
export function topologicalOrder(steps: ResearchPlanStep[]): ResearchPlanStep[] | null {
  const knownIds = new Set(steps.map((s) => s.id))
  const indegree = new Map<string, number>()
  const adj = new Map<string, string[]>()
  for (const s of steps) {
    indegree.set(s.id, 0)
    adj.set(s.id, [])
  }
  for (const s of steps) {
    for (const dep of s.dependencies) {
      if (!knownIds.has(dep)) continue
      indegree.set(s.id, (indegree.get(s.id) ?? 0) + 1)
      const arr = adj.get(dep) ?? []
      arr.push(s.id)
      adj.set(dep, arr)
    }
  }
  const queue: string[] = []
  for (const [id, deg] of indegree) if (deg === 0) queue.push(id)
  const visited: ResearchPlanStep[] = []
  const id2step = new Map(steps.map((s) => [s.id, s] as const))
  while (queue.length > 0) {
    const id = queue.shift()!
    const step = id2step.get(id)
    if (step) visited.push(step)
    for (const next of adj.get(id) ?? []) {
      const newDeg = (indegree.get(next) ?? 0) - 1
      indegree.set(next, newDeg)
      if (newDeg === 0) queue.push(next)
    }
  }
  if (visited.length !== steps.length) return null
  return visited
}

export class ResearchAgentRuntime {
  private readonly runs: Map<string, AgentRun> = new Map()
  private readonly events: EventEmitter = new EventEmitter()
  private readonly knowledge: KnowledgeCaller
  private readonly model: ModelCaller
  private readonly tool: ToolCaller
  private readonly clock: () => number

  constructor(options: {
    knowledge: KnowledgeCaller
    model: ModelCaller
    tool: ToolCaller
    clock?: () => number
  }) {
    if (!options.knowledge) throw new Error('ResearchAgentRuntime: knowledge caller required (Phase 8-A1 strict)')
    if (!options.model) throw new Error('ResearchAgentRuntime: model caller required (Phase 8-A1 strict)')
    if (!options.tool) throw new Error('ResearchAgentRuntime: tool caller required (Phase 8-A1 strict)')
    this.knowledge = options.knowledge
    this.model = options.model
    this.tool = options.tool
    this.clock = options.clock ?? (() => Date.now())
  }

  // ============ Public API (Phase 8-A1) ============

  /**
   * Phase 8-A1: create a new run from a user request + plan.
   * Creates the AgentRun in 'pending' status. Does NOT execute yet.
   */
  createRun(userRequest: string, plan: ResearchPlan): AgentRun {
    if (typeof userRequest !== 'string') {
      throw new Error('ResearchAgentRuntime.createRun: userRequest must be a string (Phase 8-A1 strict)')
    }
    if (!isValidResearchPlan(plan)) {
      throw new Error('ResearchAgentRuntime.createRun: invalid ResearchPlan (Phase 8-A1 strict)')
    }
    const now = this.clock()
    const run: AgentRun = {
      id: `run:${now}:${Math.random().toString(36).slice(2, 8)}`,
      userRequest,
      planId: plan.id,
      status: 'pending',
      startedAt: null,
      completedAt: null,
      steps: plan.tasks.map((t) => ({
        stepId: t.id,
        status: 'pending',
        input: t.input,
        startedAt: null,
        completedAt: null
      }))
    }
    assertNoSecret(run, 'createRun')
    this.runs.set(run.id, run)
    this.emitEvent('plan_created', run.id, null, {
      userRequest,
      planId: plan.id,
      taskCount: plan.tasks.length
    })
    return run
  }

  /**
   * Phase 8-A1: execute a plan in topological order.
   * Updates each step's status as it progresses; emits events.
   * Resolves when the plan finishes (completed / failed / cancelled).
   */
  async executePlan(runId: string, plan: ResearchPlan): Promise<AgentRun> {
    if (!isValidResearchPlan(plan)) {
      throw new Error('ResearchAgentRuntime.executePlan: invalid ResearchPlan (Phase 8-A1 strict)')
    }
    const run = this.runs.get(runId)
    if (!run) {
      throw new Error(`ResearchAgentRuntime.executePlan: unknown runId '${runId}' (Phase 8-A1 strict)`)
    }
    run.status = 'running'
    run.startedAt = this.clock()
    const ordered = topologicalOrder(plan.tasks)
    if (!ordered) {
      run.status = 'failed'
      run.completedAt = this.clock()
      this.emitEvent('run_completed', run.id, null, { status: 'failed', reason: 'cycle detected' })
      return run
    }
    for (const step of ordered) {
      const stepExec = run.steps.find((s) => s.stepId === step.id)
      if (!stepExec) continue
      // Phase 8-A1 strict: TS widening — run.status may be cancelled at any point
      const runStatus: string = run.status
      if (runStatus === 'cancelled') {
        stepExec.status = 'cancelled'
        stepExec.completedAt = this.clock()
        continue
      }
      await this.executeStep(run, step, stepExec)
      if (stepExec.status === 'failed' || stepExec.status === 'cancelled') {
        run.status = stepExec.status === 'cancelled' ? 'cancelled' : 'failed'
        break
      }
    }
    // Final status if we didn't break out
    if (run.status === 'running') {
      const allOk = run.steps.every((s) => s.status === 'completed')
      run.status = allOk ? 'completed' : 'failed'
    }
    run.completedAt = this.clock()
    if (run.status === 'completed') {
      run.result = this.synthesize(plan, run)
    }
    this.emitEvent('run_completed', run.id, null, { status: run.status })
    return run
  }

  /**
   * Phase 8-A1: execute a single step using the appropriate dispatcher.
   * Updates the step's status and emits step_started / step_completed / step_failed.
   */
  async executeStep(run: AgentRun, step: ResearchPlanStep, exec: AgentStepExecution): Promise<void> {
    exec.status = 'running'
    exec.startedAt = this.clock()
    this.emitEvent('step_started', run.id, step.id, { type: step.type })
    try {
      const output = await this.dispatch(step, run)
      exec.output = output
      exec.status = 'completed'
      exec.completedAt = this.clock()
      this.emitEvent('step_completed', run.id, step.id, { output })
    } catch (e) {
      exec.error = {
        code: e instanceof Error && e.message ? 'EXECUTION_ERROR' : 'UNKNOWN',
        message: e instanceof Error ? e.message : String(e)
      }
      exec.status = 'failed'
      exec.completedAt = this.clock()
      this.emitEvent('step_failed', run.id, step.id, { error: exec.error })
    }
  }

  /**
   * Phase 8-A1: cancel a running (or pending) run.
   * Marks all pending + running steps as cancelled.
   */
  cancelRun(runId: string): { ok: boolean; reason?: string } {
    const run = this.runs.get(runId)
    if (!run) return { ok: false, reason: 'unknown runId' }
    if (run.status === 'completed' || run.status === 'failed' || run.status === 'cancelled') {
      return { ok: false, reason: 'already terminal' }
    }
    run.status = 'cancelled'
    run.completedAt = this.clock()
    for (const s of run.steps) {
      if (s.status === 'pending' || s.status === 'running') {
        s.status = 'cancelled'
        s.completedAt = this.clock()
      }
    }
    this.emitEvent('run_completed', run.id, null, { status: 'cancelled' })
    return { ok: true }
  }

  /**
   * Phase 8-A1: get a run by id.
   */
  getRun(runId: string): AgentRun | null {
    return this.runs.get(runId) ?? null
  }

  /**
   * Phase 8-A1: list all runs (sorted by startedAt ascending; pending first).
   */
  listRuns(): AgentRun[] {
    return Array.from(this.runs.values()).sort((a, b) => {
      const ax = a.startedAt ?? Number.MAX_SAFE_INTEGER
      const bx = b.startedAt ?? Number.MAX_SAFE_INTEGER
      return ax - bx
    })
  }

  // ============ Event subscription ============

  onEvent(type: RuntimeEventType, listener: (e: RuntimeEvent) => void): () => void {
    this.events.on(type, listener)
    return () => this.events.off(type, listener)
  }

  removeAllListeners(eventType?: RuntimeEventType): void {
    if (eventType) this.events.removeAllListeners(eventType)
    else this.events.removeAllListeners()
  }

  // ============ Step dispatcher (Phase 8-A1) ============

  /**
   * Phase 8-A1: dispatch a step to the appropriate caller based on its type.
   * Pure dispatch — no LLM SDK, no model-provider import.
   */
  private async dispatch(step: ResearchPlanStep, run: AgentRun): Promise<Record<string, unknown>> {
    switch (step.type) {
      case 'knowledge':
        return this.dispatchKnowledge(step, run)
      case 'tool':
        return this.dispatchTool(step)
      case 'model':
        return this.dispatchModel(step)
      case 'analysis':
        return this.dispatchAnalysis(step, run)
      case 'synthesis':
        return this.dispatchSynthesis(step, run)
      default:
        throw new Error(`ResearchAgentRuntime: unknown step type '${String((step as { type: string }).type)}'`)
    }
  }

  private async dispatchKnowledge(step: ResearchPlanStep, _run: AgentRun): Promise<Record<string, unknown>> {
    const input = step.input as { entityType?: string; filter?: Record<string, unknown> }
    return this.knowledge.query({
      entityType: input.entityType,
      filter: input.filter
    })
  }

  private async dispatchTool(step: ResearchPlanStep): Promise<Record<string, unknown>> {
    const result = await this.tool.execute(step.input)
    if (!result.success) {
      throw new Error(result.error?.message ?? 'tool execution failed')
    }
    return result.data ?? {}
  }

  private async dispatchModel(step: ResearchPlanStep): Promise<Record<string, unknown>> {
    const input = step.input as { prompt: string; options?: { maxTokens?: number; temperature?: number } }
    const r = await this.model.complete(input.prompt, input.options)
    return { text: r.text, usage: r.usage ?? {} }
  }

  /**
   * Phase 8-A1: pure-function analysis.
   * Computes basic numeric summary of preceding step outputs.
   */
  private dispatchAnalysis(step: ResearchPlanStep, run: AgentRun): Record<string, unknown> {
    const input = step.input as { sourceStepId?: string }
    const sourceId = input.sourceStepId
    if (!sourceId) {
      throw new Error('ResearchAgentRuntime.dispatchAnalysis: input.sourceStepId required')
    }
    const sourceExec = run.steps.find((s) => s.stepId === sourceId)
    const data = sourceExec?.output
    if (!data || typeof data !== 'object') {
      throw new Error(`ResearchAgentRuntime.dispatchAnalysis: source step '${sourceId}' has no output`)
    }
    const values = (data as { values?: unknown }).values
    if (!Array.isArray(values) || values.length === 0) {
      throw new Error('ResearchAgentRuntime.dispatchAnalysis: source step output.values must be non-empty array')
    }
    const nums = values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v))
    if (nums.length === 0) throw new Error('ResearchAgentRuntime.dispatchAnalysis: no numeric values')
    const sum = nums.reduce((a, b) => a + b, 0)
    return {
      source: sourceId,
      count: nums.length,
      mean: sum / nums.length,
      min: Math.min(...nums),
      max: Math.max(...nums)
    }
  }

  /**
   * Phase 8-A1: pure-function synthesis.
   * Assembles the final answer from preceding step outputs.
   */
  private dispatchSynthesis(step: ResearchPlanStep, run: AgentRun): Record<string, unknown> {
    const input = step.input as { sourceStepIds?: string[]; format?: string }
    const sourceIds = input.sourceStepIds ?? run.steps.map((s) => s.stepId)
    const sections: Record<string, unknown> = {}
    for (const id of sourceIds) {
      const exec = run.steps.find((s) => s.stepId === id)
      if (exec && exec.output) sections[id] = exec.output
    }
    return {
      format: input.format ?? 'summary',
      sections,
      userRequest: run.userRequest
    }
  }

  // ============ Event helpers ============

  private emitEvent(
    type: RuntimeEventType,
    runId: string,
    stepId: string | null,
    payload?: Record<string, unknown>
  ): void {
    const event: RuntimeEvent = {
      type,
      runId,
      stepId,
      timestamp: this.clock(),
      ...(payload !== undefined ? { payload } : {})
    }
    this.events.emit(type, event)
  }

  // ============ Test helpers (Phase 8-A1) ============

  /** Phase 8-A1: in-memory run store size (for testing). */
  __runStoreSize(): number {
    return this.runs.size
  }

  /** Phase 8-A1: clear all runs (testing). */
  __clearRuns(): void {
    this.runs.clear()
    this.events.removeAllListeners()
  }

  /** Phase 8-A1: synthesize the final result (exposed for testing). */
  private synthesize(plan: ResearchPlan, run: AgentRun): Record<string, unknown> {
    const synthesisStep = plan.tasks.find((t) => t.type === 'synthesis')
    if (synthesisStep) {
      return this.dispatchSynthesis(synthesisStep, run)
    }
    const sections: Record<string, unknown> = {}
    for (const s of run.steps) {
      if (s.output) sections[s.stepId] = s.output
    }
    return { format: 'auto-summary', sections, userRequest: run.userRequest }
  }
}

export const __testHelpers = {
  FORBIDDEN,
  topologicalOrder
}
