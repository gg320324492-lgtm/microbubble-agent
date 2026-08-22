// Model IPC handlers (Phase 6-A2: SecretStore + Model IPC; Phase 6-A4: ConfigStore + Ping).
//
// Main process IPC handlers for model:* channels.
// **NEVER** returns raw API key to renderer. All key lifecycle stays in main.

import { ipcMain } from 'electron'
import { IPC_CHANNELS } from '@shared/ipc-types'
import {
  save,
  deleteKey,
  exists,
  list
} from './model-secret-store'
import {
  saveConfig,
  deleteConfig,
  getConfig,
  listConfigs,
  hasConfig,
  type ProviderConfig
} from './provider-config-store'
import { routeResearchTask } from './capability-router'
import type { ResearchTaskProfile } from '@shared/model/research-task'

/**
 * Phase 6-A2: result types for IPC (renderer only sees these shapes).
 */
export interface ModelListProvidersResult {
  providerIds: string[]
}

export interface ModelSaveKeyResult {
  ok: true
  exists: boolean
}

export interface ModelDeleteKeyResult {
  ok: true
  exists: boolean
}

export interface ModelKeyExistsResult {
  exists: boolean
}

/**
 * Phase 6-A4: provider config IPC types (non-secret metadata only).
 */
export interface ModelListConfigsResult {
  configs: ProviderConfig[]
  /**
   * hasKey is a parallel array aligned with configs[i].providerId so the
   * renderer can render "needs API key" / "configured" state without
   * ever touching the key itself.
   */
  hasKey: boolean[]
}

export interface ModelSaveConfigResult {
  ok: true
  exists: boolean
}

export interface ModelDeleteConfigResult {
  ok: true
  exists: boolean
}

export interface ModelTestProviderResult {
  ok: boolean
  latencyMs?: number
  error?: string
}

/**
 * Phase 6-C3: result of a task routing decision.
 *
 * Renderer-visible (NO apiKey). When router picks nothing, decision=null
 * and reason explains why (e.g. 'no candidate for task').
 */
export interface ModelRouteTaskResult {
  decision: {
    providerId: string
    model: string
    source: 'capability-match' | 'active-provider' | 'no-match'
    reason: string
    capabilities: import('@shared/model/research-capability').ResearchCapability[]
  } | null
  route: 'task-routed' | 'active-fallback' | 'no-route'
  reason: string
}

/**
 * Phase 6-A4: test a provider's connectivity (Phase 6-A3 ping via registry).
 *
 * Phase 6-A4 strict: ping always uses a *fake* apiKey in the test path
 * (Phase 6-A4: actual key is only injected by chat-stream.service.ts in
 * Phase 6-A5 wiring). The test result tells the user "endpoint reachable"
 * but NOT "key valid" — that requires a real call which we do not make in
 * Phase 6-A4.
 *
 * Implementation:
 *   - if no config for providerId: return { ok: false, error: 'no config' }
 *   - if no registered factory:    return { ok: false, error: 'unknown provider' }
 *   - otherwise: registry.getProvider(id, cfg).ping(cfg)
 */
function testProviderConnectivity(
  providerId: string,
  pingFn: (providerId: string, cfg: import('@shared/model/model-types').ModelConfig) => Promise<{
    ok: boolean
    latencyMs?: number
    error?: string
  }>
): Promise<ModelTestProviderResult> {
  if (!hasConfig(providerId)) {
    return Promise.resolve({ ok: false, error: 'no config saved (Phase 6-A4: save a config first)' })
  }
  const cfg = getConfig(providerId)
  if (!cfg) {
    return Promise.resolve({ ok: false, error: 'config not found (corrupted?)' })
  }
  const modelCfg: import('@shared/model/model-types').ModelConfig = {
    providerId: cfg.providerId,
    displayName: cfg.displayName,
    type: cfg.type,
    defaultModel: cfg.defaultModel,
    ...(typeof cfg.endpoint === 'string' ? { endpoint: cfg.endpoint } : {}),
    capabilities: cfg.capabilities as import('@shared/model/model-types').ModelCapability[]
  }
  return pingFn(providerId, modelCfg).then(
    (r) => ({
      ok: r.ok,
      ...(typeof r.latencyMs === 'number' ? { latencyMs: r.latencyMs } : {}),
      ...(typeof r.error === 'string' ? { error: r.error } : {})
    }),
    (e: unknown) => ({
      ok: false,
      error: e instanceof Error ? e.message : String(e)
    })
  )
}

/**
 * Phase 6-A4: optional ping function injection. The IPC handler accepts this
 * at registration time so that tests can mock the registry ping; production
 * uses the real registry ping.
 */
type PingFn = (
  providerId: string,
  cfg: import('@shared/model/model-types').ModelConfig
) => Promise<{ ok: boolean; latencyMs?: number; error?: string }>

let _pingFn: PingFn = async () => ({ ok: false, error: 'ping not wired (Phase 6-A4)' })

