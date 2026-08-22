// Agent Runtime Schema Contracts (Phase 8-A1: Research Agent Runtime Core).
//
// Phase 8-A1: typed contracts for the Research Agent Runtime layer.
// Distinct from:
//   - Phase 8-A0 ResearchPlan / ResearchPlanStep (input contract)
//   - Phase 7-A0 Knowledge Schema (entities)
//   - Phase 7-T0 ToolDefinition / ToolResult
//   - Phase 7-T5-A ToolExecutionRecord / ToolExecutionRequest
//
// Phase 8-A1 frozen contract:
//   - AgentRun (id / userRequest / planId / status / startedAt /
//     completedAt / steps / result)
//   - AgentStepExecution (stepId / status / input / output / error /
//     startedAt / completedAt)
//   - RuntimeEvent (type / runId / stepId / timestamp / payload)
//   - RuntimeStatus / AgentStepStatus enums
//
// Phase 8-A1 strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Runtime orchestrator coordinates existing modules; does NOT replace
//     ToolExecutor / KnowledgeStorage / ModelRouter
//   - Runtime does NOT call LLM SDKs directly (Phase 8-A1 strict:
//     use injected ModelCaller interface)

// ============ Status enums ============

export type RuntimeStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export const RUNTIME_STATUSES: readonly RuntimeStatus[] = Object.freeze([
  'pending', 'running', 'completed', 'failed', 'cancelled'
])

export type AgentStepStatus =
  | 'pending'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'

export const AGENT_STEP_STATUSES: readonly AgentStepStatus[] = Object.freeze([
  'pending', 'running', 'completed', 'failed', 'cancelled'
])

// ============ AgentRun / AgentStepExecution ============

/**
 * Phase 8-A1: runtime state of a single step's execution within an AgentRun.
 *
 * Populated as the runtime dispatches the step to the appropriate executor
 * (knowledge / tool / model / analysis / synthesis).
 */
export interface AgentStepExecution {
  stepId: string
  status: AgentStepStatus
  input: Record<string, unknown>
  output?: Record<string, unknown>
  error?: { code: string; message: string }
  startedAt: number | null
  completedAt: number | null
}

/**
 * Phase 8-A1: runtime state of a ResearchPlan execution.
 *
 * Phase 8-A1 strict: `result` is the final assembled answer (synthesized
 * by the last step). `steps` is the per-step execution log.
 */
export interface AgentRun {
  id: string
  userRequest: string
  planId: string
  status: RuntimeStatus
  startedAt: number | null
  completedAt: number | null
  steps: AgentStepExecution[]
  result?: Record<string, unknown>
}

// ============ RuntimeEvent (Phase 8-A1) ============

export type RuntimeEventType =
  | 'plan_created'
  | 'step_started'
  | 'step_completed'
  | 'step_failed'
  | 'run_completed'

export const RUNTIME_EVENT_TYPES: readonly RuntimeEventType[] = Object.freeze([
  'plan_created', 'step_started', 'step_completed', 'step_failed', 'run_completed'
])

/**
 * Phase 8-A1: trace event emitted by the runtime.
 * Compatible with Phase 3-B0 StreamEvent shape (used by TraceTimeline).
 */
export interface RuntimeEvent {
  type: RuntimeEventType
  runId: string
  stepId: string | null
  timestamp: number
  payload?: Record<string, unknown>
}

// ============ Injected Interfaces (Phase 8-A1 strict) ============

/**
 * Phase 8-A1: injected Knowledge caller (no model-provider / no auth).
 * Phase 8+ populates with a Phase 7-A0/7-B+ Knowledge Provider binding.
 */
export interface KnowledgeCaller {
  query(input: { entityType?: string; filter?: Record<string, unknown> }): Promise<Record<string, unknown>>
}

/**
 * Phase 8-A1: injected Model caller (no LLM SDK, no provider import).
 * Phase 8+ populates with a Phase 6 Model Layer binding.
 */
export interface ModelCaller {
  complete(prompt: string, options?: { maxTokens?: number; temperature?: number }): Promise<{
    text: string
    usage?: Record<string, number>
  }>
}

