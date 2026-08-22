// Tool Registry Implementation (Phase 7-T1: Tool Registry Implementation).
//
// Phase 7-T1: in-process ToolRegistry runtime. Stores ToolDefinitions, supports
// register / unregister / get / list / has / clear / snapshot. NO execution.
//
// Phase 7-T1 frozen contract:
//   - Duplicate tool id MUST reject (throws ToolAlreadyRegisteredError)
//   - Invalid ToolDefinition MUST reject (throws ToolValidationError)
//   - Registry MUST be deterministic (sorted list)
//   - NO tool execution
//
// Phase 7-T1 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId
//   - Tool Registry does NOT import model-provider / auth / chat / backend

import {
  isValidToolDefinition,
  type ToolDefinition
} from '@shared/tools/tool-schema'
import type {
  ToolRegistration,
  ToolRegistrySnapshot,
  ToolLookupResult,
  ToolListOptions
} from '@shared/tools/tool-registry-types'

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`tool registry leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T1 strict)`)
    }
  }
}

export class ToolAlreadyRegisteredError extends Error {
  constructor(toolId: string) {
    super(`ToolRegistry: tool '${toolId}' is already registered (Phase 7-T1 strict)`)
    this.name = 'ToolAlreadyRegisteredError'
  }
}

export class ToolValidationError extends Error {
  constructor(message: string) {
    super(`ToolRegistry: ${message} (Phase 7-T1 strict)`)
    this.name = 'ToolValidationError'
  }
}

export class ToolRegistry {
  private readonly tools: Map<string, ToolRegistration> = new Map()
  private insertionOrder: number = 0

  /**
   * Phase 7-T1: register a tool definition.
   * Throws ToolValidationError on invalid definition.
   * Throws ToolAlreadyRegisteredError on duplicate id.
   */
  register(definition: ToolDefinition): void {
    assertNoSecret(definition, 'register.input')
    if (!isValidToolDefinition(definition)) {
      throw new ToolValidationError(
        `invalid ToolDefinition for id '${(definition as Partial<ToolDefinition>)?.id ?? '<undefined>'}'`
      )
    }
    if (this.tools.has(definition.id)) {
      throw new ToolAlreadyRegisteredError(definition.id)
    }
    this.insertionOrder += 1
    const registration: ToolRegistration = {
      definition,
      registeredAt: Date.now(),
      handle: `handle:${this.insertionOrder}:${definition.id}`
    }
    this.tools.set(definition.id, registration)
  }

  /**
   * Phase 7-T1: unregister a tool by id.
   * Returns true if removed; false if not present.
   */
  unregister(toolId: string): boolean {
    if (typeof toolId !== 'string' || toolId.length === 0) return false
    return this.tools.delete(toolId)
  }

  /**
   * Phase 7-T1: get a registration by id.
   */
  get(toolId: string): ToolRegistration | null {
    if (typeof toolId !== 'string' || toolId.length === 0) return null
    return this.tools.get(toolId) ?? null
  }

  /**
   * Phase 7-T1: structured lookup result.
   */
  lookup(toolId: string): ToolLookupResult {
    const tool = this.get(toolId)
    if (!tool) return { found: false }
    return { found: true, tool }
  }

  /**
   * Phase 7-T1: list tools. Filter by category / permission / tags.
   * Returned array is deterministically sorted by toolId (alphabetical).
   */
  list(options?: ToolListOptions): ToolRegistration[] {
    let result = Array.from(this.tools.values())
    if (options?.category !== undefined) {
      result = result.filter((r) => r.definition.category === options.category)
    }
    if (options?.permission !== undefined) {
      result = result.filter((r) => r.definition.permission === options.permission)
    }
    if (options?.tags !== undefined && options.tags.length > 0) {
      const required = new Set(options.tags)
      result = result.filter((r) =>
        r.definition.tags.some((t) => required.has(t))
      )
    }
    return result.sort((a, b) => a.definition.id.localeCompare(b.definition.id))
  }

  /**
   * Phase 7-T1: check if a tool id is registered.
   */
  has(toolId: string): boolean {
    return this.tools.has(toolId)
  }

  /**
   * Phase 7-T1: number of registered tools.
   */
  size(): number {
    return this.tools.size
  }

  /**
   * Phase 7-T1: remove all registrations (Phase 7-T1 strict: testing helper).
   */
  clear(): void {
    this.tools.clear()
    this.insertionOrder = 0
  }

  /**
   * Phase 7-T1: point-in-time snapshot.
   */
  snapshot(): ToolRegistrySnapshot {
    return {
      tools: this.list(),
      count: this.tools.size,
      timestamp: Date.now()
    }
  }
}

export const __testHelpers = {
  FORBIDDEN,
  ToolAlreadyRegisteredError,
  ToolValidationError
}
