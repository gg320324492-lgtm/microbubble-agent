// Research Agent Orchestration Schema (Phase 8-E0).
//
// Phase 8-E0: typed contracts for the agent-facing orchestration layer.
// Consumes PlannerDecision / AgentRun / RAGContext / ModelResponse from prior
// phases. Never modifies them.
//
// Phase 8-E0 strict:
//   - NEVER contains apiKey / secret / token value / cipher / authorization
//   - Does NOT modify Phase 8-B0 / 8-A1 / 8-C3 / 8-D0 contracts
//   - Pure assembly / coordination only

import type { CitationReference } from '../knowledge/document-schema'

// ============ Request / Response ============

export interface AgentRunOptions {
  tokenBudget?: number
  temperature?: number
  fallbackOnError?: boolean
}

export interface ResearchAgentRequest {
  requestId: string
  question: string
  projectId?: string
  context?: Record<string, unknown>
  options?: AgentRunOptions
}

/** Phase 8-E0: per-step tool result summary surfaced in the response. */
export interface ToolResultSummary {
  stepId: string
  toolId?: string
  result: unknown
}

/** Phase 8-E0: aggregate usage across planner + runtime + downstream subsystems. */
export interface AgentUsage {
  promptTokens: number
  completionTokens: number
  totalTokens: number
  promptCalls: number
  toolCalls: number
}

export interface ResearchAgentResponse {
  requestId: string
  answer: string
  plan?: unknown
  citations: CitationReference[]
  toolResults: ToolResultSummary[]
  usage: AgentUsage
  confidence: number
}

// ============ Status ============

export type AgentRunStatus =
  | 'pending'
  | 'planning'
  | 'retrieving'
  | 'executing'
  | 'generating'
  | 'completed'
  | 'failed'
  | 'cancelled'

export const AGENT_RUN_STATUSES: readonly AgentRunStatus[] = Object.freeze([
  'pending', 'planning', 'retrieving', 'executing', 'generating',
  'completed', 'failed', 'cancelled'
])

// ============ Events ============

export type AgentEventType =
  | 'agent_started'
  | 'plan_created'
  | 'context_retrieved'
  | 'tool_started'
  | 'tool_completed'
  | 'model_started'
  | 'model_completed'
  | 'agent_completed'
  | 'agent_failed'

export const AGENT_EVENT_TYPES: readonly AgentEventType[] = Object.freeze([
  'agent_started', 'plan_created', 'context_retrieved',
  'tool_started', 'tool_completed', 'model_started', 'model_completed',
  'agent_completed', 'agent_failed'
])

export interface AgentEvent {
  type: AgentEventType
  requestId: string
  timestamp: number
  payload?: Record<string, unknown>
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'secret', 'token value', 'cipher',
                   'authorization', 'Bearer ', 'providerId/']

function findForbidden(value: unknown): string | null {
  if (typeof value === 'string') {
    for (const bad of FORBIDDEN) if (value.includes(bad)) return bad
    return null
  }
  if (Array.isArray(value)) {
    for (const v of value) { const r = findForbidden(v); if (r) return r }
    return null
  }
  if (value && typeof value === 'object') {
    for (const v of Object.values(value as Record<string, unknown>)) {
      const r = findForbidden(v); if (r) return r
    }
  }
  return null
}

function assertNoSecret(value: unknown, ctx: string): void {
  const hit = findForbidden(value)
  if (hit) {
    throw new Error(`research agent leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-E0 strict)`)
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidAgentRunStatus(s: unknown): s is AgentRunStatus {
  return typeof s === 'string' && (AGENT_RUN_STATUSES as readonly string[]).includes(s)
}

export function isValidAgentEventType(t: unknown): t is AgentEventType {
  return typeof t === 'string' && (AGENT_EVENT_TYPES as readonly string[]).includes(t)
}

export function isValidAgentRunOptions(o: unknown): o is AgentRunOptions {
  if (o === undefined) return true
  if (!isObject(o)) return false
  if (o.tokenBudget !== undefined && (typeof o.tokenBudget !== 'number' || o.tokenBudget < 1)) return false
  if (o.temperature !== undefined && (typeof o.temperature !== 'number' || o.temperature < 0 || o.temperature > 2)) return false
  if (o.fallbackOnError !== undefined && typeof o.fallbackOnError !== 'boolean') return false
  return true
}

export function isValidResearchAgentRequest(r: unknown): r is ResearchAgentRequest {
  if (!isObject(r)) return false
  if (typeof r.requestId !== 'string' || r.requestId.length === 0) return false
  if (typeof r.question !== 'string' || r.question.length === 0) return false
  if (r.projectId !== undefined && typeof r.projectId !== 'string') return false
  if (r.context !== undefined && !isObject(r.context)) return false
  if (!isValidAgentRunOptions(r.options)) return false
  assertNoSecret(r, 'ResearchAgentRequest')
  return true
}

export function isValidToolResultSummary(t: unknown): t is ToolResultSummary {
  if (!isObject(t)) return false
  if (typeof t.stepId !== 'string' || t.stepId.length === 0) return false
  if (t.toolId !== undefined && typeof t.toolId !== 'string') return false
  return true
}

export function isValidAgentUsage(u: unknown): u is AgentUsage {
  if (!isObject(u)) return false
  for (const k of ['promptTokens', 'completionTokens', 'totalTokens', 'promptCalls', 'toolCalls']) {
    const v = u[k]
    if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) return false
  }
  return true
}

export function isValidResearchAgentResponse(r: unknown): r is ResearchAgentResponse {
  if (!isObject(r)) return false
  if (typeof r.requestId !== 'string' || r.requestId.length === 0) return false
  if (typeof r.answer !== 'string') return false
  if (r.plan !== undefined && r.plan !== null) {
    if (!isObject(r.plan)) return false
    const p = r.plan as Record<string, unknown>
    if (typeof p.id !== 'string' || (p.id as string).length === 0) return false
    if (typeof p.goal !== 'string' || (p.goal as string).length === 0) return false
    if (!Array.isArray(p.tasks)) return false
  }
  if (!Array.isArray(r.citations)) return false
  if (!r.citations.every((c) => typeof c === 'object' && c !== null && 'documentId' in c && 'chunkId' in c && typeof (c as Record<string, unknown>).confidence === 'number')) return false
  if (!Array.isArray(r.toolResults) || !r.toolResults.every((x) => isValidToolResultSummary(x))) return false
  if (!isValidAgentUsage(r.usage)) return false
  if (typeof r.confidence !== 'number' || r.confidence < 0 || r.confidence > 1) return false
  assertNoSecret(r, 'ResearchAgentResponse')
  return true
}

export function isValidAgentEvent(e: unknown): e is AgentEvent {
  if (!isObject(e)) return false
  if (!isValidAgentEventType(e.type)) return false
  if (typeof e.requestId !== 'string' || e.requestId.length === 0) return false
  if (typeof e.timestamp !== 'number' || !Number.isFinite(e.timestamp) || e.timestamp < 0) return false
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  AGENT_RUN_STATUSES,
  AGENT_EVENT_TYPES,
  isValidResearchAgentRequest,
  isValidResearchAgentResponse
}