/**
 * Phase 8-A1: injected Tool caller (no Phase 7-T5-A direct import).
 * Phase 8+ populates with a Phase 7-T5-A Tool Executor binding.
 */
export interface ToolCaller {
  execute(args: unknown): Promise<{ success: boolean; data?: Record<string, unknown>; error?: { code: string; message: string } }>
}

// ============ Validators (Phase 8-A1) ============

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

const VALID_STATUSES: ReadonlySet<RuntimeStatus> = new Set(RUNTIME_STATUSES)
const VALID_STEP_STATUSES: ReadonlySet<AgentStepStatus> = new Set(AGENT_STEP_STATUSES)
const VALID_EVENT_TYPES: ReadonlySet<RuntimeEventType> = new Set(RUNTIME_EVENT_TYPES)

export function isValidRuntimeStatus(s: unknown): s is RuntimeStatus {
  return typeof s === 'string' && VALID_STATUSES.has(s as RuntimeStatus)
}

export function isValidAgentStepStatus(s: unknown): s is AgentStepStatus {
  return typeof s === 'string' && VALID_STEP_STATUSES.has(s as AgentStepStatus)
}

export function isValidRuntimeEventType(t: unknown): t is RuntimeEventType {
  return typeof t === 'string' && VALID_EVENT_TYPES.has(t as RuntimeEventType)
}

export function isValidAgentStepExecution(s: unknown): s is AgentStepExecution {
  if (!s || typeof s !== 'object') return false
  const o = s as Record<string, unknown>
  if (typeof o.stepId !== 'string' || o.stepId.length === 0) return false
  if (!isValidAgentStepStatus(o.status)) return false
  if (!o.input || typeof o.input !== 'object' || Array.isArray(o.input)) return false
  if (o.output !== undefined && (typeof o.output !== 'object' || o.output === null || Array.isArray(o.output))) return false
  if (o.error !== undefined) {
    const err = o.error as Record<string, unknown>
    if (typeof err.code !== 'string' || err.code.length === 0) return false
    if (typeof err.message !== 'string' || err.message.length === 0) return false
  }
  if (o.startedAt !== null && (typeof o.startedAt !== 'number' || o.startedAt < 0)) return false
  if (o.completedAt !== null && (typeof o.completedAt !== 'number' || o.completedAt < 0)) return false
  assertNoSecret(s, 'AgentStepExecution')
  return true
}

export function isValidAgentRun(r: unknown): r is AgentRun {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (typeof o.id !== 'string' || o.id.length === 0) return false
  if (typeof o.userRequest !== 'string' || o.userRequest.length === 0) return false
  if (typeof o.planId !== 'string' || o.planId.length === 0) return false
  if (!isValidRuntimeStatus(o.status)) return false
  if (o.startedAt !== null && (typeof o.startedAt !== 'number' || o.startedAt < 0)) return false
  if (o.completedAt !== null && (typeof o.completedAt !== 'number' || o.completedAt < 0)) return false
  if (!Array.isArray(o.steps)) return false
  for (const step of o.steps) {
    if (!isValidAgentStepExecution(step)) return false
  }
  if (o.result !== undefined && (typeof o.result !== 'object' || o.result === null || Array.isArray(o.result))) return false
  assertNoSecret(r, 'AgentRun')
  return true
}

export function isValidRuntimeEvent(e: unknown): e is RuntimeEvent {
  if (!e || typeof e !== 'object') return false
  const o = e as Record<string, unknown>
  if (!isValidRuntimeEventType(o.type)) return false
  if (typeof o.runId !== 'string' || o.runId.length === 0) return false
  if (o.stepId !== null && typeof o.stepId !== 'string') return false
  if (typeof o.timestamp !== 'number' || o.timestamp < 0) return false
  if (o.payload !== undefined && (typeof o.payload !== 'object' || o.payload === null || Array.isArray(o.payload))) return false
  assertNoSecret(e, 'RuntimeEvent')
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  RUNTIME_STATUSES,
  AGENT_STEP_STATUSES,
  RUNTIME_EVENT_TYPES,
  VALID_STATUSES,
  VALID_STEP_STATUSES,
  VALID_EVENT_TYPES
}
