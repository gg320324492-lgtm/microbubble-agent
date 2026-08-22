// LLM Planner Schema Contracts (Phase 8-B1: Hybrid LLM Planner).
//
// Phase 8-B1: typed contracts for the optional LLM planning path.
// Distinct from:
//   - Phase 8-B0 planner-schema (ResearchIntent / PlannerContext / PlannerDecision)
//   - Phase 8-A0 research-plan-schema (plan output)
//   - Phase 8-A1 agent-runtime-schema (ModelCaller runtime interface)
//   - Phase 7-T3 ToolCapabilityProfile (tool metadata)
//
// Phase 8-B1 frozen contract:
//   - PlannerMode (rule-only / hybrid / llm-only)
//   - LLMPlannerRequest (intent / context / availableTools / availableKnowledge)
//   - LLMPlannerResponse (plan / confidence / explanation)
//   - Validators + assertNoSecret guard
//
// Phase 8-B1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - The LLM planner only extends PLAN creation; it never executes tools and
//     never queries knowledge directly
//   - Independence from Model Provider / Auth / Chat / Backend

import { isValidResearchIntent, isValidPlannerContext, type ResearchIntent, type PlannerContext } from './planner-schema'
import { isValidResearchPlan, type ResearchPlan } from './research-plan-schema'
import { isValidToolCapabilityProfile, type ToolCapabilityProfile } from '../tools/tool-capability-schema'

// ============ Planner strategy mode ============

export type PlannerMode = 'rule-only' | 'hybrid' | 'llm-only'

export const PLANNER_MODES: readonly PlannerMode[] = Object.freeze([
  'rule-only', 'hybrid', 'llm-only'
])

// ============ LLM planner request ============

/**
 * Phase 8-B1: everything the LLM planner needs to produce a plan.
 *
 * `context` carries optional provenance; `availableTools` / `availableKnowledge`
 * are the reconciled lists the model is allowed to reference (never executed here).
 */
export interface LLMPlannerRequest {
  intent: ResearchIntent
  context?: PlannerContext
  availableTools?: ToolCapabilityProfile[]
  availableKnowledge?: string[]
}

// ============ LLM planner response ============

/**
 * Phase 8-B1: what the model-adapter returns.
 *
 * `plan` MUST already be a valid Phase 8-A0 ResearchPlan (the adapter validates
 * before returning). `confidence` is the model-assisted 0..1 estimate.
 */
export interface LLMPlannerResponse {
  plan: ResearchPlan
  confidence: number
  explanation: string
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`llm planner leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-B1 strict)`)
    }
  }
}

const VALID_MODES: ReadonlySet<PlannerMode> = new Set(PLANNER_MODES)

export function isValidPlannerMode(m: unknown): m is PlannerMode {
  return typeof m === 'string' && VALID_MODES.has(m as PlannerMode)
}

export function isValidLLMPlannerRequest(r: unknown): r is LLMPlannerRequest {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (!isValidResearchIntent(o.intent)) return false
  if (o.context !== undefined && !isValidPlannerContext(o.context)) return false
  if (o.availableKnowledge !== undefined
      && (!Array.isArray(o.availableKnowledge) || !o.availableKnowledge.every((x) => typeof x === 'string'))) return false
  if (o.availableTools !== undefined
      && (!Array.isArray(o.availableTools) || !o.availableTools.every((t) => isValidToolCapabilityProfile(t)))) return false
  assertNoSecret(r, 'LLMPlannerRequest')
  return true
}

export function isValidLLMPlannerResponse(r: unknown): r is LLMPlannerResponse {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (!isValidResearchPlan(o.plan as ResearchPlan)) return false
  if (typeof o.confidence !== 'number' || o.confidence < 0 || o.confidence > 1) return false
  if (typeof o.explanation !== 'string' || o.explanation.length === 0) return false
  assertNoSecret(r, 'LLMPlannerResponse')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  PLANNER_MODES,
  VALID_MODES
}