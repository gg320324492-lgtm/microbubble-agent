// Adapter Registry Runtime (Phase 7-T5-B: Adapter Registry Runtime).
//
// Phase 7-T5-B: in-process AdapterRegistry that binds ToolAdapter
// instances to toolIds, exposed to the ToolExecutor via a resolver
// function. NO IPC, NO UI, NO real scientific adapters, NO backend.
//
// Phase 7-T5-B frozen contract:
//   - AdapterRegistry class (6 public methods)
//   - One toolId maps to one adapter (deterministic; duplicate rejected)
//   - Invalid adapter rejected (Phase 7-T2 ToolAdapter validator)
//   - Deterministic ordering (sorted by toolId on list())
//   - ToolExecutor integration via getAdapterResolver()
//
// Phase 7-T5-B strict:
//   - NEVER contains apiKey / token / cipher / Authorization / providerId / modelId
//   - Does NOT import from model-provider / auth / chat / backend

import { isValidToolAdapter, type ToolAdapter } from '@shared/tools/tool-adapter-schema'

const FORBIDDEN = ['sk-', 'apiKey', 'cipher', 'Bearer ', 'token', 'authorization',
                   'providerId', 'modelId']

function assertNoSecret(value: unknown, ctx: string): void {
  const dump = JSON.stringify(value)
  for (const bad of FORBIDDEN) {
    if (dump.includes(bad)) {
      throw new Error(`adapter registry leak: '${ctx}' contains forbidden substring '${bad}' (Phase 7-T5-B strict)`)
    }
  }
}

export class AdapterAlreadyRegisteredError extends Error {
  constructor(toolId: string) {
    super(`AdapterRegistry: adapter for '${toolId}' is already registered (Phase 7-T5-B strict)`)
    this.name = 'AdapterAlreadyRegisteredError'
  }
}

export class AdapterInvalidError extends Error {
  constructor(message: string) {
    super(`AdapterRegistry: ${message} (Phase 7-T5-B strict)`)
    this.name = 'AdapterInvalidError'
  }
}

interface AdapterEntry {
  toolId: string
  adapter: ToolAdapter
  registeredAt: number
}

export class AdapterRegistry {
  private readonly entries: Map<string, AdapterEntry> = new Map()
  private insertionOrder = 0

  /** Phase 7-T5-B: register an adapter. Throws on duplicate or invalid. */
  register(adapter: ToolAdapter): void {
    assertNoSecret(adapter, 'register.adapter')
    if (!isValidToolAdapter(adapter)) {
      const aid = (adapter as Partial<ToolAdapter>)?.toolId
      throw new AdapterInvalidError(`invalid ToolAdapter for toolId '${aid ?? '<undefined>'}'`)
    }
    if (this.entries.has(adapter.toolId)) {
      throw new AdapterAlreadyRegisteredError(adapter.toolId)
    }
    this.insertionOrder += 1
    this.entries.set(adapter.toolId, {
      toolId: adapter.toolId,
      adapter,
      registeredAt: Date.now()
    })
  }

  /** Phase 7-T5-B: unregister an adapter by toolId. Returns boolean. */
  unregister(toolId: string): boolean {
    return this.entries.delete(toolId)
  }

  /** Phase 7-T5-B: get the adapter entry for a toolId. */
  get(toolId: string): AdapterEntry | null {
    return this.entries.get(toolId) ?? null
  }

  /** Phase 7-T5-B: check if an adapter is registered for toolId. */
  has(toolId: string): boolean {
    return this.entries.has(toolId)
  }

  /** Phase 7-T5-B: list all adapters, sorted alphabetically by toolId (deterministic). */
  list(): AdapterEntry[] {
    return Array.from(this.entries.values())
      .sort((a, b) => a.toolId.localeCompare(b.toolId))
  }

  /** Phase 7-T5-B: clear all adapters (testing helper). */
  clear(): void {
    this.entries.clear()
    this.insertionOrder = 0
  }

  /** Phase 7-T5-B: number of registered adapters. */
  size(): number {
    return this.entries.size
  }

  /**
   * Phase 7-T5-B: build an AdapterResolver that the ToolExecutor can consume.
   *
   * The returned function maps `toolId` -> the underlying `execute` function
   * of the registered ToolAdapter, or null if not registered.
   */
  getAdapterResolver(): (toolId: string) => ToolAdapter['execute'] | null {
    const self = this
    return (toolId: string) => {
      const entry = self.entries.get(toolId)
      if (!entry) return null
      return entry.adapter.execute
    }
  }
}

export const __testHelpers = {
  FORBIDDEN,
  AdapterAlreadyRegisteredError,
  AdapterInvalidError
}
