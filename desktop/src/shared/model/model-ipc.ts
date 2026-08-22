// IPC channel constants (Phase 6-A2: shared between main + preload + renderer).
//
// Phase 6-A2: 4 model channels. Phase 6-A3+: more channels for list-providers expanded.

export const MODEL_IPC_CHANNELS = {
  MODEL_LIST_PROVIDERS: 'model:list-providers',
  MODEL_SAVE_KEY: 'model:save-key',
  MODEL_DELETE_KEY: 'model:delete-key',
  MODEL_KEY_EXISTS: 'model:key-exists'
} as const

export type ModelIpcChannelName =
  (typeof MODEL_IPC_CHANNELS)[keyof typeof MODEL_IPC_CHANNELS]
