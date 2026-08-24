// Agent Schema — 多智能体科研协作契约。
export type AgentRole =
  | 'LiteratureAgent' | 'ExperimentAgent' | 'DataAnalysisAgent'
  | 'MechanismAgent' | 'WritingAgent' | 'ReviewerAgent' | 'CoordinatorAgent'

export const AGENT_ROLES: readonly AgentRole[] = Object.freeze([
  'LiteratureAgent', 'ExperimentAgent', 'DataAnalysisAgent',
  'MechanismAgent', 'WritingAgent', 'ReviewerAgent', 'CoordinatorAgent'
])

export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export const TASK_STATUSES: readonly TaskStatus[] = Object.freeze([
  'pending', 'running', 'completed', 'failed', 'cancelled'
])

export type MessageType = 'request' | 'response' | 'evidence' | 'critique' | 'suggestion'

export const MESSAGE_TYPES: readonly MessageType[] = Object.freeze([
  'request', 'response', 'evidence', 'critique', 'suggestion'
])

export interface ScientificAgentProfile {
  id: string
  name: string
  role: AgentRole
  description: string
  capabilities: string[]
  tools: string[]
  knowledgeDomains: string[]
  priority: number
}

export interface AgentTask {
  id: string
  agentId: string
  input: string
  status: TaskStatus
  result?: string
  confidence: number
}

export interface AgentMessage {
  id: string
  fromAgent: string
  toAgent: string
  messageType: MessageType
  content: string
  timestamp: number
}

// ============ Validators ============

const VALID_ROLES: ReadonlySet<AgentRole> = new Set(AGENT_ROLES)
const VALID_TASK_STATUSES: ReadonlySet<TaskStatus> = new Set(TASK_STATUSES)
const VALID_MESSAGE_TYPES: ReadonlySet<MessageType> = new Set(MESSAGE_TYPES)

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

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
    throw new Error(`agent schema leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-J1 strict)`)
  }
}

function isValidScore(v: unknown): v is number {
  return typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1
}

export function isValidAgentRole(r: unknown): r is AgentRole {
  return typeof r === 'string' && VALID_ROLES.has(r as AgentRole)
}

export function isValidTaskStatus(s: unknown): s is TaskStatus {
  return typeof s === 'string' && VALID_TASK_STATUSES.has(s as TaskStatus)
}

export function isValidMessageType(t: unknown): t is MessageType {
  return typeof t === 'string' && VALID_MESSAGE_TYPES.has(t as MessageType)
}

export function isValidScientificAgentProfile(p: unknown): p is ScientificAgentProfile {
  if (!isObject(p)) return false
  if (typeof p.id !== 'string' || p.id.length === 0) return false
  if (typeof p.name !== 'string' || p.name.length === 0) return false
  if (!isValidAgentRole(p.role)) return false
  if (typeof p.description !== 'string') return false
  if (!Array.isArray(p.capabilities)) return false
  if (!Array.isArray(p.tools)) return false
  if (!Array.isArray(p.knowledgeDomains)) return false
  if (typeof p.priority !== 'number') return false
  assertNoSecret(p, 'ScientificAgentProfile')
  return true
}

export function isValidAgentTask(t: unknown): t is AgentTask {
  if (!isObject(t)) return false
  if (typeof t.id !== 'string' || t.id.length === 0) return false
  if (typeof t.agentId !== 'string' || t.agentId.length === 0) return false
  if (typeof t.input !== 'string') return false
  if (!isValidTaskStatus(t.status)) return false
  if (!isValidScore(t.confidence)) return false
  if (t.result !== undefined && typeof t.result !== 'string') return false
  assertNoSecret(t, 'AgentTask')
  return true
}

export function isValidAgentMessage(m: unknown): m is AgentMessage {
  if (!isObject(m)) return false
  if (typeof m.id !== 'string' || m.id.length === 0) return false
  if (typeof m.fromAgent !== 'string') return false
  if (typeof m.toAgent !== 'string') return false
  if (!isValidMessageType(m.messageType)) return false
  if (typeof m.content !== 'string') return false
  if (typeof m.timestamp !== 'number') return false
  assertNoSecret(m, 'AgentMessage')
  return true
}

export const __testHelpers = {
  AGENT_ROLES, TASK_STATUSES, MESSAGE_TYPES, FORBIDDEN, findForbidden, isValidScore
}
