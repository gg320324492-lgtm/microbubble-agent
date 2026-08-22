// Tool Schema Contracts (Phase 7-T0: Tools Architecture Design).
//
// Phase 7-T0: typed contracts for the Tool Layer. Distinct from
//   - Phase 6 Model Runtime (Provider / Router / Chat)
//   - Phase 7-A0 Knowledge Schema (entities / metadata)
//   - Phase 7-B0 Knowledge Storage (provider interface)
//
// Phase 7-T0 frozen contract:
//   - ToolCategory (9 categories)
//   - ToolExecutionTarget (3 targets)
//   - ToolPermission (3 levels)
//   - ToolDefinition (tool metadata + schemas)
//   - ToolInputSchema (typed field validation)
//   - ToolResult (success/failure envelope)
//
// Phase 7-T0 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - Tool Layer is INDEPENDENT from Model Provider / Auth / Chat / Legacy

// ============ Enums ============

export type ToolCategory =
  | 'analysis'
  | 'simulation'
  | 'data-processing'
  | 'visualization'
  | 'calculation'
  | 'conversion'
  | 'retrieval'
  | 'export'
  | 'system'

export type ToolExecutionTarget =
  | 'application'
  | 'local-service'
  | 'remote-service'

export type ToolPermission =
  | 'public'
  | 'research'
  | 'admin'

// ============ Input schema ============

export type ToolFieldType = 'string' | 'number' | 'boolean' | 'array' | 'object'

export interface ToolFieldDef {
  name: string
  type: ToolFieldType
  description?: string
  required?: boolean
  /** For type='number': [min, max] inclusive */
  range?: [number, number]
  /** For type='string': allowed enum values */
  enum?: string[]
  /** For type='array': element type */
  itemType?: ToolFieldType
  /** For type='object': nested fields */
  fields?: ToolFieldDef[]
}

export interface ToolInputSchema {
  fields: ToolFieldDef[]
  required: string[]
  /** Free-text validation rules (e.g. "all positive numbers") */
  validationRules: string[]
}

// ============ Output schema ============

export interface ToolOutputSchema {
  /** Free-form description of the output shape (Phase 7-T0: string only; Phase 7+ may add structured schema) */
  description: string
  /** Top-level field names in the output */
  fields: string[]
}

// ============ Tool definition ============

export interface ToolDefinition {
  /** Stable id: 'tool:kinetic-analysis' */
  id: string
  /** Human-readable name */
  name: string
  /** What this tool does (LLM sees this) */
  description: string
  /** Category */
  category: ToolCategory
  /** Semver, e.g. '1.0.0' */
  version: string
  inputSchema: ToolInputSchema
  outputSchema: ToolOutputSchema
  executionTarget: ToolExecutionTarget
  /** Minimum permission level required to call this tool */
  permission: ToolPermission
  /** Free-form tags for search */
  tags: string[]
}

// ============ Result envelope ============

export interface ToolError {
  code: string
  message: string
}

export interface ToolResult {
  success: boolean
  /** Payload when success=true */
  data?: Record<string, unknown>
  /** Free-form metadata (timing, source, etc.) */
  metadata?: Record<string, unknown>
  /** Error when success=false */
  error?: ToolError
}

// ============ Validators ============

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`tool schema leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T0 strict)`)
    }
  }
}

const VALID_CATEGORIES: ReadonlySet<ToolCategory> = new Set([
  'analysis', 'simulation', 'data-processing', 'visualization', 'calculation',
  'conversion', 'retrieval', 'export', 'system'
])
const VALID_TARGETS: ReadonlySet<ToolExecutionTarget> = new Set([
  'application', 'local-service', 'remote-service'
])
const VALID_PERMISSIONS: ReadonlySet<ToolPermission> = new Set(['public', 'research', 'admin'])
const VALID_FIELD_TYPES: ReadonlySet<ToolFieldType> = new Set([
  'string', 'number', 'boolean', 'array', 'object'
])
const ID_RE = /^tool:[a-z][a-z0-9_\-:]{0,63}$/

export function isValidToolCategory(c: unknown): c is ToolCategory {
  return typeof c === 'string' && VALID_CATEGORIES.has(c as ToolCategory)
}
export function isValidToolExecutionTarget(t: unknown): t is ToolExecutionTarget {
  return typeof t === 'string' && VALID_TARGETS.has(t as ToolExecutionTarget)
}
export function isValidToolPermission(p: unknown): p is ToolPermission {
  return typeof p === 'string' && VALID_PERMISSIONS.has(p as ToolPermission)
}
export function isValidToolFieldType(t: unknown): t is ToolFieldType {
  return typeof t === 'string' && VALID_FIELD_TYPES.has(t as ToolFieldType)
}

export function isValidToolFieldDef(f: unknown): f is ToolFieldDef {
  if (!f || typeof f !== 'object') return false
  const o = f as Record<string, unknown>
  if (typeof o.name !== 'string' || o.name.length === 0) return false
  if (!isValidToolFieldType(o.type)) return false
  if (o.description !== undefined && typeof o.description !== 'string') return false
  if (o.required !== undefined && typeof o.required !== 'boolean') return false
  if (o.range !== undefined) {
    const r = o.range as unknown[]
    if (!Array.isArray(r) || r.length !== 2
        || typeof r[0] !== 'number' || typeof r[1] !== 'number'
        || r[0] > r[1]) return false
  }
  if (o.enum !== undefined) {
    if (!Array.isArray(o.enum) || !o.enum.every((x) => typeof x === 'string')) return false
  }
  if (o.itemType !== undefined && !isValidToolFieldType(o.itemType)) return false
  if (o.fields !== undefined && (!Array.isArray(o.fields)
      || !o.fields.every((x) => isValidToolFieldDef(x)))) return false
  return true
}

