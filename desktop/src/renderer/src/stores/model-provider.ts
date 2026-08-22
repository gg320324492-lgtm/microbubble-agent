// model-provider Pinia store (Phase 6-A4: Model Settings + Provider Management).
//
// Renderer-side UI state for the Model Settings page.
// Phase 6-A4 frozen contract:
//   - Never holds API keys in renderer state
//   - Never calls safeStorage directly
//   - All sensitive operations go through window.api.model IPC
//   - Store is purely UI-facing metadata; main process owns truth
//
// State shape:
//   - providers: array of ProviderEntry (config + hasKey + connectionStatus)
//   - activeProviderId: string | null
//   - activeModel: string | null
//   - per-provider connectionStatus / lastLatency / lastError (lazy-loaded map)

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { ModelProviderConfig, ModelTestProviderResult } from '@shared/preload-api'

export type ProviderConnectionStatus = 'unknown' | 'checking' | 'connected' | 'failed'

/**
 * Phase 6-A4: ProviderEntry = config + hasKey + connectionStatus.
 * NEVER holds API key value. hasKey is a boolean only.
 */
export interface ProviderEntry {
  config: ModelProviderConfig
  hasKey: boolean
  connectionStatus: ProviderConnectionStatus
  lastLatencyMs?: number
  lastError?: string
}

export const useModelProviderStore = defineStore('model-provider', () => {
  // ============ State ============

  const providers = ref<ProviderEntry[]>([])
  const activeProviderId = ref<string | null>(null)
  const activeModel = ref<string | null>(null)
  const loading = ref(false)
  const lastError = ref<string | null>(null)

  // ============ Getters ============

  const activeProvider = computed<ProviderEntry | null>(() => {
    if (!activeProviderId.value) return null
    return providers.value.find((p) => p.config.providerId === activeProviderId.value) ?? null
  })

  const providersWithKey = computed<ProviderEntry[]>(() =>
    providers.value.filter((p) => p.hasKey)
  )

  const providersMissingKey = computed<ProviderEntry[]>(() =>
    providers.value.filter((p) => !p.hasKey)
  )

  // ============ Actions ============

  /**
   * Phase 6-A4: load all provider configs from main process.
   * Refreshes the entire providers array; clears connectionStatus to 'unknown'.
   */
  async function loadProviders(): Promise<void> {
    loading.value = true
    lastError.value = null
    try {
      const result = await window.api.model.listConfigs()
      const next: ProviderEntry[] = []
      for (let i = 0; i < result.configs.length; i++) {
        const cfg = result.configs[i]
        const hasKey = result.hasKey[i] ?? false
        // Preserve existing connectionStatus if same providerId
        const existing = providers.value.find((p) => p.config.providerId === cfg.providerId)
        next.push({
          config: cfg,
          hasKey,
          connectionStatus: existing?.connectionStatus ?? 'unknown',
          ...(existing?.lastLatencyMs !== undefined ? { lastLatencyMs: existing.lastLatencyMs } : {}),
          ...(existing?.lastError !== undefined ? { lastError: existing.lastError } : {})
        })
      }
      providers.value = next
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * Phase 6-A4: save a non-secret provider config.
   * Refreshes the providers array after success.
   */
  async function saveProvider(
    providerId: string,
    config: Omit<ModelProviderConfig, 'providerId' | 'updatedAt'>
  ): Promise<void> {
    loading.value = true
    lastError.value = null
    try {
      await window.api.model.saveConfig(providerId, config)
      await loadProviders()
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * Phase 6-A4: delete a provider config.
   * Refreshes the providers array after success.
   */
  async function removeProvider(providerId: string): Promise<void> {
    loading.value = true
    lastError.value = null
    try {
      await window.api.model.deleteConfig(providerId)
      if (activeProviderId.value === providerId) {
        activeProviderId.value = null
        activeModel.value = null
      }
      await loadProviders()
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * Phase 6-A4: test a provider's connectivity (Phase 6-A3 ping).
   * Updates connectionStatus / lastLatencyMs / lastError on the entry.
   */
  async function testProvider(providerId: string): Promise<ModelTestProviderResult> {
    const entry = providers.value.find((p) => p.config.providerId === providerId)
    if (entry) {
      entry.connectionStatus = 'checking'
      entry.lastError = undefined
    }
    try {
      const result = await window.api.model.testProvider(providerId)
      const updated = providers.value.find((p) => p.config.providerId === providerId)
      if (updated) {
        updated.connectionStatus = result.ok ? 'connected' : 'failed'
        if (typeof result.latencyMs === 'number') updated.lastLatencyMs = result.latencyMs
        if (typeof result.error === 'string') updated.lastError = result.error
      }
      return result
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e)
      const updated = providers.value.find((p) => p.config.providerId === providerId)
      if (updated) {
        updated.connectionStatus = 'failed'
        updated.lastError = msg
      }
      return { ok: false, error: msg }
    }
  }

  /**
   * Phase 6-A4: set the active provider.
   * Does NOT change activeModel automatically — caller decides.
   */
  function setActiveProvider(providerId: string | null): void {
    activeProviderId.value = providerId
    if (providerId === null) {
      activeModel.value = null
    }
  }

  /**
   * Phase 6-A4: set the active model (must be one of provider's capabilities-supported models).
   */
  function setActiveModel(model: string | null): void {
    activeModel.value = model
  }

  /**
   * Phase 6-A4: save an API key. Refreshes hasKey flags via loadProviders.
   */
  async function saveApiKey(providerId: string, apiKey: string): Promise<void> {
    await window.api.model.saveKey(providerId, apiKey)
    await loadProviders()
  }

  /**
   * Phase 6-A4: delete an API key. Refreshes hasKey flags via loadProviders.
   */
  async function removeApiKey(providerId: string): Promise<void> {
    await window.api.model.deleteKey(providerId)
    await loadProviders()
  }

  function reset(): void {
    providers.value = []
    activeProviderId.value = null
    activeModel.value = null
    lastError.value = null
  }

  return {
    // state
    providers,
    activeProviderId,
    activeModel,
    loading,
    lastError,
    // getters
    activeProvider,
    providersWithKey,
    providersMissingKey,
    // actions
    loadProviders,
    saveProvider,
    removeProvider,
    testProvider,
    setActiveProvider,
    setActiveModel,
    saveApiKey,
    removeApiKey,
    reset
  }
})
