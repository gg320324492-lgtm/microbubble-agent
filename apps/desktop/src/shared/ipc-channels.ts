// IPC 通道白名单 — main / preload 唯一事实来源。
// 新增能力必须同步: 1) 这里加常量 2) main/ipc.ts 注册 handler 3) preload 暴露方法。
// tests/unit/ipc-consistency.test.ts 会校验三处一致。
export const IPC = {
  APP_INFO: 'app:info',
  AUTH_STATUS: 'auth:status',
  AUTH_REGISTER_ADMIN: 'auth:register-admin',
  AUTH_LOGIN: 'auth:login',
  AUTH_RESTORE: 'auth:restore',
  AUTH_LOGOUT: 'auth:logout',
  SETTINGS_GET: 'settings:get',
  SETTINGS_SET: 'settings:set',
  WINDOW_MINIMIZE: 'window:minimize',
  WINDOW_TOGGLE_MAXIMIZE: 'window:toggle-maximize',
  WINDOW_CLOSE: 'window:close'
} as const

export type IpcChannel = (typeof IPC)[keyof typeof IPC]
