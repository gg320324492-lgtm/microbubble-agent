// Research Agent Orchestrator (Phase 8-E0).
//
// Phase 8-E0: thin orchestration layer that composes the existing subsystems
//   - Phase 8-B0 ResearchPlanner
//   - Phase 8-A1 ResearchAgentRuntime
//   - Phase 8-C3 ResearchContextProvider
//   - Phase 8-D0 ResearchModelProvider
//   - Phase 7-T5 ToolExecutor
// into a single ResearchAgent.run(request) -> ResearchAgentResponse.
//
// Pipeline:
//   ResearchAgentRequest
//     -> planner.plan(question)                              [B0]
//     -> runtime.createRun + runtime.executePlan(plan)        [A1]
//        (runtime internally dispatches to contextProvider / toolExecutor / modelProvider)
//     -> aggregate into ResearchAgentResponse
//
// Phase 8-E0 strict:
//   - NEVER contains apiKey / secret / token value / cipher
//   - Does NOT modify Phase 8-B0 / 8-A1 / 8-C3 / 8-D0 contracts
//   - Does NOT import model-provider / auth / backend / SDKs

import type { PlannerDecision } from '../../../shared/agent/planner-schema'
import type { ResearchPlan, ResearchPlanStep } from '../../../shared/agent/research-plan-schema'
import type { AgentRun } from '../../../shared/agent/agent-runtime-schema'
import { isValidResearchPlan } from '../../../shared/agent/research-plan-schema'
import type { CitationReference } from '../../../shared/knowledge/document-schema'
import type { ModelResponse } from '../../../shared/agent/model-gateway-schema'
import type { RAGContext } from '../../../shared/knowledge/context-schema'
import type {
  ResearchAgentRequest,
  ResearchAgentResponse,
  AgentRunStatus,
  AgentEvent,
  AgentEventType,
  ToolResultSummary,
  AgentUsage
} from '../../../shared/agent/research-agent-schema'
import {
  isValidResearchAgentRequest,
  isValidResearchAgentResponse,
  isValidAgentRunStatus
} from '../../../shared/agent/research-agent-schema'

// ============ Dependency shapes (structural) ============

/** Phase 8-E0: minimum surface from Phase 8-B0 ResearchPlanner. */
export interface PlannerLike {
  plan(text: string): PlannerDecision
}

/** Phase 8-E0: minimum surface from Phase 8-A1 ResearchAgentRuntime. */
export interface RuntimeLike {
  createRun(userRequest: string, plan: ResearchPlan): AgentRun
  executePlan(runId: string, plan: ResearchPlan): Promise<AgentRun>
  cancelRun(runId: string): { ok: boolean; reason?: string }
  onEvent(listener: (event: { type: string; runId: string; timestamp: number; payload?: Record<string, unknown> }) => void): () => void
}

/** Phase 8-E0: minimum surface from Phase 8-C3 ResearchContextProvider. */
export interface ContextProviderLike {
  provideAnswer(ragContext: RAGContext, options?: unknown): Promise<ModelResponse>
}

/** Phase 8-E0: minimum surface from Phase 8-D0 ResearchModelProvider. */
export interface ModelProviderLike {
  provideAnswer(ragContext: RAGContext, options?: unknown): Promise<ModelResponse>
}

/** Phase 8-E0: minimum surface from Phase 7-T5 ToolExecutor. */
export interface ToolExecutorLike {
  execute(request: unknown, options?: unknown): Promise<unknown>
}

export interface ResearchAgentDependencies {
  planner: PlannerLike
  runtime: RuntimeLike
  contextProvider: ContextProviderLike
  modelProvider: ModelProviderLike
  toolExecutor: ToolExecutorLike
}

// ============ Event emitter ============

export type AgentEventListener = (event: AgentEvent) => void

export class AgentEventEmitter {
  private readonly listeners = new Set<AgentEventListener>()

  emit(event: AgentEvent): void {
    for (const l of this.listeners) {
      try {
        l(event)
      } catch {
        // Listener errors must not break other listeners or the orchestrator.
      }
    }
  }

  subscribe(listener: AgentEventListener): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  size(): number { return this.listeners.size }
}

// ============ Helpers ============

function emptyUsage(): AgentUsage {
  return { promptTokens: 0, completionTokens: 0, totalTokens: 0, promptCalls: 0, toolCalls: 0 }
}

function isToolStep(step: ResearchPlanStep): boolean {
  return step.type === 'tool'
}
function isModelStep(step: ResearchPlanStep): boolean {
  return step.type === 'model'
}
function isKnowledgeStep(step: ResearchPlanStep): boolean {
  return step.type === 'knowledge'
}

function pickAnswer(run: AgentRun): string {
  const result = (run.result ?? {}) as Record<string, unknown>
  if (typeof result.text === 'string') return result.text
  if (typeof result.answer === 'string') return result.answer
  if (typeof result.content === 'string') return result.content
  // Fallback: last synthesis step output text.
  const last = [...run.steps].reverse().find((s) => s.status === 'completed')
  if (last && last.output && typeof last.output === 'object') {
    const o = last.output as Record<string, unknown>
    if (typeof o.text === 'string') return o.text
    if (typeof o.answer === 'string') return o.answer
  }
  return ''
}

