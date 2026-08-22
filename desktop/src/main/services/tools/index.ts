// Tool Layer Index (Phase 7-T1 + 7-T5-B: Registry + Adapter Registry Lifecycle).
//
// Phase 7-T1: singleton ToolRegistry + built-in tools + reset helper.
// Phase 7-T5-B: adds singleton AdapterRegistry lifecycle + reset helper.
//
// Phase 7-T1 / 7-T5-B frozen contract:
//   - getToolRegistry()       -> singleton ToolRegistry
//   - initializeBuiltinTools()-> registers Phase 7-T1 built-in tools
//   - resetToolRegistry()     -> clears ToolRegistry
//   - getAdapterRegistry()    -> singleton AdapterRegistry (Phase 7-T5-B)
//   - resetAdapterRegistry()  -> clears AdapterRegistry (Phase 7-T5-B)
//   - initializeToolAdapters()-> reserved for Phase 7-T+ (no builtin adapters yet)
//   - bootToolLayer()         -> lifecycle entry point

import { ToolRegistry } from './tool-registry'
import { AdapterRegistry } from './adapter-registry'
import { BUILTIN_TOOLS } from '@shared/tools/builtin-tools'

let _registry: ToolRegistry | null = null
let _adapterRegistry: AdapterRegistry | null = null

// ============ Tool Registry (Phase 7-T1) ============

/**
 * Phase 7-T1: get the singleton ToolRegistry.
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
 * Idempotent: if a tool is already registered, the registration is skipped.
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
 * Phase 7-T1: reset the singleton ToolRegistry.
 */
export function resetToolRegistry(): void {
  if (_registry !== null) {
    _registry.clear()
  }
  _registry = null
}

// ============ Adapter Registry (Phase 7-T5-B) ============

/**
 * Phase 7-T5-B: get the singleton AdapterRegistry.
 * Lazy-initializes on first call.
 */
export function getAdapterRegistry(): AdapterRegistry {
  if (_adapterRegistry === null) {
    _adapterRegistry = new AdapterRegistry()
  }
  return _adapterRegistry
}

/**
 * Phase 7-T5-B: register Phase 7-T+ tool adapters.
 *
 * Phase 7-T5-B strict: NO builtin adapters yet. Phase 7-T+ adds the real
 * scientific adapters (kinetic-analysis, data-visualization, dataset-export).
 *
 * Currently a no-op; reserved for forward compatibility.
 */
export function initializeToolAdapters(): void {
  // Phase 7-T5-B: no-op. Phase 7-T+ populates with real adapters.
}

/**
 * Phase 7-T5-B: reset the singleton AdapterRegistry.
 */
export function resetAdapterRegistry(): void {
  if (_adapterRegistry !== null) {
    _adapterRegistry.clear()
  }
  _adapterRegistry = null
}

// ============ Lifecycle entry point ============

/**
 * Phase 7-T1 / 7-T5-B: lifecycle entry point. Main process boot can call once.
 *
 * Sequence:
 *   1. getToolRegistry()        -> creates ToolRegistry singleton
 *   2. initializeBuiltinTools() -> registers Phase 7-T1 built-in tools
 *   3. getAdapterRegistry()     -> creates AdapterRegistry singleton
 *   4. initializeToolAdapters() -> no-op (Phase 7-T+)
 */
export function bootToolLayer(): void {
  getToolRegistry()
  initializeBuiltinTools()
  getAdapterRegistry()
  initializeToolAdapters()
}

export { ToolRegistry, AdapterRegistry }
export type {
  ToolRegistration,
  ToolRegistrySnapshot,
  ToolLookupResult,
  ToolListOptions
} from '@shared/tools/tool-registry-types'
