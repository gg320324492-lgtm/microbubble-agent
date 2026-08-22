// Tool Execution Schema Contracts (Phase 7-T4: Tool Execution Runtime).
//
// Phase 7-T4: typed contracts for the Tool Execution runtime layer.
// Distinct from:
//   - Phase 7-T0 ToolDefinition / ToolInputSchema / ToolResult (definitions)
//   - Phase 7-T1 ToolRegistry (storage)
//   - Phase 7-T2 ToolAdapter (translation binding)
//   - Phase 7-T3 ToolCapabilityProfile / matchToolsForTask (selection)
//
// Phase 7-T4 frozen contract:
//   - ToolExecutionStatus (7 lifecycle states)
//   - ToolExecutionRequest (what the Agent sends to the Executor)
//   - ToolExecutionRecord (what the Executor tracks)
//   - ToolExecutionTraceEvent (4 event types, Phase 3-B0-compatible names)
//   - Validators with assertNoSecret guard
//
// Phase 7-T4 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - Executor schema is INDEPENDENT from model-provider / auth / chat / backend
//   - NO execution paths in this commit (architecture only)

import type { ToolResult } from './tool-schema'

// ============ Execution Status ============

export type ToolExecutionStatus =
  | 'created'      // request received, not yet validated
  | 'validated'    // schema + permission checks passed
  | 'queued'       // waiting for an available executor slot
  | 'running'      // execute() is in progress
  | 'completed'    // execute() returned successfully (ToolResult.success=true)
  | 'failed'       // execute() returned with error (ToolResult.success=false OR exception)
  | 'cancelled'    // user / system cancelled before completion

export const TOOL_EXECUTION_STATUSES: readonly ToolExecutionStatus[] = Object.freeze([
  'created', 'validated', 'queued', 'running', 'completed', 'failed', 'cancelled'
])

// ============ Execution Request ============

/**
 * Phase 7-T4: input to the Executor.
 *
 * Submitted by the Agent (Phase 7-G) or by the IPC channel (Phase 7-T+).
 * The Executor validates this, runs the matching adapter, and returns a Record.
 */
export interface ToolExecutionRequest {
  /** Stable id for tracing (Phase 7-T4 strict: non-empty). */
  requestId: string
  /** Tool id from ToolDefinition.id */
  toolId: string
  /** Validated args (passed through validateToolArgs at execution time) */
  args: unknown
  /** Timeout in milliseconds (Phase 7-T4 strict: positive integer) */
  timeout: number
  /** Free-form metadata (trace id, parent request id, etc.) */
  metadata?: Record<string, unknown>
}

// ============ Execution Record ============

/**
 * Phase 7-T4: state tracked by the Executor during one execution.
 *
 * The record is what gets logged + what the renderer sees via IPC (Phase 7-T+).
 */
export interface ToolExecutionRecord {
  /** Stable id (matches the request's requestId). */
  requestId: string
  /** Tool id (matches the request's toolId). */
  toolId: string
  /** Current lifecycle state. */
  status: ToolExecutionStatus
  /** Epoch ms when execution began (when status transitioned to 'running'). */
  startedAt: number | null
  /** Epoch ms when execution ended (completed / failed / cancelled). */
  finishedAt: number | null
  /** Final ToolResult from the adapter (populated when status >= completed). */
  result?: ToolResult
  /** Free-form error message (populated when status = 'failed'). */
  error?: string
}

// ============ Trace Events ============

/**
 * Phase 7-T4: trace event types emitted by the Executor.
 * Names are compatible with Phase 3-B0 StreamEvent shape (Phase 7-T+
 * integrates via TraceTimeline.vue).
 */
export type ToolExecutionTraceEvent =
  | 'tool_execution_start'
  | 'tool_execution_progress'
  | 'tool_execution_complete'
  | 'tool_execution_error'