function pickCitations(run: AgentRun): CitationReference[] {
  const seen = new Set<string>()
  const out: CitationReference[] = []
  for (const s of run.steps) {
    const out2 = s.output as Record<string, unknown> | undefined
    const cites = (out2?.citations ?? out2?.citation) as unknown
    if (Array.isArray(cites)) {
      for (const c of cites as Array<Record<string, unknown>>) {
        if (!c || typeof c !== 'object') continue
        const cc = c as unknown as CitationReference & { confidence?: number; page?: number }
        if (typeof cc.documentId !== 'string' || typeof cc.chunkId !== 'string' || typeof cc.confidence !== 'number') continue
        const k = `${cc.documentId}::${cc.chunkId}::${cc.page ?? ''}`
        if (seen.has(k)) continue
        seen.add(k)
        out.push(cc)
      }
    }
  }
  return out
}

function pickToolResults(run: AgentRun, plan: ResearchPlan): ToolResultSummary[] {
  const map = new Map<string, ResearchPlanStep>()
  for (const t of plan.tasks) map.set(t.id, t)
  const out: ToolResultSummary[] = []
  for (const s of run.steps) {
    const planStep = map.get(s.stepId)
    if (!planStep || !isToolStep(planStep)) continue
    const cs = (s.output ?? {}) as Record<string, unknown>
    out.push({
      stepId: s.stepId,
      ...(typeof cs.toolId === 'string' ? { toolId: cs.toolId } : {}),
      result: 'result' in cs ? cs.result : cs
    })
  }
  return out
}

function pickUsage(run: AgentRun, plan: ResearchPlan): AgentUsage {
  const u = emptyUsage()
  for (const s of run.steps) {
    const cs = (s.output ?? {}) as Record<string, unknown>
    const usage = cs.usage as Record<string, unknown> | undefined
    if (!usage) continue
    if (typeof usage.promptTokens === 'number') u.promptTokens += usage.promptTokens
    if (typeof usage.completionTokens === 'number') u.completionTokens += usage.completionTokens
    if (typeof usage.totalTokens === 'number') u.totalTokens += usage.totalTokens
    const planStep = plan.tasks.find((t: ResearchPlanStep) => t.id === s.stepId)
    if (planStep?.type === 'model') u.promptCalls += 1
    if (planStep?.type === 'tool') u.toolCalls += 1
  }
  return u
}

// ============ ResearchAgent ============

export class ResearchAgent {
  private readonly planner: PlannerLike
  private readonly runtime: RuntimeLike
  // The three providers are accepted in DI for forward-compat hooks (status checks,
  // future direct-call paths). The orchestrator does not call them today — the
  // runtime still owns step dispatch. Stored so they can be inspected via
  // `getForwardingProviders()` for diagnostics + tests.
  private readonly _contextProvider: ContextProviderLike
  private readonly _modelProvider: ModelProviderLike
  private readonly _toolExecutor: ToolExecutorLike
  private readonly emitter: AgentEventEmitter
  private readonly cancelled: Set<string> = new Set()
  private readonly currentStatus: Map<string, AgentRunStatus> = new Map()

  constructor(deps: ResearchAgentDependencies) {
    if (!deps?.planner) {
      throw new Error('research agent: planner required (Phase 8-E0 strict)')
    }
    if (!deps?.runtime) {
      throw new Error('research agent: runtime required (Phase 8-E0 strict)')
    }
    if (!deps?.contextProvider) {
      throw new Error('research agent: contextProvider required (Phase 8-E0 strict)')
    }
    if (!deps?.modelProvider) {
      throw new Error('research agent: modelProvider required (Phase 8-E0 strict)')
    }
    if (!deps?.toolExecutor) {
      throw new Error('research agent: toolExecutor required (Phase 8-E0 strict)')
    }
    this.planner = deps.planner
    this.runtime = deps.runtime
    this._contextProvider = deps.contextProvider
    this._modelProvider = deps.modelProvider
    this._toolExecutor = deps.toolExecutor
    this.emitter = new AgentEventEmitter()
  }

  // ============ Event subscription ============

  onEvent(listener: AgentEventListener): () => void {
    return this.emitter.subscribe(listener)
  }

  getEventEmitter(): AgentEventEmitter { return this.emitter }

  /** Phase 8-E0: read-only view of the three forwarding providers for diagnostics + tests. */
  getForwardingProviders(): {
    contextProvider: ContextProviderLike
    modelProvider: ModelProviderLike
    toolExecutor: ToolExecutorLike
  } {
    return {
      contextProvider: this._contextProvider,
      modelProvider: this._modelProvider,
      toolExecutor: this._toolExecutor
    }
  }

  // ============ Cancellation ============

