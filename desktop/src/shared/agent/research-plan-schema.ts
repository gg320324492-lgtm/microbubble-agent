// Research Plan Schema Contracts (Phase 8-A0: Research Agent Planner).
//
// Phase 8-A0: typed contracts for the Research Planner layer.
// Distinct from:
//   - Phase 6 Model Runtime (Provider / Router / Chat)
//   - Phase 7-A0 Knowledge Schema (entities / metadata)
//   - Phase 7-T0 ToolDefinition / ToolResult
//   - Phase 7-T3 ToolCapabilityProfile
//   - Phase 7-T5-A ToolExecutor
//
// Phase 8-A0 frozen contract:
//   - ResearchPlan (goal + tasks + status + metadata)
//   - ResearchPlanStep (id + type + description + input + output + dependencies)
//   - StepType enum (knowledge / tool / model / analysis / synthesis)
//   - AgentActionStatus enum (pending / running / completed / failed / cancelled)
//   - AgentAction (stepId + status + result + error)
//
// Phase 8-A0 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Planner is INDEPENDENT from Model Provider / Auth / Chat / Backend
//   - Planner coordinates; it does NOT execute directly

// ============ Step types ============

/**
 * Phase 8-A0: what kind of step the planner emits.
 *
 *  - knowledge: query the Knowledge Layer (Phase 7-A0/7-B+)
 *  - tool:      invoke a Phase 7-T0 tool via the Tool Executor
 *  - model:     call the LLM via the Phase 6 Model Layer
 *  - analysis:  pure data manipulation (stats, transforms)
 *  - synthesis: combine multiple prior step outputs into a new output
 */
export type StepType = 'knowledge' | 'tool' | 'model' | 'analysis' | 'synthesis'

export const STEP_TYPES: readonly StepType[] = Object.freeze([
  'knowledge', 'tool', 'model', 'analysis', 'synthesis'
])

// ============ Plan status ============

export type ResearchPlanStatus =
  | 'pending'      // planner just produced the plan; no step started
  | 'running'      // at least one step is running
  | 'completed'    // all steps completed successfully
  | 'failed'       // at least one step failed terminally
  | 'cancelled'    // user / system cancelled before completion

export const RESEARCH_PLAN_STATUSES: readonly ResearchPlanStatus[] = Object.freeze([
  'pending', 'running', 'completed', 'failed', 'cancelled'
])

// ============ Plan / Step / Action shapes ============

/**
 * Phase 8-A0: a single step in a ResearchPlan.
 *
 * `input` is opaque to the planner — the executor that handles the step
 * validates and consumes it. `output` is filled when the step completes.
 *
 * `dependencies` lists step ids that must complete before this step starts.
 */
export interface ResearchPlanStep {
  id: string
  type: StepType
  description: string
  input: Record<string, unknown>
  output?: Record<string, unknown>
  dependencies: string[]
}

/**
 * Phase 8-A0: a plan produced by the planner.
 *
 * Phase 8-A0 strict: `metadata` is for tracing + debug only. NEVER includes
 * apiKey / token / secret / Authorization.
 */
export interface ResearchPlan {
  id: string
  goal: string
  tasks: ResearchPlanStep[]
  status: ResearchPlanStatus
  metadata?: Record<string, unknown>
}

// ============ Action state ============

export type AgentActionStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export const AGENT_ACTION_STATUSES: readonly AgentActionStatus[] = Object.freeze([
  'pending', 'running', 'completed', 'failed', 'cancelled'
])

export interface AgentError {
  code: string
  message: string
}

/**
 * Phase 8-A0: runtime state of a single step's execution.
 *
 * Populated by the executor as the step progresses. Phase 8-A0 ships ONLY
 * the shape — the runtime that fills this state is Phase 8-A+.
 */
export interface AgentAction {
  stepId: string
  status: AgentActionStatus
  result?: Record<string, unknown>
  error?: AgentError
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`research plan leak: '${ctx}' contains forbidden substring '${bad}' (Phase 8-A0 strict)`)
    }
  }
}

const VALID_STEP_TYPES: ReadonlySet<StepType> = new Set(STEP_TYPES)
const VALID_PLAN_STATUSES: ReadonlySet<ResearchPlanStatus> = new Set(RESEARCH_PLAN_STATUSES)
const VALID_ACTION_STATUSES: ReadonlySet<AgentActionStatus> = new Set(AGENT_ACTION_STATUSES)

export function isValidStepType(t: unknown): t is StepType {
  return typeof t === 'string' && VALID_STEP_TYPES.has(t as StepType)
}

