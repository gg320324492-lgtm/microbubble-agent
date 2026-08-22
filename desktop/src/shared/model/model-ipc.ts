// IPC channel constants (Phase 6-A2: shared between main + preload + renderer).
//
// Phase 6-A2: 4 model channels.
// Phase 6-A4: +4 model channels for non-secret provider config (endpoint,
//              defaultModel, displayName, capabilities) and connectivity test.

export const MODEL_IPC_CHANNELS = {
  MODEL_LIST_PROVIDERS: 'model:list-providers',
  MODEL_SAVE_KEY: 'model:save-key',
  MODEL_DELETE_KEY: 'model:delete-key',
  MODEL_KEY_EXISTS: 'model:key-exists',
  MODEL_LIST_CONFIGS: 'model:list-configs',
  MODEL_SAVE_CONFIG: 'model:save-config',
  MODEL_DELETE_CONFIG: 'model:delete-config',
  MODEL_TEST_PROVIDER: 'model:test-provider'
} as const

export type ModelIpcChannelName =
  (typeof MODEL_IPC_CHANNELS)[keyof typeof MODEL_IPC_CHANNELS]
