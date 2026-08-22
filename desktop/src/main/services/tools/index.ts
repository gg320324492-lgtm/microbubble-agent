// Tool Layer Index (Phase 7-T1: Tool Registry Implementation).
//
// Phase 7-T1: singleton registry + lifecycle. NO global pollution
// (the singleton is process-scoped, not on `globalThis`).
//
// Phase 7-T1 frozen contract:
//   - getToolRegistry() returns the same ToolRegistry instance for the process
//   - initializeBuiltinTools() registers Phase 7-T1 built-in tool declarations
//   - resetToolRegistry() clears + re-initializes (testing helper)

import { ToolRegistry } from './tool-registry'
import { BUILTIN_TOOLS } from '@shared/tools/builtin-tools'

let _registry: ToolRegistry | null = null

/**
 * Phase 7-T1: get the singleton registry.
 * Lazy-initializes on first call.
 */
export function getToolRegistry(): ToolRegistry {
  if (_registry === null) {
    _registry = new ToolRegistry()
  }
  return _registry
}

/**
 * Phase 7-T1: register the built-in tool declarations (Phase 7-T0 contract).
 *
 * Idempotent: if a tool is already registered, the registration is skipped
 * (the existing ToolAlreadyRegisteredError from Phase 7-T1 would otherwise
 * abort the whole batch).
 *
 * Phase 7-T1 strict: declares tool metadata only. NO function wiring.
 * Phase 7-T+ adds adapter binding for each built-in tool.
 */
export function initializeBuiltinTools(): void {
  const registry = getToolRegistry()
  for (const def of BUILTIN_TOOLS) {
    if (!registry.has(def.id)) {
      registry.register(def)
    }
  }
}

/**
 * Phase 7-T1: reset the singleton registry.
 * Testing helper — does NOT persist anything (Phase 7-T1 strict).
 */
export function resetToolRegistry(): void {
  if (_registry !== null) {
    _registry.clear()
  }
  _registry = null
}

/**
 * Phase 7-T1: lifecycle entry point. Main process boot can call this once.
 *
 * Sequence:
 *   1. getToolRegistry()        -> creates the singleton
 *   2. initializeBuiltinTools() -> registers Phase 7-T1 built-in tools
 */
export function bootToolLayer(): void {
  getToolRegistry()
  initializeBuiltinTools()
}

export { ToolRegistry }
export type {
  ToolRegistration,
  ToolRegistrySnapshot,
  ToolLookupResult,
  ToolListOptions
} from '@shared/tools/tool-registry-types'