export function isValidResearchPlanStatus(s: unknown): s is ResearchPlanStatus {
  return typeof s === 'string' && VALID_PLAN_STATUSES.has(s as ResearchPlanStatus)
}

export function isValidAgentActionStatus(s: unknown): s is AgentActionStatus {
  return typeof s === 'string' && VALID_ACTION_STATUSES.has(s as AgentActionStatus)
}

export function isValidResearchPlanStep(s: unknown): s is ResearchPlanStep {
  if (!s || typeof s !== 'object') return false
  const o = s as Record<string, unknown>
  if (typeof o.id !== 'string' || o.id.length === 0) return false
  if (!isValidStepType(o.type)) return false
  if (typeof o.description !== 'string' || o.description.length === 0) return false
  if (!o.input || typeof o.input !== 'object' || Array.isArray(o.input)) return false
  if (o.output !== undefined && (typeof o.output !== 'object' || o.output === null || Array.isArray(o.output))) return false
  if (!Array.isArray(o.dependencies)) return false
  if (!o.dependencies.every((d) => typeof d === 'string')) return false
  // Phase 8-A0 strict: dependency ids should not equal the step's own id
  if ((o.dependencies as string[]).includes(o.id as string)) return false
  assertNoSecret(s, 'ResearchPlanStep')
  return true
}

export function isValidResearchPlan(p: unknown): p is ResearchPlan {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (typeof o.id !== 'string' || o.id.length === 0) return false
  if (typeof o.goal !== 'string' || o.goal.length === 0) return false
  if (!Array.isArray(o.tasks)) return false
  for (const t of o.tasks) {
    if (!isValidResearchPlanStep(t)) return false
  }
  if (!isValidResearchPlanStatus(o.status)) return false
  if (o.metadata !== undefined && (typeof o.metadata !== 'object' || o.metadata === null || Array.isArray(o.metadata))) return false
  assertNoSecret(p, 'ResearchPlan')
  return true
}

export function isValidAgentAction(a: unknown): a is AgentAction {
  if (!a || typeof a !== 'object') return false
  const o = a as Record<string, unknown>
  if (typeof o.stepId !== 'string' || o.stepId.length === 0) return false
  if (!isValidAgentActionStatus(o.status)) return false
  if (o.result !== undefined && (typeof o.result !== 'object' || o.result === null)) return false
  if (o.error !== undefined) {
    const err = o.error as Record<string, unknown>
    if (typeof err.code !== 'string' || err.code.length === 0) return false
    if (typeof err.message !== 'string' || err.message.length === 0) return false
  }
  assertNoSecret(a, 'AgentAction')
  return true
}

/**
 * Phase 8-A0: detect cycles in the step dependency graph.
 * Returns the first cycle (array of step ids) if any, or null if acyclic.
 *
 * Uses Kahn's algorithm (BFS topological sort). O(V + E).
 */
export function detectCycle(steps: ResearchPlanStep[]): string[] | null {
  // Phase 8-A0 strict: only count dependencies that refer to steps
  // within this plan. External references are auto-satisfied (no indegree).
  const knownIds = new Set(steps.map((s) => s.id))
  const indegree = new Map<string, number>()
  const adj = new Map<string, string[]>()
  for (const s of steps) {
    indegree.set(s.id, 0)
    if (!adj.has(s.id)) adj.set(s.id, [])
  }
  for (const s of steps) {
    for (const dep of s.dependencies) {
      if (!knownIds.has(dep)) continue  // external dep — auto-satisfied
      indegree.set(s.id, (indegree.get(s.id) ?? 0) + 1)
      const arr = adj.get(dep) ?? []
      arr.push(s.id)
      adj.set(dep, arr)
    }
  }
  const queue: string[] = []
  for (const [id, deg] of indegree) if (deg === 0) queue.push(id)
  const visited: string[] = []
  while (queue.length > 0) {
    const id = queue.shift()!
    visited.push(id)
    for (const next of adj.get(id) ?? []) {
      const newDeg = (indegree.get(next) ?? 0) - 1
      indegree.set(next, newDeg)
      if (newDeg === 0) queue.push(next)
    }
  }
  if (visited.length !== indegree.size) {
    return Array.from(indegree.keys()).filter((id) => !visited.includes(id))
  }
  return null
}

export const __testHelpers = {
  FORBIDDEN,
  STEP_TYPES,
  RESEARCH_PLAN_STATUSES,
  AGENT_ACTION_STATUSES,
  VALID_STEP_TYPES,
  VALID_PLAN_STATUSES,
  VALID_ACTION_STATUSES
}
