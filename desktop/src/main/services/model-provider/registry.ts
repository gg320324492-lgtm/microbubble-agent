// Provider Registry (Phase 6-A3: Provider Factory + Registry).
//
// Phase 6-A3: in-process registry that maps providerId -> factory function.
// Each factory takes a ModelConfig and returns a ModelProvider instance.
//
// Phase 6-A3 frozen contract:
//   - registerProvider(id, factory)         -> void
//   - getProvider(id, cfg?)                 -> ModelProvider (lazy-built via factory)
//   - listProviders()                       -> Array<{ providerId, type, capabilities, displayName, defaultModel }>
//   - hasProvider(id)                       -> boolean
//   - clearRegistry()                       -> void (Phase 6-A3: tests only)
//
// Phase 6-A3 explicit forbids:
//   - NO auto-loading from disk / network
//   - NO ambient registration at module import (callers must invoke registerProvider)
//   - NO throw on missing — returns undefined from getProvider (Phase 6-A3: caller decides)

import type { ModelProvider } from '@shared/model/provider-types'
import type { ModelConfig } from '@shared/model/model-types'

/**
 * Phase 6-A3: factory function that builds a ModelProvider from a ModelConfig.
 * The factory is called lazily on first getProvider() call; result is cached.
 */
export type ProviderFactory = (cfg: ModelConfig) => ModelProvider

interface RegistryEntry {
  factory: ProviderFactory
  /** Last-built provider (cached after first getProvider call). */
  cached?: ModelProvider
  /** Config used to build the cached provider (re-build if config changes). */
  cachedConfig?: ModelConfig
  /** Public metadata for listProviders() — no factory callable from this. */
  meta: ProviderRegistryMeta
}

export interface ProviderRegistryMeta {
  providerId: string
  type: ModelConfig['type']
  capabilities: ModelProvider['capabilities']
  displayName: string
  defaultModel: string
}

const REGISTRY = new Map<string, RegistryEntry>()

/**
 * Phase 6-A3: register a provider factory.
 * Throws if providerId is invalid or factory is not a function.
 * Re-registering overwrites the previous entry (Phase 6-A3: explicit override).
 */
export function registerProvider(
  providerId: string,
  factory: ProviderFactory,
  meta: Omit<ProviderRegistryMeta, 'providerId'>
): void {
  if (typeof providerId !== 'string' || providerId.length < 2 || providerId.length > 32) {
    throw new Error(
      `ProviderRegistry.registerProvider: invalid providerId '${String(providerId)}' (Phase 6-A3: 2-32 chars).`
    )
  }
  if (typeof factory !== 'function') {
    throw new Error('ProviderRegistry.registerProvider: factory must be a function.')
  }
  if (!meta || typeof meta !== 'object') {
    throw new Error('ProviderRegistry.registerProvider: meta must be an object.')
  }
  if (typeof meta.displayName !== 'string' || meta.displayName.length === 0) {
    throw new Error('ProviderRegistry.registerProvider: meta.displayName must be non-empty string.')
  }
  if (typeof meta.defaultModel !== 'string' || meta.defaultModel.length === 0) {
    throw new Error('ProviderRegistry.registerProvider: meta.defaultModel must be non-empty string.')
  }
  if (meta.type !== 'cloud' && meta.type !== 'local' && meta.type !== 'openai-compatible') {
    throw new Error(`ProviderRegistry.registerProvider: invalid type '${String(meta.type)}'.`)
  }
  REGISTRY.set(providerId, { factory, meta: { ...meta, providerId } })
}

/**
 * Phase 6-A3: look up a provider by id; lazily build + cache on first call.
 *
 * @returns ModelProvider instance, or undefined if not registered.
 */
export function getProvider(providerId: string, cfg?: ModelConfig): ModelProvider | undefined {
  const entry = REGISTRY.get(providerId)
  if (!entry) return undefined
  if (entry.cached && entry.cachedConfig === cfg) return entry.cached
  if (!cfg) {
    // Phase 6-A3: cannot build without cfg; return existing cached if any.
    return entry.cached
  }
  const built = entry.factory(cfg)
  entry.cached = built
  entry.cachedConfig = cfg
  return built
}

/**
 * Phase 6-A3: list all registered providers (metadata only, no factory callable).
 * Used by Settings UI (Phase 6-A4) to populate provider dropdown.
 */
export function listProviders(): ProviderRegistryMeta[] {
  return Array.from(REGISTRY.values()).map((e) => e.meta)
}

/**
 * Phase 6-A3: check whether a providerId is registered.
 */
export function hasProvider(providerId: string): boolean {
  return REGISTRY.has(providerId)
}

/**
 * Phase 6-A3: clear all registered providers (TEST ONLY).
 * Production code MUST NOT call this — registry is process-lifetime.
 */
export function clearRegistry(): void {
  REGISTRY.clear()
}

/**
 * Phase 6-A3: count of registered providers (test helper).
 */
export function registrySize(): number {
  return REGISTRY.size
}

// Phase 6-A3: expose registry internals for tests (NOT for production)
export const __testHelpers = {
  REGISTRY,
  hasEntry: (id: string): boolean => REGISTRY.has(id)
}
