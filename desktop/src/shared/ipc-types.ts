// IPC channel 名集中管理（preload / main 共享）。
// 任何 channel 新增 / 重命名必须仅改本文件。

export const IPC_CHANNELS = {
  // Phase 0
  PING: 'app:ping',
  // Phase 1-Impl-1: auth
  AUTH_LOGIN: 'app:auth:login',
  AUTH_LOGOUT: 'app:auth:logout',
  AUTH_RESTORE: 'app:auth:restore',
  AUTH_GET_BACKEND_URL: 'app:auth:getBackendUrl',
  // Phase 1-Impl-2: API gateway
  API_REQUEST: 'app:api:request',
  // Phase 2-Impl-1: main → renderer broadcast
  AUTH_SESSION_EXPIRED: 'auth:session-expired',
  // Phase 2-Impl-3B: SSE chat streaming
  CHAT_STREAM_START: 'chat:start-stream',
  CHAT_STREAM_CANCEL: 'chat:cancel-stream',
  CHAT_STREAM_CHUNK: 'chat:stream-chunk',
  CHAT_STREAM_END: 'chat:stream-end',
  CHAT_STREAM_ERROR: 'chat:stream-error',
  // Phase 6-A2: model provider secret store IPC (NEVER returns raw API key)
  MODEL_LIST_PROVIDERS: 'model:list-providers',
  MODEL_SAVE_KEY: 'model:save-key',
  MODEL_DELETE_KEY: 'model:delete-key',
  MODEL_KEY_EXISTS: 'model:key-exists',
  // Phase 6-A4: non-secret provider config + connectivity test
  MODEL_LIST_CONFIGS: 'model:list-configs',
  MODEL_SAVE_CONFIG: 'model:save-config',
  MODEL_DELETE_CONFIG: 'model:delete-config',
  MODEL_TEST_PROVIDER: 'model:test-provider'
} as const

export type IpcChannelName = (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS]
