// Model Gateway Schema Contracts (Phase 8-D0: Research Agent Model Gateway).
//
// Phase 8-D0: agent-facing request/response contracts between ResearchContextProvider
// (Phase 8-C3) and the online model providers.
//
// Phase 8-D0 frozen contract:
//   - ChatMessage (role / content / name?)
//   - ModelRequest (messages / context / taskType / tokenBudget / temperature)
//   - TokenUsage (promptTokens / completionTokens / totalTokens)
//   - ModelResponse (content / usage / provider / latencyMs)
//   - StreamChunk (delta / done / usage?)
//   - TaskType (qa / summarization / extraction / code / general)
//   - Validators + assertNoSecret (walks only string values; keys are identifiers)
//
// Phase 8-D0 strict:
//   - NEVER contains apiKey / secret / token value / cipher
//   - No LLM SDK imports, no provider SDK imports, no local model dependency

// ============ ChatMessage ============

export type ChatRole = 'system' | 'user' | 'assistant'

export interface ChatMessage {
  role: ChatRole
  content: string
  name?: string
}

// ============ TaskType ============

export type TaskType = 'qa' | 'summarization' | 'extraction' | 'code' | 'general'

export const TASK_TYPES: readonly TaskType[] = Object.freeze([
  'qa', 'summarization', 'extraction', 'code', 'general'
])

// ============ TokenUsage ============

export interface TokenUsage {
  promptTokens: number
  completionTokens: number
  totalTokens: number
}

// ============ ModelRequest ============

/**
 * Phase 8-D0: agent-side request shape. `context` is opaque — the gateway
 * turns it into system + context messages at dispatch time.
 */
export interface ModelRequest {
  messages: ChatMessage[]
  context: Record<string, unknown> | null
  taskType: TaskType
  tokenBudget: number
  temperature: number
}

// ============ ModelResponse ============

export interface ModelResponse {
  content: string
  usage: TokenUsage
  provider: string
  latencyMs: number
}

// ============ StreamChunk ============

export interface StreamChunk {
  delta: string
  done: boolean
  usage?: TokenUsage
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
    throw new Error(`model gateway leak: '${ctx}' contains forbidden substring '${hit}' (Phase 8-D0 strict)`)
  }
}

function isObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

export function isValidChatRole(r: unknown): r is ChatRole {
  return r === 'system' || r === 'user' || r === 'assistant'
}

export function isValidTaskType(t: unknown): t is TaskType {
  return typeof t === 'string' && TASK_TYPES.includes(t as TaskType)
}

export function isValidChatMessage(m: unknown): m is ChatMessage {
  if (!isObject(m)) return false
  if (!isValidChatRole(m.role)) return false
  if (typeof m.content !== 'string') return false
  if (m.name !== undefined && typeof m.name !== 'string') return false
  return true
}

export function isValidTokenUsage(u: unknown): u is TokenUsage {
  if (!isObject(u)) return false
  for (const k of ['promptTokens', 'completionTokens', 'totalTokens']) {
    const v = u[k]
    if (typeof v !== 'number' || !Number.isInteger(v) || v < 0) return false
  }
  return true
}

export function isValidModelRequest(r: unknown): r is ModelRequest {
  if (!isObject(r)) return false
  if (!Array.isArray(r.messages) || !r.messages.every((m) => isValidChatMessage(m))) return false
  if (r.context !== null && !isObject(r.context)) return false
  if (!isValidTaskType(r.taskType)) return false
  if (typeof r.tokenBudget !== 'number' || !Number.isInteger(r.tokenBudget) || r.tokenBudget < 1) return false
  if (typeof r.temperature !== 'number' || r.temperature < 0 || r.temperature > 2) return false
  assertNoSecret(r, 'ModelRequest')
  return true
}

export function isValidModelResponse(r: unknown): r is ModelResponse {
  if (!isObject(r)) return false
  if (typeof r.content !== 'string') return false
  if (!isValidTokenUsage(r.usage)) return false
  if (typeof r.provider !== 'string' || r.provider.length === 0) return false
  if (typeof r.latencyMs !== 'number' || !Number.isFinite(r.latencyMs) || r.latencyMs < 0) return false
  assertNoSecret(r, 'ModelResponse')
  return true
}

export function isValidStreamChunk(c: unknown): c is StreamChunk {
  if (!isObject(c)) return false
  if (typeof c.delta !== 'string') return false
  if (typeof c.done !== 'boolean') return false
  if (c.usage !== undefined && !isValidTokenUsage(c.usage)) return false
  return true
}

export const __testHelpers = {
  FORBIDDEN,
  findForbidden,
  TASK_TYPES
}