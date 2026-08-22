// Provider ConfigStore (Phase 6-A4: Model Settings + Provider Management).
//
// Phase 6-A4: persists NON-SECRET provider configuration (endpoint, defaultModel,
// displayName, capabilities snapshot). API keys are managed by SecretStore (Phase 6-A2)
// and live in safeStorage — this store ONLY handles plaintext-safe metadata.
//
// Phase 6-A4 frozen contract:
//   - saveConfig(providerId, config)            -> void
//   - getConfig(providerId)                     -> ProviderConfig | null
//   - deleteConfig(providerId)                  -> void (idempotent)
//   - listConfigs()                             -> string[] (providerIds)
//   - hasConfig(providerId)                     -> boolean
//   - clearAll()                                -> void
//
// Phase 6-A4 explicit forbids:
//   - NEVER store API keys here (use SecretStore instead)
//   - NEVER log config contents
//   - Renderer never receives raw API key (Phase 6-A2 IPC contract still holds)

import Store from 'electron-store'

// Phase 6-A4: namespace key prefix (distinct from auth + model key prefixes)
const STORAGE_PREFIX = 'model_provider_config_'

interface ProviderConfigBlob {
  providerId: string
  type: 'cloud' | 'local' | 'openai-compatible'
  endpoint?: string
  defaultModel: string
  displayName: string
  capabilities: string[]
  /** Phase 6-C1: optional research capability profile. */
  researchProfile?: {
    providerId: string
    model: string
    capabilities: string[]
    maxContext?: number
    strengths?: string[]
    limitations?: string[]
  }
  updatedAt: number
}

interface ProviderConfigStoreSchema {
  [key: string]: ProviderConfigBlob
}

const store = new Store<ProviderConfigStoreSchema>({ name: 'model-provider-configs' })

// Phase 6-A4: same validation as Phase 6-A2 SecretStore for providerId (consistency).
function isValidProviderId(id: unknown): id is string {
  if (typeof id !== 'string') return false
  if (id.length < 2 || id.length > 32) return false
  return /^[a-z][a-z0-9-]*$/.test(id)
}

function keyFor(providerId: string): string {
  return STORAGE_PREFIX + providerId
}

/**
 * Phase 6-A4: Provider config (non-secret metadata).
 * Renderer-visible shape — NEVER contains API key.
 *
 * Phase 6-C1: optional researchProfile field.
 */
export interface ProviderConfig {
  providerId: string
  type: 'cloud' | 'local' | 'openai-compatible'
  endpoint?: string
  defaultModel: string
  displayName: string
  capabilities: string[]
  researchProfile?: {
    providerId: string
    model: string
    capabilities: string[]
    maxContext?: number
    strengths?: string[]
    limitations?: string[]
  }
  updatedAt: number
}

/**
 * Phase 6-A4: Save non-secret provider config.
 * Throws on invalid providerId or invalid config shape.
 */
export function saveConfig(
  providerId: string,
  config: Omit<ProviderConfig, 'providerId' | 'updatedAt'>
): void {
  if (!isValidProviderId(providerId)) {
    throw new Error(
      `ProviderConfigStore.saveConfig: invalid providerId '${String(providerId)}'.`
    )
  }
  if (!config || typeof config !== 'object') {
    throw new Error('ProviderConfigStore.saveConfig: config must be an object.')
  }
  if (typeof config.defaultModel !== 'string' || config.defaultModel.length === 0) {
    throw new Error('ProviderConfigStore.saveConfig: defaultModel must be non-empty string.')
  }
  if (typeof config.displayName !== 'string' || config.displayName.length === 0) {
    throw new Error('ProviderConfigStore.saveConfig: displayName must be non-empty string.')
  }
  if (
    config.type !== 'cloud' &&
    config.type !== 'local' &&
    config.type !== 'openai-compatible'
  ) {
    throw new Error(`ProviderConfigStore.saveConfig: invalid type '${String(config.type)}'.`)
  }
  if (!Array.isArray(config.capabilities)) {
    throw new Error('ProviderConfigStore.saveConfig: capabilities must be an array.')
  }
  // Phase 6-A4: local / openai-compatible requires endpoint
  if ((config.type === 'local' || config.type === 'openai-compatible') &&
      (typeof config.endpoint !== 'string' || config.endpoint.length === 0)) {
    throw new Error(
      `ProviderConfigStore.saveConfig: endpoint required for type '${config.type}'.`
    )
  }
  const blob: ProviderConfigBlob = {
    providerId,
    type: config.type,
    defaultModel: config.defaultModel,
    displayName: config.displayName,
    capabilities: [...config.capabilities],
    ...(typeof config.endpoint === 'string' && config.endpoint.length > 0
      ? { endpoint: config.endpoint }
      : {}),
    updatedAt: Date.now()
  }
  if (config.researchProfile) {
    blob.researchProfile = {
      providerId: config.researchProfile.providerId,
      model: config.researchProfile.model,
      capabilities: [...config.researchProfile.capabilities],
      ...(typeof config.researchProfile.maxContext === 'number'
        ? { maxContext: config.researchProfile.maxContext }
        : {}),
      ...(Array.isArray(config.researchProfile.strengths)
        ? { strengths: [...config.researchProfile.strengths] }
        : {}),
      ...(Array.isArray(config.researchProfile.limitations)
        ? { limitations: [...config.researchProfile.limitations] }
        : {})
    }
  }
  store.set(keyFor(providerId), blob)
}

