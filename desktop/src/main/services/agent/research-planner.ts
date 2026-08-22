// Research Planner Service (Phase 8-B0: Research Intent Understanding + Planner Core).
//
// Phase 8-B0: assembly of the deterministic planner chain —
//
//   user request
//      -> IntentClassifier (ResearchIntent)
//      -> RulePlanner (ResearchPlan)
//      -> confidence + reasoning (PlannerDecision)
//      -> Phase 8-A1 runtime executes the plan  (separate module, NOT imported)
//
// Phase 8-B0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import model-provider / auth / chat / backend
//   - Decides WHAT; the runtime decides HOW (planner never executes)
//   - Deterministic: no LLM call, no RNG

import type {
  ResearchIntent,
  PlannerContext,
  PlannerDecision,
  IntentEvidence
} from '../../../shared/agent/planner-schema'
import { isValidResearchIntent } from '../../../shared/agent/planner-schema'
import type { ResearchPlan } from '../../../shared/agent/research-plan-schema'
import { isValidResearchPlan, detectCycle } from '../../../shared/agent/research-plan-schema'
import { classifyIntent, classifyIntentWithEvidence } from './intent-classifier'
import { createPlanFromIntent, TEMPLATE_CHAINS } from './rule-planner'
import { isValidToolCapabilityProfile } from '../../../shared/tools/tool-capability-schema'

export interface ValidationReport {
  ok: boolean
  errors: string[]
}

function round2(x: number): number {
  return Math.round(x * 100) / 100
}

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x
}

export class ResearchPlanner {
  // ============ Step 5 core API ============

  /** Phase 8-B0: user text -> ResearchIntent (deterministic classifier). */
  analyzeIntent(userText: string): ResearchIntent {
    return classifyIntent(userText)
  }

  /** Phase 8-B0: expose classifier evidence (domain/task scores + matches). */
  analyzeIntentWithEvidence(userText: string): IntentEvidence {
    return classifyIntentWithEvidence(userText)
  }

  /** Phase 8-B0: ResearchIntent -> ResearchPlan (rule templates). */
  createPlan(intent: ResearchIntent): ResearchPlan {
    return createPlanFromIntent(intent)
  }

  /**
   * Phase 8-B0: validate a plan BEFORE handing it to the runtime.
   * Checks structural validity + no cycles + resolvable internal deps.
   */
  validatePlan(plan: ResearchPlan): ValidationReport {
    const errors: string[] = []
    if (!plan || typeof plan !== 'object') {
      return { ok: false, errors: ['plan is not an object'] }
    }
    if (!isValidResearchPlan(plan)) {
      errors.push('plan failed Phase 8-A0 structural validation')
    }
    if (!Array.isArray(plan.tasks) || plan.tasks.length === 0) {
      errors.push('plan has no tasks')
      return { ok: false, errors }
    }
    const cyc = detectCycle(plan.tasks)
    if (cyc) errors.push(`cycle detected: ${cyc.join(' -> ')}`)
    const ids = new Set(plan.tasks.map((t) => t.id))
    const seen = new Set<string>()
    for (const t of plan.tasks) {
      if (seen.has(t.id)) errors.push(`duplicate step id '${t.id}'`)
      seen.add(t.id)
      for (const d of t.dependencies) {
        // Phase 8-B0 strict: planner-generated plans use internal refs only
        if (!ids.has(d)) errors.push(`step '${t.id}' references unknown dependency '${d}'`)
      }
    }
    return { ok: errors.length === 0, errors }
  }

  /**
   * Phase 8-B0: deterministic 0..1 confidence that the rule template fits.
   *
   * Components (all pure / clamped):
   *   base                     0.45
   *   template depth >=3       0.15  (else 0.05)
   *   non-fallback domain      0.08  (fallback 'experiment' domain 0.02)
   *   topic length >=8         0.05  (else 0.01)
   *   each matched constraint  0.02  (cap 0.06)
   *   capability coverage vs context.availableTools   cov * 0.20  (if context given)
   */
  estimateConfidence(intent: ResearchIntent, context?: PlannerContext): number {
    if (!isValidResearchIntent(intent)) return 0
    let c = 0.45
    const chain = TEMPLATE_CHAINS[intent.taskType]
    c += chain.length >= 3 ? 0.15 : 0.05
    c += intent.domain === 'experiment' ? 0.02 : 0.08
    c += intent.topic.length >= 8 ? 0.05 : 0.01
    c += Math.min(0.06, intent.constraints.length * 0.02)

    const tools = context?.availableTools
    if (tools && tools.length > 0) {
      const have = new Set<string>()
      for (const t of tools) {
        if (!isValidToolCapabilityProfile(t)) continue
        for (const cap of t.requiredCapabilities) have.add(cap)
      }
      const need = intent.requiredCapabilities
      if (need.length > 0) {
        const covered = need.filter((cap) => have.has(cap)).length
        c += round2((covered / need.length) * 0.2)
      }
    }
    return round2(clamp01(c))
  }

  // ============ Convenience (full pipeline) ============

  /**
   * Phase 8-B0: user text -> PlannerDecision (plan + confidence + reasoning).
   * Validates before returning; throws on structural failure.
   */
  plan(userText: string, context?: PlannerContext): PlannerDecision {
    const evidence = classifyIntentWithEvidence(userText)
    const intent = evidence.intent
    const plan = createPlanFromIntent(intent)
    const report = this.validatePlan(plan)
    if (!report.ok) {
      throw new Error(`research planner: invalid plan generated: ${report.errors.join('; ')} (Phase 8-B0 strict)`)
    }
    const confidence = this.estimateConfidence(intent, context)
    const reasoningSummary = this.buildReasoning(evidence, plan, confidence, context)
    return { plan, confidence, reasoningSummary }
  }

  /** Phase 8-B0: secret-free reasoning trace for the decision. */
  buildReasoning(
    evidence: IntentEvidence,
    plan: ResearchPlan,
    confidence: number,
    _context?: PlannerContext
  ): string {
    const chain = plan.tasks.map((t) => t.type).join(' -> ')
    const parts = [
      `domain=${evidence.intent.domain}(${evidence.domainScore})`,
      `task=${evidence.intent.taskType}(${evidence.taskMatched.join(',') || 'fallback'})`,
      `template=${chain}`,
      `steps=${plan.tasks.length}`,
      `confidence=${confidence}`
    ]
    return parts.join('; ')
  }
}

export const __testHelpers = {
  round2,
  clamp01,
  buildReasoning: (p: ResearchPlanner, e: IntentEvidence, plan: ResearchPlan, c: number): string =>
    p.buildReasoning(e, plan, c)
}