  cancelRun(requestId: string): { ok: boolean; reason?: string } {
    // Always set the intent flag — even when the id is unknown to the orchestrator,
    // a follow-up run() may see it.
    this.cancelled.add(requestId)
    const status = this.currentStatus.get(requestId)
    const runtimeResult = this.runtime.cancelRun(requestId)
    if (status === undefined) {
      return { ok: false, reason: 'unknown requestId' }
    }
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      // Already terminal — cancellation is a no-op success.
      return { ok: true, reason: `already ${status}` }
    }
    this.setStatus(requestId, 'cancelled')
    this.emitEvent('agent_failed', requestId, { reason: 'cancelled' })
    return runtimeResult
  }

  // ============ Pipeline ============

  async run(req: ResearchAgentRequest): Promise<ResearchAgentResponse> {
    if (!isValidResearchAgentRequest(req)) {
      throw new Error('research agent: invalid ResearchAgentRequest (Phase 8-E0 strict)')
    }
    const requestId = req.requestId
    // NOTE: cancellation flag is NOT cleared here — it persists across the run
    // so cancellation requested BEFORE run() takes effect. The flag is cleared
    // when the run reaches a terminal state.
    this.setStatus(requestId, 'pending')
    const startedAt = Date.now()
    this.emitEvent('agent_started', requestId, { question: req.question })

    let decision: PlannerDecision | undefined
    try {
      this.setStatus(requestId, 'planning')
      decision = this.planner.plan(req.question)
      if (decision && isValidResearchPlan(decision.plan)) {
        this.emitEvent('plan_created', requestId, { plan: decision.plan })
      } else {
        this.emitEvent('agent_failed', requestId, { reason: 'invalid plan from planner' })
        throw new Error('research agent: planner produced invalid plan (Phase 8-E0 strict)')
      }
      if (this.cancelled.has(requestId)) {
        return this.buildCancelledResponse(req, decision, startedAt)
      }

      this.setStatus(requestId, 'executing')
      const runtimeRun = this.runtime.createRun(req.question, decision.plan)
      const run = await this.runtime.executePlan(runtimeRun.id, decision.plan)

      if (this.cancelled.has(requestId)) {
        return this.buildCancelledResponse(req, decision, startedAt, run)
      }

      this.setStatus(requestId, 'generating')
      const response = this.buildResponse(req, run, decision, startedAt)
      this.setStatus(requestId, 'completed')
      this.emitEvent('agent_completed', requestId, { response })
      return response
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      this.emitEvent('agent_failed', requestId, { error: message })
      this.setStatus(requestId, 'failed')
      throw e
    }
  }

  // ============ Internals ============

  private setStatus(requestId: string, status: AgentRunStatus): void {
    if (!isValidAgentRunStatus(status)) return
    this.currentStatus.set(requestId, status)
  }

  getStatus(requestId: string): AgentRunStatus | undefined {
    return this.currentStatus.get(requestId)
  }

  private emitEvent(type: AgentEventType, requestId: string, payload?: Record<string, unknown>): void {
    this.emitter.emit({
      type,
      requestId,
      timestamp: Date.now(),
      ...(payload !== undefined ? { payload } : {})
    })
  }

  private buildResponse(
    req: ResearchAgentRequest,
    run: AgentRun,
    decision: PlannerDecision,
    startedAt: number
  ): ResearchAgentResponse {
    const citations = pickCitations(run)
    const toolResults = pickToolResults(run, decision.plan)
    const usage = pickUsage(run, decision.plan)
    const confidence = typeof decision.confidence === 'number'
      ? Math.max(0, Math.min(1, decision.confidence))
      : 0
    void startedAt
    const response: ResearchAgentResponse = {
      requestId: req.requestId,
      answer: pickAnswer(run),
      citations,
      toolResults,
      usage,
      confidence,
      ...(decision.plan !== undefined ? { plan: decision.plan } : {})
    }
    if (!isValidResearchAgentResponse(response)) {
      throw new Error('research agent: produced invalid ResearchAgentResponse (Phase 8-E0 strict)')
    }
    return response
  }

  private buildCancelledResponse(
    req: ResearchAgentRequest,
    decision: PlannerDecision | undefined,
    startedAt: number,
    run?: AgentRun
  ): ResearchAgentResponse {
    const usage = run ? pickUsage(run, decision?.plan ?? { id: 'cancelled', goal: '', tasks: [], status: 'pending' }) : emptyUsage()
    const citations = run ? pickCitations(run) : []
    const toolResults = run && decision ? pickToolResults(run, decision.plan) : []
    const response: ResearchAgentResponse = {
      requestId: req.requestId,
      answer: '',
      citations,
      toolResults,
      usage,
      confidence: 0,
      ...(decision?.plan !== undefined ? { plan: decision.plan } : {})
    }
    void startedAt
    return response
  }
}

export const __testHelpers = {
  pickAnswer,
  pickCitations,
  pickToolResults,
  pickUsage,
  emptyUsage,
  isToolStep,
  isModelStep,
  isKnowledgeStep
}