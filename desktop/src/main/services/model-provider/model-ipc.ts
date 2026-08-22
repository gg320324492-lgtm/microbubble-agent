// Model IPC handlers (Phase 6-A2: SecretStore + Model IPC).
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
 * Phase 6-A2: register all model:* IPC handlers.
 * Idempotent — safe to call multiple times (Phase 6-A2: only at main boot).
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
}