/**
 * Phase 6-A4: register the ping function (called once at main boot after
 * provider factories are registered). Tests can swap this before invoking handlers.
 */
export function setProviderPingFn(fn: PingFn): void {
  _pingFn = fn
}

/**
 * Phase 6-A2 + Phase 6-A4: register all model:* IPC handlers.
 * Idempotent — safe to call multiple times (only at main boot).
 */
export function registerModelIpcHandlers(): void {
  ipcMain.handle(IPC_CHANNELS.MODEL_LIST_PROVIDERS, (): ModelListProvidersResult => {
    return { providerIds: list() }
  })

  ipcMain.handle(
    IPC_CHANNELS.MODEL_SAVE_KEY,
    (_event, providerId: unknown, apiKey: unknown): ModelSaveKeyResult => {
      if (typeof providerId !== 'string' || typeof apiKey !== 'string') {
        throw new Error('ModelSaveKey: invalid args (Phase 6-A2 expects string providerId + string apiKey).')
      }
      save(providerId, apiKey)
      return { ok: true, exists: true }
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.MODEL_DELETE_KEY,
    (_event, providerId: unknown): ModelDeleteKeyResult => {
      if (typeof providerId !== 'string') {
        throw new Error('ModelDeleteKey: invalid providerId (Phase 6-A2 expects string).')
      }
      const had = exists(providerId)
      deleteKey(providerId)
      return { ok: true, exists: had }
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.MODEL_KEY_EXISTS,
    (_event, providerId: unknown): ModelKeyExistsResult => {
      if (typeof providerId !== 'string') {
        throw new Error('ModelKeyExists: invalid providerId (Phase 6-A2 expects string).')
      }
      return { exists: exists(providerId) }
    }
  )

  // ============ Phase 6-A4: non-secret config + connectivity ============

  ipcMain.handle(IPC_CHANNELS.MODEL_LIST_CONFIGS, (): ModelListConfigsResult => {
    const ids = listConfigs()
    const configs: ProviderConfig[] = []
    const hasKey: boolean[] = []
    for (const id of ids) {
      const cfg = getConfig(id)
      if (cfg) {
        configs.push(cfg)
        hasKey.push(exists(id))
      }
    }
    return { configs, hasKey }
  })

  ipcMain.handle(
    IPC_CHANNELS.MODEL_SAVE_CONFIG,
    (
      _event,
      providerId: unknown,
      partial: unknown
    ): ModelSaveConfigResult => {
      if (typeof providerId !== 'string') {
        throw new Error('ModelSaveConfig: invalid providerId (Phase 6-A4 expects string).')
      }
      if (!partial || typeof partial !== 'object') {
        throw new Error('ModelSaveConfig: invalid config payload.')
      }
      const p = partial as Record<string, unknown>
      saveConfig(providerId, {
        type: p.type as 'cloud' | 'local' | 'openai-compatible',
        defaultModel: typeof p.defaultModel === 'string' ? p.defaultModel : '',
        displayName: typeof p.displayName === 'string' ? p.displayName : providerId,
        capabilities: Array.isArray(p.capabilities)
          ? (p.capabilities as string[]).filter((c) => typeof c === 'string')
          : [],
        ...(typeof p.endpoint === 'string' ? { endpoint: p.endpoint } : {})
      })
      return { ok: true, exists: hasConfig(providerId) }
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.MODEL_DELETE_CONFIG,
    (_event, providerId: unknown): ModelDeleteConfigResult => {
      if (typeof providerId !== 'string') {
        throw new Error('ModelDeleteConfig: invalid providerId.')
      }
      const had = hasConfig(providerId)
      deleteConfig(providerId)
      return { ok: true, exists: had }
    }
  )

  ipcMain.handle(
    IPC_CHANNELS.MODEL_TEST_PROVIDER,
    async (_event, providerId: unknown): Promise<ModelTestProviderResult> => {
      if (typeof providerId !== 'string') {
        throw new Error('ModelTestProvider: invalid providerId.')
      }
      return testProviderConnectivity(providerId, _pingFn)
    }
  )

  // ============ Phase 6-C3: capability-driven task routing ============

  ipcMain.handle(
    IPC_CHANNELS.MODEL_ROUTE_TASK,
    async (_event, profile: unknown): Promise<ModelRouteTaskResult> => {
      const decision = routeResearchTask(profile as ResearchTaskProfile | null)
      if (!decision) {
        return { decision: null, route: 'no-route', reason: 'no provider + no active (Phase 6-C3)' }
      }
      const route = decision.source === 'capability-match' ? 'task-routed' : 'active-fallback'
      return {
        decision: {
          providerId: decision.providerId,
          model: decision.model,
          source: decision.source,
          reason: decision.reason,
          capabilities: [...decision.profile.capabilities]
        },
        route,
        reason: decision.reason
      }
    }
  )
}
