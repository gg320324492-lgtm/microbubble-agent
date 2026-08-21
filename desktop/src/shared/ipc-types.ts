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
  AUTH_SESSION_EXPIRED: 'auth:session-expired'
} as const

export type IpcChannelName = (typeof IPC_CHANNELS)[keyof typeof IPC_CHANNELS]