export const TOOL_EXECUTION_TRACE_EVENTS: readonly ToolExecutionTraceEvent[] = Object.freeze([
  'tool_execution_start',
  'tool_execution_progress',
  'tool_execution_complete',
  'tool_execution_error'
])

export interface ToolExecutionTracePayload {
  /** Tool id (matches the request's toolId). */
  toolId: string
  /** Request id (matches ToolExecutionRecord.requestId). */
  requestId: string
  /** Phase 7-T4 strict: epoch ms when the event was emitted. */
  emittedAt: number
  /** Status at the time of the event. */
  status: ToolExecutionStatus
  /** Phase 7-T4: progress in [0, 100]; only set on 'tool_execution_progress'. */
  progress?: number
  /** Phase 7-T4: error message; only set on 'tool_execution_error'. */
  error?: string
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`tool execution leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T4 strict)`)
    }
  }
}

const VALID_STATUSES: ReadonlySet<ToolExecutionStatus> = new Set(TOOL_EXECUTION_STATUSES)
const VALID_TRACE_EVENTS: ReadonlySet<ToolExecutionTraceEvent> = new Set(TOOL_EXECUTION_TRACE_EVENTS)

export function isValidToolExecutionStatus(s: unknown): s is ToolExecutionStatus {
  return typeof s === 'string' && VALID_STATUSES.has(s as ToolExecutionStatus)
}

export function isValidToolExecutionRequest(r: unknown): r is ToolExecutionRequest {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (typeof o.requestId !== 'string' || o.requestId.length === 0) return false
  if (typeof o.toolId !== 'string' || !/^tool:[a-z][a-z0-9_\-:]{0,63}$/.test(o.toolId as string)) return false
  // args: any (Phase 7-T0 validateToolArgs runs at execution time)
  if (typeof o.timeout !== 'number' || o.timeout <= 0 || !Number.isInteger(o.timeout)) return false
  if (o.metadata !== undefined && (typeof o.metadata !== 'object' || o.metadata === null || Array.isArray(o.metadata))) return false
  assertNoSecret(r, 'ToolExecutionRequest')
  return true
}

export function isValidToolExecutionRecord(r: unknown): r is ToolExecutionRecord {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (typeof o.requestId !== 'string' || o.requestId.length === 0) return false
  if (typeof o.toolId !== 'string') return false
  if (!isValidToolExecutionStatus(o.status)) return false
  if (o.startedAt !== null && (typeof o.startedAt !== 'number' || o.startedAt < 0)) return false
  if (o.finishedAt !== null && (typeof o.finishedAt !== 'number' || o.finishedAt < 0)) return false
  if (o.result !== undefined && (typeof o.result !== 'object' || o.result === null)) return false
  if (o.error !== undefined && typeof o.error !== 'string') return false
  assertNoSecret(r, 'ToolExecutionRecord')
  return true
}

export function isValidToolExecutionTracePayload(p: unknown): p is ToolExecutionTracePayload {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (typeof o.toolId !== 'string') return false
  if (typeof o.requestId !== 'string') return false
  if (typeof o.emittedAt !== 'number' || o.emittedAt < 0) return false
  if (!isValidToolExecutionStatus(o.status)) return false
  if (o.progress !== undefined && (typeof o.progress !== 'number' || o.progress < 0 || o.progress > 100)) return false
  if (o.error !== undefined && typeof o.error !== 'string') return false
  assertNoSecret(p, 'ToolExecutionTracePayload')
  return true
}

export function isValidToolExecutionTraceEvent(e: unknown): e is ToolExecutionTraceEvent {
  return typeof e === 'string' && VALID_TRACE_EVENTS.has(e as ToolExecutionTraceEvent)
}

export const __testHelpers = {
  FORBIDDEN,
  VALID_STATUSES,
  VALID_TRACE_EVENTS,
  TOOL_EXECUTION_STATUSES,
  TOOL_EXECUTION_TRACE_EVENTS
}
