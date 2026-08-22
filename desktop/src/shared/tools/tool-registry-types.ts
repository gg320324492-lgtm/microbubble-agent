// Tool Registry Types (Phase 7-T1: Tool Registry Implementation).
//
// Phase 7-T1: shared types for the Tool Registry runtime. Distinct from
//   - Phase 7-T0 ToolDefinition / ToolInputSchema / ToolResult (contracts)
//   - Phase 6 Model Runtime (Provider / Router / Chat)
//   - Phase 7-A0 Knowledge Schema
//
// Phase 7-T1 frozen contract:
//   - ToolRegistration (definition + registeredAt + handle)
//   - ToolRegistrySnapshot (tools list + count + timestamp)
//   - ToolLookupResult (found boolean + optional tool)
//   - ToolRegistryEvent (register / unregister event names)
//
// Phase 7-T1 strict:
//   - NEVER contains apiKey / token / cipher / authorization / providerId / modelId

import type { ToolDefinition } from './tool-schema'

export interface ToolRegistration {
  /** Frozen definition (Phase 7-T0 contract). */
  definition: ToolDefinition
  /** Epoch ms when this registration was added. */
  registeredAt: number
  /** Internal handle (Phase 7-T+ executor binding). Phase 7-T1: empty string. */
  handle: string
}

/**
 * Phase 7-T1: a snapshot of the registry at a point in time.
 * Phase 7-T+ may extend with usage metrics.
 */
export interface ToolRegistrySnapshot {
  tools: ToolRegistration[]
  count: number
  timestamp: number
}

/**
 * Phase 7-T1: result of a lookup operation.
 * `found=true` implies `tool` is set; `found=false` implies `tool` is undefined.
 */
export interface ToolLookupResult {
  found: boolean
  tool?: ToolRegistration
}

/**
 * Phase 7-T1: registry event names. Phase 7-T+ emits events via EventEmitter.
 * Phase 7-T1 ships ONLY the type names — no EventEmitter yet.
 */
export type ToolRegistryEvent = 'register' | 'unregister'

/**
 * Phase 7-T1: filter options for `ToolRegistry.list()`.
 */
export interface ToolListOptions {
  category?: import('./tool-schema').ToolCategory
  permission?: import('./tool-schema').ToolPermission
  tags?: string[]
}
