// Hybrid Planner (Phase 8-B1: Hybrid LLM Planner).
//
// Phase 8-B1: upgrades the deterministic B0 planner with an optional LLM path.
//
//   user request
//      -> IntentClassifier (B0)
//      -> rule baseline plan (ResearchPlanner, B0)      [always computed]
//      -> LLM planner (PlannerModelAdapter)             [when mode allows]
//      -> accept LLM plan ONLY IF:
//            validatePlan ok (structure + no cycle + resolvable deps)
//            (hybrid) llm confidence > rule confidence
//            capability satisfied for context
//      -> else fallback to the rule plan
//      -> Phase 8-A1 runtime executes  (separate module, NOT imported)
//
// Modes (default 'hybrid'): rule-only | hybrid | llm-only.
//
// Phase 8-B1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - The LLM planner only extends PLAN creation; it never executes tools and
//     never queries knowledge directly
//   - Does NOT import model-provider / auth / chat / backend / runtime

import type { PlannerDecision, ResearchIntent, PlannerContext } from '../../../shared/agent/planner-schema'
import type { PlannerMode, LLMPlannerResponse } from '../../../shared/agent/llm-planner-schema'
import { isValidPlannerMode } from '../../../shared/agent/llm-planner-schema'
import type { ResearchPlan } from '../../../shared/agent/research-plan-schema'
import { ResearchPlanner } from './research-planner'
import type { PlannerModelAdapter } from './planner-model-adapter'

export type PlannerWinner = 'rule' | 'llm'

export interface HybridDecisionResult {
  decision: PlannerDecision
  winner: PlannerWinner
  reason: string
  ruleConfidence: number
}

export class HybridPlanner {
  private readonly rule: ResearchPlanner
  private readonly adapter?: PlannerModelAdapter
  private mode: PlannerMode

  constructor(options: { mode?: PlannerMode; adapter?: PlannerModelAdapter } = {}) {
    const m = options?.mode ?? 'hybrid'
    if (!isValidPlannerMode(m)) {
      throw new Error(`hybrid planner: invalid mode '${String(m)}' (Phase 8-B1 strict)`)
    }
    this.mode = m
    this.adapter = options?.adapter
    this.rule = new ResearchPlanner()
  }

  getMode(): PlannerMode {
    return this.mode
  }

  /** Phase 8-B1: switch strategy at runtime (validates the value). */
  setMode(mode: PlannerMode): void {
    if (!isValidPlannerMode(mode)) {
      throw new Error(`hybrid planner: invalid mode '${String(mode)}' (Phase 8-B1 strict)`)
    }
    this.mode = mode
  }

  hasAdapter(): boolean {
    return this.adapter !== undefined
  }

  // ============ Full pipeline ============

  /**
   * Phase 8-B1: user text -> HybridDecisionResult (winner-aware).
   * `mode` overrides the constructor default for this call.
   */
  async plan(userText: string, context?: PlannerContext, mode?: PlannerMode): Promise<HybridDecisionResult> {
    const intent = this.rule.analyzeIntent(userText)
    return this.planFromIntent(intent, context, mode)
  }

  async planFromIntent(
    intent: ResearchIntent,
    context?: PlannerContext,
    mode?: PlannerMode
  ): Promise<HybridDecisionResult> {
    const m = mode ?? this.mode
    if (!isValidPlannerMode(m)) {
      throw new Error(`hybrid planner: invalid mode '${String(m)}' (Phase 8-B1 strict)`)
    }

    // Always compute the deterministic rule baseline first.
    const rulePlan = this.rule.createPlan(intent)
    const ruleConfidence = this.rule.estimateConfidence(intent, context)

    if (m === 'rule-only') {
      return this.finish('rule', rulePlan, ruleConfidence, 'rule-only', m, ruleConfidence)
    }

    if (m === 'llm-only' && !this.adapter) {
      throw new Error('hybrid planner: llm-only mode requires an adapter (Phase 8-B1 strict)')
    }

    if (!this.adapter) {
      // hybrid without an adapter: nothing to improve with.
      return this.finish('rule', rulePlan, ruleConfidence, 'no-adapter', m, ruleConfidence)
    }

    // Ask the LLM planner (adapter). Any throw degrades to the rule baseline.
    let llm: LLMPlannerResponse | undefined
    let reason = 'llm-error'
    try {
      const request = {
        intent,
        context,
        availableTools: context?.availableTools,
        availableKnowledge: context?.availableKnowledge
      }
      llm = await this.adapter.generatePlan(request)
    } catch {
      llm = undefined
    }

    if (llm) {
      const report = this.rule.validatePlan(llm.plan)
      if (!report.ok) {
        reason = 'llm-invalid'
      } else if (m === 'hybrid' && llm.confidence <= ruleConfidence) {
        reason = 'llm-lower-confidence'
      } else if (!this.capabilitySatisfied(llm.plan, context)) {
        reason = 'llm-capability-mismatch'
      } else {
        return this.finish('llm', llm.plan, llm.confidence, 'llm-accepted', m, ruleConfidence)
      }
    }

    return this.finish('rule', rulePlan, ruleConfidence, reason, m, ruleConfidence)
  }

  // ============ Validation + capability gate ============

  validateLLMPlan(plan: ResearchPlan): { ok: boolean; errors: string[] } {
    return this.rule.validatePlan(plan)
  }

  /**
   * Phase 8-B1: deterministic check that every resource step in `plan` is
   * satisfiable from `context`. When context lists are absent, passes
   * (nothing to verify against).
   */
  capabilitySatisfied(plan: ResearchPlan, context?: PlannerContext): boolean {
    const tools = context?.availableTools
    const knowledge = context?.availableKnowledge
    if (!tools && !knowledge) return true
    const toolIds = new Set((tools ?? []).map((t) => t.toolId))
    const caps = new Set<string>()
    for (const t of tools ?? []) {
      for (const c of t.requiredCapabilities) caps.add(c)
    }
    for (const step of plan.tasks) {
      if (step.type === 'tool') {
        const toolId = step.input.toolId
        const capability = step.input.capability
        if (typeof toolId === 'string') {
          if (tools && !toolIds.has(toolId) && !caps.has(toolId)) return false
        } else if (typeof capability === 'string') {
          if (tools && !caps.has(capability) && !toolIds.has(capability)) return false
        }
      } else if (step.type === 'knowledge') {
        const entityType = step.input.entityType
        if (typeof entityType === 'string' && knowledge && !knowledge.includes(entityType)) return false
      }
    }
    return true
  }

  // ============ Decision assembly ============

  private finish(
    winner: PlannerWinner,
    plan: ResearchPlan,
    confidence: number,
    reason: string,
    mode: PlannerMode,
    ruleConfidence: number
  ): HybridDecisionResult {
    // Trace the strategy on the plan metadata (secret-free).
    plan.metadata = { ...(plan.metadata ?? {}), plannerStrategy: winner }
    const reasoningSummary = [
      `mode=${mode}`,
      `winner=${winner}`,
      `confidence=${confidence}`,
      `reason=${reason}`,
      `steps=${plan.tasks.length}`,
      `template=${plan.tasks.map((t) => t.type).join(' -> ')}`
    ].join('; ')
    const decision: PlannerDecision = { plan, confidence, reasoningSummary }
    return { decision, winner, reason, ruleConfidence }
  }
}

export const __testHelpers = {}