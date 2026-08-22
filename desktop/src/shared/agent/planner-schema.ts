// Planner Schema Contracts (Phase 8-B0: Research Intent Understanding + Planner Core).
//
// Phase 8-B0: typed contracts for the deterministic Planner layer.
// Distinct from:
//   - Phase 8-A0 ResearchPlan / ResearchPlanStep (plan output contract)
//   - Phase 8-A1 AgentRun / AgentStepExecution (runtime state contract)
//   - Phase 7-A0 Knowledge Schema (entities)
//   - Phase 7-T3 ToolCapabilityProfile (tool metadata)
//
// Phase 8-B0 frozen contract:
//   - ResearchDomain (5 domains)
//   - PlannerTaskType (5 task types)
//   - ResearchIntent (topic / goal / domain / taskType / constraints /
//     requiredCapabilities)
//   - PlannerContext (previousResults / availableTools / availableKnowledge)
//   - PlannerDecision (plan / confidence / reasoningSummary)
//   - Validators (isValid* + assertNoSecret guard)
//
// Phase 8-B0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Planner is INDEPENDENT from Model Provider / Auth / Chat / Backend
//   - Planner decides WHAT; the Phase 8-A1 Runtime executes HOW
//   - Deterministic only: NO LLM call, NO RNG in the Planner path

import { isValidResearchPlan, type ResearchPlan } from './research-plan-schema'
import type { ToolCapabilityProfile } from '../tools/tool-capability-schema'

// ============ Domains / Task types ============

/**
 * Phase 8-B0: a research subject domain (used by the intent classifier).
 * 'experiment' is the lab-wide fallback domain.
 */
export type ResearchDomain =
  | 'environment'
  | 'chemistry'
  | 'communication'
  | 'control'
  | 'experiment'

export const RESEARCH_DOMAINS: readonly ResearchDomain[] = Object.freeze([
  'environment', 'chemistry', 'communication', 'control', 'experiment'
])

/**
 * Phase 8-B0: what the user is asking the research agent to do.
 *
 * Each task type maps to a deterministic plan template (rule-planner.ts).
 */
export type PlannerTaskType =
  | 'literature-review'
  | 'experiment-analysis'
  | 'data-analysis'
  | 'simulation'
  | 'paper-writing'

export const PLANNER_TASK_TYPES: readonly PlannerTaskType[] = Object.freeze([
  'literature-review', 'experiment-analysis', 'data-analysis', 'simulation', 'paper-writing'
])

// ============ ResearchIntent ============

/**
 * Phase 8-B0: the classifier output — what the user wants.
 *
 * Fields:
 *   - topic:            deterministic short subject (first sentence of the request)
 *   - goal:             the normalized full user request
 *   - domain:           research subject domain (5-value enum)
 *   - taskType:         detected request kind (5-value enum)
 *   - constraints:      matched deterministic constraint tags (quantitative / recent / ...)
 *   - requiredCapabilities: capabilities the plan template needs (tool-task aligned)
 */
export interface ResearchIntent {
  topic: string
  goal: string
  domain: ResearchDomain
  taskType: PlannerTaskType
  constraints: string[]
  requiredCapabilities: string[]
}

// ============ PlannerContext ============

/**
 * Phase 8-B0: additional (optional) context the planner may consult.
 *
 * VOLUNTARY — the Phase 8-B0 planner produces deterministic plans from the
 * intent alone. Context refines confidence (capability coverage) and carries
 * provenance for future LLM-planner phases.
 */
export interface PlannerContext {
  /** Outputs from earlier steps of the same user request. */
  previousResults?: Record<string, unknown>
  /** Phase 7-T3 profiles of tools the agent can currently invoke. */
  availableTools?: ToolCapabilityProfile[]
  /** Knowledge entity types the agent can currently query. */
  availableKnowledge?: string[]
}

// ============ PlannerDecision ============

/**
 * Phase 8-B0: the full planner output handed to the Phase 8-A1 runtime.
 */
export interface PlannerDecision {
  plan: ResearchPlan
  /** Deterministic 0..1 estimate of how confidently the rule template fits. */
  confidence: number
  /** Human-readable, secret-free reasoning trace (safe to log / render). */
  reasoningSummary: string
}

/**
 * Phase 8-B0: classifier internals surfaced for confidence + traceability.
 */
export interface IntentEvidence {
  intent: ResearchIntent
  domain: ResearchDomain
  domainScore: number
  domainMatched: string[]
  task: PlannerTaskType
  taskScore: number
  taskMatched: string[]
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`planner leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-B0 strict)`)
    }
  }
}

const VALID_DOMAINS: ReadonlySet<ResearchDomain> = new Set(RESEARCH_DOMAINS)
const VALID_TASK_TYPES: ReadonlySet<PlannerTaskType> = new Set(PLANNER_TASK_TYPES)

export function isValidResearchDomain(d: unknown): d is ResearchDomain {
  return typeof d === 'string' && VALID_DOMAINS.has(d as ResearchDomain)
}

export function isValidPlannerTaskType(t: unknown): t is PlannerTaskType {
  return typeof t === 'string' && VALID_TASK_TYPES.has(t as PlannerTaskType)
}

function isStringArray(v: unknown): v is string[] {
  return Array.isArray(v) && v.every((x) => typeof x === 'string')
}

export function isValidResearchIntent(i: unknown): i is ResearchIntent {
  if (!i || typeof i !== 'object') return false
  const o = i as Record<string, unknown>
  if (typeof o.topic !== 'string' || o.topic.length === 0) return false
  if (typeof o.goal !== 'string' || o.goal.length === 0) return false
  if (!isValidResearchDomain(o.domain)) return false
  if (!isValidPlannerTaskType(o.taskType)) return false
  if (!isStringArray(o.constraints)) return false
  if (!isStringArray(o.requiredCapabilities)) return false
  assertNoSecret(i, 'ResearchIntent')
  return true
}

export function isValidPlannerContext(c: unknown): c is PlannerContext {
  if (!c || typeof c !== 'object') return false
  const o = c as Record<string, unknown>
  if (o.previousResults !== undefined
      && (typeof o.previousResults !== 'object' || o.previousResults === null || Array.isArray(o.previousResults))) return false
  if (o.availableKnowledge !== undefined && !isStringArray(o.availableKnowledge)) return false
  assertNoSecret(c, 'PlannerContext')
  return true
}

export function isValidPlannerDecision(d: unknown): d is PlannerDecision {
  if (!d || typeof d !== 'object') return false
  const o = d as Record<string, unknown>
  if (!o.plan || typeof o.plan !== 'object') return false
  if (!isValidResearchPlan(o.plan as ResearchPlan)) return false
  if (typeof o.confidence !== 'number' || o.confidence < 0 || o.confidence > 1) return false
  if (typeof o.reasoningSummary !== 'string' || o.reasoningSummary.length === 0) return false
  assertNoSecret(d, 'PlannerDecision')
  return true
}

export function isValidIntentEvidence(e: unknown): e is IntentEvidence {
  if (!e || typeof e !== 'object') return false
  const o = e as Record<string, unknown>
  if (!isValidResearchIntent(o.intent)) return false
  if (!isValidResearchDomain(o.domain)) return false
  if (typeof o.domainScore !== 'number' || typeof o.taskScore !== 'number') return false
  if (!isValidPlannerTaskType(o.task)) return false
  if (!isStringArray(o.domainMatched) || !isStringArray(o.taskMatched)) return false
  assertNoSecret(e, 'IntentEvidence')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  RESEARCH_DOMAINS,
  PLANNER_TASK_TYPES,
  VALID_DOMAINS,
  VALID_TASK_TYPES
}