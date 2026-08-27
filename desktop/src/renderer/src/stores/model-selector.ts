// model-selector Pinia store (Phase 6-B: Active Model Integration).
//
// Phase 6-B: renderer-side state for the chat-side model selector.
// Distinct from `model-provider` (Phase 6-A4): the latter owns the
// Settings page UI; this one owns the chat-side selection + display.
//
// Phase 6-B frozen contract:
//   - selected: ConversationModelContext | null
//   - capabilities: list of capabilities derived from selected provider
//   - loadAvailable() -> reloads available providers from main
//   - select(providerId, model) -> sets active selection
//   - selectForSession(sessionId, ctx) -> per-session override
//   - capabilityList() -> string[] for UI display
//
// Phase 6-B strict forbids:
//   - NEVER holds apiKey field anywhere in state
//   - NEVER logs ConversationModelContext with raw apiKey (it doesn't exist)
//   - All capability derivation goes through main process via Phase 6-A4 IPC

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type {
  ConversationModelContext,
  ModelCapability
} from '@shared/model/conversation-model'

/**
 * Phase 6-B: available provider entry (renderer-visible).
 * NEVER contains apiKey. hasKey is a boolean only.
 */
export interface AvailableProvider {
  providerId: string
  displayName: string
  type: 'cloud' | 'local' | 'openai-compatible'
  defaultModel: string
  capabilities: ModelCapability[]
  hasKey: boolean
}

export const useModelSelectorStore = defineStore('model-selector', () => {
  // ============ State ============
  const available = ref<AvailableProvider[]>([])
  const selected = ref<ConversationModelContext | null>(null)
  /** Per-session override map: sessionId -> ConversationModelContext */
  const sessionOverrides = ref<Map<string, ConversationModelContext>>(new Map())
  const loading = ref(false)
  const lastError = ref<string | null>(null)

  // ============ Getters ============
  const selectedId = computed(() => selected.value?.providerId ?? null)
  const selectedModel = computed(() => selected.value?.model ?? null)
  const selectedDisplayName = computed(() => selected.value?.displayName ?? null)
  const selectedCapabilities = computed<ModelCapability[]>(
    () => selected.value?.capabilities ?? []
  )
  const availableWithKey = computed<AvailableProvider[]>(() =>
    available.value.filter((p) => p.hasKey)
  )

  /**
   * Phase 6-B: resolve the model context to use for a given session.
   * Per-session override wins; otherwise the global selection; otherwise null.
   */
  function resolveForSession(sessionId: string | null | undefined): ConversationModelContext | null {
    if (sessionId && sessionOverrides.value.has(sessionId)) {
      return sessionOverrides.value.get(sessionId) ?? null
    }
    return selected.value
  }

  // ============ Actions ============

  /**
   * Phase 6-B: load available providers from main process.
   * Reuses the Phase 6-A4 `window.api.model.listConfigs` IPC.
   */
  async function loadAvailable(): Promise<void> {
    loading.value = true
    lastError.value = null
    try {
      const result = await window.api.model.listConfigs()
      const next: AvailableProvider[] = []
      for (let i = 0; i < result.configs.length; i++) {
        const cfg = result.configs[i]
        const hasKey = result.hasKey[i] ?? false
        next.push({
          providerId: cfg.providerId,
          displayName: cfg.displayName,
          type: cfg.type,
          defaultModel: cfg.defaultModel,
          capabilities: cfg.capabilities as ModelCapability[],
          hasKey
        })
      }
      available.value = next
      // [类 20.207] 2026-08-28: loadAvailable 后, 如果还没有 selected 且有可用 provider (含 key),
      //   自动选第一个. 之前 selected 永远 null, chat 顶部永远 "Default (no provider selected)".
      if (!selected.value) {
        const firstReady = next.find((p) => p.hasKey) ?? next[0]
        if (firstReady) {
          // 直接赋 ConversationModelContext, 不走 select() 避免循环
          selected.value = {
            providerId: firstReady.providerId,
            displayName: firstReady.displayName,
            type: firstReady.type,
            model: firstReady.defaultModel,
            capabilities: firstReady.capabilities,
            hasKey: firstReady.hasKey
          }
        }
      }
    } catch (e) {
      lastError.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      loading.value = false
    }
  }

  /**
   * Phase 6-B: select a provider + model as the global active selection.
   * If the providerId is unknown, throws.
   * If model is omitted, uses provider's defaultModel.
   */
  async function select(providerId: string, model?: string): Promise<void> {
    const provider = available.value.find((p) => p.providerId === providerId)
    if (!provider) {
      throw new Error(`ModelSelectorStore.select: unknown providerId '${providerId}'.`)
    }
    const chosenModel = model ?? provider.defaultModel
    selected.value = {
      providerId: provider.providerId,
      model: chosenModel,
      displayName: provider.displayName,
      capabilities: provider.capabilities
    }
  }

  /**
   * Phase 6-B: clear global selection (revert to legacy / no provider).
   */
  function clear(): void {
    selected.value = null
  }

  /**
   * Phase 6-B: per-session override (Phase 6-B UI exposes this in chat header).
   */
  function selectForSession(sessionId: string, ctx: ConversationModelContext | null): void {
    if (!sessionId || sessionId.length === 0) return
    if (ctx === null) {
      sessionOverrides.value.delete(sessionId)
    } else {
      sessionOverrides.value.set(sessionId, ctx)
    }
  }

  /**
   * Phase 6-B: capability display list (renderer-only; no API key).
   * Returns the canonical ModelCapability[] so UI can pass directly
   * to capabilityLabel().
   */
  function capabilityList(ctx?: ConversationModelContext | null): ModelCapability[] {
    const target = ctx ?? selected.value
    return target?.capabilities ?? []
  }

  function reset(): void {
    available.value = []
    selected.value = null
    sessionOverrides.value.clear()
    lastError.value = null
  }

  return {
    // state
    available,
    selected,
    sessionOverrides,
    loading,
    lastError,
    // getters
    selectedId,
    selectedModel,
    selectedDisplayName,
    selectedCapabilities,
    availableWithKey,
    resolveForSession,
    // actions
    loadAvailable,
    select,
    clear,
    selectForSession,
    capabilityList,
    reset
  }
})