/**
 * Phase 6-A4: existence check (does NOT return the config).
 */
export function hasConfig(providerId: string): boolean {
  if (!isValidProviderId(providerId)) return false
  return store.has(keyFor(providerId))
}

/**
 * Phase 6-A4: load provider config (returns plain shape; NEVER includes key).
 */
export function getConfig(providerId: string): ProviderConfig | null {
  if (!isValidProviderId(providerId)) return null
  const blob = store.get(keyFor(providerId))
  if (!blob) return null
  const out: ProviderConfig = {
    providerId: blob.providerId,
    type: blob.type,
    defaultModel: blob.defaultModel,
    displayName: blob.displayName,
    capabilities: [...blob.capabilities],
    ...(typeof blob.endpoint === 'string' ? { endpoint: blob.endpoint } : {}),
    updatedAt: blob.updatedAt
  }
  if (blob.researchProfile) {
    const rp = blob.researchProfile
    out.researchProfile = {
      providerId: rp.providerId,
      model: rp.model,
      capabilities: [...rp.capabilities],
      ...(typeof rp.maxContext === 'number' ? { maxContext: rp.maxContext } : {}),
      ...(Array.isArray(rp.strengths) ? { strengths: [...rp.strengths] } : {}),
      ...(Array.isArray(rp.limitations) ? { limitations: [...rp.limitations] } : {})
    }
  }
  return out
}

/**
 * Phase 6-A4: delete config (idempotent).
 */
export function deleteConfig(providerId: string): void {
  if (!isValidProviderId(providerId)) return
  store.delete(keyFor(providerId))
}

/**
 * Phase 6-A4: list providerIds that have configs (NOT keys).
 */
export function listConfigs(): string[] {
  const all = store.store as Record<string, unknown>
  const out: string[] = []
  for (const k of Object.keys(all)) {
    if (k.startsWith(STORAGE_PREFIX)) {
      out.push(k.slice(STORAGE_PREFIX.length))
    }
  }
  return out
}

/**
 * Phase 6-A4: list ALL configs (joined with key existence via injected hasKey fn).
 * Renderer never sees keys; only { providerId, hasKey }.
 */
export function listAllConfigs(hasKey: (providerId: string) => boolean): ProviderConfig[] {
  const ids = listConfigs()
  const out: ProviderConfig[] = []
  for (const id of ids) {
    const cfg = getConfig(id)
    if (cfg) {
      // Phase 6-A4: do NOT include key data; consumer can call hasKey() separately.
      out.push({ ...cfg, capabilities: [...cfg.capabilities] })
    }
  }
  // Phase 6-A4: filter to include only configs with at least the hasKey semantic
  // — keep all here; renderer decides what to show based on hasKey.
  void hasKey
  return out
}

/**
 * Phase 6-A4: clear all configs (TEST ONLY).
 */
export function clearAll(): void {
  for (const k of Object.keys(store.store as Record<string, unknown>)) {
    if (k.startsWith(STORAGE_PREFIX)) store.delete(k)
  }
}

export const __testHelpers = {
  STORAGE_PREFIX,
  keyFor,
  isValidProviderId
}
