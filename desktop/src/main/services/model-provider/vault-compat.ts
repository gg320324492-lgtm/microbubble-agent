// safeStorage availability helper (Phase 6-A2).
// Phase 6-A2: imported by model-secret-store + IPC handlers.
// Centralizes OS-detection logic so we don't bypass via direct electron import.

export function safeStorageAvailable(): boolean {
  try {
    // Phase 6-A2: dynamic require avoids top-level electron dep at module-load time
    // (Phase 1-2 token-vault does the same).
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const { safeStorage } = require('electron') as typeof import('electron')
    return safeStorage.isEncryptionAvailable()
  } catch (_e) {
    return false
  }
}
