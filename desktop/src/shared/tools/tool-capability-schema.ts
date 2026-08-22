// Tool Capability Contracts (Phase 7-T3: Tool Capability Matching Design).
//
// Phase 7-T3: typed contracts for the Tool Capability Matching layer.
// Distinct from:
//   - Phase 7-A0/7-C1 ResearchCapability (research-domain taxonomy)
//   - Phase 6-C1 ModelCapability (LLM API surface)
//   - Phase 7-T0 ToolCategory (broad purpose: analysis / simulation / etc.)
//   - Phase 7-T0 ToolDefinition (what the tool IS)
//
// Phase 7-T3 frozen contract:
//   - ToolTaskType (8 task types)
//   - ToolCapabilityProfile (toolId + capabilities + tasks + priority)
//   - ToolMatchResult (toolId + score + reason)
//   - matchToolsForTask(task, profiles) -> ToolMatchResult[] (sorted)
//   - 3 validators + assertNoSecret guard
//
// Phase 7-T3 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - Tool matching does NOT import model-provider / auth / chat / backend
//   - Tool matching is INDEPENDENT from Phase 7-C2 Model capability router

// ============ Tool Task Type ============

export type ToolTaskType =
  | 'literature-processing'
  | 'data-analysis'
  | 'experiment-analysis'
  | 'visualization'
  | 'simulation'
  | 'calculation'
  | 'export'
  | 'preprocessing'

export const TOOL_TASK_TYPES: readonly ToolTaskType[] = Object.freeze([
  'literature-processing',
  'data-analysis',
  'experiment-analysis',
  'visualization',
  'simulation',
  'calculation',
  'export',
  'preprocessing'
])

// ============ Tool Capability Profile ============

/**
 * Phase 7-T3: free-form capability tags (Phase 7-T3 strict: Tool-LAYER only;
 * do NOT re-use Phase 7-C1 ResearchCapability here to keep independence).
 */
export type ToolCapability = string

/**
 * Phase 7-T3: per-tool metadata used by the matcher.
 *
 * Phase 7-T+ extends ToolDefinition with this profile (Phase 7-T3 ships the type).
 * Phase 7-T3 strict: no apiKey / token / cipher / providerId / modelId.
 */
export interface ToolCapabilityProfile {
  toolId: string
  requiredCapabilities: ToolCapability[]
  optionalCapabilities: ToolCapability[]
  supportedTasks: ToolTaskType[]
  /** Priority 0-10; higher = preferred when ties. */
  priority: number
}

// ============ Match Result ============

/**
 * Phase 7-T3: a single matching result.
 */
export interface ToolMatchResult {
  toolId: string
  /** Higher is better. Phase 7-T+ surfaces to the Agent. */
  score: number
  /** Human-readable reason (NO secrets; safe to log). */
  reason: string
  /** Optional breakdown (Phase 7-T+ uses for debug UI). */
  breakdown?: {
    taskScore: number
    capabilityScore: number
    priorityScore: number
  }
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`tool capability leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T3 strict)`)
    }
  }
}

const VALID_TASK_TYPES: ReadonlySet<ToolTaskType> = new Set(TOOL_TASK_TYPES)

export function isValidToolTaskType(t: unknown): t is ToolTaskType {
  return typeof t === 'string' && VALID_TASK_TYPES.has(t as ToolTaskType)
}

export function isValidToolCapabilityProfile(p: unknown): p is ToolCapabilityProfile {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (typeof o.toolId !== 'string' || o.toolId.length === 0) return false
  if (!Array.isArray(o.requiredCapabilities)
      || !o.requiredCapabilities.every((c) => typeof c === 'string')) return false
  if (!Array.isArray(o.optionalCapabilities)
      || !o.optionalCapabilities.every((c) => typeof c === 'string')) return false
  if (!Array.isArray(o.supportedTasks)
      || !o.supportedTasks.every((t) => typeof t === 'string' && VALID_TASK_TYPES.has(t as ToolTaskType))) return false
  if (typeof o.priority !== 'number' || o.priority < 0 || o.priority > 10
      || !Number.isInteger(o.priority)) return false
  assertNoSecret(p, 'ToolCapabilityProfile')
  return true
}

export function isValidToolMatchResult(r: unknown): r is ToolMatchResult {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (typeof o.toolId !== 'string' || o.toolId.length === 0) return false
  if (typeof o.score !== 'number' || o.score < 0) return false
  if (typeof o.reason !== 'string' || o.reason.length === 0) return false
  if (o.breakdown !== undefined) {
    const b = o.breakdown as Record<string, unknown>
    if (typeof b.taskScore !== 'number'
        || typeof b.capabilityScore !== 'number'
        || typeof b.priorityScore !== 'number') return false
  }
  assertNoSecret(r, 'ToolMatchResult')
  return true
}

// ============ Matching Algorithm (Phase 7-T3 pure function) ============

export interface ToolMatchInput {
  /** Required tasks (Phase 7-T+ uses Phase 7-C2 task profile or similar). */
  requiredTasks: ToolTaskType[]
  /** Optional tasks (boost score but not required). */
  optionalTasks?: ToolTaskType[]
  /** Required capabilities. */
  requiredCapabilities: ToolCapability[]
}

/**
 * Phase 7-T3: deterministic matching algorithm. Pure function — no IO.
 *
 * Score:
 *   taskScore       = (# requiredTasks hit) * 10 + (# optionalTasks hit) * 2
 *   capabilityScore = (# requiredCapabilities hit) * 5
 *   priorityScore   = profile.priority (0..10)
 *   total           = taskScore + capabilityScore + priorityScore
 *
 * Tie-breaker: alphabetical by toolId (deterministic).
 */
export function matchToolsForTask(
  input: ToolMatchInput,
  profiles: ToolCapabilityProfile[]
): ToolMatchResult[] {
  if (!input || !Array.isArray(profiles)) return []
  const reqTasks = new Set(input.requiredTasks)
  const optTasks = new Set(input.optionalTasks ?? [])
  const reqCaps = new Set(input.requiredCapabilities)

  const scored = profiles
    .map((p) => {
      const taskHits = p.supportedTasks.filter((t) => reqTasks.has(t))
      const optHits = p.supportedTasks.filter((t) => optTasks.has(t))
      const capHits = p.requiredCapabilities.filter((c) => reqCaps.has(c))
      const taskScore = taskHits.length * 10 + optHits.length * 2
      const capabilityScore = capHits.length * 5
      const priorityScore = p.priority
      const total = taskScore + capabilityScore + priorityScore
      const reason =
        `tasks=[${taskHits.join(',')}] ` +
        `caps=[${capHits.join(',')}] ` +
        `priority=${p.priority}`
      return {
        toolId: p.toolId,
        score: total,
        reason,
        breakdown: { taskScore, capabilityScore, priorityScore }
      }
    })
    // Phase 7-T3 strict: a tool must have at least one relevant hit
    // (required task OR required capability) to be returned. A profile
    // with only priority and no matching task/capability is irrelevant.
    .filter((m) => {
      const b = m.breakdown
      return b !== undefined && (b.taskScore > 0 || b.capabilityScore > 0)
    })
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score
      return a.toolId.localeCompare(b.toolId)
    })

  return scored
}

export const __testHelpers = {
  FORBIDDEN,
  VALID_TASK_TYPES,
  TOOL_TASK_TYPES
}
