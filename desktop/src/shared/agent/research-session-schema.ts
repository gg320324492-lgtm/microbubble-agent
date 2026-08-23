// Research Memory / Session Schema (Phase 8-F0).
//
// Phase 8-F0: persistence boundary ABOVE the agent. Sessions, conversation,
// memory items, and checkpoints that survive across ResearchAgent.run() calls.
//
// Phase 8-F0 strict:
//   - NEVER contains apiKey / secret / token value / cipher / authorization
//   - Does NOT modify Phase 8-E0 / 8-A1 / 8-B / 8-C / 8-D / 7 / 6 modules

// ============ SessionStatus ============

export type SessionStatus = 'active' | 'paused' | 'completed' | 'archived'

export const SESSION_STATUSES: readonly SessionStatus[] = Object.freeze([
  'active', 'paused', 'completed', 'archived'
])

// ============ MemoryType ============

export type MemoryType = 'conversation' | 'experiment' | 'paper' | 'parameter' | 'conclusion'

export const MEMORY_TYPES: readonly MemoryType[] = Object.freeze([
  'conversation', 'experiment', 'paper', 'parameter', 'conclusion'
])

// ============ ResearchSession ============

export interface ResearchSession {
  sessionId: string
  projectId?: string
  title: string
  createdAt: number
  updatedAt: number
  status: SessionStatus
}

// ============ ConversationEntry ============

export type ConversationRole = 'user' | 'assistant'

export interface ConversationEntry {
  entryId: string
  role: ConversationRole
  content: string
  timestamp: number
}

// ============ MemoryItem ============

/**
 * Phase 8-F0: a fact the agent remembers about the user/project/history.
 * `confidence` is 0..1 (higher = more certain). `source` is where it came from.
 */
export interface MemoryItem {
  memoryId: string
  type: MemoryType
  content: string
  confidence: number
  source: string
}

// ============ AgentCheckpoint ============

/**
 * Phase 8-F0: a snapshot of an agent run's progress (e.g. per-step state)
 * so a session can be resumed after interruption.
 */
export interface AgentCheckpoint {
  checkpointId: string
  sessionId: string
  planId: string
  stepState: Record<string, unknown>
  createdAt: number
}

// ============ Session events (Phase 8-E0 AgentEvent-compatible) ============

export type SessionEventType =
  | 'session_created'
  | 'memory_added'
  | 'checkpoint_saved'
  | 'context_restored'

export const SESSION_EVENT_TYPES: readonly SessionEventType[] = Object.freeze([
  'session_created', 'memory_added', 'checkpoint_saved', 'context_restored'
])

export interface SessionEvent {
  type: SessionEventType
  sessionId: string
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
    throw new Error(`research session leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-F0 strict)`)
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidSessionStatus(s: unknown): s is SessionStatus {
  return typeof s === 'string' && (SESSION_STATUSES as readonly string[]).includes(s)
}

export function isValidMemoryType(t: unknown): t is MemoryType {
  return typeof t === 'string' && (MEMORY_TYPES as readonly string[]).includes(t)
}

export function isValidResearchSession(s: unknown): s is ResearchSession {
  if (!isObject(s)) return false
  if (typeof s.sessionId !== 'string' || s.sessionId.length === 0) return false
  if (s.projectId !== undefined && typeof s.projectId !== 'string') return false
  if (typeof s.title !== 'string' || s.title.length === 0) return false
  if (typeof s.createdAt !== 'number' || !Number.isFinite(s.createdAt) || s.createdAt < 0) return false
  if (typeof s.updatedAt !== 'number' || !Number.isFinite(s.updatedAt) || s.updatedAt < s.createdAt) return false
  if (!isValidSessionStatus(s.status)) return false
  assertNoSecret(s, 'ResearchSession')
  return true
}

export function isValidConversationRole(r: unknown): r is ConversationRole {
  return r === 'user' || r === 'assistant'
}

export function isValidConversationEntry(e: unknown): e is ConversationEntry {
  if (!isObject(e)) return false
  if (typeof e.entryId !== 'string' || e.entryId.length === 0) return false
  if (!isValidConversationRole(e.role)) return false
  if (typeof e.content !== 'string') return false
  if (typeof e.timestamp !== 'number' || !Number.isFinite(e.timestamp) || e.timestamp < 0) return false
  assertNoSecret(e, 'ConversationEntry')
  return true
}

export function isValidMemoryItem(m: unknown): m is MemoryItem {
  if (!isObject(m)) return false
  if (typeof m.memoryId !== 'string' || m.memoryId.length === 0) return false
  if (!isValidMemoryType(m.type)) return false
  if (typeof m.content !== 'string' || m.content.length === 0) return false
  if (typeof m.confidence !== 'number' || !Number.isFinite(m.confidence) || m.confidence < 0 || m.confidence > 1) return false
  if (typeof m.source !== 'string' || m.source.length === 0) return false
  assertNoSecret(m, 'MemoryItem')
  return true
}

export function isValidAgentCheckpoint(c: unknown): c is AgentCheckpoint {
  if (!isObject(c)) return false
  if (typeof c.checkpointId !== 'string' || c.checkpointId.length === 0) return false
  if (typeof c.sessionId !== 'string' || c.sessionId.length === 0) return false
  if (typeof c.planId !== 'string' || c.planId.length === 0) return false
  if (!isObject(c.stepState)) return false
  if (typeof c.createdAt !== 'number' || !Number.isFinite(c.createdAt) || c.createdAt < 0) return false
  assertNoSecret(c, 'AgentCheckpoint')
  return true
}

export function isValidSessionEventType(t: unknown): t is SessionEventType {
  return typeof t === 'string' && (SESSION_EVENT_TYPES as readonly string[]).includes(t)
}

export function isValidSessionEvent(e: unknown): e is SessionEvent {
  if (!isObject(e)) return false
  if (!isValidSessionEventType(e.type)) return false
  if (typeof e.sessionId !== 'string' || e.sessionId.length === 0) return false
  if (typeof e.timestamp !== 'number' || !Number.isFinite(e.timestamp) || e.timestamp < 0) return false
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  SESSION_STATUSES,
  MEMORY_TYPES,
  SESSION_EVENT_TYPES
}