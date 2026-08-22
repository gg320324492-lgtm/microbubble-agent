// Active Provider Store (Phase 6-A5: Model Runtime Integration).
//
// Phase 6-A5: persists the user's currently-selected provider + model.
// Lives in electron-store as plain JSON (NO secrets, NO apiKey, NO tokens).
//
// Phase 6-A5 frozen contract:
//   - getActive()            -> { providerId, model, enabled } | null
//   - setActive(p)           -> void
//   - clearActive()          -> void
//   - isActiveProviderSet()  -> boolean
//
// Phase 6-A5 explicit forbids:
//   - NEVER store apiKey (Phase 6-A2 SecretStore owns keys)
//   - NEVER log the model name in clear (Phase 6-A5: providerId + model are non-sensitive)
//
// Singleton — main process only.

import Store from 'electron-store'

interface ActiveProviderBlob {
  providerId: string
  model: string
  enabled: boolean
  updatedAt: number
}

interface ActiveProviderStoreSchema {
  active: ActiveProviderBlob | null
}

const store = new Store<ActiveProviderStoreSchema>({ name: 'model-active-provider' })

/**
 * Phase 6-A5: currently selected provider (non-secret).
 */
export interface ActiveProvider {
  providerId: string
  model: string
  enabled: boolean
}

/**
 * Phase 6-A5: same providerId format as Phase 6-A2 SecretStore.
 */
function isValidProviderId(id: unknown): id is string {
  if (typeof id !== 'string') return false
  if (id.length < 2 || id.length > 32) return false
  return /^[a-z][a-z0-9-]*$/.test(id)
}

/**
 * Phase 6-A5: read active provider (returns null if not set).
 */
export function getActive(): ActiveProvider | null {
  const blob = store.get('active')
  if (!blob || typeof blob !== 'object') return null
  if (!isValidProviderId(blob.providerId)) return null
  if (typeof blob.model !== 'string' || blob.model.length === 0) return null
  return {
    providerId: blob.providerId,
    model: blob.model,
    enabled: blob.enabled !== false
  }
}

/**
 * Phase 6-A5: set active provider.
 * Throws on invalid providerId or empty model.
 */
export function setActive(active: ActiveProvider): void {
  if (!isValidProviderId(active.providerId)) {
    throw new Error(`ActiveProviderStore.setActive: invalid providerId '${String(active.providerId)}'.`)
  }
  if (typeof active.model !== 'string' || active.model.length === 0) {
    throw new Error('ActiveProviderStore.setActive: model must be a non-empty string.')
  }
  store.set('active', {
    providerId: active.providerId,
    model: active.model,
    enabled: active.enabled !== false,
    updatedAt: Date.now()
  })
}

/**
 * Phase 6-A5: clear active provider (Phase 6-A5: not used; reserved for reset).
 */
export function clearActive(): void {
  store.delete('active')
}

/**
 * Phase 6-A5: convenience — does the user have an active provider set?
 */
export function isActiveProviderSet(): boolean {
  return getActive() !== null
}

export const __testHelpers = {
  isValidProviderId
}
