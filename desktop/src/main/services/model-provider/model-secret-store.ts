// Model SecretStore (Phase 6-A2: SecretStore + Model IPC).
//
// Reuses Phase 1-2 token-vault pattern (safeStorage + electron-store).
// **Never** returns raw key to renderer; **never** logs key contents.
//
// Phase 6-A2 frozen contract:
//   save(providerId, key)      -> void (throws on invalid input)
//   get(providerId)            -> null (Phase 6-A2: existence-only; key never returned to renderer)
//   delete(providerId)         -> void
//   exists(providerId)         -> boolean
//   list()                     -> string[] (providerIds only; keys never returned)

import { safeStorage } from 'electron'
import { safeStorageAvailable } from './vault-compat'
import Store from 'electron-store'

// Phase 6-A2: namespace key prefix (distinct from auth refresh_token prefix)
const STORAGE_PREFIX = 'model_api_key_'

// Phase 6-A2: validated providerId format. Mirrors agent-interaction's isValidProviderId
// for symmetry. Phase 6-A2 server-side registry check lives in Phase 6-A3.
function isValidProviderId(id: unknown): id is string {
  if (typeof id !== 'string') return false
  if (id.length < 2 || id.length > 32) return false
  return /^[a-z][a-z0-9-]*$/.test(id)
}

function keyFor(providerId: string): string {
  return STORAGE_PREFIX + providerId
}

interface ModelKeyStoreSchema {
  [key: string]: string
}

const store = new Store<ModelKeyStoreSchema>({ name: 'model-provider-keys' })

/**
 * Phase 6-A2: Save API key (Phase 6-A2 is the only place that holds plaintext key in main memory).
 *
 * @param providerId - validated providerId (Phase 6-A2: lowercase a-z, 2-32 chars)
 * @param apiKey     - plaintext API key (Phase 6-A2: not logged anywhere)
 * @throws Error if providerId invalid OR key empty OR safeStorage unavailable
 */
export function save(providerId: string, apiKey: string): void {
  if (!isValidProviderId(providerId)) {
    throw new Error(
      `ModelSecretStore.save: invalid providerId '${String(providerId)}'. ` +
      'Phase 6-A2: lowercase a-z, 2-32 chars, must start with letter.'
    )
  }
  if (typeof apiKey !== 'string' || apiKey.length === 0) {
    throw new Error(
      'ModelSecretStore.save: apiKey is empty (Phase 6-A2 strictly forbids empty keys).'
    )
  }
  if (!safeStorageAvailable()) {
    throw new Error(
      'ModelSecretStore.save: OS-level encryption (safeStorage) not available. ' +
        'Verify OS user has a protected keychain (Win DPAPI / macOS Keychain / Linux libsecret).'
    )
  }
  const cipher = safeStorage.encryptString(apiKey)
  store.set(keyFor(providerId), cipher.toString('base64'))
}

/**
 * Phase 6-A2: existence check (does NOT return the key).
 *
 * Note: Phase 6-A2 frozen contract — Phase 6-A3 IPC layer calls this internally
 * before deciding whether to spawn a provider. Renderer NEVER receives the key
 * (Phase 6-A2 strict).
 */
export function exists(providerId: string): boolean {
  if (!isValidProviderId(providerId)) return false
  return store.has(keyFor(providerId))
}

/**
 * Phase 6-A2: load API key (INTERNAL USE ONLY — Phase 6-A3+ main process provider factories).
 *
 * Phase 6-A2: NEVER returned to renderer. Used only inside main process when
 * actually constructing a request (Phase 6-A6: provider buildRequest path).
 *
 * @returns plaintext key, or null if missing/corrupted.
 */
export function get(providerId: string): string | null {
  if (!isValidProviderId(providerId)) return null
  const cipherB64 = store.get(keyFor(providerId))
  if (!cipherB64) return null
  if (!safeStorageAvailable()) return null
  try {
    const buf = Buffer.from(cipherB64, 'base64')
    const plaintext = safeStorage.decryptString(buf)
    return plaintext && plaintext.length > 0 ? plaintext : null
  } catch (_e) {
    // Phase 6-A2: corrupted cipher; treat as missing.
    return null
  }
}

/**
 * Phase 6-A2: delete a stored key (Phase 6-A2 strict — never logs the key contents).
 */
export function deleteKey(providerId: string): void {
  if (!isValidProviderId(providerId)) return
  store.delete(keyFor(providerId))
}

/**
 * Phase 6-A2: list stored providerIds (returns IDs only, NEVER key contents).
 */
export function list(): string[] {
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
 * Phase 6-A2: clear all stored keys (Phase 6-A2 reserved for logout / vault reset).
 */
export function clearAll(): void {
  for (const k of Object.keys(store.store as Record<string, unknown>)) {
    if (k.startsWith(STORAGE_PREFIX)) store.delete(k)
  }
}

// Phase 6-A2: expose prefixed helpers for tests (NOT for renderer)
export const __testHelpers = {
  STORAGE_PREFIX,
  keyFor,
  isValidProviderId
}