export function isValidToolInputSchema(s: unknown): s is ToolInputSchema {
  if (!s || typeof s !== 'object') return false
  const o = s as Record<string, unknown>
  if (!Array.isArray(o.fields)) return false
  for (const f of o.fields) {
    if (!isValidToolFieldDef(f)) return false
  }
  if (!Array.isArray(o.required) || !o.required.every((x) => typeof x === 'string')) return false
  if (!Array.isArray(o.validationRules)
      || !o.validationRules.every((x) => typeof x === 'string')) return false
  // every required name MUST appear in fields
  const fieldNames = (o.fields as Array<{ name: string }>).map((f) => f.name)
  for (const r of o.required as string[]) {
    if (!fieldNames.includes(r)) return false
  }
  assertNoSecret(s, 'ToolInputSchema')
  return true
}

export function isValidToolOutputSchema(s: unknown): s is ToolOutputSchema {
  if (!s || typeof s !== 'object') return false
  const o = s as Record<string, unknown>
  if (typeof o.description !== 'string') return false
  if (!Array.isArray(o.fields) || !o.fields.every((x) => typeof x === 'string')) return false
  assertNoSecret(s, 'ToolOutputSchema')
  return true
}

export function isValidToolDefinition(d: unknown): d is ToolDefinition {
  if (!d || typeof d !== 'object') return false
  const o = d as Record<string, unknown>
  if (typeof o.id !== 'string' || !ID_RE.test(o.id as string)) return false
  if (typeof o.name !== 'string' || o.name.length === 0) return false
  if (typeof o.description !== 'string' || o.description.length === 0) return false
  if (!isValidToolCategory(o.category)) return false
  if (typeof o.version !== 'string' || !/^\d+\.\d+\.\d+$/.test(o.version as string)) return false
  if (!isValidToolInputSchema(o.inputSchema)) return false
  if (!isValidToolOutputSchema(o.outputSchema)) return false
  if (!isValidToolExecutionTarget(o.executionTarget)) return false
  if (!isValidToolPermission(o.permission)) return false
  if (!Array.isArray(o.tags) || !o.tags.every((x) => typeof x === 'string')) return false
  assertNoSecret(d, 'ToolDefinition')
  return true
}

export function isValidToolResult(r: unknown): r is ToolResult {
  if (!r || typeof r !== 'object') return false
  const o = r as Record<string, unknown>
  if (typeof o.success !== 'boolean') return false
  if (o.success === true) {
    if (o.data !== undefined && (typeof o.data !== 'object' || o.data === null)) return false
  } else {
    if (!o.error || typeof o.error !== 'object') return false
    const err = o.error as Record<string, unknown>
    if (typeof err.code !== 'string' || err.code.length === 0) return false
    if (typeof err.message !== 'string' || err.message.length === 0) return false
  }
  if (o.metadata !== undefined && (typeof o.metadata !== 'object' || o.metadata === null)) return false
  assertNoSecret(r, 'ToolResult')
  return true
}

/**
 * Phase 7-T0: validate tool arguments against a tool's input schema.
 * Returns null when valid; returns an error message string when invalid.
 *
 * Pure structural validation — NO tool execution, NO model calls.
 */
export function validateToolArgs(
  def: ToolDefinition,
  args: unknown
): string | null {
  if (!def || !args || typeof args !== 'object') {
    return 'args must be an object'
  }
  const a = args as Record<string, unknown>
  // required fields present
  for (const r of def.inputSchema.required) {
    if (!(r in a)) return `missing required field '${r}'`
  }
  // type check per field
  for (const f of def.inputSchema.fields) {
    if (!(f.name in a)) continue
    const v = a[f.name]
    if (!matchesFieldType(v, f)) {
      return `field '${f.name}' has wrong type (expected ${f.type})`
    }
    if (f.type === 'number' && f.range) {
      const num = v as number
      if (num < f.range[0] || num > f.range[1]) {
        return `field '${f.name}' out of range [${f.range[0]}, ${f.range[1]}]`
      }
    }
    if (f.type === 'string' && f.enum) {
      if (!f.enum.includes(v as string)) {
        return `field '${f.name}' not in enum`
      }
    }
  }
  return null
}

function matchesFieldType(v: unknown, f: ToolFieldDef): boolean {
  switch (f.type) {
    case 'string': return typeof v === 'string'
    case 'number': return typeof v === 'number'
    case 'boolean': return typeof v === 'boolean'
    case 'array': return Array.isArray(v)
    case 'object': return typeof v === 'object' && v !== null && !Array.isArray(v)
    default: return false
  }
}

export const __testHelpers = {
  FORBIDDEN,
  VALID_CATEGORIES,
  VALID_TARGETS,
  VALID_PERMISSIONS,
  VALID_FIELD_TYPES,
  ID_RE
}
