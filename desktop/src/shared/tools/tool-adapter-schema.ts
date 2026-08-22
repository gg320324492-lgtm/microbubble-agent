// Tool Adapter Contracts (Phase 7-T2: Tool Adapter Runtime Architecture).
//
// Phase 7-T2: typed contracts for the Tool Adapter layer. Distinct from
//   - Phase 7-T0 ToolDefinition / ToolInputSchema / ToolResult (definitions)
//   - Phase 7-T1 ToolRegistry (storage / lookup)
//   - Phase 6 Model Runtime
//   - Phase 7-A0 Knowledge Schema
//
// Phase 7-T2 frozen contract:
//   - ToolAdapter (toolId + version + execute + validate + metadata)
//   - ToolExecutionContext (requestId + optional userContext/projectContext/metadata)
//   - ToolExecutionResult (reuses ToolResult envelope; adds Phase 7-T2 metadata)
//   - AdapterRegistry (Phase 7-T2 +) binds ToolAdapters to ToolDefinitions
//
// Phase 7-T2 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - NO execution paths (Phase 7-T2 ships contracts only)
//   - Tool Adapter does NOT import model-provider / auth / chat / backend

import type { ToolResult, ToolDefinition } from './tool-schema'

// ============ Adapter contract ============

/**
 * Phase 7-T2: a function-shaped contract for tool execution.
 * The Adapter wraps an existing application function (Phase 7-T+).
 *
 * Phase 7-T2 strict: `execute` is a contract only — Phase 7-T+ ships implementations.
 */
export type AdapterExecuteFn = (args: unknown, ctx: ToolExecutionContext) => Promise<ToolResult>

/**
 * Phase 7-T2: optional adapter-level validation hook.
 * Adapters may add domain-specific checks beyond Phase 7-T0 schema validation.
 * Returns null when valid; returns an error message when invalid.
 */
export type AdapterValidateFn = (args: unknown) => string | null

/**
 * Phase 7-T2: free-form adapter metadata (not a contract).
 * Examples (Phase 7-T+): "{ function: 'analyzeKinetics' }" or
 *   "{ library: 'numpy', version: '1.24' }".
 */
export interface AdapterMetadata {
  [key: string]: unknown
}

/**
 * Phase 7-T2: ToolAdapter — wraps an existing function as a Tool.
 *
 * The Adapter REGISTERS against a ToolDefinition (Phase 7-T0 contract).
 * The Adapter does NOT define the ToolDefinition — that's Phase 7-T0's role.
 */
export interface ToolAdapter {
  /** Matches the ToolDefinition.id this adapter binds to. */
  toolId: string
  /** Adapter implementation version (semver). */
  version: string
  /** Phase 7-T2 strict: contract only — no execution in Phase 7-T2. */
  execute: AdapterExecuteFn
  /** Optional domain-specific validation. */
  validate?: AdapterValidateFn
  /** Free-form metadata (e.g. underlying function name, library version). */
  metadata?: AdapterMetadata
}

// ============ Execution context ============

/**
 * Phase 7-T2: free-form user context (Phase 7+: user identity; Phase 7-T2: empty).
 * Phase 7-T2 strict: NEVER include Authorization / Bearer / token values here.
 */
export interface UserContext {
  /** Phase 7-T2 strict: empty string. Phase 7+: actual user id. */
  userId: string
  /** Phase 7-T2 strict: empty string. Phase 7+: actual user role. */
  role: string
  /** Phase 7-T2 strict: empty array. Phase 7+: user permissions. */
  permissions: string[]
}

/**
 * Phase 7-T2: free-form project context (Phase 7+: project membership; Phase 7-T2: empty).
 */
export interface ProjectContext {
  /** Phase 7-T2 strict: empty string. Phase 7+: actual project id. */
  projectId: string
  /** Phase 7-T2 strict: empty array. Phase 7+: project-scoped permissions. */
  permissions: string[]
}

/**
 * Phase 7-T2: execution context passed to every Adapter.
 * Phase 7-T2 ships the shape; Phase 7-T+ populates these fields.
 */
export interface ToolExecutionContext {
  /** Stable id for tracing (Phase 7-T2: ''; Phase 7-T+: uuid). */
  requestId: string
  /** Phase 7-T2 strict: optional. Phase 7+: from auth service. */
  userContext?: UserContext
  /** Phase 7-T2 strict: optional. Phase 7+: from project membership. */
  projectContext?: ProjectContext
  /** Free-form metadata (timing, trace id, parent request id). */
  metadata?: Record<string, unknown>
}

// ============ Execution result ============

/**
 * Phase 7-T2: result envelope. Re-uses Phase 7-T0 ToolResult shape
 * (success / data / error / metadata) for full compatibility.
 *
 * Phase 7-T2 strict: shape-equivalent to ToolResult; Phase 7-T2 just
 * aliases the type for clarity in the Adapter layer.
 */
export type ToolExecutionResult = ToolResult

// ============ Adapter registry contract ============

/**
 * Phase 7-T2: AdapterRegistry binds ToolAdapter to ToolDefinition by toolId.
 * Phase 7-T2 strict: contract only — Phase 7-T+ ships the implementation.
 */
export interface AdapterRegistry {
  register(adapter: ToolAdapter, definition: ToolDefinition): void
  unregister(toolId: string): boolean
  get(toolId: string): ToolAdapter | null
  has(toolId: string): boolean
  list(): ToolAdapter[]
  size(): number
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`tool adapter leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T2 strict)`)
    }
  }
}

export function isValidToolAdapter(a: unknown): a is ToolAdapter {
  if (!a || typeof a !== 'object') return false
  const o = a as Record<string, unknown>
  if (typeof o.toolId !== 'string' || o.toolId.length === 0) return false
  if (typeof o.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(o.version as string)) return false
  if (typeof o.execute !== 'function') return false
  if (o.validate !== undefined && typeof o.validate !== 'function') return false
  if (o.metadata !== undefined && (typeof o.metadata !== 'object' || o.metadata === null || Array.isArray(o.metadata))) return false
  assertNoSecret(a, 'ToolAdapter')
  return true
}

export function isValidUserContext(u: unknown): u is UserContext {
  if (!u || typeof u !== 'object') return false
  const o = u as Record<string, unknown>
  if (typeof o.userId !== 'string') return false
  if (typeof o.role !== 'string') return false
  if (!Array.isArray(o.permissions) || !o.permissions.every((x) => typeof x === 'string')) return false
  assertNoSecret(u, 'UserContext')
  return true
}

export function isValidProjectContext(p: unknown): p is ProjectContext {
  if (!p || typeof p !== 'object') return false
  const o = p as Record<string, unknown>
  if (typeof o.projectId !== 'string') return false
  if (!Array.isArray(o.permissions) || !o.permissions.every((x) => typeof x === 'string')) return false
  assertNoSecret(p, 'ProjectContext')
  return true
}

export const __testHelpers = {
  FORBIDDEN
}
